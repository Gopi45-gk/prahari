import asyncio
import websockets
import json
import os
import redis
import time

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WS_URL = os.getenv("PRAHARI_WS_URL", "ws://host.docker.internal:8000/ws/stream")

client = redis.from_url(REDIS_URL)

async def connect_to_fatigue_stream():
    print(f"Fatigue Connector starting. Redis: {REDIS_URL}, WS: {WS_URL}")
    while True:
        try:
            print(f"Connecting to {WS_URL}...")
            async with websockets.connect(WS_URL) as websocket:
                print("Connected to Fatigue Service!")
                async for message in websocket:
                    data = json.loads(message)
                    if data.get("type") == "telemetry":
                        cai_score = data.get("cai", 0)
                        payload = {
                            "train_id": "Train-101",
                            "domain": "crew",
                            "score": cai_score,
                            "metrics": {
                                "risk_level": data.get("risk_level"),
                                "microsleep_events": data.get("microsleep_events")
                            },
                            "timestamp": time.time()
                        }
                        client.publish("prahari/telemetry/crew", json.dumps(payload))
        except Exception as e:
            print(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_fatigue_stream())
