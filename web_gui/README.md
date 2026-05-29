# TelekineRob-BCI Web GUI

Web UI + Python backend for the `TelekineRob-BCI` workspace.

## Goals

- Works on local machine even when ROS2 hardware runtime is unavailable.
- Charts display real pipeline data via `RosBridge` when pipeline is running, empty when idle.
- Provides full experiment configuration, start/stop control, and web-based teleop.

## Directory Layout

- `backend/`: FastAPI service, WebSocket streams, RosBridge, config model, command runner.
- `frontend/`: React + Vite + ECharts dashboard.

## Quick Start

### 1) Backend

```bash
cd web_gui/backend
source ../../.venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Backend defaults to `http://localhost:8010`.

### 2) Frontend

```bash
cd web_gui/frontend
npm install
npm run dev
```

Frontend defaults to `http://localhost:5173`.

## Architecture

```
frontend ←WebSocket→ backend ←rclpy→ ROS2 topics
                │
                ├── /ws/stream  ← RosBridge ← /eeg_analysis
                ├── /ws/teleop  → RosBridge → /cmd_vel (Twist)
                ├── /ws/gazebo_frame ← camera_bridge proxy
                ├── /api/config  ← config_store (YAML persistence)
                └── /api/system/start|stop → command_runner (subprocess)
```

- **RosBridge**: single rclpy thread manages both signal subscription and teleop publishing
- **Signal flow**: pipeline → `/eeg_analysis` (JSON) → RosBridge → WebSocket → charts
- **Teleop flow**: web keypad → `/ws/teleop` → RosBridge `pub.publish()` (direct, zero-latency)
- **Config persistence**: web UI changes are written back to `launch_args.yaml`, `eeg_control_node.params.yaml`, `experiment_config.yaml`

## Available APIs

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health + RosBridge status (ready, error, msg_count) |
| `/api/config` | GET/PUT | Full experiment configuration |
| `/api/status` | GET | System status (ROS, Thymio, stream alive) |
| `/api/system/start` | POST | Save config + launch ROS2 pipeline |
| `/api/system/stop` | POST | Stop pipeline + kill all ROS/Gazebo processes |
| `/ws/stream` | WS | Real-time signal data (channels, features, control) |
| `/ws/teleop` | WS | Directional teleop commands |
| `/ws/gazebo_frame` | WS | Gazebo camera proxy |

## Process Lifecycle

- **Startup**: cleans residual ROS/Gazebo processes, inits RosBridge in background
- **Stop button**: SIGTERM child processes + `pkill` all known ROS/Gazebo patterns
- **Shutdown (Ctrl+C)**: same cleanup as Stop
