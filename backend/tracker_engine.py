import asyncio
import logging
import time
from datetime import datetime, timezone
from httpx import HTTPStatusError
import database
import pyth_client
import telegram_notifier
import polymarket_scanner
import wti_contract_resolver

logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 4  # Seconds between price checks
POLY_SCAN_INTERVAL = 3600  # 1 hour
CLEANUP_INTERVAL = 6 * 3600  # 6 hours
HEARTBEAT_INTERVAL = 24 * 3600  # 24 hours

# Track the current WTI symbol to detect rollovers
_current_wti_symbol = None


async def _handle_rollover():
    """Check if WTI contract has rolled over, deactivate old trackers if so."""
    global _current_wti_symbol

    new_symbol, _, _ = wti_contract_resolver.get_active_wti_symbol()
    if not new_symbol:
        return

    if _current_wti_symbol is None:
        _current_wti_symbol = new_symbol
        logger.info(f"WTI contract initialized: {new_symbol}")
        return

    if new_symbol != _current_wti_symbol:
        old_symbol = _current_wti_symbol
        _current_wti_symbol = new_symbol
        logger.info(f"WTI ROLLOVER DETECTED: {old_symbol} -> {new_symbol}")

        # Deactivate all trackers for the old contract
        count = await database.deactivate_trackers_by_symbol(old_symbol)

        msg = (
            f"🔄 <b>WTI KONTRAT DEĞİŞİMİ (ROLLOVER)</b> 🔄\n\n"
            f"<b>Eski kontrat:</b> {old_symbol}\n"
            f"<b>Yeni aktif kontrat:</b> {new_symbol}\n\n"
            f"📌 {count} eski alarm otomatik olarak deaktif edildi.\n"
            f"Yeni alarmlar bir sonraki Polymarket taramasında otomatik eklenecek."
        )
        await telegram_notifier.send_notification(msg)


async def _run_cleanup():
    """Run periodic cleanup of old/stale trackers."""
    try:
        triggered_cleaned = await database.cleanup_old_triggered(days=3)
        stale_cleaned = await database.cleanup_stale_polymarket(days=7)

        total = triggered_cleaned + stale_cleaned
        if total > 0:
            msg = (
                f"🧹 <b>Otomatik Temizlik</b>\n\n"
                f"• {triggered_cleaned} eski tetiklenmiş alarm silindi\n"
                f"• {stale_cleaned} süresi geçmiş Polymarket alarmı silindi"
            )
            await telegram_notifier.send_notification(msg)
            logger.info(f"Cleanup: {triggered_cleaned} triggered + {stale_cleaned} stale removed")
        else:
            logger.info("Cleanup: nothing to clean")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


async def _send_heartbeat():
    """Send a daily status report via Telegram."""
    try:
        stats = await database.get_tracker_stats()
        rollover_info = wti_contract_resolver.get_next_rollover_info()

        rollover_text = ""
        if rollover_info:
            rollover_dt = rollover_info["rollover_utc"]
            days_until = (rollover_dt - datetime.now(timezone.utc)).days
            rollover_text = (
                f"\n<b>WTI Aktif Kontrat:</b> {rollover_info['current_symbol']}\n"
                f"<b>Sonraki Rollover:</b> {rollover_dt.strftime('%d %B %Y')} ({days_until} gün)\n"
            )

        msg = (
            f"📊 <b>Günlük Durum Raporu</b> 📊\n\n"
            f"<b>Aktif alarmlar:</b> {stats['active']}\n"
            f"  • Manuel: {stats['manual_active']}\n"
            f"  • Polymarket: {stats['polymarket_active']}\n"
            f"<b>Tetiklenmiş (bekleyen):</b> {stats['triggered']}\n"
            f"{rollover_text}\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"✅ Sistem çalışıyor."
        )
        await telegram_notifier.send_notification(msg)
        logger.info("Heartbeat sent.")
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")


