import json
import uuid

from confluent_kafka import Producer

producer_config = {
    'bootstrap.servers': 'localhost:9092', # Replace with your Kafka broker address
}

# Create a Kafka producer instance
producer = Producer(producer_config)

order = {
    "order_id": str(uuid.uuid4()),
    "user": "jane_doe",
    "item": "chicken_pizza",
    "quantity": 1,
}

# Convert JSON to bytes
order_bytes = json.dumps(order).encode('utf-8') # or simply json.dumps(order).encode() since utf-8 is the default encoding

# Define a callback function to handle delivery reports
def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Delivered {msg.value().decode('utf-8')} to {msg.topic()} [partition {msg.partition()}] at offset {msg.offset()}")
        print(dir(msg))

# Send the order to the 'orders' topic
producer.produce(
    topic='orders',
    value=order_bytes,
    callback=delivery_report
)

# Flush the producer to ensure all messages are sent
producer.flush()
