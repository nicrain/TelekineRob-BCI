# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a ROS2-based Thymio robot control platform for EEG experiments using g.tec devices, developed primarily on **Windows + WSL2** (Ubuntu 24.04 with ROS2 Kilted). The system bridges EEG input devices to Thymio robot control via ROS2 topics.

## Build & Run Commands

### ROS2 Packages
```bash
colcon build --symlink-install
source install/setup.bash
```

### Launch Files
| Command | Purpose |
|---|---|
| `ros2 launch thymio_control experiment_core.launch.py` | Unified orchestration (use_sim, run_eeg) |

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

Main components communicate via ROS2 topics, WebSockets, and LSL:

```
web_gui (React + FastAPI) ←──WebSocket──→ RosBridge (single rclpy thread)
         │                      │                ├── sub: /eeg_analysis
         │                      │                └── pub: /cmd_vel (teleop)
         │                      │
         │              thymio_web_bridge (Gazebo camera proxy)
         │                      ↑
         │              ros2 launch (subprocess)
         │                      ↓
         │              thymio_control (EEG processing)
         │                      ↓ /cmd_vel
         │              Gazebo sim OR Real Thymio (asebaros)
         │
         └── REST: /api/config, /api/system/start|stop
```

Windows ↔ WSL2 bridge: g.tec EEG devices stream via LSL from Windows host; WSL2 receives with `RawLslAdapter`.

### Key Files
- `thymio_control/thymio_control/pipeline.py` — Pipeline assembler (adapter + processor + policy)
- `thymio_control/scripts/eeg_control_node.py` — ROS2 node (subscribes adapter, publishes Twist + analysis)
- `thymio_control/launch/experiment_core.launch.py` — Main launch orchestration
- `thymio_control/config/eeg_control_node.params.yaml` — ROS2 node parameters
- `thymio_control/config/thymio_world.sdf` — Gazebo world (ground plane + overhead camera)
- `web_gui/backend/app/main.py` — FastAPI app (REST + WebSocket endpoints)
- `web_gui/backend/app/signal_subscriber.py` — RosBridge (single rclpy thread: signal sub + teleop pub)
- `web_gui/backend/app/command_runner.py` — Subprocess launcher + process cleanup
- `web_gui/backend/app/config_store.py` — YAML config persistence
- `web_gui/frontend/src/App.jsx` — React dashboard (controls, charts, teleop, camera)
- `gtec_bridge/` — Windows-side LSL bridge scripts

### Data Flow
1. Adapter (LSL/Keyboard) → reads EEG data → `EegFrame` with metrics
2. `enrich_features()` computes derived features (theta/beta, alpha asymmetry, etc.)
3. `Policy.compute_intents()` maps features → `speed_intent` / `steer_intent`
4. `_intents_to_twist()` converts intents → `geometry_msgs/Twist` → `/cmd_vel`
5. Analysis JSON (metrics + features + intents) published to `/eeg_analysis`
6. RosBridge subscribes to `/eeg_analysis` → transforms to web format → WebSocket → charts

### Key ROS2 Topics
- `/cmd_vel` — velocity commands (Twist)
- `/eeg_analysis` — EEG feature analysis output (JSON string)
- `/camera/image_raw` — camera feed from Gazebo overhead camera

## Key Design Principles

1. **Config-driven**: All device ports, channel mappings, algorithms are YAML-injected, never hardcoded
2. **Strategy Pattern**: `POLICIES` dict in `pipeline.py` for swappable control algorithms (Ei/Tbr/Alpha)
3. **Adapter Pattern**: `build_adapter()` factory supports `keyboard` and `lsl` modes
4. **Watchdog (0.5s)**: If no EEG data received, reuse last known Twist — NOT default to full speed
5. **Fail-fast**: Missing fields or out-of-bounds channel indices must raise explicit exceptions, not silently default

## Testing Strategy

Given the difficulty of physical robot testing, the project uses **test-driven development with pytest**:
- All tests live in `thymio_control/test/` as `test_*.py` files
- Each new feature requires a unit test in the same directory
- Tests use test data to verify logic correctness
- Run tests: `pytest thymio_control/test/test_<name>.py -v`

## Pre-commit Rules

Before committing code changes (except documentation-only changes):

1. Run the full test suite and confirm all pass: `pytest thymio_control/test/ -q`
2. If the change is not covered by existing tests, add a test for it first
3. Only commit after tests pass

## Workflow

- Every session: read `TASKS.md` first to understand current task status.
- When a task is completed: update `TASKS.md`, marking it ✅ with date.
- Before session ends: append any newly discovered TODOs to `TASKS.md`.
- Also keep system `/tasks` in sync via TaskCreate/TaskUpdate when relevant.

## Development Guidelines

Based on [Andrej Karpathy's coding principles](https://github.com/forrestchang/andrej-karpathy-skills), adapted for ROS2/robotics projects.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly — especially about ROS2 topic timing, hardware handshake, or data format assumptions
- If multiple interpretations exist, present them before implementing
- If a simpler approach exists, say so
- If something is unclear, stop and ask

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was requested
- No abstractions for single-use code — the `POLICIES` dict and `build_adapter()` factory are the exceptions (justified by the strategy/adapter patterns)
- No "flexibility" not in the YAML config
- If you write 200 lines and it could be 50, rewrite it

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting
- Don't refactor things that aren't broken
- Match existing style
- When your changes create unused imports/variables, remove them — but don't touch pre-existing dead code
- The test: every changed line should trace directly to the user's request
