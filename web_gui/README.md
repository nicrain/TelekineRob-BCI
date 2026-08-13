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

## Security & Environment Variables

The backend controls a **physical robot**, so its *network* posture is
locked down by default (loopback bind + origin whitelist + optional control
token). Real commands are **enabled by default**; set
`WEB_GUI_ALLOW_REAL_COMMANDS=false` for a mock/dry-run backend.

| Variable | Default | Meaning |
|---|---|---|
| `WEB_GUI_ALLOW_REAL_COMMANDS` | `true` | Master gate for real commands. Default is real execution; `false` → `/api/system/start` is a **dry-run** (nothing launched) and `/api/system/stop` / shutdown cleanup never blanket-`pkill` ROS/Gazebo processes. Set `false` only when you want a mock backend. |
| `WEB_GUI_HOST` | `127.0.0.1` | Bind address. Loopback only by default — not reachable from the LAN. Set `0.0.0.0` to expose, then also set a token. |
| `WEB_GUI_PORT` | `8010` | Bind port. |
| `WEB_GUI_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | Origin whitelist for CORS + WebSocket. The local Vite origins (`localhost:5173` / `127.0.0.1:5173`) are always allowed. Set a remote origin (e.g. `https://eeg.zhaoyu.wang`) to allow access from a specific host; `"*"` re-disables the check (research only). |
| `WEB_GUI_CONTROL_TOKEN` | *(empty)* | Control-token auth for the robot-driving endpoints: `/api/system/start`, `/api/system/stop` (`Authorization: Bearer <token>`) and `/ws/teleop` (`?token=<token>`). When empty, no token is required — use it when binding non-loopback. |
| `EXPERIMENT_DATA_DIR` | `<repo>/experiment_data` | Where experiment-mode sessions are written (per-session folder with `session.json` / `labels.csv` / `trials.csv` / `trial_<NNN>.csv`). Default is repo-root `experiment_data/` (gitignored). |

Example — real experiment, LAN-exposed with a token:

```bash
WEB_GUI_HOST=0.0.0.0 \
WEB_GUI_CONTROL_TOKEN=change-me \
python -m app.main
```

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
- **Config persistence**: web UI changes are written back to `launch_args.yaml`, `eeg_control_node.params.yaml`

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
| `/api/experiment/protocol` | GET | Default protocol file (trials + shuffle + prompt_sec) |
| `/api/experiment/configure` | POST | Start a session: metadata + protocol, shuffle applied |
| `/api/experiment/state` | GET | Current phase / target / countdown / progress |
| `/api/experiment/start` `pause` `resume` `reset` | POST | Trial-sequence control |

## Experiment Mode (P16)

Drive a protocol of ground-truth-labelled trials from the web GUI
(`04 — Experiment Mode` panel, `ExperimentPanel.jsx`). Fields follow
`docs/EXPERIMENT_PLAN.md` §2. Each session writes to
`<EXPERIMENT_DATA_DIR>/<session_id>/`:

- `session.json` — metadata (§2 #7) + the shuffled protocol (reproducibility)
- `labels.csv` — **E4 label stream**: one row per trial at prompt entry,
  `wall_ts` on the same wall clock as the samples' `row_ts` (EEG-aligned)
- `trials.csv` — one summary row per trial: truth (§2 #4) + prompt/start/end
  timestamps + mean alpha/tbr/ei + blink count
- `trial_<NNN>.csv` — per-trial sample rows: truth columns repeated +
  alpha/tbr/ei + speed/steer intents + steer_direction + cmd_lin/cmd_ang +
  `is_blink` (steer-direction toggles) + `latency_ms` (§2 #5/#6)

The trial state machine (prompt → trial → rest → next) is derived from wall
time in the backend — no background thread, pause keeps the remaining time.
Edit `backend/app/protocol.json` to change the trial list, ordering
(`none`/`random`/`balanced`) or prompt/rest durations.

## Process Lifecycle

- **Startup**: loads config from YAML, inits RosBridge in background (no residual process cleanup)
- **Stop button**: SIGTERM child processes; the blanket `pkill` of known ROS/Gazebo patterns runs by default and is only disabled by `WEB_GUI_ALLOW_REAL_COMMANDS=false` (mock mode never touches real processes)
- **Shutdown (Ctrl+C)**: same cleanup as Stop, gated on `WEB_GUI_ALLOW_REAL_COMMANDS` (opt out with `false`)
