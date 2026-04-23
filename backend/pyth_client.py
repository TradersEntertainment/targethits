import httpx
import logging

logger = logging.getLogger(__name__)

# Base URLs
HERMES_URL = "https://hermes.pyth.network/v2"

# Cache of symbol to ID mapping
symbol_to_id_cache = {}

async def init_feeds_cache():
    """Fetches all price feeds from limit to memorize symbol to ID mapping."""
    global symbol_to_id_cache
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{HERMES_URL}/price_feeds", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            for feed in data:
                feed_id = feed.get("id")
                attrs = feed.get("attributes", {})
                symbol = attrs.get("symbol")
                if feed_id and symbol:
                    # we keep the ID without the leading 0x just in case, but pyth usually returns without it here,
                    # and endpoints require with or without depending on the exact version. v2 API uses raw hex or 0x. We'll keep raw hex as returned.
                    symbol_to_id_cache[symbol] = "0x" + feed_id if not feed_id.startswith("0x") else feed_id
                    
        logger.info(f"Successfully cached {len(symbol_to_id_cache)} Pyth feeds.")
    except Exception as e:
        logger.error(f"Failed to fetch pyth feeds cache: {e}")

def get_pyth_id_from_url(url: str) -> str:
    """Extracts symbol from url and looks up the ID."""
    # E.g. https://pythdata.app/explore/Commodities.WTIM6%2FUSD
    import urllib.parse
    parsed = urllib.parse.unquote(url)
    symbol = parsed.split("/explore/")[-1] 
    return symbol, symbol_to_id_cache.get(symbol)

async def get_latest_prices(pyth_ids: list[str]) -> dict:
    """
    Fetches the latest prices for a list of Pyth IDs.
    Returns a dict mapping ID to float price.
    """
    if not pyth_ids:
        return {}
    
    unique_ids = list(set(pyth_ids))
    url = f"{HERMES_URL}/updates/price/latest"
    params = [("ids[]", pyth_id) for pyth_id in unique_ids]
    
    try:
        # User requested to be careful about bans. We handle 429 later.
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            
            results = {}
            for item in data.get("parsed", []):
                price_id = "0x" + item.get("id") if not item.get("id").startswith("0x") else item.get("id")
                price_info = item.get("price", {})
                price_str = price_info.get("price")
                expo_str = price_info.get("expo")
                if price_str and expo_str:
                    price = float(price_str) * (10 ** int(expo_str))
                    results[price_id] = price
            return results
    except Exception as e:
        logger.error(f"Error fetching latest prices: {e}")
        # Will raise so the caller knows it failed
        raise
