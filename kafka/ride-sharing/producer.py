import json
from datetime import datetime, timedelta
import uuid
import random
import math
import time as tm

from confluent_kafka import Producer
from pydantic import BaseModel, Field
from typing import Literal


# Producer config 

producer_config = {"bootstrap.servers": "localhost:29092"}
producer = Producer(producer_config)


# Pydantic models

class RideRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    zone_id: int = Field(..., ge=1, le=10)
    pickup_lat: float
    pickup_lon: float
    dest_lat: float
    dest_lon: float


class DriverLocation(BaseModel):
    driver_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    lat: float
    lon: float
    status: Literal["available", "busy"]


class TripCompletion(BaseModel):
    trip_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    driver_id: str
    rider_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    zone_id: int
    start_time: str
    end_time: str
    fare: int
    distance_km: float


# Helpers

def delivery_report(err, msg):
    """Called by Kafka after each produce to confirm delivery or log errors."""
    if err:
        print(f"[ERROR] Delivery failed for {msg.topic()}: {err}")
    else:
        print(f"[OK] {msg.topic()} | partition {msg.partition()} | offset {msg.offset()}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance between two lat/lon points in km."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# Producers

def produce_ride_request() -> RideRequest:
    event = RideRequest(
        zone_id=random.randint(1, 10),
        pickup_lat=random.uniform(-90, 90),
        pickup_lon=random.uniform(-180, 180),
        dest_lat=random.uniform(-90, 90),
        dest_lon=random.uniform(-180, 180),
    )
    producer.produce(
        topic="ride_requests",
        key=str(event.zone_id),          # partition by zone
        value=json.dumps(event.model_dump()).encode(),
        on_delivery=delivery_report,
    )
    return event


def produce_driver_location() -> DriverLocation:
    event = DriverLocation(
        lat=random.uniform(-90, 90),
        lon=random.uniform(-180, 180),
        status="available" if random.random() > 0.5 else "busy",
    )
    producer.produce(
        topic="driver_locations",
        key=event.driver_id,             # partition by driver
        value=json.dumps(event.model_dump()).encode(),
        on_delivery=delivery_report,
    )
    return event


def produce_trip_completion(
    driver_id: str,
    zone_id: int,
    src_lat: float,
    src_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> TripCompletion:
    dist = haversine_km(src_lat, src_lon, dest_lat, dest_lon)
    fare = max(5, int(dist * 6))         # minimum fare of $5
    start = datetime.now()
    end = start + timedelta(minutes=random.randint(15, 120))

    event = TripCompletion(
        driver_id=driver_id,
        zone_id=zone_id,
        start_time=start.isoformat(),
        end_time=end.isoformat(),
        distance_km=round(dist, 3),
        fare=fare,
    )
    producer.produce(
        topic="trip_completions",
        key=str(event.zone_id),          # partition by zone (matches ride_requests)
        value=json.dumps(event.model_dump()).encode(),
        on_delivery=delivery_report,
    )
    return event


# Main loop 

print("Producer started. Sending events every 2 seconds. Ctrl+C to stop.\n")

try:
    while True:
        rr = produce_ride_request()
        dl = produce_driver_location()
        tc = produce_trip_completion(
            driver_id=dl.driver_id,
            zone_id=rr.zone_id,
            src_lat=rr.pickup_lat,
            src_lon=rr.pickup_lon,
            dest_lat=rr.dest_lat,
            dest_lon=rr.dest_lon,
        )
        producer.poll(0)   # trigger delivery callbacks without blocking
        print(f"  ride_request zone={rr.zone_id} | driver={dl.driver_id[:8]}... | dist={tc.distance_km}km fare=${tc.fare}")
        tm.sleep(2)

except KeyboardInterrupt:
    print("\nShutting down — flushing remaining messages...")
    producer.flush()       # flush once on exit
    print("Done.")