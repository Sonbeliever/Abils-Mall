import sqlite3

DB_CANDIDATES = ["abils_mall.db", "instance/abils_mall.db"]


def add_column(cur, sql):
    try:
        cur.execute(sql)
    except sqlite3.OperationalError as exc:
        # Ignore duplicate column errors to allow re-runs
        if "duplicate column name" not in str(exc).lower():
            raise


def _has_table(con, name):
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def main():
    db_path = None
    for candidate in DB_CANDIDATES:
        try:
            con = sqlite3.connect(candidate)
        except Exception:
            continue
        if _has_table(con, "product") and _has_table(con, "order"):
            db_path = candidate
            con.close()
            break
        con.close()

    if not db_path:
        raise SystemExit("No database with product/order tables found. Run app once or check DB path.")

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    add_column(cur, "ALTER TABLE product ADD COLUMN weight_grams INTEGER DEFAULT 0")
    add_column(cur, "ALTER TABLE product ADD COLUMN size_desc VARCHAR(120)")

    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_country VARCHAR(120)")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_state VARCHAR(120)")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_area VARCHAR(120)")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_bus_stop VARCHAR(120)")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_address VARCHAR(255)")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_map_url VARCHAR(500)")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_distance_km FLOAT")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN shipping_fee FLOAT DEFAULT 0.0")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN total_weight_grams INTEGER DEFAULT 0")
    add_column(cur, "ALTER TABLE \"order\" ADD COLUMN delivery_phone VARCHAR(30)")

    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_country VARCHAR(120)")
    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_state VARCHAR(120)")
    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_area VARCHAR(120)")
    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_bus_stop VARCHAR(120)")
    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_address VARCHAR(255)")
    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_map_url VARCHAR(500)")
    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_lat FLOAT")
    add_column(cur, "ALTER TABLE company ADD COLUMN pickup_lng FLOAT")

    con.commit()
    con.close()
    print(f"OK: {db_path}")


if __name__ == "__main__":
    main()