async def _run_poly_scan():
    """Run Polymarket scanner and notify about new alarms."""
    try:
        logger.info("Running Polymarket auto-scanner...")
        all_trackers_db = await database.get_all_trackers()

        new_targets = await polymarket_scanner.scan_and_get_targets(
            None, pyth_client.symbol_to_id_cache
        )

        added_count = 0
        added_names = []

        for nt in new_targets:
            is_dup = False
            for existing in all_trackers_db:
                if (existing['symbol'] == nt['symbol'] and
                        abs(existing['target_price'] - nt['target_price']) < 0.01):
                    is_dup = True
                    break
            if not is_dup:
                logger.info(f"Auto-adding: {nt['symbol']} @ {nt['target_price']}")
                await database.add_tracker(
                    url=nt['url'],
                    symbol=nt['symbol'],
                    pyth_id=nt['pyth_id'],
                    target_price=nt['target_price'],
                    condition=nt['condition'],
                    source=nt['source']
                )
                added_count += 1
                direction = "↑" if nt['condition'] == 'above' else "↓"
                added_names.append(f"  • {nt['symbol']} @ ${nt['target_price']:.2f} {direction}")

        if added_count > 0:
            details = "\n".join(added_names[:10])  # Max 10 in notification
            msg = (
                f"🤖 <b>Yeni Otomatik Alarmlar Eklendi</b> ({added_count} adet)\n\n"
                f"{details}"
            )
            await telegram_notifier.send_notification(msg)
            logger.info(f"Poly scan: {added_count} new targets added")
        else:
            logger.info("Poly scan: no new targets found")

    except Exception as ex:
        logger.error(f"Failed poly scan: {ex}")
        try:
            await telegram_notifier.send_alert_error(
                f"Polymarket taraması başarısız oldu:\n{str(ex)[:200]}"
            )
        except Exception:
            pass


