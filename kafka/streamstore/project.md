# Kafka Food‑Delivery Project

This project demonstrates a minimal, realistic Kafka‑based backend for a food‑delivery app (similar to Uber Eats or DoorDash). It uses **Python** for producers/consumers and **Docker Compose** to run Apache Kafka locally.

---

## Overview

- **Goal**: Show how Kafka decouples microservices using events.
- **Use case**: Simulate a food‑delivery system where:
  - A **producer** sends new food orders to a Kafka topic.
  - A **consumer** reads those orders and “processes” them (e.g., order service, inventory service).
- **Tech stack**:
  - Apache Kafka 7.8.x (KRaft mode, no ZooKeeper).
  - Docker Compose for local Kafka.
  - Python `confluent‑kafka` library.

---

## Kafka Concepts Used

Key concepts applied in the demo:

- **Topics**: Logical streams of events (e.g., `new_orders`).
- **Producers**: Python services that send events to Kafka.
- **Consumers**: Python services that read events from a topic.
- **Partitions**: Kafka splits topics into partitions for parallelism and scaling.
- **Persistence**: Kafka stores messages on disk, so multiple consumers can replay events (unlike traditional message brokers).

The architecture mimics a real‑world event‑driven system where:

- `order_service` → sends `new_order` event → Kafka → `invoice_service`, `inventory_service`, `notifications_service`.

---

## Project Setup

### 1. Docker Compose for Kafka

A `docker-compose.yml` starts a single Kafka node:

- Image: `confluentinc/cp‑kafka:7.8.8‑3`.
- Ports:
  - `9092`: Clients (producers/consumers).
  - `9093`: Internal controller communication.
- Environment:
  - `KAFKA_KRAFT_MODE=true`: Uses KRaft (no ZooKeeper).
  - `KAFKA_CLUSTER_ID` and `KAFKA_NODE_ID`: Identifies the cluster and broker.
  - `KAFKA_CONTROLLER_QUORUM_VOTERS`: Defines which nodes vote in cluster decisions.
  - `KAFKA_LISTENERS` / `KAFKA_ADVERTISED_LISTENERS`: Configure client/controller endpoints.
- Volume:
  - `kafka_data` persists Kafka logs and metadata on the host machine.

Run with:

```bash
docker compose up -d
```

---

## Producer: Simulating New Orders

File: `producer.py`

### 1. Dependencies

```bash
pip install confluent-kafka
```

### 2. Code Walkthrough

- **Import producer**:

  ```python
  from confluent_kafka import Producer
  ```

- **Kafka config**:

  ```python
  producer_config = {
      "bootstrap.servers": "localhost:9092",
  }
  producer = Producer(producer_config)
  ```

- **Create an order event**:

  ```python
  import uuid
  import json

  order = {
      "order_id": str(uuid.uuid4()),
      "user": "test_user",
      "item": "mushroom_pizza",
      "quantity": 2,
  }

  # Serialize to bytes
  order_value = json.dumps(order).encode("utf-8")
  ```

- **Send to Kafka topic**:

  ```python
  topic = "new_orders"

  def delivery_report(err, msg):
      if err:
          print(f"Delivery failed: {err}")
      else:
          print(
              f"Delivered to {msg.topic()} partition {msg.partition()} at offset {msg.offset()}"
          )

  producer.produce(
      topic=topic,
      value=order_value,
      on_delivery=delivery_report
  )

  producer.flush()  # Send all buffered messages
  ```

When `new_orders` doesn’t exist, Kafka auto‑creates it with one partition.

---

## Consumer: Processing Orders

File: `consumer.py`

### 1. Basic consumer setup

```python
from confluent_kafka import Consumer

consumer_config = {
    "bootstrap.servers": "localhost:9092",
    "group.id": "order_processor",
    "auto.offset.reset": "earliest",  # Replay from start
}

consumer = Consumer(consumer_config)
```

### 2. Subscribe and read events

```python
topic = "new_orders"
consumer.subscribe([topic])

while True:
    msg = consumer.poll(timeout=1.0)
    if msg is None:
        continue
    if msg.error():
        print(f"Consumer error: {msg.error()}")
        continue

    order = json.loads(msg.value().decode("utf-8"))
    print("Processing order:", order)
```

The consumer group (`order_processor`) can be scaled to multiple instances for parallel processing.

---

## Running the Demo Flow

1. **Start Kafka**:

   ```bash
   docker compose up -d
   ```

2. **Run the producer**:

   ```bash
   python producer.py
   ```

   - Creates/appends events to the `new_orders` topic.
   - Prints delivery reports including topic, partition, and offset.

3. **Run the consumer**:

   ```bash
   python consumer.py
   ```

   - Subscribes to `new_orders`.
   - Prints each received order as it arrives.

4. **Optional**:
   - Use Kafka CLI in the container to inspect topics:

     ```bash
     docker exec -it kafka bash
     kafka-topics --bootstrap-server localhost:9092 --list
     kafka-console-consumer --bootstrap-server localhost:9092 --topic new_orders
     ```

---

## Key Takeaways

- Kafka decouples services by acting as a **message backbone** between microservices.
- Events are **stored and replayable**, enabling analytics, auditing, and multiple subscribers.
- With Docker Compose and Python, you can quickly bootstrap a Kafka‑based event‑driven system for local development.
- Best practices:
  - Always `flush()` producers before exit.
  - Use consumer groups and partitions for scaling.
  - Persist Kafka data with volumes for local development.
