import aiosqlite

DB_FILE = "trackers.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trackers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                symbol TEXT NOT NULL,
                pyth_id TEXT NOT NULL,
                target_price REAL NOT NULL,
                condition TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                source TEXT DEFAULT 'manual'
            )
        """)
        await db.commit()

async def add_tracker(url: str, symbol: str, pyth_id: str, target_price: float, condition: str, source: str = 'manual'):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "INSERT INTO trackers (url, symbol, pyth_id, target_price, condition, status, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (url, symbol, pyth_id, target_price, condition, 'active', source)
        )
        await db.commit()
        return cursor.lastrowid

async def get_active_trackers():
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM trackers WHERE status = 'active'") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_all_trackers():
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM trackers ORDER BY id DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def mark_tracker_triggered(tracker_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE trackers SET status = 'triggered' WHERE id = ?", (tracker_id,))
        await db.commit()

async def delete_tracker(tracker_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM trackers WHERE id = ?", (tracker_id,))
        await db.commit()

