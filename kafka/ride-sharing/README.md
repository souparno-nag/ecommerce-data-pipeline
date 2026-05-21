# Real-Time Ride-Sharing Event Pipeline

A local event streaming pipeline that simulates a ride-sharing platform using Apache Kafka. Ride requests, driver location updates, and trip completions are produced as real-time events, consumed to compute live metrics, and aggregated results are persisted to PostgreSQL for dashboard queries in Grafana.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Infrastructure](#infrastructure)
  - [Services](#services)
  - [Kafka Topics](#kafka-topics)
  - [PostgreSQL Schema](#postgresql-schema)
- [Components](#components)
  - [producer.py](#producerpy)
  - [consumer.py](#consumerpy)
  - [db.py](#dbpy)
- [Event Schemas](#event-schemas)
- [Metrics Computed](#metrics-computed)
- [Getting Started](#getting-started)
- [Grafana Dashboard Setup](#grafana-dashboard-setup)
- [Key Concepts](#key-concepts)

---

## Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │               Apache Kafka                   │
                        │                                             │
  producer.py  ───────► │  ride_requests      (3 partitions, key=zone_id)  │
                        │  driver_locations   (3 partitions, key=driver_id) │ ───► consumer.py
                        │  trip_completions   (3 partitions, key=zone_id)  │
                        │                                             │
                        └─────────────────────────────────────────────┘
                                                                          │
                                                                          ▼
                                                                   PostgreSQL
                                                                  zone_metrics
                                                                          │
                                                                          ▼
                                                                     Grafana
                                                                    Dashboard
```

Every 2 seconds, the producer emits one event on each of the three topics. The consumer reads all three topics in a single poll loop, maintains in-memory state, prints a metrics snapshot every 10 seconds, and upserts zone-level aggregates to PostgreSQL every 30 seconds.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Message broker | Apache Kafka 7.5.0 (Confluent) |
| Coordination | Apache Zookeeper 7.5.0 (Confluent) |
| Broker UI | Redpanda Console v3.7.0 |
| Producer / Consumer | Python 3.10+ with `confluent-kafka` |
| Data validation | Pydantic v2 |
| Operational storage | PostgreSQL 15 |
| Dashboard | Grafana (latest) |
| Container runtime | Docker + Docker Compose |

---

## Project Structure

```
ride-sharing/
├── docker-compose.yml   # All infrastructure services
├── producer.py          # Kafka event producer (mock data generator)
├── consumer.py          # Kafka consumer + metrics engine + Postgres flush
└── db.py                # One-time Postgres table initialisation
```

---

## Infrastructure

### Services

All services are defined in `docker-compose.yml` and managed with Docker Compose.

| Service | Image | Host Port | Purpose |
|---|---|---|---|
| `zookeeper` | confluentinc/cp-zookeeper:7.5.0 | 2181 | Kafka coordination |
| `kafka` | confluentinc/cp-kafka:7.5.0 | 9092 (internal), 29092 (external) | Message broker |
| `redpanda-console` | redpandadata/console:v3.7.0 | 8080 | Visual topic inspector |
| `postgres` | postgres:15 | 5433 | Aggregated metrics storage |
| `grafana` | grafana/grafana:latest | 3000 | Metrics dashboard |

**Kafka listeners:** Two listeners are configured — `PLAINTEXT://kafka:9092` for inter-container communication and `OUTSIDE://localhost:29092` for connections from Python scripts running on the host machine.

**Volumes:** `kafka_data`, `postgres_data`, and `grafana_data` are named Docker volumes, so state persists across `docker compose down` restarts (but is wiped by `docker compose down -v`).

### Kafka Topics

| Topic | Partition key | Partitions | Purpose |
|---|---|---|---|
| `ride_requests` | `zone_id` | 3 | Incoming rider pickup requests |
| `driver_locations` | `driver_id` | 3 | Periodic driver GPS pings |
| `trip_completions` | `zone_id` | 3 | Completed trip summaries |

Partitioning by `zone_id` on `ride_requests` and `trip_completions` means all events for the same zone land on the same partition, keeping zone-level aggregations efficient. Partitioning by `driver_id` on `driver_locations` keeps each driver's location history ordered.

`KAFKA_AUTO_CREATE_TOPICS_ENABLE` is set to `false` — topics must be created explicitly:

```bash
docker exec -it kafka bash

kafka-topics --create --bootstrap-server localhost:9092 \
  --topic ride_requests --partitions 3 --replication-factor 1

kafka-topics --create --bootstrap-server localhost:9092 \
  --topic driver_locations --partitions 3 --replication-factor 1

kafka-topics --create --bootstrap-server localhost:9092 \
  --topic trip_completions --partitions 3 --replication-factor 1

kafka-topics --list --bootstrap-server localhost:9092
```

### PostgreSQL Schema

Database: `ridedb` | User: `ride` | Port: `5433`

```sql
CREATE TABLE IF NOT EXISTS zone_metrics (
    zone_id          INTEGER   PRIMARY KEY,
    avg_wait_seconds FLOAT     NOT NULL DEFAULT 0,
    active_drivers   INTEGER   NOT NULL DEFAULT 0,
    trips_last_hour  INTEGER   NOT NULL DEFAULT 0,
    updated_at       TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Rows are upserted (not inserted) using `ON CONFLICT (zone_id) DO UPDATE`, so each zone always has exactly one row reflecting its latest state.

---

## Components

### producer.py

Generates mock ride-sharing events and publishes them to Kafka every 2 seconds. Uses Pydantic models for data validation and the Confluent Kafka Python client for producing.

**Pydantic models:**

`RideRequest` — published to `ride_requests`, keyed by `zone_id`

| Field | Type | Description |
|---|---|---|
| `request_id` | str (UUID4) | Unique request identifier |
| `timestamp` | str (ISO 8601) | Event creation time |
| `zone_id` | int (1–10) | Geographic zone |
| `pickup_lat` | float | Pickup latitude |
| `pickup_lon` | float | Pickup longitude |
| `dest_lat` | float | Destination latitude |
| `dest_lon` | float | Destination longitude |

`DriverLocation` — published to `driver_locations`, keyed by `driver_id`

| Field | Type | Description |
|---|---|---|
| `driver_id` | str (UUID4) | Unique driver identifier |
| `timestamp` | str (ISO 8601) | Ping time |
| `zone_id` | int (1–10) | Driver's current zone |
| `lat` | float | Current latitude |
| `lon` | float | Current longitude |
| `status` | `"available"` \| `"busy"` | Driver availability |

`TripCompletion` — published to `trip_completions`, keyed by `zone_id`

| Field | Type | Description |
|---|---|---|
| `trip_id` | str (UUID4) | Unique trip identifier |
| `driver_id` | str (UUID4) | Assigned driver |
| `rider_id` | str (UUID4) | Rider identifier |
| `zone_id` | int | Zone where trip originated |
| `start_time` | str (ISO 8601) | Trip start time |
| `end_time` | str (ISO 8601) | Trip end time |
| `fare` | int | Fare in dollars (minimum $5) |
| `distance_km` | float | Haversine distance in km |

**Key implementation details:**

- Distance is calculated using the **Haversine formula** (accounts for Earth's curvature) rather than Euclidean distance
- Fare is `max(5, int(distance_km * 6))` — a $6/km rate with a $5 floor
- `producer.poll(0)` is called in the loop to trigger delivery callbacks without blocking; `producer.flush()` is called once on `KeyboardInterrupt` to drain remaining messages
- Each `produce()` call passes `on_delivery=delivery_report` which prints partition and offset on success, or the error on failure

**Kafka config:**

```python
{"bootstrap.servers": "localhost:29092"}  # external listener
```

---

### consumer.py

Subscribes to all three topics in a single consumer group (`metrics-group`), maintains in-memory state, computes metrics, prints a snapshot every 10 seconds, and upserts to PostgreSQL every 30 seconds.

**Consumer group:** `metrics-group` with `auto.offset.reset = earliest`. Running a second instance of the consumer with the same `group.id` will trigger Kafka to automatically rebalance — splitting partitions between the two instances for horizontal scaling.

**In-memory state:**

| Variable | Type | Description |
|---|---|---|
| `ride_request_times` | `dict[int, list[datetime]]` | zone_id → list of request timestamps |
| `active_drivers` | `dict[str, datetime]` | driver_id → last seen timestamp |
| `trip_counts` | `list[datetime]` | One entry per trip completion |
| `wait_times` | `list[float]` | Global wait times in seconds |
| `zone_wait_times` | `dict[int, list[float]]` | Per-zone wait times in seconds |

**Message routing:**

On each poll, `msg.topic()` routes the decoded JSON payload to one of three handlers:

- `ride_requests` → appends the timestamp to `ride_request_times[zone_id]`
- `driver_locations` → overwrites `active_drivers[driver_id]` with the latest timestamp
- `trip_completions` → pops the oldest pending request for the zone, computes wait time as `start_time − request_time`, appends to `wait_times` and `zone_wait_times`

**Timers:**

| Interval | Action |
|---|---|
| Every 10s | `print_metrics()` — console snapshot |
| Every 30s | `flush_to_postgres()` — upsert to `zone_metrics` |
| Every 5min | `prune_old_state()` — remove stale entries from `trip_counts` and `active_drivers` |

**Shutdown:** A `finally` block guarantees `consumer.close()`, `pg_cur.close()`, and `pg.close()` are always called, cleanly releasing partition assignments from the consumer group.

**Kafka config:**

```python
{
    "bootstrap.servers": "localhost:29092",
    "group.id": "metrics-group",
    "auto.offset.reset": "earliest"
}
```

**PostgreSQL config:**

```python
{"host": "localhost", "port": 5433, "dbname": "ridedb", "user": "ride", "password": "ride123"}
```

---

### db.py

One-time initialisation script. Creates the `zone_metrics` table in PostgreSQL using `CREATE TABLE IF NOT EXISTS`, so it is safe to re-run. Run this once before starting the consumer.

---

## Event Schemas

All events are serialised as UTF-8 JSON. Example payloads:

**ride_requests**
```json
{
  "request_id": "a3f1c2d4-...",
  "timestamp": "2024-01-15T10:23:45.123456",
  "zone_id": 3,
  "pickup_lat": 40.7128,
  "pickup_lon": -74.0060,
  "dest_lat": 40.7580,
  "dest_lon": -73.9855
}
```

**driver_locations**
```json
{
  "driver_id": "b7e2d1a8-...",
  "timestamp": "2024-01-15T10:23:46.234567",
  "zone_id": 3,
  "lat": 40.7200,
  "lon": -74.0100,
  "status": "available"
}
```

**trip_completions**
```json
{
  "trip_id": "c9f3e2b1-...",
  "driver_id": "b7e2d1a8-...",
  "rider_id": "d4a5c6e7-...",
  "zone_id": 3,
  "start_time": "2024-01-15T10:23:47.345678",
  "end_time": "2024-01-15T11:23:47.345678",
  "fare": 42,
  "distance_km": 7.012
}
```

---

## Metrics Computed

| Metric | Window | How |
|---|---|---|
| Active drivers | Last 30 seconds | Count `active_drivers` entries with timestamp > now − 30s |
| Trips completed | Last 60 seconds | Count `trip_counts` entries > now − 60s |
| Trips completed | Last 1 hour | Count `trip_counts` entries > now − 1h |
| Avg wait time (global) | All time | `mean(wait_times)` |
| Avg wait time (per zone) | All time | `mean(zone_wait_times[zone_id])` |
| Pending riders (per zone) | Current | `len(ride_request_times[zone_id])` |

Wait time is defined as `trip.start_time − ride_request.timestamp` for matched zone pairs. Negative values (clock skew) are discarded.

Console output example:
```
───────────────────────────────────────────────────────
  [10:24:30] METRICS SNAPSHOT
  Active drivers  (last 30s) : 4
  Trips completed (last 60s) : 6
  Trips completed (last  1h) : 48
  Avg wait time   (all time) : 142.3s
  Per-zone avg wait (seconds):
    Zone  1:  138.0s  |  2 pending riders
    Zone  3:  155.2s  |  0 pending riders
    Zone  7:  129.8s  |  1 pending riders
───────────────────────────────────────────────────────
```

---

## Getting Started

### Prerequisites

- Docker Desktop
- Python 3.10+
- pip

### 1. Start infrastructure

```bash
docker compose up -d
```

Wait ~15 seconds for Kafka to fully start, then verify:

```bash
docker compose ps          # all services should show "running"
```

Open Redpanda Console at **http://localhost:8080** to confirm the broker is healthy.

### 2. Create Kafka topics

```bash
docker exec -it kafka bash

kafka-topics --create --bootstrap-server localhost:9092 --topic ride_requests    --partitions 3 --replication-factor 1
kafka-topics --create --bootstrap-server localhost:9092 --topic driver_locations --partitions 3 --replication-factor 1
kafka-topics --create --bootstrap-server localhost:9092 --topic trip_completions --partitions 3 --replication-factor 1
kafka-topics --create --bootstrap-server localhost:9092 --topic matched_rides    --partitions 3 --replication-factor 1

kafka-topics --list --bootstrap-server localhost:9092
exit
```

### 3. Install Python dependencies

```bash
pip install confluent-kafka pydantic psycopg2-binary faust
```

### 4. Initialise the database

```bash
python db.py
# Table zone_metrics created (or already exists).
```

### 5. Run the pipeline

Open three terminals:

```bash
# Terminal 1 — producer
python producer.py

# Terminal 2 — consumer
python consumer.py

# Terminal 3 — matcher (optional Faust stream-table join)
python matcher.py worker -l info
```

### 6. Tear down

```bash
# Stop containers, keep volumes
docker compose down

# Stop containers, wipe all data
docker compose down -v
```

---

## Grafana Dashboard Setup

1. Open **http://localhost:3000** — login: `admin` / `admin123`
2. Go to **Connections → Data Sources → Add new → PostgreSQL**
3. Fill in the connection form:

| Field | Value |
|---|---|
| Host | `localhost:5433` |
| Database | `ridedb` |
| User | `ride` |
| Password | `ride123` |
| SSL mode | `disable` |

4. Click **Save & Test** — should return "Database Connection OK"
5. Create a new dashboard, add a panel, select the Postgres data source, and paste:

```sql
SELECT zone_id, avg_wait_seconds, active_drivers, trips_last_hour, updated_at
FROM zone_metrics
ORDER BY zone_id;
```

6. Set the panel type to **Table** and hit **Apply**. The panel refreshes automatically as the consumer flushes new data every 30 seconds.

---

## Key Concepts

**Partitioning** — Topics are split into N partitions. Messages with the same key always route to the same partition via `hash(key) % N`. This guarantees ordering per key and enables efficient zone/driver-level aggregations.

**Consumer groups** — All consumers sharing the same `group.id` form a group. Kafka automatically assigns partitions across group members. Running a second `consumer.py` instance with the same group ID will trigger a rebalance and split the load — this is Kafka's horizontal scaling mechanism.

**Offsets** — Each message in a partition has a sequential offset. Kafka tracks the last committed offset per consumer group so consumers can resume from the right position after a restart. `auto.offset.reset = earliest` replays all messages from the beginning if no committed offset exists.

**Stream-table join** (matcher.py) — `driver_locations` is modelled as a KTable (latest value per driver key), and `ride_requests` is the stream. For each incoming request, the matcher looks up available drivers in the same zone from the table — enriching the stream with current state. Matched pairs are published to `matched_rides`.

**At-least-once delivery** — The producer uses `poll(0)` in the loop and `flush()` on shutdown to ensure all messages are acknowledged by the broker. The consumer uses auto-commit, meaning messages are considered processed once polled. For exactly-once semantics, manual offset commits and idempotent producers would be needed.