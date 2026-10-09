# TelekineRob-BCI Web GUI

`TelekineRob-BCI` 工作区的 Web 界面 + Python 后端。

本文是模块专项参考，面向开发者。[返回中文项目总览](../README_cn.md)；完整安装、调试与维护见[中文版开发者交接手册](../docs/GUIDE_DEVELOPPEUR_cn.md)，日常使用见[中文操作手册](../docs/MANUEL_OPERATEUR_cn.md)。下列命令不代表真机验收通过。

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
python -m pip install -r ../../requirements.txt
source /opt/ros/kilted/setup.bash
source ../../install/setup.bash
python -m app.main
```

后端默认 `http://localhost:8010`。

上述命令从仓库根目录开始，需已创建 `.venv` 并完成 colcon构建。在无ROS的开发电脑上只能验证部分接口和逻辑；界面能加载不表示机器人控制可用。仅做mock检查时启动为 `WEB_GUI_ALLOW_REAL_COMMANDS=false python -m app.main`。

### 2) Frontend

```bash
cd web_gui/frontend
npm install
npm run dev
```

前端默认 `http://localhost:5173`。

## 安全与环境变量

真实命令默认开启。后端默认回环绑定、部分接口支持 origin / token 检查，但前端代理仍可能将后端接口暴露给其他客户端，不能当成完整权限体系。`WEB_GUI_ALLOW_REAL_COMMANDS=false` 只限制进程启动 / 清理，不阻断直接 Teleop 发布；无硬件开发仍需隔离真机输出。完整边界见[技术档案](../docs/DOSSIER_TECHNIQUE_cn.md#312-网络命令与数据边界)。

| 变量 | 默认 | 说明 |
|---|---|---|
| `WEB_GUI_ALLOW_REAL_COMMANDS` | `true` | 进程执行门禁。`false` 时 Start 为 dry-run、Stop / 关闭不清理真实 ROS / Gazebo 进程；不是全局运动总闸，直接 Teleop 不受此变量阻断 |
| `WEB_GUI_HOST` | `127.0.0.1` | 后端绑定地址；默认不能直连局域网，但可经 Vite 代理访问，不能据此认定接口对局域网不可达 |
| `WEB_GUI_PORT` | `8010` | 绑定端口 |
| `WEB_GUI_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | CORS + WebSocket 的 origin 白名单。本地 Vite origin 恒放行；launcher 模板设为 `"*"`，放宽 origin 校验，不是授权机制 |
| `WEB_GUI_CONTROL_TOKEN` | *(空)* | 部分控制接口的 token：`/api/system/start`、`/api/system/stop`（Bearer）与 `/ws/teleop`（`?token=`）。为空时无需 token；不覆盖全部 API，也不能仅按后端绑定地址判断实际访问范围 |
| `EXPERIMENT_DATA_DIR` | `<repo>/experiment_data` | 开发者研究验证数据目录，每 session 一个文件夹。历史数据已从当前工作区移除；整个默认目录已加入 `.gitignore`，不作为源码交付内容。收集功能仍可生成新数据；其他输出位置须单独检查权限与忽略规则。 |

局域网配置先核对监听、代理、端口转发、origin 和实际授权路径，不把添加 token 当成所有接口均受保护。当前不提供已经安全验收的互联网部署方案。

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
- **遥控流**：Device选项名为 Keyboard，但当前网页通过鼠标 / 触摸按住方向按钮发送命令，不提供实体键盘按键绑定。路径是 `/ws/teleop` → RosBridge → 速度topic；不是零延迟保证。
- **配置持久化**：后端回写仓库中的 `launch_args.yaml` 和两路 `eeg_control_node*.params.yaml`，查看 `/api/config` 的 `source_files` 可确认源码配置路径。ROS launch读取 colcon安装目录中的配置，使用 `--symlink-install` 时须确认链接指向预期源码；校准另外尝试写回源码及安装目录。

## 可用 API

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/health` | GET | 健康 + RosBridge 状态(ready、error、msg_count) |
| `/api/config` | GET/PUT | 完整实验配置 |
| `/api/status` | GET | 系统状态(ROS、Thymio、流活性) |
| `/api/system/start` | POST | 按已保存配置启动 ROS2 管线；配置另通过 `/api/config` 保存 |
| `/api/system/stop` | POST | 停止托管管线，并在真执行模式下按预设进程名模式清理 ROS/Gazebo；可能影响同机其他匹配进程 |
| `/ws/stream` | WS | 实时信号数据(通道、特征、控制) |
| `/ws/teleop` | WS | 方向遥控命令 |
| `/ws/gazebo_frame` | WS | Gazebo 相机代理 |
| `/api/logs` | GET | 最近后端日志记录 + WSL launcher 日志尾部(日志面板) |
| `/api/experiment/protocol` | GET | 默认协议文件(trials + shuffle + prompt_sec) |
| `/api/experiment/configure` | POST | 启动 session:元数据 + 协议,应用 shuffle |
| `/api/experiment/state` | GET | 当前相位 / 目标 / 倒计时 / 进度 |
| `/api/experiment/start` `pause` `resume` `reset` | POST | 试次序列控制 |

## 开发者数据记录（研究验证）

`ExperimentPanel.jsx` 用于开发者收集带真值标签的数据以验证系统，不属于非技术用户的正常使用流程。字段参考研究资料 `docs/EXPERIMENT_PLAN.md`；实际列名以代码为准。每个 session写入 `<EXPERIMENT_DATA_DIR>/<session_id>/`：

- `session.json` — 手填 `meta`(§2 #7:subject/role/session/electrode/date)+ **实际运行 `system` 配置**(metric / device_mode / roles / devices)——由前端从其实时 01 状态提供、后端校验(P20/P21:从不手填;has_hybrid 覆盖单设备 hybrid)+ 打乱协议(可复现)
- `labels.csv` — **E4 标签流**:每试次在 prompt 入口写一行,`wall_ts` 与样本 `row_ts` 同一墙上时钟(EEG 对齐)
- `trials.csv` — 每试次一行汇总:真值(§2 #4)+ prompt/start/end 时间戳 + mean alpha/tbr/ei + blink count
- `trial_<NNN>.csv` — 每试次样本行:重复真值列 + alpha/tbr/ei + speed/steer 意图 + steer_direction + cmd_lin/cmd_ang + `is_blink`(转向翻转)+ `latency_ms`(§2 #5/#6)

当前试次状态机为 prompt → trial → 下一个prompt（最后一次trial后done），没有独立rest阶段。后端按墙上时间惰性推进，无专用计时线程；暂停保留剩余时间。协议配置位于 `backend/app/protocol.json`，可改试次、shuffle、seed和 `prompt_sec`。

## 开发测试

从 `web_gui/backend` 使用仓库根虚拟环境执行 `../../.venv/bin/python -m pytest app -v`。仓库根直接 `pytest` 默认不发现该目录，完整套件入口见[开发者交接手册](../docs/GUIDE_DEVELOPPEUR_cn.md#71-现有测试入口)。

## 进程生命周期

- **启动**:从 YAML 加载配置,后台初始化 RosBridge(无残留进程清理)
- **停止按钮**:SIGTERM 子进程;对已知 ROS/Gazebo 模式的 blanket `pkill` 默认执行,仅 `WEB_GUI_ALLOW_REAL_COMMANDS=false` 时禁用(mock 模式永不触碰真实进程)
- **关闭(Ctrl+C)**:与 Stop 相同的清理,受 `WEB_GUI_ALLOW_REAL_COMMANDS` 门控(设 `false` 退出)
