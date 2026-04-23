import asyncio
import pyth_client
import polymarket_scanner

async def main():
    await pyth_client.init_feeds_cache()
    # Mock current price of WTI loosely as $80
    wti_id = pyth_client.symbol_to_id_cache.get('Commodities.WTIJ6/USD')
    if not wti_id:
        print("WTI ID NOT FOUND")
        return
    current_prices = {wti_id: 80.0}
    
    events = await polymarket_scanner.fetch_active_events()
    print("Fetched", len(events), "events")
    for e in events[:5]:
        print(e.get('title'))

    res = await polymarket_scanner.scan_and_get_targets(current_prices, pyth_client.symbol_to_id_cache)
    print("RESULTS:")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
