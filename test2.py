import httpx

r = httpx.get('https://gamma-api.polymarket.com/events?slug=will-wti-hit-week-of-april-20-2026')
if r.status_code == 200:
    data = r.json()
    if data:
        event = data[0]
        print('Event Title:', event.get('title'))
        markets = event.get('markets', [])
        print('Markets:')
        for m in markets:
            print('-', m.get('question', ''))
    else:
        print('No data returned')
else:
    print('Failed', r.status_code)
