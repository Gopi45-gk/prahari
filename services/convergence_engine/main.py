from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import redis.asyncio as redis
from typing import Dict, Any

app = FastAPI(title="PRAHARI Convergence Risk Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL)

WEIGHTS = {
    "crew": 0.30,
    "signal": 0.20,
    "infrastructure": 0.20,
    "operational": 0.15,
    "cyber": 0.15,
}

state = {
    "Train-101": {
        "crew": 0.0,
        "signal": 0.0,
        "infrastructure": 0.0,
        "operational": 0.0,
        "cyber": 0.0,
    }
}

active_connections = []

def compute_ccrs(train_id: str) -> Dict[str, Any]:
    inputs = state.get(train_id, {})
    
    # Base score
    base_score = sum(inputs.get(k, 0) * WEIGHTS[k] for k in WEIGHTS)
    
    # Convergence bonus
    above_threshold = sum(1 for v in inputs.values() if v > 40)
    if above_threshold == 3:
        bonus = 15
    elif above_threshold >= 4:
        bonus = 25
    else:
        bonus = 0
        
    ccrs = min(100, round(base_score + bonus))
    
    # Tier
    if ccrs < 40:
        tier = "Safe"
    elif ccrs < 70:
        tier = "Warning"
    elif ccrs < 90:
        tier = "High Risk"
    else:
        tier = "Critical Risk"

    # Explainability Breakdown
    breakdown = {}
    total_val = base_score + bonus
    if total_val > 0:
        for k in WEIGHTS:
            breakdown[k] = round((inputs.get(k, 0) * WEIGHTS[k] / total_val) * 100)
        if bonus > 0:
            breakdown["convergence_bonus"] = round((bonus / total_val) * 100)
    else:
        for k in WEIGHTS:
            breakdown[k] = 0

    # Decision Support
    dominant_factor = max(WEIGHTS.keys(), key=lambda k: inputs.get(k, 0) * WEIGHTS[k]) if total_val > 0 else "None"
    action = ""
    if ccrs >= 40:
        actions = {
            "crew": "Alert loco pilot, dispatch relief crew to next station",
            "signal": "Flag signaling link for priority OT inspection",
            "infrastructure": "Issue advisory speed restriction, dispatch inspection team",
            "cyber": "Notify SOC team, consider isolating affected subsystem",
            "operational": "Reduce speed, notify station ahead"
        }
        action = actions.get(dominant_factor, "Monitor closely")
    
    return {
        "train_id": train_id,
        "ccrs": ccrs,
        "tier": tier,
        "base_score": round(base_score, 1),
        "bonus": bonus,
        "inputs": inputs,
        "breakdown": breakdown,
        "dominant_factor": dominant_factor,
        "recommended_action": action
    }

async def redis_listener():
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("prahari/telemetry/*")
    print("Convergence Engine subscribed to Redis telemetry.")
    
    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            data = json.loads(message["data"])
            train_id = data.get("train_id")
            domain = data.get("domain")
            score = data.get("score")
            
            if train_id not in state:
                state[train_id] = {"crew":0,"signal":0,"infrastructure":0,"operational":0,"cyber":0}
            
            state[train_id][domain] = score
            
            # Compute new CCRS
            result = compute_ccrs(train_id)
            
            # Broadcast to WebSockets
            for connection in active_connections:
                try:
                    await connection.send_json(result)
                except Exception:
                    active_connections.remove(connection)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())

@app.websocket("/ws/convergence")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.get("/api/ccrs/{train_id}")
async def get_ccrs(train_id: str):
    return compute_ccrs(train_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
