import json
from confluent_kafka import Consumer

consumer_config = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'order-tracker-group',
    'auto.offset.reset': 'earliest' # Start consuming from the earliest message if no offset is found
}

# Create a Kafka consumer instance
consumer = Consumer(consumer_config)
# Subscribe to the 'orders' topic
consumer.subscribe(['orders'])

print("Consumer is running and subscribed to the 'orders' topic...")

while True:
    try:
        msg = consumer.poll(1.0)  # Poll for messages with a timeout of 1 second
        if msg is None:
            continue  # No message received, continue polling
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        # Process the received message
        value = msg.value().decode('utf-8') #type: ignore
        order = json.loads(value)
        print(f"Received message: {order}")
    except KeyboardInterrupt:
        print("\nConsumer is shutting down...")
        break
    except Exception as e:
        print(f"An error occurred: {e}")