# TelekineRob-BCI

脑机接口（BCI）驱动的 Thymio 机器人控制平台。基于 ROS2 + Gazebo，支持 g.tec EEG 设备和 Web 远程控制。

本仓库是一个用于 Thymio 机器人的 ROS/ROS2 工作区，主要包含：

- `thymio_driver`、`thymio_description`、`thymio_msgs` 等包
- 通过 `ros-aseba` 与 Aseba 的集成
- Gazebo 仿真资源（URDF、mesh、传感器）

## 功能特性

- 双设备 EEG 输入：g.tec BCI Core-4 Headband / Unicorn Hybrid Black（经 LSL）
- 三种控制策略：TBR（θ/β）、EI（β/(α+θ)）、Alpha
- **眨眼切换转向**（metric-only 检测）+ 原地转向（`role=steering`）
- 30 秒自动校准（p5/p50）→ 写入 YAML
- Web GUI：实时波形、校准、遥控（FastAPI + React）

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
# 后端
cd web_gui/backend && source ../../.venv/bin/activate && python -m app.main

# 前端
cd web_gui/frontend && npm install && npm run dev
```

## Web GUI 设备选择

| 品牌 | Source | LSL stream |
|---|---|---|
| g.tec Headband | LSL Stream | `gtec_bci_core4` |
| g.tec Hybrid Black | LSL Stream | `gtec_hybrid_black` |

校准功能：选 g.tec 设备后点 **Calibrate** 按钮，30 秒自动采集 → 计算 p5/p95 → 虚线标注。

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
