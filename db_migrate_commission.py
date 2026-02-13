import sqlite3
conn = sqlite3.connect("instance/abils_mall.db")
cur = conn.cursor()
cur.execute("ALTER TABLE user ADD COLUMN commission_rate REAL DEFAULT 5")
cur.execute("ALTER TABLE product ADD COLUMN manager_id INTEGER")
cur.execute("UPDATE user SET commission_rate=5 WHERE role='manager' AND (commission_rate IS NULL)")
conn.commit()
conn.close()
print("DB updated")
