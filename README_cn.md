# TelekineRob-BCI

[操作手册](docs/MANUEL_OPERATEUR_cn.md) · [排障手册](docs/GUIDE_DEBUG_cn.md)

TelekineRob-BCI 是一个基于 EEG 的 Thymio 机器人控制平台。系统将 g.tec 设备采集的脑电数据通过 LSL 传入 ROS2，计算频带功率与控制指标，再生成机器人运动命令；网页提供设备连接、校准、实时分析和控制界面。

项目面向 EEG 与机器人交互研究，支持单人单设备控制，以及两人分别负责速度和转向的协同控制。真实设备在 Windows 上连接，信号处理、ROS2 和网页服务运行于 WSL2；也可使用合成 EEG 与 Gazebo 在没有真实设备的情况下进行开发验证。

## 主要功能

- **单 EEG 控制**：选择 Speed 控制前进，或 Steering 控制原地转向。
- **双 EEG 协同**：Headband 与 Hybrid Black 分别承担速度和转向，经融合器输出最终速度。
- **三种指标映射**：Alpha 频带功率、TBR（θ / β）、EI（β / (α + θ)）。
- **眨眼切换方向**：Steering 角色通过指标眨眼检测切换左 / 右方向。
- **逐设备校准**：收到数据后采集 30 秒，计算参考值并保存至各自参数文件。
- **网页控制**：选择设备、角色、指标与输出，查看频带功率、指标和控制方向。
- **手动与仿真验证**：网页 Keyboard 方向按钮、Gazebo Thymio 仿真、双路合成 LSL 工具。
- **断流保护**：EEG 节点与双路融合器检查数据新鲜度，处理缺失或陈旧输入。

单设备只承担一个角色，第二行设为 None；双设备分配 Speed 与 Steering。网页图表是处理后的分析结果，不是原始 EEG 的逐样本波形。

## 支持的硬件

| 设备 | 当前接入方式 | EEG 通道 / LSL source_id |
|---|---|---|
| g.tec BCI Core-4 Headband | Windows 的 gpype 桥 | 4：F8、Fp2、Fp1、F7；`gtec_bci_core4` |
| Unicorn Hybrid Black | Windows 的 UnicornPy 桥 | 8：Fz、C3、Cz、C4、Pz、PO7、Oz、PO8；`gtec_hybrid_black` |
| 无线 Thymio 与 USB Dongle | usbipd-win 将 Dongle 接入 WSL，再由 ROS 驱动控制 | 真机输出 |
| Gazebo 中的 Thymio | ROS / Gazebo 桥 | 仿真输出，无需真实 Dongle |

本项目两台 EEG 默认使用电脑集成蓝牙，不使用 Hybrid Black 附带的 USB 蓝牙适配器；Thymio 的 USB Dongle 是另一种设备，真机控制仍需要它。当前桥使用每种型号固定的 source_id，不支持把任意两台同型号 EEG 直接作为两路独立设备。

