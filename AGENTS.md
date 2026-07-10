# AGENTS.md

This file provides guidance to Codex when working with code in this repository.

## Project Overview

This is a ROS2-based Thymio robot control platform for EEG experiments using g.tec devices, developed primarily on **Windows + WSL2** (Ubuntu 24.04 with ROS2 Kilted). The system bridges g.tec EEG devices to Thymio robot control via ROS2 topics.

## Build & Run Commands

### ROS2 Packages
```bash
colcon build --symlink-install
source install/setup.bash
```

### Launch
```bash
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true use_teleop:=false input:=mock
```

### Tests
```bash
pytest thymio_control/test/test_*.py -v
```

### Web GUI
```bash
# Backend (FastAPI, port 8010)
cd web_gui/backend && source ../../.venv/bin/activate && python -m app.main

# Frontend (Vite, port 5173)
cd web_gui/frontend && npm install && npm run dev
```

## Architecture

```
Windows 主机:
  gtec_bridge/gpype_lsl_bridge.py        (BCI Core-4, gpype → LSL)
  gtec_bridge/unicornpy_lsl_bridge.py    (Hybrid Black, UnicornPy → LSL)
        ↓ LSL

WSL2/Ubuntu:
  RawLslAdapter → Welch PSD → enrich_features → Policy → /cmd_vel
                                                      ↓
  web_gui (React + FastAPI) ←──WebSocket──→ RosBridge (rclpy)
```

## Key Files
- `thymio_control/thymio_control/pipeline.py` — Pipeline assembler (adapter + processor + policy)
- `thymio_control/scripts/eeg_control_node.py` — ROS2 node
- `thymio_control/launch/experiment_core.launch.py` — Main launch
- `thymio_control/config/eeg_control_node.params.yaml` — ROS2 params
- `web_gui/backend/app/signal_subscriber.py` — RosBridge
- `web_gui/backend/app/command_runner.py` — Process lifecycle
- `web_gui/backend/app/config_store.py` — YAML persistence
- `gtec_bridge/` — Windows LSL bridge scripts

## Data Flow
1. Adapter (LSL/Mock/Keyboard) → `EegFrame`
2. `enrich_features()` → theta_beta, alpha_asym, beta_alpha_theta
3. `Policy.compute_intents()` → speed_intent / steer_intent
4. `_intents_to_twist()` → Twist → /cmd_vel
5. Analysis JSON → /eeg_analysis → WebSocket → charts

## Key ROS2 Topics
- `/cmd_vel` — velocity commands (Twist)
- `/eeg_analysis` — EEG analysis JSON

## Key Design Principles
1. **Config-driven** — YAML for all parameters
2. **Strategy Pattern** — `POLICIES` dict in `pipeline.py` (Ei/Tbr/Alpha)
3. **Adapter Pattern** — `build_adapter()` supports `mock`, `keyboard`, `lsl`
4. **Watchdog (0.5s)** — reuse last Twist on data loss
5. **Fail-fast** — explicit exceptions, no silent defaults

## Testing
- Tests: `thymio_control/test/test_*.py` (23 tests)
- Run: `pytest thymio_control/test/test_*.py -v`

## Devices
| key | Device | Channels |
|---|---|---|
| `bci-core-4` | BCI Core-4 Headband | 4 (F8, Fp2, Fp1, F7) |
| `hybrid-black` | Unicorn Hybrid Black | 8 (Fz, C3, Cz, C4, Pz, PO7, Oz, PO8) |

## Development Guidelines

### 1. Think Before Coding
- State assumptions explicitly
- Present multiple interpretations before implementing
- If unclear, stop and ask

### 2. Simplicity First
- No features beyond what was requested
- No abstractions for single-use code
- If 200 lines can be 50, rewrite it

### 3. Surgical Changes
- Touch only what you must
- Don't refactor things that aren't broken
- Every changed line should trace directly to the request

### 4. Goal-Driven Execution
- Define success criteria; loop until verified

## Environment
- ROS2 Kilted on Ubuntu 24.04 inside WSL2
- Python 3.12+, `.venv` virtual environment
- Aseba Runtime for real Thymio hardware
