# TelekineRob-BCI

脑机接口（BCI）驱动的 Thymio 机器人控制平台。基于 ROS2 + Gazebo，支持 g.tec EEG 设备和 Web 远程控制。

本仓库是一个用于 Thymio 机器人的 ROS/ROS2 工作区，主要包含：

- `thymio_driver`、`thymio_description`、`thymio_msgs` 等包
- 通过 `ros-aseba` 与 Aseba 的集成
- Gazebo 仿真资源（URDF、mesh、传感器）

## 功能特性

- 双设备 EEG 输入：g.tec BCI Core-4 Headband / Unicorn Hybrid Black（经 LSL）
- **双设备模式（Phase 3）**：一台负责 speed、一台负责 steering，`cmd_vel_fuser` 融合；每设备独立参数文件与独立校准
- 三种控制策略：TBR（θ/β）、EI（β/(α+θ)）、Alpha
- **眨眼切换转向**（metric-only 检测）+ 原地转向（`role=steering`）
- 30 秒自动校准（p5/p50）→ 写入各自 YAML
- Web GUI：实时波形（双列）、逐设备校准、遥控（FastAPI + React）

## 硬件

| 设备 | API | 通道 |
|---|---|---|
| g.tec BCI Core-4 Headband | gpype (`BCICore8`) | 4 (F8, Fp2, Fp1, F7) |
| g.tec Unicorn Hybrid Black | gpype (`HybridBlack`) 或 UnicornPy | 8 (Fz, C3, Cz, C4, Pz, PO7, Oz, PO8) |

## 环境要求

- **操作系统**：Windows + WSL2（Ubuntu 24.04，ROS2 在 WSL2 内运行）
- **ROS2**：Kilted
- **Python**：3.12+
- **Thymio 机器人**（真机运行时需要）
- **Aseba Runtime**（`ros-aseba` 与 Thymio 通信需要）

### WSL2 网络配置（必需）

g.tec 的 LSL 流在 WSL2 上发现时，liblsl 可能选中 **不可达的 IPv6 link-local 地址**（`fe80::...`）来建立数据连接，导致 eeg 节点连接挂起、无波形、校准卡在 preparing。需要在 WSL2 内禁用 eth0 的 IPv6，强制 LSL 走 IPv4：

```bash
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl --system
```

WSL2 需启用 systemd（`/etc/wsl.conf` 中 `[boot] systemd=true`），systemd 会在每次 WSL 启动时自动应用该配置。若未启用 systemd，改用 `/etc/wsl.conf` 的 `[boot] command` 每次启动执行上述 sysctl。

## 架构

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

## 构建

```bash
cd ~/TelekineRob-BCI
source /opt/ros/kilted/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## 运行

### 仿真

```bash
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true use_teleop:=false input:=lsl
```

### 真设备（g.tec）

Windows 端启动 bridge，WSL2 端启动 EEG：

```bash
# Windows（根据设备选一个）
python gtec_bridge/gpype_lsl_bridge.py
python gtec_bridge/unicornpy_lsl_bridge.py

# WSL2
ros2 launch thymio_control experiment_core.launch.py use_sim:=false run_eeg:=true use_teleop:=false input:=lsl
```

### Web GUI

```bash
# 后端（默认真实执行；设 WEB_GUI_ALLOW_REAL_COMMANDS=false 可切回 dry-run）
cd web_gui/backend && source ../../.venv/bin/activate && python -m app.main

# 前端
cd web_gui/frontend && npm install && npm run dev
```

### 双设备（Dual-device）

一台设备负责 **speed**、另一台负责 **steering**（`/eeg_cmd_vel/<role>` 后缀主题），`cmd_vel_fuser` 融合后发布最终 `/cmd_vel`。任一流断流 → fuser 在 0.5s 内整车零速（fail-safe）。

```bash
# 双设备仿真（dummy 双流验证）
python lsl_test/dummy_dual_streams.py --blink
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true run_eeg2:=true eeg2_role:=steering
```

主题约定：双设备分析/指令主题按 **role 字面量** 后缀（`/eeg_analysis/steering`、`/eeg_cmd_vel/steering`，非 `steer`）。每设备有独立参数文件（`eeg_control_node.params.yaml` / `eeg_control_node.eeg2.params.yaml`），校准回写互不覆盖。

## Web GUI 后端环境变量

后端默认**锁紧网络**：origin 白名单为本地 Vite、绑定 `127.0.0.1`（真实命令默认开启，见下）。

| 变量 | 默认 | 说明 |
|---|---|---|
| `WEB_GUI_ALLOW_REAL_COMMANDS` | `true` | 真实命令门禁。默认即真执行；设 `false` → Start 是 dry-run、Stop 不 pkill 真实进程。仅当主动绑 `0.0.0.0` 暴露网络时建议关闭 |
| `WEB_GUI_HOST` | `127.0.0.1` | 绑定地址。设 `0.0.0.0` 暴露到局域网（建议同时配 token） |
| `WEB_GUI_PORT` | `8010` | 绑定端口 |
| `WEB_GUI_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | origin 白名单（本地 `localhost:5173`/`127.0.0.1:5173` 恒放行） |
| `WEB_GUI_CONTROL_TOKEN` | *(空)* | 控制接口 token：REST `Authorization: Bearer`、teleop WS `?token=`。前端启动时经 `/api/config/control_token` 获取（仅 loopback 可读）；未配置则前端不带 → 行为不变 |

## Web GUI 设备选择

| 品牌 | Source | LSL stream |
|---|---|---|
| g.tec Headband | LSL Stream | `gtec_bci_core4` |
| g.tec Hybrid Black | LSL Stream | `gtec_hybrid_black` |

校准功能：选 g.tec 设备后点 **Calibrate** 按钮，30 秒自动采集 → 计算 p5/p50（中位数参考）→ 虚线标注。双设备模式下每列有独立的 Calibrate 按钮，校准结束自动停止，用户手动 **Start** 开始正式实验。

## 测试

```bash
pytest thymio_control/test/test_*.py -v
```

## 仓库结构

- `thymio_control/`：EEG 处理管线（adapter、processor、policy）、ROS2 节点、launch
- `gtec_bridge/`：Windows 端 LSL 桥接脚本和测试脚本
- `web_gui/`：FastAPI 后端 + React 前端
- `src/ros-thymio/`：Thymio ROS2 包
- `src/ros-aseba/`：Aseba 桥接