下一阶段主要需求是支持**两台同型号 g.tec EEG**，分别承担 Speed 与 Steering，并保留现有单设备和混合型号模式。这是尚未实现、尚未完成真机验证的开发目标，见[需求与验收条件](docs/DOSSIER_TECHNIQUE_cn.md#25-下一阶段主要需求同型号双-gtec)和[新实习生实施路线](docs/GUIDE_DEVELOPPEUR_cn.md#75-首要开发任务同型号双-gtec-集成)。

## 系统架构

```text
Windows
  System Control：管理网页服务、设备桥与 USB 连接
  Headband / Hybrid Black → 设备桥 → LSL
                                      ↓
WSL2 / Ubuntu
  RawLslAdapter → Welch PSD → 特征 → Policy → EEG 控制节点
                                               ├─ 单路 → 最终速度
                                               └─ 双路部分速度 → fuser → 最终速度
  ROS 分析 → FastAPI / WebSocket → React 网页
  网页手动按钮 → RosBridge → 最终速度
                                      ↓
                            Thymio / Gazebo
```

真机最终话题为 `/cmd_vel`，仿真为 `/model/thymio/cmd_vel`。双路部分命令发布至 `/eeg_cmd_vel/speed`、`/eeg_cmd_vel/steering`；分析话题为 `/eeg_analysis` 或对应角色后缀话题。

更详细的算法、运动映射、配置和接口见[技术档案](docs/DOSSIER_TECHNIQUE_cn.md#3-系统设计)。

## 环境要求

| 环境 | 要求 |
|---|---|
| 操作系统 | Windows + WSL2，Ubuntu 24.04 |
| ROS2 | Kilted；使用与系统 ROS 兼容的 Python，项目基线为 Python 3.12 |
| WSL Python 依赖 | 仓库根 `.venv` 与 [requirements.txt](requirements.txt) |
| 前端 | 支持仓库 Vite 5 的 Node.js / npm；依赖版本由 [package-lock.json](web_gui/frontend/package-lock.json)管理 |
| Windows 设备环境 | gpype / UnicornPy、pylsl 及对应 SDK / 驱动；Python 版本和位数需与 SDK 匹配 |
| Windows 工具 | Python / Pythonw、VS Code、usbipd-win |
| ROS 工作区依赖 | 仓库中的 Thymio / Aseba 包；仿真还需 ROS Gazebo 相关包 |

g.tec SDK 不包含在根 pip 依赖清单中。完整系统依赖、SDK 准备、WSL 网络与首次 Windows 部署见[环境安装说明](docs/GUIDE_DEVELOPPEUR_cn.md#3-环境安装与重建)。

## 快速开始

### 1. 获取源码并准备 WSL 工作区

以下命令在 **WSL Bash** 执行。先按[安装说明](docs/GUIDE_DEVELOPPEUR_cn.md#32-wsl-与-ros-前置条件)准备 ROS2、colcon 和工作区系统依赖；在选定父目录 clone，不覆盖已有仓库。

```bash
git clone --branch main https://github.com/nicrain/TelekineRob-BCI.git
cd TelekineRob-BCI
source /opt/ros/kilted/setup.bash
colcon build --symlink-install
source install/setup.bash

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

前端安装与构建，从仓库根开始：

```bash
cd web_gui/frontend
npm ci
npm run build
```

已有 `.venv` 或可运行系统时先核对环境，不重复创建。首次 ROS 构建包含 `src/` 内依赖包，不能仅构建 EEG 控制包。

### 2. 启动网页

可通过 Windows 的 System Control 管理网页，也可在开发时分开运行前后端；**不要同时启动两份**。

WSL 终端 A，从仓库根开始：

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
cd web_gui/backend
python -m app.main
```

WSL 终端 B，从仓库根开始：

```bash
cd web_gui/frontend
npm run dev -- --port 5173 --strictPort
```

打开 `http://localhost:5173`。后端默认端口为 8010，健康检查入口是 `http://localhost:8010/api/health`。网页启动后，在 **01 — Input Source** 选择输入和角色，在 **02 — Output Target** 选择输出；网页顶部 Start / Stop 启停控制管线。

### 3. 无真实设备的仿真示例

先停止真实 EEG 桥，不连接真机输出。WSL 终端 C，从仓库根开始：

```bash
source .venv/bin/activate
python thymio_control/lsl_test/dummy_dual_streams.py --blink
```

在网页中设置第一行 `Role = Speed`、`Device = EEG`、`Brand = g.tec Headband`，第二行 `Role = Steering`、`Device = EEG`、`Brand = g.tec Hybrid Black`，Source 保持 LSL Stream；输出选择 **Thymio Simu**。逐台 Calibrate，校准完成后若仍在运行则先 Stop，再 Start，观察两路指标和仿真控制。

合成流与真实桥使用相同 source_id，不要同时运行。网页保存与校准会修改 YAML；复用真实实验电脑时先备份参数，结束后恢复，不能把合成流的校准结果用于真人。这个示例需要已安装 Gazebo 依赖，但不需要 Windows SDK、蓝牙或真实 Thymio。

### 4. 使用真实设备

完成[Windows 首次部署](docs/GUIDE_DEVELOPPEUR_cn.md#35-windows-launcher-首次部署)后，双击 Windows 的 `windows_launcher/launcher.bat` 打开 **System Control**，点 **Start System**，再连接设备：

- **Headband**：Connect 打开桥脚本；在 VS Code 选择现有 venv，点右上角 **▶** 运行。断开时需在脚本终端 **Ctrl+C**。
- **Hybrid Black**：总控页面直接 Connect / Disconnect，桥使用 UnicornPy。
- **Thymio**：Dongle 插入指定 USB 口，确认当前 BUSID `1-1` 已 Shared，再点 Connect attach 到 WSL。新 Dongle 的命令与状态解释见[共享检查](docs/GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)。

网页选择对应品牌和角色，输出 **Thymio**，逐台校准后 Start。详细操作与停止顺序见[操作手册](docs/MANUEL_OPERATEUR_cn.md)，常见问题见[排障手册](docs/GUIDE_DEBUG_cn.md)。

## 配置

| 文件 | 用途 |
|---|---|
| Windows 本地 `windows_launcher/config.json` | WSL 名称 / 路径、同步目标、解释器、服务与 USB 命令；同步时不覆盖此文件 |
| [launch_args.yaml](thymio_control/config/launch_args.yaml) | 真机 / 仿真、节点启用和驱动入口等启动设置 |
| [eeg_control_node.params.yaml](thymio_control/config/eeg_control_node.params.yaml) | 第一条 EEG 配置的指标、source_id、校准及运动参数 |
| [eeg_control_node.eeg2.params.yaml](thymio_control/config/eeg_control_node.eeg2.params.yaml) | 第二条 EEG 配置的独立参数，不固定对应某个品牌 |

日常通过网页配置。源码 YAML 由网页保存，ROS launch 默认读取安装目录配置；两者的一致性和校准写回见[配置说明](docs/GUIDE_DEVELOPPEUR_cn.md#53-三套配置边界)。仓库保存值可能来自某次运行，不应当作所有人的统一默认配置。

## 目录结构

```text
windows_launcher/       Windows 总控与设备生命周期
gtec_bridge/            Windows 设备 API → LSL 桥
thymio_control/
  launch/               ROS 启动入口
  scripts/              EEG 节点、双路融合器
  thymio_control/       adapter、processor、policy、校准、watchdog
  config/               YAML 参数与仿真资源
  test/                 控制模块测试
  lsl_test/             合成流、回放与离线测试
web_gui/
  backend/              FastAPI、RosBridge、配置与进程管理
  frontend/             React、Vite、ECharts
src/                    ROS Thymio / Aseba 等依赖
docs/                   操作、技术、开发与参考文档
experiment_data/        研究分析数据
```

## 测试

在 WSL 仓库根激活 `.venv` 后：

```bash
python -m pytest thymio_control/test -v
python -m pytest windows_launcher/tests -v
python -m pytest thymio_control/lsl_test -v
```

后端测试从 `web_gui/backend` 执行：

```bash
../../.venv/bin/python -m pytest app -v
```

前端构建从 `web_gui/frontend` 执行 `npm run build`。根目录默认 pytest 不包含后端；launcher 测试使用 fake executor，不要求真实 Windows 命令；缺少可选依赖或样本时的 skip 不等于通过。测试范围和设备验证入口见[开发者手册](docs/GUIDE_DEVELOPPEUR_cn.md#7-修改与测试)。

## 使用注意

- 机器人周围留出空地；暂停、排障和退出前先网页 Stop 并确认停车。关浏览器或刷新页面不是停车操作。
- 断流保护阈值不是实测整机停车保证；系统仍 Running 时，数据恢复可能恢复动作。浏览器 / 网络故障的实际停止行为需在所用系统上验证。
- 后端真实命令默认开启。dry-run 不阻断直接 Teleop；回环绑定与可选 token 不构成完整网络权限体系，勿直接作为互联网公开控制服务。
- 网页图表和指标不等于原始 EEG 记录，也不代表经过验证的注意力诊断。数据访问和保存按项目使用范围管理。

## 文档

| 文档 | 用途 |
|---|---|
| 本 README | 项目简介、架构、安装运行和开发入口 |
| [操作手册](docs/MANUEL_OPERATEUR_cn.md) | 已安装电脑上的日常使用 |
| [排障手册](docs/GUIDE_DEBUG_cn.md) | EEG、机器人、网页及 USB 的常见问题 |
| [技术档案](docs/DOSSIER_TECHNIQUE_cn.md) | 产品定义、需求、算法、接口与设计 |
| [开发者交接手册](docs/GUIDE_DEVELOPPEUR_cn.md#交接索引) | 交接索引、部署、代码导读、调试、测试、维护及恢复 |

模块专项说明见 [Windows launcher](windows_launcher/README.md) 与 [Web GUI](web_gui/README.md)。旧设计和研究资料保留在 `docs/`，不作为默认运行入口。

## 第三方组件

仓库包含 ROS Thymio / Aseba 等第三方源码，其许可证与声明保留在对应目录，例如 [ros-thymio 的 LICENSE](src/ros-thymio/LICENSE)。g.tec SDK 需单独准备，不随仓库 pip 清单提供；各组件的授权信息不应混作整个项目的一份统一许可。

项目的两份 Hybrid Black API licence 均由 Lucas 申请，相关授权信息由 Lucas 掌握。用户确认：第一份已在原项目电脑激活，第二份未激活；需要部署 / 迁移时，产品详情和许可条件向 Lucas 获取，见[授权交接说明](docs/GUIDE_DEVELOPPEUR_cn.md#24-hybrid-black-api-授权交接)。完整授权密钥不写入仓库。
