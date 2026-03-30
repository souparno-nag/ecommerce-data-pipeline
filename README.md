# Projects in order

## Kafka Food‑Delivery Project (Kafka Project 1)

This project builds a minimal Kafka‑based backend for a food‑delivery app using Python and Docker Compose.

### Overview

It simulates a system where:

- A **producer** sends `new_order` events to a Kafka topic `orders`.
- A **consumer** reads those events and processes them.

Used tech:

- Apache Kafka 7.8.x (KRaft mode, no ZooKeeper).
- Docker Compose for local Kafka.
- Python `confluent‑kafka`.

### Setup

A `docker-compose.yml` starts a single Kafka node on port `9092` with KRaft mode and persisted data. Run it with:

```bash
docker compose up -d
```

### Producer

`producer.py`:

- Configures a Kafka producer pointing to `localhost:9092`.
- Creates an order event (e.g., user, item, quantity) and sends it to `orders`.
- Uses `producer.flush()` to ensure messages are sent and a `delivery_report` callback to log success/failure.

### Consumer

`consumer.py`:

- Configures a consumer with `group.id=order_processor` and `auto.offset.reset=earliest`.
- Subscribes to `orders` and loops, decoding JSON events and printing each order.

### Workflow

1. Start Kafka: `docker compose up -d`.
2. Run producer: `python producer.py` (creates orders in Kafka).
3. Run consumer: `python consumer.py` (reads and prints orders).

This shows Kafka decoupling services via events, with replayable, partitioned topics for scalability.
