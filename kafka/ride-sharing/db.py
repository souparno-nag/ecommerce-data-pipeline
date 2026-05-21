import psycopg2
 
conn = psycopg2.connect(
    host="localhost",
    port=5433,
    dbname="ridedb",
    user="ride",
    password="ride123",
)
cur = conn.cursor()
 
cur.execute("""
    CREATE TABLE IF NOT EXISTS zone_metrics (
        zone_id          INTEGER PRIMARY KEY,
        avg_wait_seconds FLOAT   NOT NULL DEFAULT 0,
        active_drivers   INTEGER NOT NULL DEFAULT 0,
        trips_last_hour  INTEGER NOT NULL DEFAULT 0,
        updated_at       TIMESTAMP NOT NULL DEFAULT NOW()
    );
""")
 
conn.commit()
cur.close()
conn.close()
print("Table zone_metrics created (or already exists).")