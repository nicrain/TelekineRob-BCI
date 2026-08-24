# TelekineRob-BCI

脑机接口(BCI)驱动的 Thymio 机器人控制平台:基于 ROS2 + Gazebo,支持 g.tec EEG 设备、Web 远程控制与双人协同实验。

## 功能特性

- 双设备 EEG 输入:g.tec BCI Core-4 Headband / Unicorn Hybrid Black(经 LSL)
- **双设备模式(Phase 3)**:一台负责 speed、一台负责 steering,`cmd_vel_fuser` 融合;每设备独立参数文件与独立校准
- 三种控制策略:TBR(θ/β)、EI(β/(α+θ))、Alpha
- **眨眼切换转向**(metric-only 检测)+ 原地转向(`role=steering`)
- 30 秒自动校准(p5/p50)→ 写入各自 YAML
- Web GUI:实时波形(双列)、逐设备校准、遥控(FastAPI + React)

## 硬件

| 设备 | API | 通道 |
|---|---|---|
| g.tec BCI Core-4 Headband | gpype (`BCICore8`) | 4 (F8, Fp2, Fp1, F7) |
| g.tec Unicorn Hybrid Black | gpype (`HybridBlack`) 或 UnicornPy | 8 (Fz, C3, Cz, C4, Pz, PO7, Oz, PO8) |

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

## 快速开始

**colcon 构建:**

```bash
cd ~/TelekineRob-BCI
source /opt/ros/kilted/setup.bash
colcon build --symlink-install
source install/setup.bash
```

**仿真:**

```bash
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true use_teleop:=false input:=lsl
```

**真设备(g.tec):**

```bash
# Windows(按设备选一个)
python gtec_bridge/gpype_lsl_bridge.py
python gtec_bridge/unicornpy_lsl_bridge.py

# WSL2
ros2 launch thymio_control experiment_core.launch.py use_sim:=false run_eeg:=true use_teleop:=false input:=lsl
```

**双设备(dummy 双流验证):**

```bash
python thymio_control/lsl_test/dummy_dual_streams.py --blink
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true run_eeg2:=true eeg2_role:=steering
```

双设备:一台 speed、一台 steering,`cmd_vel_fuser` 融合发布最终 `/cmd_vel`;任一流断流 → 0.5s 内整车零速(fail-safe)。主题按 role 字面量后缀(`/eeg_analysis/steering`、`/eeg_cmd_vel/steering`,非 `steer`);每设备独立参数文件,校准回写互不覆盖。

**Web GUI:**

```bash
cd web_gui/backend && source ../../.venv/bin/activate && python -m app.main
cd web_gui/frontend && npm install && npm run dev
```

后端默认真执行(`WEB_GUI_ALLOW_REAL_COMMANDS` 默认 `true`)——设 `false` 切 dry-run;完整环境变量见 `web_gui/README.md`。

**测试:**

```bash
pytest thymio_control/test/test_*.py -v
```

完整测试与扩展见 `docs/GUIDE_DEVELOPPEUR.md` §3。

## 文档导航

| 文档 | 说明 | 受众 |
|---|---|---|
| README.md(本文件) | 项目总览与文档导航 | 全体 |
| docs/GLOSSAIRE.md | 术语表:中文术语 ↔ 技术标识符 | 全体 |
| docs/MANUEL_OPERATEUR.md | 操作手册:启动/连设备/校准/跑实验/导出/排查 | 操作者 |
| docs/GUIDE_INSTALLATION.md | 安装手册:Windows+WSL2+ROS2 从零搭建 | 技术人员 |
| docs/PROTOCOLE_EXPERIMENTAL.md | 实验协议:设计/数据管道/统计分析 | 研究者/论文 |
| docs/ARCHITECTURE_TECHNIQUE.md | 技术架构:数据流/双设备融合/fail-safe | 开发者 |
| docs/GUIDE_DEVELOPPEUR.md | 开发者导读:包结构/测试/扩展 | 开发者 |
| docs/DONNEES_EXPERIMENTALES.md | 实验数据格式:各文件字段 | 研究者 |

## 目录结构

- `web_gui/`:web 前后端(FastAPI 后端 + React 前端;实验模式、导出、O2 对接)
- `windows_launcher/`:O2 总控(操作者控制面板、服务编排、设备桥启动)
- `thymio_control/`:ROS 控制 + 验证(EEG 处理管线 adapter/processor/policy、ROS2 节点、launch、单测)
- `gtec_bridge/`:设备桥(g.tec gpype/UnicornPy → LSL 流)
- `src/`:ROS2 工作区(`ros-aseba` Thymio 驱动 + `ros-thymio` + `thymio_web_bridge`)
- `docs/`:计划 / 设计 / review(EXPERIMENT_PLAN、O2_LAUNCHER、PHASE3_DESIGN、REVIEW_FINDINGS、archived/)
- `experiment_data/`:实验日志(session 目录、trial CSV、导出分析表)
- `thymio_control/lsl_test/`:LSL 离线验证工具与测试(原根目录 `lsl_test/`,已移入 `thymio_control/`)

## 环境要求

- **操作系统**:Windows + WSL2(Ubuntu 24.04,ROS2 在 WSL2 内运行)
- **ROS2**:Kilted
- **Python**:3.12+
- **Thymio 机器人**(真机运行时需要)+ **Aseba Runtime**(`ros-aseba` 与 Thymio 通信需要)
- **⚠️ WSL2 需禁用 eth0 的 IPv6**,否则 liblsl 可能选中不可达的 IPv6 link-local 地址导致 LSL 连接挂起(无波形/校准卡 preparing)——配置见 `docs/GUIDE_INSTALLATION.md` §4
- 完整安装(驱动 / 设备桥 / WSL2 网络 / Web GUI)见 `docs/GUIDE_INSTALLATION.md`。
