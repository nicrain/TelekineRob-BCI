# TelekineRob-BCI Web GUI

`TelekineRob-BCI` 工作区的 Web 界面 + Python 后端。

## 目标

- 即使没有可用的 ROS2 硬件运行时,也能在本机工作。
- 管线运行时,图表经 `RosBridge` 显示真实管线数据;空闲时为空。
- 提供完整的实验配置、启停控制与基于网页的遥控。

## 目录结构

- `backend/`:FastAPI 服务、WebSocket 流、RosBridge、配置模型、命令执行器。
- `frontend/`:React + Vite + ECharts 仪表盘。

## Quick Start

### 1) Backend

```bash
cd web_gui/backend
source ../../.venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

后端默认 `http://localhost:8010`。

### 2) Frontend

```bash
cd web_gui/frontend
npm install
npm run dev
```

前端默认 `http://localhost:5173`。

## 安全与环境变量

后端控制的是**真实机器人**,因此其*网络*姿态默认锁紧(loopback 绑定 + origin 白名单 + 可选控制 token)。真实命令**默认开启**;设 `WEB_GUI_ALLOW_REAL_COMMANDS=false` 得到 mock/dry-run 后端。

| 变量 | 默认 | 说明 |
|---|---|---|
| `WEB_GUI_ALLOW_REAL_COMMANDS` | `true` | 真实命令总闸。默认即真执行;`false` → `/api/system/start` 是 **dry-run**(不启动任何东西),`/api/system/stop` 与关闭清理永不 blanket-`pkill` ROS/Gazebo 进程。仅想要 mock 后端时设 `false` |
| `WEB_GUI_HOST` | `127.0.0.1` | 绑定地址。默认仅 loopback——局域网不可达。设 `0.0.0.0` 暴露,然后也建议配 token |
| `WEB_GUI_PORT` | `8010` | 绑定端口 |
| `WEB_GUI_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | CORS + WebSocket 的 origin 白名单。本地 Vite origin(`localhost:5173` / `127.0.0.1:5173`)恒放行。设远程 origin(如 `https://eeg.zhaoyu.wang`)允许特定主机访问;`"*"` 重新关闭校验(仅研究) |
| `WEB_GUI_CONTROL_TOKEN` | *(空)* | 驾驶机器人端点的控制 token:`/api/system/start`、`/api/system/stop`(`Authorization: Bearer <token>`)与 `/ws/teleop`(`?token=<token>`)。为空时无需 token——绑定非 loopback 时使用 |
| `EXPERIMENT_DATA_DIR` | `<repo>/experiment_data` | 实验模式会话写入目录(每 session 一个文件夹:`session.json` / `labels.csv` / `trials.csv` / `trial_<NNN>.csv`)。默认仓库根 `experiment_data/`(gitignored) |

示例——真机实验、LAN 暴露 + token:

```bash
WEB_GUI_HOST=0.0.0.0 \
WEB_GUI_CONTROL_TOKEN=change-me \
python -m app.main
```

## 架构

```
frontend ←WebSocket→ backend ←rclpy→ ROS2 topics
                │
                ├── /ws/stream  ← RosBridge ← /eeg_analysis
                ├── /ws/teleop  → RosBridge → /cmd_vel (Twist)
                ├── /ws/gazebo_frame ← camera_bridge proxy
                ├── /api/config  ← config_store (YAML persistence)
                └── /api/system/start|stop → command_runner (subprocess)
```

- **RosBridge**:单 rclpy 线程同时管理信号订阅与遥控发布
- **信号流**:管线 → `/eeg_analysis`(JSON)→ RosBridge → WebSocket → 图表
- **遥控流**:网页键盘 → `/ws/teleop` → RosBridge `pub.publish()`(直接、零延迟)
- **配置持久化**:web UI 改动回写 `launch_args.yaml`、`eeg_control_node.params.yaml`

## 可用 API

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 健康 + RosBridge 状态(ready、error、msg_count) |
| `/api/config` | GET/PUT | 完整实验配置 |
| `/api/status` | GET | 系统状态(ROS、Thymio、流活性) |
| `/api/system/start` | POST | 保存配置 + 启动 ROS2 管线 |
| `/api/system/stop` | POST | 停止管线 + 杀全部 ROS/Gazebo 进程 |
| `/ws/stream` | WS | 实时信号数据(通道、特征、控制) |
| `/ws/teleop` | WS | 方向遥控命令 |
| `/ws/gazebo_frame` | WS | Gazebo 相机代理 |
| `/api/logs` | GET | 最近后端日志记录 + WSL launcher 日志尾部(日志面板) |
| `/api/experiment/protocol` | GET | 默认协议文件(trials + shuffle + prompt_sec) |
| `/api/experiment/configure` | POST | 启动 session:元数据 + 协议,应用 shuffle |
| `/api/experiment/state` | GET | 当前相位 / 目标 / 倒计时 / 进度 |
| `/api/experiment/start` `pause` `resume` `reset` | POST | 试次序列控制 |

## 实验模式(P16)

从 web GUI(`04 — Experiment Mode` 面板,`ExperimentPanel.jsx`)驱动一组带真值标签的试次协议。字段遵循 `docs/EXPERIMENT_PLAN.md` §2。每个 session 写入 `<EXPERIMENT_DATA_DIR>/<session_id>/`:

- `session.json` — 手填 `meta`(§2 #7:subject/role/session/electrode/date)+ **实际运行 `system` 配置**(metric / device_mode / roles / devices)——由前端从其实时 01 状态提供、后端校验(P20/P21:从不手填;has_hybrid 覆盖单设备 hybrid)+ 打乱协议(可复现)
- `labels.csv` — **E4 标签流**:每试次在 prompt 入口写一行,`wall_ts` 与样本 `row_ts` 同一墙上时钟(EEG 对齐)
- `trials.csv` — 每试次一行汇总:真值(§2 #4)+ prompt/start/end 时间戳 + mean alpha/tbr/ei + blink count
- `trial_<NNN>.csv` — 每试次样本行:重复真值列 + alpha/tbr/ei + speed/steer 意图 + steer_direction + cmd_lin/cmd_ang + `is_blink`(转向翻转)+ `latency_ms`(§2 #5/#6)

试次状态机(prompt → trial → rest → next)由后端按墙上时间推导——无后台线程,暂停保留剩余时间。编辑 `backend/app/protocol.json` 可改试次列表、顺序(`none`/`random`/`balanced`)或 prompt/rest 时长。

## 进程生命周期

- **启动**:从 YAML 加载配置,后台初始化 RosBridge(无残留进程清理)
- **停止按钮**:SIGTERM 子进程;对已知 ROS/Gazebo 模式的 blanket `pkill` 默认执行,仅 `WEB_GUI_ALLOW_REAL_COMMANDS=false` 时禁用(mock 模式永不触碰真实进程)
- **关闭(Ctrl+C)**:与 Stop 相同的清理,受 `WEB_GUI_ALLOW_REAL_COMMANDS` 门控(设 `false` 退出)
