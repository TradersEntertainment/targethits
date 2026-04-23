import sqlite3
conn=sqlite3.connect('backend/trackers.db')
c=conn.cursor()
c.execute("DELETE FROM trackers WHERE source='polymarket'")
conn.commit()
conn.close()
