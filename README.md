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

## Real Time Weather Streaming Project using Kafka, Flint & PostgresDB (Kafka Project 2)

### Project Overview

This project demonstrates the construction of a **real-time data streaming pipeline** from scratch. It integrates three powerful technologies:

- **Apache Kafka** for efficient event ingestion and message brokering.
- **Apache Flink** for real-time stream processing.
- **PostgreSQL (Postgres)** as a data sink for storing processed results.

The pipeline enables instant insights from streaming data, applicable to domains like finance, e-commerce, and IoT.

### Architecture

The pipeline follows a linear, decoupled architecture:

1. **Data Source** → **Kafka Producer** (sends raw events to a Kafka topic)
2. **Apache Kafka** (acts as the distributed event streaming platform)
3. **Apache Flink Consumer** (consumes events from Kafka, processes them in real-time)
4. **PostgreSQL Sink** (Flink writes the processed results to a Postgres table)
5. **Data Storage & Query** (Postgres stores final insights for analysis or visualization)

### Technologies Used

| Technology | Role in Pipeline |
| --- | --- |
| **Apache Kafka** | Event ingestion, buffering, and decoupling producer from consumer. |
| **Apache Flink** | Real-time stream processing (e.g., filtering, aggregation, transformation). |
| **PostgreSQL** | Persistent storage for processed results, enabling querying and analysis. |
| **Java** (implied) | Primary language for Kafka producer and Flink job implementation. |
| **SQL** | Schema definition and data insertion in Postgres. |

### Setup & Implementation Steps

The video walks through four main phases:

#### Phase 1: Environment Setup

- **Folder structure** creation for the project.
- **PostgreSQL setup**: Installing, creating a database, and designing a target table schema to receive processed data.

#### Phase 2: Kafka Producer Implementation

- Developing a producer application (likely in Java) to simulate or forward real-time events to a specified Kafka topic.
- Configuration of Kafka broker address, topic name, serializers, and message sending logic.

#### Phase 3: Flink Consumer & Processing Job

- Building a Flink job that:

- Consumes the data stream from the Kafka topic.
- Performs real-time transformations (details depend on use case, e.g., windowed aggregations, filtering, enrichment).
- Uses a **Flink PostgreSQL sink connector** to write output to the Postgres table.

#### Phase 4: Integration & Testing

- Connecting all components: Kafka → Flink → Postgres.
- **End-to-end testing** to verify data flows correctly from producer to database.
