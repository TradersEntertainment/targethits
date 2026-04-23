import requests

requests.post('http://localhost:8000/api/trackers', json={
    "url": "https://pythdata.app/explore/Commodities.WTIM6%2FUSD",
    "target_price": 95.0
})

requests.post('http://localhost:8000/api/trackers', json={
    "url": "https://pythdata.app/explore/Metal.XAU%2FUSD",
    "target_price": 2800.0
})

import sqlite3
# Also let's insert a dummy polymarket one just so the user sees the icon
conn = sqlite3.connect('backend/trackers.db')
c = conn.cursor()
c.execute("INSERT INTO trackers (url, symbol, pyth_id, target_price, condition, status, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
         ('https://polymarket.com/event/will-wti-hit-80-in-april-2026', 'Commodities.WTIJ6/USD', '0x6a60b0d1ea6809b47dbe599f24a71c8bda335aa5c77e503e7260cde5ba2f4694', 80.0, 'above', 'active', 'polymarket'))
conn.commit()
conn.close()
