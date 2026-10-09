# TelekineRob-BCI

[操作手册](docs/MANUEL_OPERATEUR_cn.md) · [排障手册](docs/GUIDE_DEBUG_cn.md) · [技术档案](docs/DOSSIER_TECHNIQUE_cn.md) · [开发者交接手册](docs/GUIDE_DEVELOPPEUR_cn.md)

TelekineRob-BCI 是一个基于 EEG（脑电）的 Thymio 机器人控制平台。系统将 g.tec 设备采集的数据通过 LSL（Lab Streaming Layer，数据流传输库）传入 ROS2（机器人软件框架），计算频带功率与控制指标，再生成机器人运动命令；网页提供设备连接、校准、实时分析和控制界面。

项目面向 EEG 与机器人交互研究，支持单人单设备控制，以及两人分别负责速度和转向的协同控制。真实设备在 Windows 上连接，信号处理、ROS2 和网页服务运行于 WSL2。仓库还提供合成 EEG 工具及 Gazebo 仿真接入代码，用于无真实设备条件下的开发测试；完整仿真流程尚待验证。

在**已安装的项目电脑上日常使用**，直接看[操作手册](docs/MANUEL_OPERATEUR_cn.md)，遇到问题看[排障手册](docs/GUIDE_DEBUG_cn.md)，无需重新安装。开发者首次部署从下面的[环境要求](#环境要求)与[快速开始](#快速开始)进入；换电脑优先评估[整套 WSL 迁移](docs/GUIDE_DEVELOPPEUR_cn.md#93-推荐迁移方式导出与导入整套-wsl)，Windows 设备环境仍需单独配置。

## 主要功能

- **单 EEG 控制**：选择 Speed 控制前进，或 Steering 控制原地转向。
- **双 EEG 协同**：Headband 与 Hybrid Black 分别承担速度和转向，经融合器输出最终速度。
- **三种指标映射**：Alpha 频带功率、TBR（θ / β）、EI（β / (α + θ)）。
- **眨眼切换方向**：Steering 角色通过指标眨眼检测切换左 / 右方向。
- **逐设备校准**：收到有效数据后采集 30 秒；样本数满足要求时计算参考值并保存至各自参数文件。
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

Headband 和 Hybrid Black 在本项目中均使用电脑自带的集成蓝牙。Hybrid Black 虽附带 USB 蓝牙适配器，但在原项目电脑上使用时经常断连，改用集成蓝牙后更稳定，因此默认不使用附带适配器。更换电脑后需重新验证连接稳定性，详见[开发者手册第 3.8 节](docs/GUIDE_DEVELOPPEUR_cn.md#38-sdk-使用边界与连接方式)。Thymio 的 USB Dongle 与该蓝牙适配器不同，真机控制仍需要插入。

当前桥使用每种型号固定的 source_id，不支持把任意两台同型号 EEG 直接作为两路独立设备。

下一阶段主要需求是支持**两台同型号 g.tec EEG**，分别承担 Speed 与 Steering，并保留现有单设备和混合型号模式。这是尚未实现、尚未完成真机验证的开发目标，见[需求与验收条件](docs/DOSSIER_TECHNIQUE_cn.md#25-下一阶段主要需求同型号双-gtec)和[新开发人员实施路线](docs/GUIDE_DEVELOPPEUR_cn.md#75-首要开发任务同型号双-gtec-集成)。

## 系统架构

```text
Windows
  System Control：管理网页服务、设备桥与 USB 连接
  Headband / Hybrid Black → 设备桥 → LSL
                                      ↓
WSL2 / Ubuntu
  EEG 控制节点：RawLslAdapter → Welch PSD → 特征 → Policy → 运动命令
                                      ├─ 单路 → 最终速度
                                      └─ 双路部分速度 → fuser → 最终速度
  ROS 分析 → FastAPI / WebSocket → React 网页
  网页手动按钮 → RosBridge → 最终速度
                                      ↓
                            Thymio / Gazebo
```

真机最终话题为 `/cmd_vel`，仿真为 `/model/thymio/cmd_vel`。双路部分命令发布至 `/eeg_cmd_vel/speed`、`/eeg_cmd_vel/steering`；分析话题为 `/eeg_analysis` 或对应角色后缀话题。

更详细的算法、运动映射、配置和接口见[技术档案](docs/DOSSIER_TECHNIQUE_cn.md#3-系统设计)。

Headband 在 Windows 桥中调用 gpype 滤波；Hybrid Black 的这一步在 WSL 适配器中完成，两路随后进入频带功率计算。具体处理位置与限制见[滤波实现](docs/GUIDE_DEVELOPPEUR_cn.md#54-两类-eeg-的预滤波实现)。

## 环境要求

| 环境 | 要求 |
|---|---|
| 操作系统 | Windows + WSL2，Ubuntu 24.04 |
| ROS2 | Kilted；使用与系统 ROS 兼容的 Python，项目基线为 Python 3.12 |
| WSL Python 依赖 | 仓库根 `.venv` 与 [requirements.txt](requirements.txt) |
| 前端 | 支持仓库 Vite 5 的 Node.js / npm；依赖版本由 [package-lock.json](web_gui/frontend/package-lock.json)管理 |
| Windows 设备环境 | gpype / UnicornPy、pylsl 及对应 SDK / 驱动；Python 版本和位数需与 SDK 匹配 |
| Windows 工具 | Python、VS Code、usbipd-win（Windows USB 共享工具，命令为 `usbipd`） |
| ROS 工作区依赖 | 仓库中的 Thymio / Aseba 包；仿真还需 ROS Gazebo 相关包 |

g.tec SDK 不包含在根 pip 依赖清单中。完整系统依赖、SDK 准备、WSL 网络与首次 Windows 部署见[环境安装说明](docs/GUIDE_DEVELOPPEUR_cn.md#3-环境安装与重建)，厂商和依赖资料见[官方链接](docs/GUIDE_DEVELOPPEUR_cn.md#37-官方资料与依赖来源)。上述是项目环境基线，不是原电脑所有软件的实际版本记录；实值由现场接手人员在部署 / 迁移前核对。

## 快速开始

以下介绍首次部署和开发测试的基本流程。第 3 节是供开发人员验证的合成 EEG 与仿真入口，完整流程尚待验证；第 4 节是真实设备的使用方式，两者不是连续步骤。已安装项目电脑的日常使用，请直接参阅[操作手册](docs/MANUEL_OPERATEUR_cn.md)。

### 1. 获取源码并准备 WSL 工作区

以下命令在 **WSL Bash** 执行。先按[安装说明](docs/GUIDE_DEVELOPPEUR_cn.md#32-wsl-与-ros-前置条件)准备 ROS2、colcon 和工作区系统依赖；在选定父目录 clone，不覆盖已有仓库。

已有 `.venv` 或可运行系统时先核对环境，不重复创建；下面是新建工作区的流程。首次 ROS 构建包含 `src/` 内依赖包，不能仅构建 EEG 控制包。

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

安装后在仓库根、新的 WSL 终端中确认实际解释器和关键依赖：

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
python -c "import sys; print(sys.executable); import rclpy, pylsl, numpy, scipy, fastapi, yaml; print('WSL imports OK')"
```

导入失败先按[环境检查](docs/GUIDE_DEVELOPPEUR_cn.md#34-wsl-python-与前端环境)处理，不把 pip 安装成功当作 ROS / LSL 已可用。

### 2. 启动网页

以下两种方式任选一种，**不要同时使用两种方式启动网页服务**。

#### 方式一：通过 System Control 自动启动

适用于已完成[Windows launcher 首次部署](docs/GUIDE_DEVELOPPEUR_cn.md#35-windows-launcher-首次部署)的电脑。双击 Windows 本地的 `windows_launcher/launcher.bat` 打开总控页面，点击 **Start System**。总控会自动启动 WSL 中的后端和前端，并在主区域显示控制网页，无需手动在终端使用命令启动网页服务。

#### 方式二：用两个 WSL 终端手动启动

手动启动时，后端和前端需要分别运行。打开两个 WSL 终端窗口，两个终端都先进入项目根目录（`TelekineRob-BCI`，包含 `web_gui/` 的目录），再分别执行下面的命令。使用期间保持两个终端中的服务运行。

**启动后端（第一个 WSL 终端）：**

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
cd web_gui/backend
python -m app.main
```

**启动前端（第二个 WSL 终端）：**

```bash
cd web_gui/frontend
npm run dev -- --port 5173 --strictPort
```

两个服务启动后，在浏览器打开 `http://localhost:5173`。

#### 启动后的检查与操作

后端默认端口为 8010，健康检查入口是 `http://localhost:8010/api/health`；页面可访问不等于 EEG、ROS 或机器人已经可用。网页启动后，在 **01 — Input Source** 选择输入和角色，在 **02 — Output Target** 选择输出。

System Control 的 **Start System / Stop System** 管理网页服务与设备环境；控制网页顶部的 **Start / Stop** 启停机器人控制管线。两套按钮用途不同，退出时仍须先在控制网页 Stop 并确认停车。

### 3. 开发测试工具：合成 EEG 与仿真（完整流程待验证）

仓库确实包含[双路合成 EEG 脚本](thymio_control/lsl_test/dummy_dual_streams.py)和[ROS / Gazebo 仿真启动代码](thymio_control/launch/experiment_core.launch.py)。相关软件测试覆盖合成信号处理、融合、断流保护及滤波，但不验证“网页 → LSL / ROS2 控制 → Gazebo 机器人”的完整流程。因此，下文是接手开发人员的验证入口，不是已确认正常运行的操作流程，也不属于操作者日常使用步骤。

执行前须准备 ROS2、Gazebo 及工作区依赖并完成构建。完整流程的实际运行结果由开发人员验证和记录，详见[开发者手册的离线验证说明](docs/GUIDE_DEVELOPPEUR_cn.md#43-无设备离线验证)。

先停止真实 EEG 桥，不连接真机输出。另外打开一个 WSL 终端，先进入项目根目录，再运行模拟脑电数据生成脚本：

```bash
source .venv/bin/activate
python thymio_control/lsl_test/dummy_dual_streams.py --blink
```

完整流程的验证配置：在网页中设置第一行 `Role = Speed`、`Device = EEG`、`Brand = g.tec Headband`，第二行 `Role = Steering`、`Device = EEG`、`Brand = g.tec Hybrid Black`，Source 保持 LSL Stream；输出选择 **Thymio Simu**。逐台点 Calibrate（无需先点顶部 Start），确认第一路校准成功后再校准第二路。全部完成后若仍在运行则先 Stop，再 Start，检查两路分析数据是否持续更新、仿真机器人是否响应控制，并记录启动错误或异常；不能只凭网页显示 Running 判断验证成功。

合成流与真实桥使用相同 source_id，不要同时运行。网页保存与校准会修改 YAML；复用真实实验电脑时先备份参数，结束后恢复，不能把合成流的校准结果用于真人。这条开发测试路径不需要 Windows SDK、蓝牙或真实 Thymio，用于检查模拟输入下的数据流与控制链路，不复现真实设备的完整滤波、蓝牙和 USB 链路。结束时先网页 Stop，再在运行模拟脑电脚本的终端按 Ctrl+C 停止合成流。

### 4. 使用真实设备

按[第 2 节的方式一](#方式一通过-system-control-自动启动)通过 Windows 总控启动系统后，再连接设备；已经启动时无需重复启动：

- **Headband**：Connect 打开桥脚本；在 VS Code 选择现有 venv，点右上角 **▶** 运行。断开时需在脚本终端 **Ctrl+C**。
- **Hybrid Black**：总控页面直接 Connect / Disconnect，桥使用 UnicornPy。
- **Thymio**：Dongle 插入指定 USB 口，确认当前 BUSID `1-1` 已 "Shared"，再点 Connect 将该 USB 设备接入 WSL，状态变为 "Attached"。"Shared" 是 Windows 允许将设备共享给 Linux，"Attached" 表示已经接入；新 Dongle 的命令与检查步骤见[共享检查](docs/GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)。

设备充好电，电脑连接充电器，以降低蓝牙省电相关断连风险。网页选择对应品牌和角色，输出 **Thymio**，逐台校准。

点击 Calibrate 会启动校准所需的控制管线。双 EEG 模式下，每台校准结束后，网页会自动发出 Stop 请求；单 EEG 模式下可能继续运行。建议校准成功后，若仍在运行则先 Stop，确认机器人已停止，再 Start 开始正式控制，以区分校准与正式运行，并重新加载最新校准参考。这是建议流程，不是单设备校准参数生效的硬性要求。

除自动校准外，也可在控制停止时，手动调整各设备的 min／max 控制映射参考值，修改后点击 Start 使用新值。这些值不是原始脑电信号的最小值和最大值。通常先自动校准，需要微调时再手动调整。

校准结束到停止完成之间可能短暂输出运动命令。校准前应将 Thymio 放在平坦、安全的位置，周围不要放置障碍物，并远离桌边或台阶。详细操作与停止顺序见[操作手册](docs/MANUEL_OPERATEUR_cn.md)，常见问题见[排障手册](docs/GUIDE_DEBUG_cn.md)。

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
```

## 测试

在 WSL 仓库根，已安装依赖并完成工作区构建后：

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
python -m pytest thymio_control/test -v
python -m pytest windows_launcher/tests -v
python -m pytest thymio_control/lsl_test -v
```

后端测试在另一个已加载上述 ROS 环境的终端中，从仓库根开始：

```bash
cd web_gui/backend
../../.venv/bin/python -m pytest app -v
```

前端构建从 `web_gui/frontend` 执行 `npm run build`。根目录默认 pytest 不包含后端；launcher 测试使用 fake executor，不要求真实 Windows 命令；缺少可选依赖或样本时的 skip 不等于通过。测试范围和设备验证入口见[开发者手册](docs/GUIDE_DEVELOPPEUR_cn.md#7-修改与测试)。

## 使用注意

- 机器人周围留出空地；暂停、排障和退出前先网页 Stop 并确认停车。关浏览器或刷新页面不是停车操作。
- 断流保护阈值不是实测整机停车保证；系统仍 Running 时，数据恢复可能恢复动作。浏览器 / 网络故障的实际停止行为需在所用系统上验证。
- 后端真实命令默认开启。dry-run 不阻断直接 Teleop；回环绑定与可选 token 不构成完整网络权限体系，勿直接作为互联网公开控制服务。
- 网页图表和指标不等于原始 EEG 记录，也不代表经过验证的注意力诊断。数据访问和保存按项目使用范围管理。
- 网页第 4 部分仅供开发人员收集研究验证数据，用于评估和验证本系统，不是日常 EEG / Thymio 控制的必要步骤。后续可考虑在面向使用者的界面中屏蔽，或在不再需要开发验证时删除；当前功能代码仍保留，并未在本次修改中禁用。

仓库不再包含历史研究数据。若使用仍保留的数据收集功能，后端仍会生成新的数据目录；默认的 `experiment_data/` 整个目录已加入 Git 忽略规则，不作为源码交付内容。

## 文档

| 文档 | 用途 |
|---|---|
| 本 README | 项目简介、架构、安装运行和开发入口 |
| [操作手册](docs/MANUEL_OPERATEUR_cn.md) | 已安装电脑上的日常使用 |
| [排障手册](docs/GUIDE_DEBUG_cn.md) | EEG、机器人、网页及 USB 的常见问题 |
| [技术档案](docs/DOSSIER_TECHNIQUE_cn.md) | 产品定义、需求、算法、接口与设计 |
| [开发者交接手册](docs/GUIDE_DEVELOPPEUR_cn.md#交接索引) | 交接索引、部署、代码导读、调试、测试、维护及恢复 |

中文正式交接文档以上面五类为准。模块专项说明见 [Windows launcher](windows_launcher/README.md) 与 [Web GUI](web_gui/README.md)，仅作补充参考；旧设计和研究资料保留在 `docs/`，不作为默认运行入口或另一套正式安装指南。

## 第三方组件

仓库包含 ROS Thymio / Aseba 等第三方源码，其许可证与声明保留在对应目录，例如 [ros-thymio 的 LICENSE](src/ros-thymio/LICENSE)。g.tec SDK 需单独准备，不随仓库 pip 清单提供；各组件的授权信息不应混作整个项目的一份统一许可。

项目的两份 Hybrid Black API licence 均由 Lucas 申请，相关授权信息由 Lucas 掌握。用户确认：第一份已在原项目电脑激活，第二份未激活；需要部署 / 迁移时，产品详情和许可条件向 Lucas 获取，见[授权交接说明](docs/GUIDE_DEVELOPPEUR_cn.md#24-hybrid-black-api-授权交接)。完整授权密钥不写入仓库。
