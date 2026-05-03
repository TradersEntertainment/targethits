import httpx
import logging
import re
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

# Gold symbol is static (no rollover)
GOLD_PYTH_SYMBOL = "Metal.XAU/USD"

# Keywords that indicate a price-target market
PRICE_KEYWORDS = ["hit", "reach", "above", "below", "close", "price", "drop", "rise", "fall"]

# Calendar month names for filtering
MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
]


def _get_dynamic_asset_map(symbol_to_id: dict):
    """
    Build the asset map dynamically, resolving the current WTI symbol
    using the CME rollover logic.
    """
    import wti_contract_resolver
    wti_symbol, _, _ = wti_contract_resolver.get_active_wti_symbol()

    asset_map = {}

    if wti_symbol:
        wti_pyth_id = symbol_to_id.get(wti_symbol)
        if wti_pyth_id:
            asset_map["WTI"] = {"symbol": wti_symbol, "pyth_id": wti_pyth_id}
            logger.info(f"WTI dynamic symbol resolved: {wti_symbol} -> {wti_pyth_id}")
        else:
            # Try fuzzy match: look for any Commodities.WTI*/USD in cache
            for sym, pid in symbol_to_id.items():
                if sym.startswith("Commodities.WTI") and sym.endswith("/USD"):
                    asset_map["WTI"] = {"symbol": sym, "pyth_id": pid}
                    logger.warning(f"WTI exact symbol {wti_symbol} not in cache, using fallback: {sym}")
                    break
            if "WTI" not in asset_map:
                logger.error(f"WTI symbol {wti_symbol} not found in Pyth cache at all!")

    gold_pyth_id = symbol_to_id.get(GOLD_PYTH_SYMBOL)
    if gold_pyth_id:
        asset_map["Gold"] = {"symbol": GOLD_PYTH_SYMBOL, "pyth_id": gold_pyth_id}
    else:
        logger.error(f"Gold symbol {GOLD_PYTH_SYMBOL} not found in Pyth cache!")

    return asset_map


async def fetch_active_events():
    events = []
    try:
        async with httpx.AsyncClient() as client:
            # Polymarket pagination
            for i in range(10):  # Fetch up to 5000 events
                url = f"https://gamma-api.polymarket.com/events?active=true&closed=false&limit=500&offset={i*500}"
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    break
                events.extend(data)
    except Exception as e:
        logger.error(f"Failed to fetch polymarket events: {e}")
    return events


def extract_prices_from_title(title: str) -> list[float]:
    """Extract dollar amounts like $X, $XX.XX, $X,XXX.XX from text."""
    matches = re.findall(r'\$([0-9,]+\.?[0-9]*)', title)
    return [float(m.replace(',', '')) for m in matches if m]


def _matches_time_filter(title_lower: str) -> bool:
    """
    Check if an event title has a relevant time context.
    Accepts: current month, next month, 'week of', current year, or generic.
    """
    now = datetime.now(timezone.utc)
    current_month_name = MONTH_NAMES[now.month - 1]
    next_month_idx = now.month % 12  # 0-indexed for next month
    next_month_name = MONTH_NAMES[next_month_idx]
    current_year = str(now.year)

    # Accept if it mentions current month, next month, week-based, or has the year
    if current_month_name in title_lower:
        return True
    if next_month_name in title_lower:
        return True
    if "week of" in title_lower:
        return True
    if current_year in title_lower:
        return True

    return False


def _matches_price_keyword(title_lower: str) -> bool:
    """Check if event title contains any price-related keyword."""
    return any(kw in title_lower for kw in PRICE_KEYWORDS)


async def scan_and_get_targets(current_prices: dict, symbol_to_id: dict):
    """
    Scans Polymarket for active WTI and Gold price target events.

    Returns a list of dicts:
    [{'symbol': '...', 'pyth_id': '...', 'target_price': 80.0,
      'url': '...', 'condition': 'above', 'source': 'polymarket'}]

    Takes the 2 closest above and 2 closest below for each asset.
    """
    asset_map = _get_dynamic_asset_map(symbol_to_id)
    if not asset_map:
        logger.warning("No assets resolved in dynamic asset map. Skipping scan.")
        return []

    events = await fetch_active_events()
    if not events:
        logger.warning("No events fetched from Polymarket.")
        return []

    # Fetch current prices for our target assets
    from pyth_client import get_latest_prices
    assets_pyth_ids = [info["pyth_id"] for info in asset_map.values()]
    try:
        current_prices = await get_latest_prices(assets_pyth_ids)
    except Exception as e:
        logger.error(f"Failed to get current prices for scanning: {e}")
        return []

    extracted_targets = {asset: [] for asset in asset_map.keys()}

    for event in events:
        title = event.get('title', '')
        slug = event.get('slug', '')
        if not title:
            continue

        lower_title = title.lower()

        # Must have a price keyword
        if not _matches_price_keyword(lower_title):
            continue

        # Must have a relevant time context
        if not _matches_time_filter(lower_title):
            continue

        for asset, mapping in asset_map.items():
            # Check asset name in title
            asset_lower = asset.lower()
            # Also check common aliases
            aliases = [asset_lower]
            if asset_lower == "wti":
                aliases.extend(["crude oil", "crude", "oil price"])
            elif asset_lower == "gold":
                aliases.extend(["xau", "gold price"])

            if not any(alias in lower_title for alias in aliases):
                continue

            prices = []
            markets = event.get('markets', [])

            if not markets:
                prices = extract_prices_from_title(title)
            else:
                for m in markets:
                    if m.get('closed') or not m.get('active'):
                        continue
                    q = m.get('question', '')
                    m_prices = extract_prices_from_title(q)
                    prices.extend(m_prices)

            # De-duplicate
            prices = list(set(prices))
            poly_url = f"https://polymarket.com/event/{slug}"
            for p in prices:
                extracted_targets[asset].append({'price': p, 'url': poly_url})

    final_additions = []

    for asset, targets in extracted_targets.items():
        if not targets:
            continue

        mapping = asset_map[asset]
        pyth_id = mapping["pyth_id"]
        pyth_symbol = mapping["symbol"]
        current_price = current_prices.get(pyth_id)
        if current_price is None:
            continue

        targets_above = []
        targets_below = []

        seen_prices = set()
        for t in targets:
            tp = t['price']
            if tp in seen_prices:
                continue
            seen_prices.add(tp)

            # Discard if too far away (> 15%)
            if abs(tp - current_price) / current_price > 0.15:
                continue

            if tp > current_price:
                targets_above.append(t)
            elif tp < current_price:
                targets_below.append(t)

        targets_above.sort(key=lambda x: x['price'])
        targets_below.sort(key=lambda x: x['price'], reverse=True)

        # Take closest 2 above, 2 below
        best_targets = targets_above[:2] + targets_below[:2]

        for bt in best_targets:
            condition = 'above' if bt['price'] > current_price else 'below'
            final_additions.append({
                'symbol': pyth_symbol,
                'pyth_id': pyth_id,
                'target_price': bt['price'],
                'url': bt['url'],
                'condition': condition,
                'source': 'polymarket'
            })

    logger.info(
        f"Polymarket scan complete: {len(events)} events checked, "
        f"{len(final_additions)} new targets found"
    )
    return final_additions
