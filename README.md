---
title: PRAHARI Backend
emoji: 🚂
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---
# 🛡️ PRAHARI — Loco Pilot Fatigue & Microsleep Detection System

**AI-powered real-time fatigue detection for Indian Railways loco pilots**

Built with PyTorch, MediaPipe, FastAPI, and WebSocket streaming. Designed to prevent Signal Passed At Danger (SPAD) incidents through continuous monitoring of driver alertness.

---

## Architecture

```
Camera → Face Detection → Feature Extraction → CNN Classification
                                              → Temporal LSTM
                              ↓                    ↓
                         Multi-Modal Fusion → Risk Engine → Alerts
                              ↓
                      Dashboard (WebSocket)
```

### 6-Stage Processing Pipeline

| Stage | Component | Purpose |
|-------|-----------|---------|
| 1 | **Face Detection** | MediaPipe FaceMesh (468 landmarks) + CLAHE low-light |
| 2 | **Feature Extraction** | EAR, MAR, PERCLOS, blink metrics, head pose (PnP) |
| 3 | **CNN Classifier** | 5-class fatigue classification (Alert → Microsleep) |
| 4 | **Temporal LSTM** | BiLSTM + attention for fatigue trend & microsleep onset |
| 5 | **Fusion Engine** | 8-signal weighted fusion → Crew Alertness Index (0-100) |
| 6 | **Risk Engine** | 4-level risk classification + alert dispatch |

---

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install PRAHARI
pip install -e ".[dev]"

# For GPU support
pip install -e ".[gpu]"
```

### 2. Run the System

```bash
# Start with default webcam
python -m prahari.main

# Or with custom config
PRAHARI_CAMERA_SOURCE=0 python -m prahari.main
```

### 3. Open Dashboard

Navigate to **http://localhost:8000** — the dashboard opens automatically.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System health check |
| `GET` | `/api/status` | Current fatigue metrics snapshot |
| `POST` | `/api/fatigue-alert` | Receive/log fatigue alerts |
| `GET` | `/api/history` | Recent alert history |
| `POST` | `/api/config` | Runtime config updates |
| `GET` | `/api/metrics` | Prometheus metrics |
| `WS` | `/ws/stream` | Real-time telemetry stream |

### Alert Payload

```json
{
  "crew_id": "LP001",
  "alertness_score": 18,
  "fatigue_score": 92,
  "risk_level": "CRITICAL",
  "timestamp": "2026-06-12T10:00:00Z"
}
```

---

## Training

### CNN Fatigue Classifier

```bash
python -m prahari.training.train_cnn \
  --data data/train \
  --epochs 100 \
  --batch-size 32 \
  --lr 1e-3
```

### Temporal LSTM

```bash
python -m prahari.training.train_lstm \
  --data data/temporal \
  --epochs 80 \
  --batch-size 64
```

### Evaluation

```bash
python -m prahari.training.evaluate \
  --model models/fatigue_cnn_best.pt \
  --data data/val
```

---

## Docker Deployment

```bash
# Build and run with GPU
docker compose up --build

# Services:
#   PRAHARI:    http://localhost:8000
#   Prometheus: http://localhost:9090
#   Grafana:    http://localhost:3000
```

---

## Risk Levels

| CAI Range | Level | Action |
|-----------|-------|--------|
| 0–40 | 🟢 LOW | Normal monitoring |
| 41–70 | 🟡 MEDIUM | Increased monitoring |
| 71–85 | 🟠 HIGH | Audible alert to operator |
| 86–100 | 🔴 CRITICAL | Control room alert + emergency |

---

## Target Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Accuracy | > 95% | Overall classification accuracy |
| Recall | > 97% | Sensitivity to fatigue states |
| Precision | > 95% | Low false alarms |
| FPR | < 3% | False positive rate |
| Latency | < 50ms | End-to-end inference time |
| FPS | ≥ 30 | Real-time processing speed |

---

## Full Tech Stack

### Frontend (Command Center UI)
- **Framework:** React 19, TypeScript
- **Routing & SSR:** TanStack Router, TanStack Start
- **Build Tool:** Vite
- **Styling:** Tailwind CSS v4, tw-animate-css
- **UI Components:** shadcn/ui (Radix UI Primitives), Lucide React
- **Animations:** Framer Motion
- **Maps & Data Viz:** Leaflet, React-Leaflet, Recharts
- **Forms & Validation:** React Hook Form, Zod
- **Backend-as-a-Service / Auth:** Firebase Authentication, Firestore
- **State Management:** TanStack Query

### Backend API (Middleware)
- **Framework:** FastAPI, Uvicorn (ASGI server)
- **Real-Time Communication:** WebSockets
- **Language:** Python 3.10+

### Machine Learning & Computer Vision (PRAHARI Engine)
- **Deep Learning Frameworks:** PyTorch, TorchVision
- **Computer Vision:** Ultralytics (YOLO), OpenCV, MediaPipe
- **Scientific Computing:** NumPy, SciPy, scikit-learn
- **Architecture & Validation:** Pydantic
- **Monitoring:** Prometheus Client
- **Tooling:** Ruff (Linting), Pytest (Testing)

---

## License

Proprietary — Indian Railways / PRAHARI Project
