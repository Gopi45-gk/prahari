import time
import json
import random
import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
client = redis.from_url(REDIS_URL)

def generate_infrastructure():
    return {
        "score": random.randint(20, 60),
        "metrics": {
            "track_vibration": random.uniform(0.5, 2.5),
            "rail_temp": random.uniform(25, 45)
        }
    }

def generate_operational():
    return {
        "score": random.randint(10, 50),
        "metrics": {
            "speed": random.uniform(60, 110),
            "schedule_adherence": random.uniform(-5, 5)
        }
    }

def generate_cyber():
    return {
        "score": random.randint(5, 30),
        "metrics": {
            "network_anomalies": random.randint(0, 5)
        }
    }

def generate_signal():
    return {
        "score": random.randint(10, 45),
        "metrics": {
            "signal_delay": random.uniform(0.1, 1.5)
        }
    }

print(f"Starting PRAHARI Domain Simulators. Connected to {REDIS_URL}")

# Create an occasional anomaly
anomaly_counter = 0

while True:
    anomaly_counter += 1
    
    # Base scores
    i1 = generate_infrastructure()
    i2 = generate_operational()
    i4 = generate_cyber()
    i5 = generate_signal()

    # Inject convergence anomaly every ~30 seconds (30 ticks)
    if anomaly_counter % 30 == 0:
        print("Injecting convergence anomaly across domains!")
        i1["score"] = random.randint(65, 85)
        i2["score"] = random.randint(60, 80)
        i5["score"] = random.randint(70, 90)

    # Publish to Redis
    train_id = "Train-101"
    timestamp = time.time()
    
    for domain, data in [("infrastructure", i1), ("operational", i2), ("cyber", i4), ("signal", i5)]:
        payload = {
            "train_id": train_id,
            "domain": domain,
            "score": data["score"],
            "metrics": data["metrics"],
            "timestamp": timestamp
        }
        client.publish(f"prahari/telemetry/{domain}", json.dumps(payload))
    
    time.sleep(1)
