import json
from datetime import datetime, timedelta
from confluent_kafka import Consumer
import psycopg2

# Consumer config

consumer_config = {
    'bootstrap.servers': 'localhost:29092',
    'group.id': 'metrics-group',
    'auto.offset.reset': 'earliest',
}

consumer = Consumer(consumer_config)
consumer.subscribe(['ride_requests', 'driver_locations', 'trip_completions'])

# Postgres Connection

pg = psycopg2.connect(
    host="localhost", port=5433,
    dbname="ridedb", user="ride", password="ride123",
)
pg_cur = pg.cursor()

# In-memory state

ride_request_times = {}   # zone_id (int) → list of datetime objects
active_drivers     = {}   # driver_id (str) → last seen datetime
trip_counts        = []   # list of datetime objects (one per completion)
wait_times         = []   # list of floats (seconds) — for avg wait calculation
zone_wait_times    = {}   # zone_id → list of wait floats (for per-zone avg)

# Helpers

def compute_metrics():
    """Return a dict of current metric values."""
    now        = datetime.now()
    cutoff_30s = now - timedelta(seconds=30)
    cutoff_60s = now - timedelta(seconds=60)
    cutoff_1hr = now - timedelta(hours=1)
 
    active_count = sum(1 for ts in active_drivers.values() if ts > cutoff_30s)
    recent_trips = sum(1 for ts in trip_counts      if ts > cutoff_1hr)
    trips_60s    = sum(1 for ts in trip_counts      if ts > cutoff_60s)
    avg_wait     = (sum(wait_times) / len(wait_times)) if wait_times else 0
 
    # Per-zone: avg wait and active driver count
    zones = {}
    all_zone_ids = set(ride_request_times) | set(zone_wait_times)
    for z in all_zone_ids:
        waits = zone_wait_times.get(z, [])
        zones[z] = {
            'avg_wait':       round(sum(waits) / len(waits), 2) if waits else 0,
            'pending_riders': len(ride_request_times.get(z, [])),
        }
 
    return {
        'active_drivers': active_count,
        'trips_last_60s': trips_60s,
        'trips_last_hour': recent_trips,
        'avg_wait_all':  round(avg_wait, 2),
        'zones':         zones,
    }

def print_metrics(m):
    now = datetime.now()
    print("\n" + "─" * 55)
    print(f"  [{now.strftime('%H:%M:%S')}] METRICS SNAPSHOT")
    print(f"  Active drivers  (last 30s) : {m['active_drivers']}")
    print(f"  Trips completed (last 60s) : {m['trips_last_60s']}")
    print(f"  Trips completed (last  1h) : {m['trips_last_hour']}")
    print(f"  Avg wait time   (all time) : {m['avg_wait_all']}s")
    if m['zones']:
        print(f"  Per-zone avg wait (seconds):")
        for z, data in sorted(m['zones'].items()):
            print(f"    Zone {z:>2}: {data['avg_wait']:>6.1f}s  |  {data['pending_riders']} pending riders")
    print("─" * 55)

def flush_to_postgres(m):
    """Upsert aggregated metrics into zone_metrics table."""
    now = datetime.now()
    for zone_id, data in m['zones'].items():
        pg_cur.execute("""
            INSERT INTO zone_metrics
                (zone_id, avg_wait_seconds, active_drivers, trips_last_hour, updated_at)
            VALUES
                (%s, %s, %s, %s, %s)
            ON CONFLICT (zone_id) DO UPDATE SET
                avg_wait_seconds = EXCLUDED.avg_wait_seconds,
                active_drivers   = EXCLUDED.active_drivers,
                trips_last_hour  = EXCLUDED.trips_last_hour,
                updated_at       = EXCLUDED.updated_at;
        """, (
            zone_id,
            data['avg_wait'],
            m['active_drivers'],   # global count (zone-level not tracked separately)
            m['trips_last_hour'],
            now,
        ))
    pg.commit()
    print(f"  [DB] Flushed {len(m['zones'])} zone(s) to Postgres.")


def prune_old_state():
    """Keep memory flat by removing stale entries."""
    cutoff = datetime.now() - timedelta(minutes=5)

    # Remove trip_counts older than 5 minutes
    trip_counts[:] = [ts for ts in trip_counts if ts > cutoff]

    # Remove driver entries older than 5 minutes
    stale = [d for d, ts in active_drivers.items() if ts < cutoff]
    for d in stale:
        del active_drivers[d]


# Main loop

print("Consumer started. Metrics printed every 10s, flushed to Postgres every 30s.\n")

last_metrics_time = datetime.now()
last_postgres_time = datetime.now()

try:
    while True:
        msg = consumer.poll(1.0)

        if msg is None:
            pass  # no message this second, fall through to metrics check
        elif msg.error():
            print(f"[ERROR] {msg.error()}")
        else:
            topic = msg.topic()
            data  = json.loads(msg.value().decode('utf-8')) # type: ignore

            # ride_requests
            if topic == 'ride_requests':
                zone_id   = data['zone_id']
                timestamp = datetime.fromisoformat(data['timestamp'])
                ride_request_times.setdefault(zone_id, []).append(timestamp)    

            # driver_locations
            elif topic == 'driver_locations':
                driver_id = data['driver_id']
                timestamp = datetime.fromisoformat(data['timestamp'])
                active_drivers[driver_id] = timestamp  # overwrites with latest ping

            # trip_completions
            elif topic == 'trip_completions':
                zone_id    = data['zone_id']
                start_time = datetime.fromisoformat(data['start_time'])
 
                if zone_id in ride_request_times and ride_request_times[zone_id]:
                    request_time = ride_request_times[zone_id].pop(0)
                    wait = (start_time - request_time).total_seconds()
                    if wait >= 0:
                        wait_times.append(wait)
                        zone_wait_times.setdefault(zone_id, []).append(wait)
 
                trip_counts.append(datetime.now())

        now = datetime.now()

        # Print metrics every 10 seconds
        if (now - last_metrics_time).seconds >= 10:
            m = compute_metrics()
            print_metrics(m)
            prune_old_state()
            last_metrics_time = now
 
        # Flush to Postgres every 30 seconds
        if (now - last_postgres_time).seconds >= 30:
            m = compute_metrics()
            flush_to_postgres(m)
            last_postgres_time = now

except KeyboardInterrupt:
    print("\nShutting down consumer...")

finally:
    consumer.close()   # always close cleanly — releases partition assignments
    pg_cur.close()
    pg.close()
    print("Consumer closed.")