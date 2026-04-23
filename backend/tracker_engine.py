import asyncio
import logging
from httpx import HTTPStatusError
import database
import pyth_client
import telegram_notifier
import polymarket_scanner

logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 4 # Seconds between requests to avoid rate limits

async def check_prices_loop():
    logger.info("Starting Price Tracker Engine...")
    last_poly_scan = 0
    last_rollover_alert_date = ""
    consecutive_errors = 0
    
    while True:
        try:
            # --- WTI ROLLOVER ALERT ---
            from datetime import datetime
            import wti_rollover_checker
            now_dt = datetime.now()
            today_str = now_dt.strftime('%Y-%m-%d')
            if today_str != last_rollover_alert_date:
                # Calculate alert date for this month
                alert_date = wti_rollover_checker.get_wti_alert_date(now_dt.year, now_dt.month)
                if today_str == alert_date:
                    msg = (
                        "🚨 <b>WTI KONTARATI YENİLEME (ROLLOVER) UYARISI!</b> 🚨\n\n"
                        "Polymarket kurallarına göre WTI sözleşmesi için <b>aktif ayın değişmesine 1 GÜN KALDI!</b>\n\n"
                        "Lütfen yarın akşam (18:00 ET civarı) Pyth feed'inde aktif işlem gören kontrat ayının (örn. WTIK6 -> WTIM6) değişip değişmediğini kontrol etmeyi ve panodaki hedeflerinizi buna göre yenilemeyi unutmayın. Gözünüz grupta olsun! ⚠️"
                    )
                    await telegram_notifier.send_notification(msg)
                    last_rollover_alert_date = today_str
            # --- POLYMARKET SCANNER ---
            import time
            now = time.time()
            if now - last_poly_scan > 3600: # Every 1 hour
                last_poly_scan = now
                try:
                    logger.info("Running Polymarket auto-scanner...")
                    all_trackers_db = await database.get_all_trackers()
                    
                    # Prices arg is now dummy (None) because polymarket_scanner fetches what it needs internally
                    new_targets = await polymarket_scanner.scan_and_get_targets(None, pyth_client.symbol_to_id_cache)
                    for nt in new_targets:
                        is_dup = False
                        for existing in all_trackers_db:
                            if existing['symbol'] == nt['symbol'] and abs(existing['target_price'] - nt['target_price']) < 0.0001:
                                is_dup = True
                                break
                        if not is_dup:
                            logger.info(f"Auto-adding Polymarket target: {nt['symbol']} @ {nt['target_price']}")
                            await database.add_tracker(
                                url=nt['url'],
                                symbol=nt['symbol'],
                                pyth_id=nt['pyth_id'],
                                target_price=nt['target_price'],
                                condition=nt['condition'],
                                source=nt['source']
                            )
                except Exception as ex:
                    logger.error(f"Failed poly scan: {ex}")

            active_trackers = await database.get_active_trackers()
            if not active_trackers:
                await asyncio.sleep(SLEEP_INTERVAL)
                continue
            
            pyth_ids = [t['pyth_id'] for t in active_trackers]
            
            try:
                prices = await pyth_client.get_latest_prices(pyth_ids)
                consecutive_errors = 0 # reset on success
            except HTTPStatusError as e:
                # HTTP 429 Too Many Requests -> Ban warning
                if e.response.status_code == 429:
                    logger.warning("Rate limit hit from Pyth Hermes API (429)!")
                    if consecutive_errors == 0:
                        await telegram_notifier.send_alert_error("Pyth API 'Rate Limit (429)' uyarısı verdi. İstekleri yavaşlatıyoruz, ban yememek için lütfen çok fazla token araması yapmayın.")
                    consecutive_errors += 1
                    await asyncio.sleep(SLEEP_INTERVAL * 5) # Backoff
                    continue
                else:
                    logger.error(f"HTTPError checking prices: {e}")
                    await asyncio.sleep(SLEEP_INTERVAL)
                    continue
            except Exception as e:
                logger.error(f"Error checking prices: {e}")
                consecutive_errors += 1
                if consecutive_errors == 5:
                     await telegram_notifier.send_alert_error(f"Pyth API'ye {consecutive_errors} keredir ulaşılamıyor.\nHata: {str(e)[:100]}")
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
                        
                        # Add a little emoji if it was from polymarket
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
                    elif not t.get('warning_sent'):
                        # Early warning check
                        symbol_upper = t['symbol'].upper()
                        distance = abs(current_price - target)
                        
                        is_wti_warning = "WTI" in symbol_upper and distance <= 0.50
                        is_gold_warning = "XAU" in symbol_upper and distance <= 1.00
                        
                        if is_wti_warning or is_gold_warning:
                            logger.info(f"Early Warning: {t['symbol']} at {current_price} target {target} distance {distance}")
                            await database.mark_warning_sent(t['id'])
                            
                            source_icon = "🤖" if t.get('source') == 'polymarket' else "👤"
                            pyth_encoded = t['symbol'].replace("/", "%2F")
                            pyth_link = f"https://pythdata.app/explore/{pyth_encoded}"
                            
                            links_html = f"🔍 <a href='{pyth_link}'>Veriyi Kontrol Et (Pyth)</a>"
                            if t.get('source') == 'polymarket':
                                links_html += f"\n🎲 <a href='{t['url']}'>Bet Al (Polymarket)</a>"
                            
                            msg = (
                                f"⚠️ <b>DİKKAT! HEDEFE ÇOK AZ KALDI!</b> ⚠️ {source_icon}\n\n"
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
