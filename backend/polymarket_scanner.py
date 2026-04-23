import httpx
import logging
import re
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

# Map asset to their pyth symbol equivalents
# Following the ones we specified, standard pyth feeds
ASSET_MAP = {
    "WTI": {"symbol": "Commodities.WTIM6/USD", "id": ""}, # We'll look up pyth_id dynamically or use the string if cached
    "Gold": {"symbol": "Metal.XAU/USD", "id": ""}
}

async def fetch_active_events():
    events = []
    try:
        async with httpx.AsyncClient() as client:
            # Polymarket pagination
            for i in range(10): # Fetch up to 5000 events
                url = f"https://gamma-api.polymarket.com/events?active=true&closed=false&limit=500&offset={i*500}"
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
                if not data: break
                events.extend(data)
    except Exception as e:
        logger.error(f"Failed to fetch polymarket events: {e}")
    return events

def extract_prices_from_title(title: str) -> list[float]:
    # Extract $X or $XX.XX or $X,XXX.XX from the title
    matches = re.findall(r'\$([0-9,]+\.?[0-9]*)', title)
    return [float(m.replace(',', '')) for m in matches if m]

async def scan_and_get_targets(current_prices: dict, symbol_to_id: dict):
    """
    Returns a list of dicts:
    [{'asset': 'WTI', 'target': 80.0, 'url': '...', 'condition': 'above'}]
    We only take the 2 closest above and 2 closest below for each asset.
    """
    events = await fetch_active_events()
    if not events:
        return []

    # Filter events that contain our asset keywords
    # "will WTI hit", "price will WTI hit", "will Gold hit"
    # User also asked for "week of" or "in April"
    
    now = datetime.now()
    current_month_name = now.strftime("%B") # e.g. April
    current_year = now.strftime("%Y") # e.g. 2026
    
    extracted_targets = {asset: [] for asset in ASSET_MAP.keys()}
    
    # We need to fetch the current prices for our target assets
    from pyth_client import get_latest_prices
    assets_pyth_ids = []
    for asset, mapping in ASSET_MAP.items():
        pyth_id = symbol_to_id.get(mapping["symbol"])
        if pyth_id:
            assets_pyth_ids.append(pyth_id)
            
    current_prices = await get_latest_prices(assets_pyth_ids)

    for event in events:
        title = event.get('title', '')
        slug = event.get('slug', '')
        if not title:
            continue
            
        lower_title = title.lower()
        if 'hit' not in lower_title:
             continue
             
        # Check if it has a time context for this month or week
        has_month = current_month_name.lower() in lower_title
        has_year = current_year.lower() in lower_title
        
        # We allow it if it has the year and month, OR if it's explicitly a "week of" event (which happens frequently for WTI)
        if not (has_month or "week of" in lower_title):
            continue
            
        for asset, mapping in ASSET_MAP.items():
            if asset.lower() in lower_title:
                prices = []
                markets = event.get('markets', [])
                
                # If no markets returned, fallback to title, otherwise only use active valid markets
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
    
    # Now find the closest ones
    for asset, targets in extracted_targets.items():
        if not targets:
            continue
            
        pyth_symbol = ASSET_MAP[asset]["symbol"]
        pyth_id = symbol_to_id.get(pyth_symbol)
        if not pyth_id:
            continue
            
        current_price = current_prices.get(pyth_id)
        if current_price is None:
            continue
            
        targets_above = []
        targets_below = []
        
        for t in targets:
            tp = t['price']
            # Dedup
            if any(x['price'] == tp for x in targets_above) or any(x['price'] == tp for x in targets_below):
                continue
                
            # Discard if it's too far (e.g., > 15% away, don't spam)
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
            condition = 'above' if pyth_id in current_prices and bt['price'] > current_prices[pyth_id] else 'below'
            final_additions.append({
                'symbol': pyth_symbol,
                'pyth_id': pyth_id,
                'target_price': bt['price'],
                'url': bt['url'],
                'condition': condition,
                'source': 'polymarket'
            })
            
    return final_additions
