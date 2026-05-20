import json
from datetime import datetime, timedelta
from confluent_kafka import Consumer

# ── Consumer config ────────────────────────────────────────────────────────────

consumer_config = {
    'bootstrap.servers': 'localhost:29092',
    'group.id': 'metrics-group',
    'auto.offset.reset': 'earliest',
}

consumer = Consumer(consumer_config)
consumer.subscribe(['ride_requests', 'driver_locations', 'trip_completions'])

# In-memory state

ride_request_times = {}   # zone_id (int) → list of datetime objects
active_drivers     = {}   # driver_id (str) → last seen datetime
trip_counts        = []   # list of datetime objects (one per completion)
wait_times         = []   # list of floats (seconds) — for avg wait calculation

# Helpers

def print_metrics():
    now = datetime.now()
    cutoff_30s  = now - timedelta(seconds=30)
    cutoff_60s  = now - timedelta(seconds=60)

    # Active drivers: seen a location ping in the last 30 seconds
    active_count = sum(
        1 for ts in active_drivers.values()
        if ts > cutoff_30s
    )

    # Trips per minute: completions in the last 60 seconds
    recent_trips = sum(1 for ts in trip_counts if ts > cutoff_60s)

    # Average wait time across all recorded waits
    avg_wait = (sum(wait_times) / len(wait_times)) if wait_times else 0

    # Per-zone average wait time
    zone_waits = {}
    for zone_id, timestamps in ride_request_times.items():
        if timestamps:
            zone_waits[zone_id] = len(timestamps)  # pending (unmatched) requests

    print("\n" + "─" * 50)
    print(f"  [{now.strftime('%H:%M:%S')}] METRICS SNAPSHOT")
    print(f"  Active drivers (last 30s) : {active_count}")
    print(f"  Trips completed (last 60s): {recent_trips}")
    print(f"  Avg wait time (all time)  : {avg_wait:.1f}s")
    print(f"  Pending ride requests     : { {z: len(t) for z, t in ride_request_times.items()} }")
    print("─" * 50)


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

print("Consumer started. Listening on ride_requests, driver_locations, trip_completions...\n")

last_metrics_time = datetime.now()

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

                if zone_id not in ride_request_times:
                    ride_request_times[zone_id] = []
                ride_request_times[zone_id].append(timestamp)

            # driver_locations
            elif topic == 'driver_locations':
                driver_id = data['driver_id']
                timestamp = datetime.fromisoformat(data['timestamp'])
                active_drivers[driver_id] = timestamp  # overwrites with latest ping

            # trip_completions
            elif topic == 'trip_completions':
                zone_id    = data['zone_id']
                start_time = datetime.fromisoformat(data['start_time'])
                end_time   = datetime.fromisoformat(data['end_time'])

                # Calculate wait time for this zone if we have a pending request
                if zone_id in ride_request_times and ride_request_times[zone_id]:
                    request_time = ride_request_times[zone_id].pop(0)  # oldest request first
                    wait = (start_time - request_time).total_seconds()
                    if wait >= 0:   # guard against clock skew
                        wait_times.append(wait)

                trip_counts.append(datetime.now())

        # Print metrics every 10 seconds
        if (datetime.now() - last_metrics_time).seconds >= 10:
            print_metrics()
            prune_old_state()
            last_metrics_time = datetime.now()

except KeyboardInterrupt:
    print("\nShutting down consumer...")

finally:
    consumer.close()   # always close cleanly — releases partition assignments
    print("Consumer closed.")