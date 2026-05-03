import aiosqlite
from datetime import datetime, timezone

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
                source TEXT DEFAULT 'manual',
                warning_sent INTEGER DEFAULT 0,
                created_at TEXT DEFAULT ''
            )
        """)
        # Migrate: add columns if they don't exist (for existing DBs)
        for col, default in [
            ("warning_sent", "0"),
            ("created_at", "''"),
            ("triggered_at", "''"),
        ]:
            try:
                await db.execute(f"ALTER TABLE trackers ADD COLUMN {col} TEXT DEFAULT {default}")
            except aiosqlite.OperationalError:
                pass
        await db.commit()

async def add_tracker(url: str, symbol: str, pyth_id: str, target_price: float, condition: str, source: str = 'manual'):
    now_iso = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "INSERT INTO trackers (url, symbol, pyth_id, target_price, condition, status, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (url, symbol, pyth_id, target_price, condition, 'active', source, now_iso)
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
    now_iso = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE trackers SET status = 'triggered', triggered_at = ? WHERE id = ?",
            (now_iso, tracker_id)
        )
        await db.commit()

async def mark_warning_sent(tracker_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE trackers SET warning_sent = 1 WHERE id = ?", (tracker_id,))
        await db.commit()

async def delete_tracker(tracker_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM trackers WHERE id = ?", (tracker_id,))
        await db.commit()

# --- Cleanup Functions ---

async def cleanup_old_triggered(days: int = 3) -> int:
    """Delete triggered trackers older than `days` days. Returns count deleted."""
    async with aiosqlite.connect(DB_FILE) as db:
        # Delete triggered trackers that have been triggered for more than N days
        cursor = await db.execute(
            "DELETE FROM trackers WHERE status = 'triggered' AND created_at != '' "
            "AND julianday('now') - julianday(created_at) > ?",
            (days,)
        )
        await db.commit()
        return cursor.rowcount

async def cleanup_stale_polymarket(days: int = 7) -> int:
    """Delete polymarket-sourced active trackers older than `days` days. Returns count deleted."""
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "DELETE FROM trackers WHERE source = 'polymarket' AND status = 'active' "
            "AND created_at != '' AND julianday('now') - julianday(created_at) > ?",
            (days,)
        )
        await db.commit()
        return cursor.rowcount

async def deactivate_trackers_by_symbol(old_symbol: str) -> int:
    """Deactivate all active trackers for a specific symbol (used during rollover)."""
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "UPDATE trackers SET status = 'expired' WHERE symbol = ? AND status = 'active'",
            (old_symbol,)
        )
        await db.commit()
        return cursor.rowcount

async def get_tracker_stats() -> dict:
    """Get counts for heartbeat report."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row

        active = await db.execute("SELECT COUNT(*) as cnt FROM trackers WHERE status = 'active'")
        active_count = (await active.fetchone())['cnt']

        triggered = await db.execute("SELECT COUNT(*) as cnt FROM trackers WHERE status = 'triggered'")
        triggered_count = (await triggered.fetchone())['cnt']

        polymarket = await db.execute("SELECT COUNT(*) as cnt FROM trackers WHERE source = 'polymarket' AND status = 'active'")
        poly_count = (await polymarket.fetchone())['cnt']

        manual = await db.execute("SELECT COUNT(*) as cnt FROM trackers WHERE source = 'manual' AND status = 'active'")
        manual_count = (await manual.fetchone())['cnt']

        return {
            "active": active_count,
            "triggered": triggered_count,
            "polymarket_active": poly_count,
            "manual_active": manual_count,
        }