async def check_prices_loop():
    logger.info("Starting Price Tracker Engine v2...")

    last_poly_scan = 0
    last_cleanup = 0
    last_heartbeat = 0
    last_rollover_alert_date = ""
    consecutive_errors = 0

    # Send startup notification
    try:
        await telegram_notifier.send_notification(
            "🚀 <b>Pyth Tracker Engine başlatıldı!</b>\n\nSistem aktif, alarmlar takip ediliyor."
        )
    except Exception:
        pass

    while True:
        try:
            now_ts = time.time()
            now_dt = datetime.now(timezone.utc)

            # --- WTI ROLLOVER DETECTION ---
            await _handle_rollover()

            # --- WTI ROLLOVER ADVANCE ALERT ---
            from datetime import datetime as dt_cls
            import wti_rollover_checker
            today_str = datetime.now().strftime('%Y-%m-%d')
            now_local = datetime.now()
            if today_str != last_rollover_alert_date:
                alert_date = wti_rollover_checker.get_wti_alert_date(now_local.year, now_local.month)
                if today_str == alert_date:
                    msg = (
                        "🚨 <b>WTI KONTRATI YENİLEME (ROLLOVER) UYARISI!</b> 🚨\n\n"
                        "Polymarket kurallarına göre WTI sözleşmesi için <b>aktif ayın değişmesine 1 GÜN KALDI!</b>\n\n"
                        "Lütfen yarın akşam (18:00 ET civarı) Pyth feed'inde aktif işlem gören kontrat ayının "
                        "değişip değişmediğini kontrol etmeyi ve panodaki hedeflerinizi buna göre yenilemeyi "
                        "unutmayın. ⚠️"
                    )
                    await telegram_notifier.send_notification(msg)
                    last_rollover_alert_date = today_str

            # --- POLYMARKET SCANNER (every hour) ---
            if now_ts - last_poly_scan > POLY_SCAN_INTERVAL:
                last_poly_scan = now_ts
                await _run_poly_scan()

            # --- CLEANUP (every 6 hours) ---
            if now_ts - last_cleanup > CLEANUP_INTERVAL:
                last_cleanup = now_ts
                await _run_cleanup()

            # --- HEARTBEAT (every 24 hours) ---
            if now_ts - last_heartbeat > HEARTBEAT_INTERVAL:
                last_heartbeat = now_ts
                await _send_heartbeat()

            # --- PRICE CHECKING ---
            active_trackers = await database.get_active_trackers()
            if not active_trackers:
                await asyncio.sleep(SLEEP_INTERVAL)
                continue

            pyth_ids = [t['pyth_id'] for t in active_trackers]

            try:
                prices = await pyth_client.get_latest_prices(pyth_ids)
                consecutive_errors = 0
            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Rate limit hit from Pyth Hermes API (429)!")
                    if consecutive_errors == 0:
                        await telegram_notifier.send_alert_error(
                            "Pyth API 'Rate Limit (429)' uyarısı verdi. İstekleri yavaşlatıyoruz."
                        )
                    consecutive_errors += 1
                    await asyncio.sleep(SLEEP_INTERVAL * 5)
                    continue
                else:
                    logger.error(f"HTTPError checking prices: {e}")
                    await asyncio.sleep(SLEEP_INTERVAL)
                    continue
            except Exception as e:
                logger.error(f"Error checking prices: {e}")
                consecutive_errors += 1
                if consecutive_errors == 5:
                    await telegram_notifier.send_alert_error(
                        f"Pyth API'ye {consecutive_errors} keredir ulaşılamıyor.\nHata: {str(e)[:100]}"
                    )
                await asyncio.sleep(SLEEP_INTERVAL)
                continue

            for t in active_trackers:
                pyth_id = t['pyth_id']
                if pyth_id in prices:
                    current_price = prices[pyth_id]
                    target = t['target_price']
                    condition = t['condition']
                    triggered = False

                    if condition == 'above' and current_price >= target:
                        triggered = True
                    elif condition == 'below' and current_price <= target:
                        triggered = True

                    if triggered:
                        logger.info(f"Triggered: {t['symbol']} at {current_price} target {target}")
                        await database.mark_tracker_triggered(t['id'])

                        source_icon = "🤖" if t.get('source') == 'polymarket' else "👤"

                        pyth_encoded = t['symbol'].replace("/", "%2F")
                        pyth_link = f"https://pythdata.app/explore/{pyth_encoded}"

                        links_html = f"🔍 <a href='{pyth_link}'>Veriyi Kontrol Et (Pyth)</a>"
                        if t.get('source') == 'polymarket':
                            links_html += f"\n🎲 <a href='{t['url']}'>Bet Al (Polymarket)</a>"

                        msg = (
                            f"🔔 <b>FİYAT ALARMI TETİKLENDİ!</b> 🔔 {source_icon}\n\n"
                            f"<b>Varlık:</b> {t['symbol']}\n"
                            f"<b>Hedef Fiyat:</b> {target}\n"
                            f"<b>Anlık Fiyat:</b> {current_price}\n\n"
                            f"{links_html}"
                        )
                        await telegram_notifier.send_notification(msg)

                    else:
                        # Progressive early warning system
                        symbol_upper = t['symbol'].upper()
                        distance = abs(current_price - target)

                        # Determine warning zone and step size per asset
                        warning_zone = 0
                        step_size = 0
                        if "WTI" in symbol_upper:
                            warning_zone = 0.50
                            step_size = 0.10
                        elif "XAU" in symbol_upper:
                            warning_zone = 1.00
                            step_size = 0.25
                        elif "XAG" in symbol_upper:
                            warning_zone = 0.50
                            step_size = 0.10

                        if warning_zone > 0 and distance <= warning_zone:
                            # Get the last warning distance (default 999 = never warned)
                            last_dist = float(t.get('last_warning_distance') or 999)

                            # Calculate which step threshold we're at
                            # E.g. for WTI with step 0.10: thresholds are 0.50, 0.40, 0.30, 0.20, 0.10
                            current_threshold = int(distance / step_size) * step_size

                            # Only send if we've crossed a new threshold closer than last time
                            if current_threshold < last_dist:
                                logger.info(
                                    f"Progressive Warning: {t['symbol']} at {current_price} "
                                    f"target {target} distance {distance:.2f} threshold {current_threshold:.2f}"
                                )
                                await database.update_warning_distance(t['id'], current_threshold)

                                source_icon = "🤖" if t.get('source') == 'polymarket' else "👤"
                                pyth_encoded = t['symbol'].replace("/", "%2F")
                                pyth_link = f"https://pythdata.app/explore/{pyth_encoded}"

                                links_html = f"🔍 <a href='{pyth_link}'>Veriyi Kontrol Et (Pyth)</a>"
                                if t.get('source') == 'polymarket':
                                    links_html += f"\n🎲 <a href='{t['url']}'>Bet Al (Polymarket)</a>"

                                urgency = "🔴" if distance <= step_size else "🟡" if distance <= step_size * 3 else "⚠️"

                                msg = (
                                    f"{urgency} <b>HEDEFE YAKLAŞIYOR!</b> {urgency} {source_icon}\n\n"
                                    f"<b>Varlık:</b> {t['symbol']}\n"
                                    f"<b>Hedef Fiyat:</b> {target}\n"
                                    f"<b>Anlık Fiyat:</b> {current_price}\n"
                                    f"<b>Kalan Fark:</b> ${distance:.2f}\n\n"
                                    f"Hedefe değmek üzere, tetikte olun!\n\n"
                                    f"{links_html}"
                                )
                                await telegram_notifier.send_notification(msg)

        except Exception as e:
            logger.error(f"Fatal error in tracker engine loop: {e}")

        await asyncio.sleep(SLEEP_INTERVAL)


def start_background_task():
    asyncio.create_task(check_prices_loop())
