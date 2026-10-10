# TelekineRob-BCI 开发手册（中文版）

[返回中文项目总览](README_cn.md) · [法语版](../GUIDE_DEVELOPPEUR.md)

> 面向项目开发人员，说明环境搭建、代码定位、开发调试、修改与测试，以及更新、备份和恢复。

## 项目文档导航

本手册说明如何开发和维护系统；产品定义、需求、算法和接口以技术档案为准，日常操作与常见问题分别查操作手册、排障手册。

### 五类正式文档

| 文档 | 开发时的参考用途 |
|---|---|
| [项目 README（中文版）](README_cn.md) | 项目概览、环境要求与快速开始 |
| [技术档案（中文版）](DOSSIER_TECHNIQUE_cn.md) | 产品定义、需求、设计、算法、接口与验收依据 |
| [操作手册（中文版）](MANUEL_OPERATEUR_cn.md) | 复现现有用户操作流程，检查修改是否影响日常使用 |
| [排障手册（中文版）](GUIDE_DEBUG_cn.md) | 排除常见硬件与连接问题，再进入代码诊断 |
| [开发手册（本文件）](#1-开发上手路线) | 环境搭建、代码导读、开发调试、测试、更新、备份与恢复 |

### 建议阅读顺序

- **开发人员**：先读[项目 README](README_cn.md)了解系统，再按[开发上手路线](#1-开发上手路线)运行现有系统；结合[技术档案](DOSSIER_TECHNIQUE_cn.md)与本手册理解和修改代码。
- **下一阶段主要开发任务**：[同型号双 g.tec 集成](#75-首要开发任务同型号双-gtec-集成)。该节说明当前代码限制、实施步骤和回归场景，不是已实现功能。
- **授权资料入口**：[Hybrid Black API 授权](#hybrid-black-api-授权)。
- **部署与维护入口**：[官方资料](#37-官方资料与依赖来源) · [SDK 使用边界](#38-sdk-使用边界与连接方式) · [滤波实现](#54-两类-eeg-的预滤波实现) · [第三方源码修改](#55-第三方源码与本项目修改) · [整套 WSL 迁移](#93-推荐迁移方式导出与导入整套-wsl)。

系统验证范围与验收要求见[技术档案第 4 章](DOSSIER_TECHNIQUE_cn.md#4-验收与验证状态)，已知限制见[第 5.1 节](DOSSIER_TECHNIQUE_cn.md#51-当前限制及优先验证事项)。

开发验证的数据格式说明另见[专题参考资料](../reference/DONNEES_EXPERIMENTALES.md)，实际字段以代码为准。[归档目录](../archived/)保留旧指南、设计历史及研究计划，不作为现行开发步骤或需求清单。

## 阅读导航

- [1. 开发上手路线](#1-开发上手路线)：先运行现有系统，再理解和修改。
- [2. 开发环境与本地配置](#2-开发环境与本地配置)：环境基线、版本检查、路径与配置。
- [3. 环境安装与重建](#3-环境安装与重建)：Windows 与 WSL 分开准备。
- [4. 启动与开发调试](#4-启动与开发调试)：正常启动、分开启动网页、离线双流。
- [5. 代码与配置导读](#5-代码与配置导读)：修改应该落在哪一层。
- [6. 分层排障与日志](#6-分层排障与日志)：从设备逐层查到机器人。
- [7. 修改与测试](#7-修改与测试)：现有测试、验证范围、安全边界及[同型号双设备首要任务](#75-首要开发任务同型号双-gtec-集成)。
- [8. 更新与发布](#8-更新与发布)：Git、构建、Windows 同步的不同边界。
- [9. 备份与恢复](#9-备份与恢复)：配置、依赖与整套 WSL 环境的备份、恢复和迁移。

命令块标明执行环境。Windows PowerShell 命令不能直接放进 WSL Bash；`<…>` 是必须替换的占位符，不要原样执行。安装、校准、网页保存配置、更新及恢复都会改变状态，先停止控制并备份相关配置。

## 1. 开发上手路线

首次参与开发时，按以下顺序熟悉系统，不必先读完所有历史文档。

1. 按[环境与配置检查](#2-开发环境与本地配置)确认实际解释器、路径、硬件和指定 USB 口，备份现有配置；设备 SDK 与授权准备见[第 3 节](#3-环境安装与重建)。
2. 按[操作手册](MANUEL_OPERATEUR_cn.md)完成一次启动、Keyboard 单独测试 Thymio、EEG 连接、校准、运行和停止；遇到常见问题先按[用户排障手册](GUIDE_DEBUG_cn.md)。
3. 阅读[技术档案的系统设计](DOSSIER_TECHNIQUE_cn.md#3-系统设计)，沿[代码导读](#5-代码与配置导读)追踪一个设备从 LSL 到 `/cmd_vel` 的路径。
4. 在开发环境运行[分层测试](#7-修改与测试)，理解纯逻辑、模拟服务和真机验证的区别。
5. 在开发副本完成一个范围明确的小修改，补充相关验证，再按[更新流程](#8-更新与发布)部署。同型号双设备按[实施路线](#75-首要开发任务同型号双-gtec-集成)先验证 SDK，不直接在现有运行电脑上试错。
6. 熟悉[备份与恢复](#9-备份与恢复)，在独立环境验证恢复流程，避免覆盖正在使用的系统。

开发前应认识的三个区别：

- **System Control 与实验控制网页不同**：前者管理系统、设备桥和 USB；后者选择角色 / 输出、校准、Start / Stop 和 Teleop。
- **连接与控制不同**：EEG 绿色表示探针收到新鲜样本；图表要在校准或控制管线运行时才更新。Thymio 绿色主要表示 `/dev/ttyACM0` 可见，不证明机器人已经响应。
- **代码与运行配置不同**：网页保存、校准会改 YAML；Windows 本地 `config.json` 不随同步覆盖。开发测试前备份实际配置，结束后不要把测试参数留在运行环境中。

## 2. 开发环境与本地配置

### 2.1 环境基线与检查

以下是项目环境基线及检查要点，不是某台电脑的完整安装记录。部署、迁移或升级前，核对实际版本与路径，不将模板直接当作本地配置。

| 项目 | 环境基线 / 当前入口 | 检查要点 |
|---|---|---|
| 源码与分支 | [项目仓库](https://github.com/nicrain/TelekineRob-BCI)，部署入口为 `main` | 用 Git 检查实际分支、commit 和本地修改 |
| Windows / WSL | Windows + WSL2 | 检查 WSL 版本、注册发行版名与网络模式 |
| Ubuntu / ROS | Ubuntu 24.04 / ROS2 Kilted | 检查系统版本和 `ROS_DISTRO`；不要混用其他 ROS 发行版 |
| WSL Python | Python 3.12；仓库根 `.venv` | 检查解释器路径与 ROS Python 兼容性，执行[导入检查](#34-wsl-python-与前端环境) |
| Windows Python | launcher 模板与两台设备的 `python_cmd` 为 `python` | 分别检查 launcher、桥、探针和 VS Code 实际解释器；SDK 二进制须匹配版本与位数 |
| SDK | Headband 用 `gpype`；Hybrid Black 用 `UnicornPy` | [第 3.1 节](#31-windows-前置条件)查询版本，[第 3.8 节](#38-sdk-使用边界与连接方式)说明安装与授权边界 |
| Node / npm | 前端使用 Vite 5、React 18；有 npm lockfile | 检查现有版本，按 lockfile 安装，不无条件升级 |
| USB 与机器人 | usbipd-win；BUSID `1-1`；`/dev/ttyACM0` | 检查指定 USB 口、Shared / Attached 状态与串口权限 |
| Gazebo / Aseba | 仿真用 ROS Gazebo 包；真机用仓库内 ROS Thymio / Aseba 驱动 | 核对构建依赖及实际使用的驱动版本，保留[第三方修改](#55-第三方源码与本项目修改) |
| 网络与数据 | [网络设置](#36-网络与访问范围)、[日志](#64-日志位置与故障记录)、[备份](#9-备份与恢复) | 确认实际访问路径、日志位置及数据保存范围 |

以下命令用于只读检查环境。分享输出前去除不必要的用户名、设备名或内网地址；账号凭据与 token 不写进公开仓库。

Windows PowerShell：

```powershell
wsl --version
wsl -l -v
usbipd --version
Get-Command python, pythonw, code, usbipd
python --version
```

WSL Bash，在实际仓库根目录执行：

```bash
git status --short --branch
git rev-parse HEAD
lsb_release -ds
python3 --version
.venv/bin/python --version
node --version
npm --version
source /opt/ros/kilted/setup.bash
printenv ROS_DISTRO
```

Windows 的 `python --version` 仅代表当前终端默认解释器；还要用配置中每一个实际 `python_cmd` 检查。Headband 在 VS Code 选中的解释器也要单独核对。

### 2.2 路径与配置模板

| 项目 | 仓库模板值 / 当前入口 | 必须确认的内容 |
|---|---|---|
| WSL 发行版名 | `Ubuntu` | 是注册名称，不是系统版本；以 `wsl -l -v` 为准 |
| WSL 仓库 | `/home/robot/TelekineRob-BCI` | 是模板路径，不证明目标电脑就在这里 |
| Windows 同步目标 | `C:\Users\Robot\Desktop\gpype_test\TelekineRob-BCI` | 目标电脑实际 Windows 项目目录 |
| WSL 同步源 | `\\wsl$\Ubuntu\home\robot\TelekineRob-BCI` | 发行版名、用户目录与仓库路径一致 |
| Windows 本地配置 | Windows 项目目录下 `windows_launcher/config.json` | 备份实际文件，不拿仓库模板直接覆盖 |
| 用户启动入口 | Windows 项目目录下 `windows_launcher/launcher.bat` | 实际快捷方式指向哪个副本 |
| ROS 运行参数 | `thymio_control/config/` 中三个 YAML | 已确认角色、设备、指标、速度与校准值 |
| 服务端口 | launcher 8020；后端 8010；前端 5173 | 占用情况、实际 URL 与防火墙规则 |

`config.json` 的字段和占位符解析见[launcher 配置说明](../../windows_launcher/README.md)。手改 JSON 时注意 Windows 路径中的反斜杠需要转义。该文件包含可执行命令，只允许可信维护者修改。

### 2.3 硬件部署约定

- 原项目电脑的 Headband 与 Hybrid Black 默认使用集成蓝牙；换电脑或增加设备时须重新验证连接稳定性。选择依据见[第 3.8 节](#38-sdk-使用边界与连接方式)。
- Thymio Dongle 使用指定 USB 口，当前配置的 BUSID 为 `1-1`。迁移后若确实无法保持该编号，开发者须统一核对并更新连接、断开、设备检查命令及相关用户手册。

设备准备、连接和角色选择见[操作手册](MANUEL_OPERATEUR_cn.md)；蓝牙异常、配对和新 Dongle 共享问题见[排障手册](GUIDE_DEBUG_cn.md)。

## 3. 环境安装与重建

本节供新电脑或恢复环境使用。已有可运行电脑先做[备份](#9-备份与恢复)，不要为了“统一环境”直接重装或升级。系统安装参考官方文档，项目特定命令以下文及实际配置为准。

### 3.1 Windows 前置条件

1. 准备 WSL2 与 Ubuntu 24.04；登记注册发行版名。不要因为新安装默认版本变化，就替换项目已验证的 Ubuntu / ROS 组合。
2. 安装 usbipd-win 并检查命令可用。USB 共享不是 WSL 内置能力；安装及权限要求参考 [Microsoft USB 连接文档](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)。官方文档的 BUSID 是示例，本项目仍使用 `1-1`。
3. 准备 Python / Pythonw 与 VS Code，确认 `code` 命令可用。按 g.tec 随设备提供的 SDK 资料恢复 `gpype`、`UnicornPy` 和所需驱动 / 授权；Windows Python 版本、位数及 `.pyd` 兼容性须匹配 SDK。资料入口见[第 3.7 节](#37-官方资料与依赖来源)，API 使用及连接边界见[第 3.8 节](#38-sdk-使用边界与连接方式)。
4. 分别检查桥和探针使用的 Python。根 `requirements.txt` 不包含两个厂商 SDK，也不是 Windows 两个桥的完整安装清单。
5. 先用内置蓝牙和已配对设备复现现有桥；不要同时运行同一设备的多个桥，也不要自动替换 SDK 版本来试错。

Windows PowerShell，下面的命令以当前 `python` 确实是该设备解释器为前提；否则替换为已登记路径：

```powershell
python -c "import sys; print(sys.executable); print(sys.version)"
python -c "import pylsl; import gpype; print('Headband imports OK')"
python -c "import pylsl; import numpy; import UnicornPy; print('Hybrid imports OK')"
```

两个设备可以使用不同环境，导入检查也应分别执行。路径含空格时，PowerShell 使用 `& "C:\实际路径\python.exe" ...`；不要把这个 PowerShell 写法直接填入 launcher 的 `python_cmd`，其执行规则见[配置实现](../../windows_launcher/config.py)与[命令实现](../../windows_launcher/commands.py)。

在 Headband 桥实际使用的 Python 环境中，查询已安装的 g.Pype 版本（Windows PowerShell）：

```powershell
python -m pip show gpype
```

在 Hybrid 桥实际使用的 Python 环境中，查询解释器路径与 API 版本（Windows PowerShell，不连接 EEG）：

```powershell
python -c "import sys, UnicornPy; print(sys.executable); print(UnicornPy.GetApiVersion())"
```

分别登记 Unicorn Suite 与 UnicornPy API 版本，不将软件版本当作授权产品信息。`GetApiVersion()` 只查询 API 版本，不能证明授权状态或双设备并发许可；授权核对见[第 3.8 节](#hybrid-black-api-授权)。导入失败先诊断环境，不停用授权来试错。

### 3.2 WSL 与 ROS 前置条件

项目使用 Ubuntu 24.04 / ROS2 Kilted；Ubuntu 对应关系及安装入口见 [ROS2 Kilted 官方安装说明](https://docs.ros.org/en/kilted/Installation/Ubuntu-Install-Debs.html)，页面不可用时参考同一官方仓库的 [Kilted 安装源文档](https://github.com/ros2/ros2_documentation/blob/kilted/source/Installation/Ubuntu-Install-Debs.rst)。按该版本文档设置软件源与开发工具，不混用其他 ROS 发行版的安装命令。

WSL 内确认 systemd，配置方法参考 [Microsoft systemd 文档](https://learn.microsoft.com/en-us/windows/wsl/systemd)。先检查是否已启用；确实需要时再编辑 `/etc/wsl.conf`，保留其他已有配置：

```ini
[boot]
systemd=true
```

应用 WSL 启动配置需要重启相应环境，先保存并停止其中其他任务。launcher 会检查 `systemctl is-system-running`，也有共享路径可访问的就绪回退；`degraded` 可能被视为可继续启动，但仍应查明失败服务，不能把它当成全部正常。

WSL Bash：

```bash
systemctl is-system-running
source /opt/ros/kilted/setup.bash
command -v ros2
command -v colcon
command -v rosdep
```

ROS 依赖由包清单声明，但仓库内旧版第三方包可能声明不完整。例如 `asebaros` 的 CMake 要求 LibXml2，不能因为 rosdep 没报错就认定编译依赖齐全。缺失依赖应依据具体错误及包的 CMake / package.xml 处理，并记录实际安装项；不要通过跳过整个驱动包来伪装构建成功。

### 3.3 获取源码与首次构建

新安装时在选定的 WSL 父目录执行以下命令；已有仓库不再 clone 到同一个目录。用户名不必叫 `robot`，之后将实际路径填入 Windows 配置。

```bash
git clone --branch main https://github.com/nicrain/TelekineRob-BCI.git TelekineRob-BCI
cd TelekineRob-BCI
git rev-parse HEAD
source /opt/ros/kilted/setup.bash
```

按 ROS 开发环境说明准备 rosdep；只在尚未初始化的系统执行 `sudo rosdep init`。更新索引后，可先检查再安装仓库声明的依赖（WSL Bash，仓库根）：

```bash
rosdep update
rosdep check --from-paths src thymio_control --ignore-src --rosdistro kilted
rosdep install --from-paths src thymio_control --ignore-src --rosdistro kilted -y
colcon build --symlink-install
source install/setup.bash
ros2 pkg prefix thymio_control
ros2 pkg executables thymio_control
```

首次构建包含 `src/` 的 Thymio / Aseba 等依赖，不仅是 `thymio_control`。后两条应能找到本工作区的包及 `eeg_control_node.py`、`cmd_vel_fuser.py`。若构建失败，保留完整错误和构建日志，解决依赖后重试。

构建用系统 ROS 对应的 Python，不让其他版本的 Python / Conda 环境抢占解释器。

### 3.4 WSL Python 与前端环境

WSL Bash，在仓库根创建项目环境。以下用于从源码重新安装：已有 `.venv` 时先核对，不覆盖；重建时重新创建，不单独跨电脑复制 venv。若采用[整套 WSL 导入](#93-推荐迁移方式导出与导入整套-wsl)，其中 Linux 环境可以随镜像保留，先验证，不要求无条件删除 / 重建：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
source /opt/ros/kilted/setup.bash
source install/setup.bash
python -c "import sys; print(sys.executable); import rclpy, pylsl, numpy, scipy, fastapi, yaml; print('WSL imports OK')"
```

预期解释器来自仓库 `.venv`，且导入无异常。ROS 的 `rclpy` 由 ROS 环境提供，不通过随意 `pip install rclpy` 补救；失败时检查 ROS 是否 source、Python ABI 是否匹配及工作区构建环境。`pylsl` 若报告 liblsl 缺失，按报错检查本机库加载，不能仅凭 pip 安装成功判定 LSL 可用。

前端在 WSL 安装，使用已经验证的 Node / npm 与仓库 lockfile：

```bash
cd web_gui/frontend
npm ci
npm run build
```

安装成功及构建成功只验证依赖 / 构建，不证明网页、WebSocket、Gazebo 或机器人正常。新增依赖或升级时应单独审查并提交 lockfile，而不是每次部署重新生成它。

### 3.5 Windows launcher 首次部署

1. 将 WSL 仓库的 `windows_launcher` 复制到选定的 Windows 本地项目目录，再创建需要的启动快捷方式。首次可以用资源管理器访问 `\\wsl$\<发行版>\<仓库路径>` 复制。
2. 编辑 Windows 那份 `windows_launcher/config.json`，同步源、目标、WSL 仓库、发行版名与所有嵌入命令中的发行版名必须对应。检查 `devices.thymio.attach_cmd` 和 `verify_cmd`，不是只改 `wsl.distro`。
3. 为两个设备分别配置可用的 `python_cmd`；Headband 的 VS Code 环境和探针解释器都要有对应依赖。`open_in_ide` 不会替操作者选择 Python 环境。
4. 检查 `web.backend_cmd` 的 ROS、install 和 venv 路径，及 `frontend_cmd` 的 npm 可用性。
5. 配置 Thymio 连接前，确认指定口的 Dongle（BUSID `1-1`）已允许共享；新 Dongle 的首次共享及状态检查见[排障手册](GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)。
6. 双击 launcher，按[操作手册](MANUEL_OPERATEUR_cn.md)检查启动与设备连接；备份实际配置。后续分层检查见[第 6 节](#6-分层排障与日志)。

Thymio 的 `attach_cmd` 将 BUSID `1-1` 的 USB 设备从 Shared 接入 WSL（Attached），`verify_cmd` 检查 `/dev/ttyACM0`。修改端口或发行版配置时，两条命令须一起核对。

每次 Start System 同步 WSL 的 `windows_launcher/`（排除 `config.json`）与 `gtec_bridge/` 到 Windows。它不安装 SDK、不安装依赖、不构建 ROS、不执行 Git pull，也不替换机器本地配置。

### 3.6 网络与访问范围

先确保同一电脑的本地访问能工作，再考虑局域网。仓库默认 launcher 监听 `127.0.0.1:8020`，后端监听 `127.0.0.1:8010`，Vite 前端监听 `0.0.0.0:5173` 并代理后端的 `/api`、`/ws`。

launcher 会尝试更新 Windows 的 5173 端口转发；失败并不必然阻止 System State 进入 Running。先检查实际 WSL 网络模式、端口转发和防火墙规则，不要把一台电脑的网络处理办法推广为所有 WSL 配置。

| 后端变量 | 当前默认 / 模板 | 注意事项 |
|---|---|---|
| `WEB_GUI_HOST` / `WEB_GUI_PORT` | `127.0.0.1` / `8010` | 回环绑定仍可能经 Vite 代理被局域网访问 |
| `WEB_GUI_FRONTEND_ORIGIN` | 后端默认本地 origin；launcher 模板设为 `*` | `*` 放宽 origin 校验，不是授权机制 |
| `WEB_GUI_CONTROL_TOKEN` | 默认空 | 部分控制接口支持 token，但不构成全站权限体系 |
| `WEB_GUI_ALLOW_REAL_COMMANDS` | 默认 `true` | 设 `false` 限制进程启动 / 清理；不阻断直接 Teleop 发布 |

仅在经过确认的可信网络范围使用。不能因为后端只监听 loopback、设置了 token 或开启 dry-run，就认为所有控制 / 配置接口受到完整保护。具体代码边界和代理风险见[技术档案的网络边界](DOSSIER_TECHNIQUE_cn.md#312-网络命令与数据边界)，不要直接将当前系统作为互联网公开控制服务部署。

### 3.7 官方资料与依赖来源

以下为厂商 / 维护者资料入口，用于安装、API 查询和维护。在线页面会更新，页面版本不等于本机已安装版本；先检查现有可运行环境，再按对应版本恢复，不照着最新示例直接升级。

| 设备 / 组件 | 官方或上游入口 | 本项目如何使用 |
|---|---|---|
| Headband | [BCI Core-4 产品](https://www.gtec.at/product/unicorn-bci-core-4-headband/)、[g.Pype GitHub](https://github.com/gtec-medical-engineering/gpype)、[文档首页](https://gpype.gtec.at/index.html)、[培训与示例](https://gpype.gtec.at/content/2_gpype_training/index.html)、[SDK 参考](https://gpype.gtec.at/content/7_sdk_reference/index.html) | 查询 SDK 安装 / 采集 / 滤波接口；项目连接用 gpype 桥，不直接把官方展示程序当作本项目入口 |
| g.Pype 使用条件 | [官方 FAQ](https://gpype.gtec.at/content/5_faq/index.html)、[GNCL 许可文本](https://github.com/gtec-medical-engineering/gpype/blob/main/LICENSE-GNCL.txt) | 核对 IDE 内个人 / 教学使用与 Runtime 部署的边界；项目保留 VS Code 手动流程 |
| Hybrid Black | [产品](https://www.gtec.at/product/unicorn-hybrid-black-bci-platform/)、[Windows APIs GitHub](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs)、[Python API 安装与使用](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api.md)、[Python API 参考](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api-reference.md) | 查询 UnicornPy 库路径、Python / 二进制兼容性、设备发现、序列号连接与采集；桥只向 LSL 转发 8 个 EEG 通道 |
| Unicorn Suite Hybrid Black | [安装、蓝牙、授权和配对手册](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornSuite.md)、[维护者安装包发布页](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/releases) | Windows 驱动 / API 准备与 licence 管理；用 Lucas 的实际授权信息，不把任意 Suite 应用授权当作 Python API 授权 |
| Thymio | [官网（法语）](https://www.thymio.org/fr/)、[Thymio Suite 下载](https://www.thymio.org/fr/telecharger-thymio-suite/)、[编程与使用资料](https://www.thymio.org/fr/produits/programmer-avec-thymio-suite/)、[无线 Dongle 配对](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/) | 查设备维护、厂商工具安装与必要时的配对；本项目日常动作由 ROS 驱动发送，不要求在 Thymio Suite 内启动控制 |
| ROS2 Kilted | [版本文档](https://docs.ros.org/en/kilted/)、[Ubuntu 安装](https://docs.ros.org/en/kilted/Installation/Ubuntu-Install-Debs.html)、[同一官方安装文档源码](https://github.com/ros2/ros2_documentation/blob/kilted/source/Installation/Ubuntu-Install-Debs.rst) | Ubuntu 24.04 / ROS2 基础安装、colcon 与 ROS 调试；按项目指定发行版准备环境 |
| ROS-Aseba / asebaros | [jeguzzi/ros-aseba](https://github.com/jeguzzi/ros-aseba)、[维护者文档](https://jeguzzi.github.io/ros-aseba/) | `asebaros` 提供通用 ROS ↔ Aseba 网络接口；本项目在 `src/ros-aseba` 保留源码及嵌套 Aseba / Dashel 依赖 |
| ROS-Thymio | [jeguzzi/ros-thymio](https://github.com/jeguzzi/ros-thymio)、[同一维护者文档](https://jeguzzi.github.io/ros-aseba/) | 在 asebaros 之上提供 Thymio 驱动、消息和模型；本项目使用 `src/ros-thymio` 中的 ROS 包，通过 colcon 构建，不另行 pip 安装 |
| Windows / WSL / USB | [WSL 命令](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)、[导入发行版](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro)、[USB 接入 WSL](https://learn.microsoft.com/en-us/windows/wsl/connect-usb) | 导出 / 导入 Linux 环境及 usbipd 操作；本项目 BUSID 和路径约定以实际配置与手册为准 |

ROS-Aseba / ROS-Thymio 的上游分支及旧教程含 ROS1 历史内容，不是 Thymio 厂商直接发布的本项目驱动。安装优先使用本项目跟踪的源码和固定版本；来源与修改见[第 5.5 节](#55-第三方源码与本项目修改)。官方资料用于了解接口，不能替代本项目的配置、构建、停止和验收步骤。

### 3.8 SDK 使用边界与连接方式

#### Headband / g.Pype

[官方 FAQ](https://gpype.gtec.at/content/5_faq/index.html)说明个人及教学用途可在 IDE 内免费使用，商业部署需要 g.Pype Runtime；具体遵守对应版本的[GNCL 条款](https://github.com/gtec-medical-engineering/gpype/blob/main/LICENSE-GNCL.txt)。本项目保留 IDE 人工运行方式，变更部署方式前须核对适用许可。

升级 SDK 前核对现有桥使用的接口和类名，不直接照新文档替换。版本查询见[第 3.1 节](#31-windows-前置条件)；现有 venv 路径及选择步骤只在[排障手册](GUIDE_DEBUG_cn.md#在-vs-code-中选择-venv)维护。

#### Hybrid Black / UnicornPy

按对应版本的 Suite / DevTools 资料准备驱动和 Unicorn Python API，加载方式参考[官方安装说明](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api.md)。确认 `UnicornPy.pyd` 的库目录可被实际解释器加载（官方说明使用 `PYTHONPATH`），Python 版本、位数及本机库依赖匹配；仅安装仓库根依赖清单不能完成部署。导入检查和版本查询见[第 3.1 节](#31-windows-前置条件)。

连接与进程管理设计见[技术档案第 3.4 节](DOSSIER_TECHNIQUE_cn.md#34-设备连接设计)；同型号双设备的修改入口见[第 7.5.2 节](#752-当前代码的限制与修改入口)。

##### Hybrid Black API 授权

项目有两份 Hybrid Black API licence，均由 Lucas 申请，授权资料由他掌握；第一份已在原项目 Windows 电脑激活，**第二份未激活**。部署或迁移时向 Lucas 获取对应的产品信息、适用条款与凭据。不从“两份授权”推导“一台 EEG 必须一份”或已经允许同机双设备并发。

在 **Unicorn Suite Hybrid Black → Licenses** 中查看授权状态；激活与停用按对应版本的[官方授权说明](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornSuite.md#licensing)操作。只核对状态时不要停用现有授权；迁移前与 Lucas 确认许可条件和停机安排。完整 licence key、购买邮件与账号信息仅经受控渠道交接，不放入 Git、日志或公开截图。

#### 蓝牙选择

原电脑使用集成蓝牙是基于现场连接稳定性的选择，与[厂商手册](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornSuite.md#bluetooth-configuration)推荐随设备提供的适配器不同。换电脑或增加设备时须重新验证，不假定所有集成蓝牙都适用。

## 4. 启动与开发调试

### 4.1 正常启动与停止

正常启动、设备连接、校准、运行及收尾，按[操作手册](MANUEL_OPERATEUR_cn.md)执行。开发调试时注意以下进程管理边界：

- 已有网页服务或控制管线运行时，不要再从终端启动另一套相同服务／管线。
- VS Code 启动的 Headband 脚本不由 launcher 管理，仍需人工中断。
- Stop System 默认终止整个配置的 WSL 发行版；其中其他任务应先保存。
- Restart Web 前先停止控制并确认停车；重启网页不代替 Stop。

### 4.2 分开启动前后端

只在 launcher 没有管理这些服务时使用。以下后端命令会启动实际服务，真实命令默认开启；先确保真机未处于控制状态。

后端与前端需要分别在两个终端中启动。两个终端都先进入项目根目录，再执行各自命令。

#### 启动后端（WSL Bash 终端 A）

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
cd web_gui/backend
python -m app.main
```

#### 启动前端（WSL Bash 终端 B）

```bash
cd web_gui/frontend
npm run dev -- --port 5173 --strictPort
```

前端访问 `http://localhost:5173`。后端健康入口是 `http://localhost:8010/api/health`，不是 `/health`。`subscriber_ready` 为真仍需检查 `subscriber_error`；服务响应、ROS 就绪、收到 EEG 和机器人动作需要分别检查。

手动终端的 Ctrl+C 用于结束该进程；网页 Start 创建的控制管线先由网页 Stop 结束。不要只关浏览器来停车。

### 4.3 无设备离线验证

离线工具在 `thymio_control/lsl_test/`，不是仓库根 `lsl_test/`。它们用于开发，不替代真实 Windows 桥、蓝牙、跨系统网络与 USB 验证。

在独立测试环境中，停止真实桥，不连接真机输出，先备份三个 YAML。WSL Bash，仓库根：

```bash
source .venv/bin/activate
python thymio_control/lsl_test/dummy_dual_streams.py --blink
```

该脚本发布 `gtec_bci_core4` 与 `gtec_hybrid_black` 两个合成流，均 250 Hz，持续到 Ctrl+C。它们和真桥使用相同 source_id，不能混在一起让程序随机匹配。

另一终端启动网页后，在界面选择 Headband 与 Hybrid Black、Speed 与 Steering，并明确选择 **Thymio Simu**（仿真输出），再 Start，检查双路图表和合成信号响应。无需 Windows 设备状态全绿；这是 WSL 合成输入。网页保存仍会修改实际 YAML；不要把合成信号校准值留下用于真人，结束后恢复已备份配置。

需要观察 ROS 启动细节时，在网页控制已 Stop 的前提下，用手动 launch 代替网页 Start：

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
ros2 launch thymio_control experiment_core.launch.py --show-args
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true run_eeg2:=true use_teleop:=false input:=lsl role:=speed eeg2_input:=lsl eeg2_role:=steering
```

前提是两份安装目录的 EEG 参数确实分别指向两个不同的合成 source_id，并且没有残留校准任务；上面的 launch 参数没有覆盖 source_id。仿真依赖未就绪时先解决 Gazebo / ROS 包问题，不把失败认定为设备故障。退出手动 launch 后再停止合成流，恢复配置并核对无残留控制节点。

## 5. 代码与配置导读

### 5.1 功能与代码定位

排查或调整某项功能时，可从下表定位代码。它是查找入口，不是新增需求或待修复问题清单，也不表示每次都要修改所列的全部文件。

| 功能 / 排查目标 | 主要代码入口 |
|---|---|
| 总控启动、设备连接和状态显示 | [launcher_server.py](../../windows_launcher/launcher_server.py)、[commands.py](../../windows_launcher/commands.py)、[state.py](../../windows_launcher/state.py)、[lsl_probe.py](../../windows_launcher/lsl_probe.py) |
| EEG 采集与重连 | [gpype_lsl_bridge.py](../../gtec_bridge/gpype_lsl_bridge.py)、[unicornpy_lsl_bridge.py](../../gtec_bridge/unicornpy_lsl_bridge.py) |
| 滤波、频带功率和派生指标 | [lsl_raw.py](../../thymio_control/thymio_control/adapters/lsl_raw.py)、[band_power.py](../../thymio_control/thymio_control/processors/band_power.py)、[enrich.py](../../thymio_control/thymio_control/processors/enrich.py) |
| 控制策略与速度／转向映射 | [policies/](../../thymio_control/thymio_control/policies/)、[pipeline.py](../../thymio_control/thymio_control/pipeline.py)、[eeg_control_node.py](../../thymio_control/scripts/eeg_control_node.py) |
| 校准与眨眼检测 | [eeg_control_node.py](../../thymio_control/scripts/eeg_control_node.py)、[calibration.py](../../thymio_control/thymio_control/calibration.py)、[blink_metric.py](../../thymio_control/thymio_control/processors/blink_metric.py)；涉及界面时再看[App.jsx](../../web_gui/frontend/src/App.jsx) |
| 双设备融合与断流保护 | [cmd_vel_fuser.py](../../thymio_control/scripts/cmd_vel_fuser.py)、[watchdog.py](../../thymio_control/thymio_control/watchdog.py)、[eeg_control_node.py](../../thymio_control/scripts/eeg_control_node.py) |
| 网页界面与参数保存 | [App.jsx](../../web_gui/frontend/src/App.jsx)、[models.py](../../web_gui/backend/app/models.py)、[config_store.py](../../web_gui/backend/app/config_store.py) |
| ROS 数据显示与网页遥控 | [signal_subscriber.py](../../web_gui/backend/app/signal_subscriber.py)、[main.py](../../web_gui/backend/app/main.py) |
| 控制管线启动、真机／仿真切换 | [command_runner.py](../../web_gui/backend/app/command_runner.py)、[experiment_core.launch.py](../../thymio_control/launch/experiment_core.launch.py) |

当前指标眨眼检测使用 `blink_metric.py`，不要与旧 `blink.py` 路径混淆。模块职责、算法和接口定义见[技术档案的系统设计](DOSSIER_TECHNIQUE_cn.md#3-系统设计)；第三方驱动维护见[第 5.5 节](#55-第三方源码与本项目修改)。

### 5.2 主链路与接口

系统架构与数据流见[技术档案第 3.1 节](DOSSIER_TECHNIQUE_cn.md#31-系统总体设计)；ROS 话题、分析 JSON、HTTP 与 WebSocket 接口定义见[第 3.10 节](DOSSIER_TECHNIQUE_cn.md#310-接口与数据契约)。

调试实际运行链路时，按[本手册第 6.3 节](#63-wsl网页与-ros-检查)检查节点、话题、发布者、消息和运行参数，不能只根据保存的 YAML 判断当前运行状态。

网页 Keyboard 与终端键盘控制是两条不同的路径，不要混淆它们的启动开关，也不要同时启动多个运动命令来源。具体启动条件见[技术档案第 3.3 节](DOSSIER_TECHNIQUE_cn.md#33-启动与状态设计)。

### 5.3 三套配置边界

1. **Windows 本地 launcher JSON**：路径、解释器、服务、attach / detach 命令；同步排除，不由网页配置 API 管理。
2. **WSL 源码 YAML**：`launch_args.yaml`、`eeg_control_node.params.yaml`、`eeg_control_node.eeg2.params.yaml`；网页保存配置主要写这里。
3. **ROS 安装目录 YAML**：launch 默认从 ROS package share 读取；校准代码会尝试写回源码及安装目录。是否为 symlink 必须实际检查，不能假设两个目录永远一致。

第二份 EEG 文件对应第二条设备配置，不固定等于 Hybrid Black 或 Steering。关闭第二角色以 `run_eeg2` 等配置为准，不要求删除第二份 YAML。

网页保存参数后，若实际运行未使用新值，先核对后端写入的源码文件、ROS launch 读取的安装目录文件，以及两者是否链接到同一文件，并检查保存日志。`GET /api/config` 返回的 `source_files` 只报告后端源码配置路径，不代表 ROS 实际读取的安装配置。

自动校准的保存机制、参数生效方式及需要 Stop / Start 的具体情况，见[技术档案第 3.7 节](DOSSIER_TECHNIQUE_cn.md#37-校准设计)；完整配置读写关系见[第 3.9 节](DOSSIER_TECHNIQUE_cn.md#39-配置与持久化设计)。不要通过删除 `thymio_control/` 源码目录解决配置不一致问题。

### 5.4 两类 EEG 的预滤波实现

滤波位置、截止频率、API 能力及两种实现的差异，见[技术档案第 3.5 节](DOSSIER_TECHNIQUE_cn.md#35-eeg信号处理设计)。本节保留代码维护与验证入口。

- **代码入口**：Headband 的 SDK 滤波节点在[桥的 `GpypeBridge.build()`](../../gtec_bridge/gpype_lsl_bridge.py)中连接；Linux 补滤波的启用逻辑在[适配器 `lsl_raw.py`](../../thymio_control/thymio_control/adapters/lsl_raw.py)，实现为[`band_power.py` 中的 `StreamingPreFilter`](../../thymio_control/thymio_control/processors/band_power.py)。
- **设备标识变更**：当前 Hybrid 补滤波按流名称 `gtec_hybrid_black` 启用，不是按 `source_id`。改名称、换桥或增加同型号设备时，要检查是否漏滤波或重复滤波。
- **流式状态**：保留各通道在连续数据块之间的滤波状态，不能每个数据块都重新初始化滤波器。
- **单位检查**：[Hybrid 桥](../../gtec_bridge/unicornpy_lsl_bridge.py)目前未写入 `source_unit`；适配器默认使用 µV 不代表单位已确认，须核实 SDK 输出与流元数据，不能按曲线外观猜测。

修改后可用[预滤波测试](../../thymio_control/test/test_pre_filter.py)核对直流抑制、50 Hz 抑制、10 Hz 保留、流式连续性、多通道和 reset；[频带功率测试](../../thymio_control/test/test_band_power.py)核对后续计算。这些是软件数值测试，不能验证 Windows SDK 的实际滤波响应或蓝牙连接稳定性。

### 5.5 第三方源码与本项目修改

`src/ros-aseba`、`src/ros-thymio` 已在本项目提交 `12c093c` 转成普通 Git 跟踪目录，嵌套依赖也随源码保留；不是部署时自动从上游取最新版的子模块。部分目录保留 `.gitmodules` 是来源线索，不说明现在仍应执行递归子模块更新。

本项目第三方源码的固定上游版本如下；嵌套版本来自对应 ros-aseba 的上游 Git 树，不以最新分支代替：

| 本项目目录 / 组件 | 固定上游版本 |
|---|---|
| `src/ros-aseba` | [jeguzzi/ros-aseba @ 94acaba](https://github.com/jeguzzi/ros-aseba/tree/94acaba803d748b84fce62ab0527d1348b28be12) |
| `src/ros-aseba/asebaros/aseba` | [aseba-community/aseba @ 3c14f0c](https://github.com/aseba-community/aseba/tree/3c14f0cb9510c60502821bfd7adb22e795540479) |
| `src/ros-aseba/asebaros/dashel` | [aseba-community/dashel @ 1a8d36e](https://github.com/aseba-community/dashel/tree/1a8d36e7fe48ce0f4fd292f5b64b2a0a880953da) |
| `src/ros-thymio` | [jeguzzi/ros-thymio @ d996f49](https://github.com/jeguzzi/ros-thymio/tree/d996f4994feb5332c42a2b58c2c2c17fed0c938d) |

| 实际不同的文件 | 已确认的差异及维护含义 |
|---|---|
| [Aseba `TargetDescription.h`](../../src/ros-aseba/asebaros/aseba/aseba/common/msg/TargetDescription.h) | 增加 `#include <cstdint>`；该头声明使用 `uint16_t`。这是显式提供整数类型声明的编译兼容性修正，不是采集性能优化。换上游后核对是否仍需保留，并在目标编译器构建 |
| [Aseba `DashelTarget.cpp`](../../src/ros-aseba/asebaros/aseba/aseba/clients/studio/DashelTarget.cpp)、[`challenge.cpp`](../../src/ros-aseba/asebaros/aseba/aseba/targets/challenge/challenge.cpp) | 中文语言选项标签由“汉语”改为“Chinois”，语言代码仍为 `zh`；只是界面文字，不是 ROS 通信修复 |
| [Thymio `base.urdf.xacro`](../../src/ros-thymio/thymio_description/urdf/base.urdf.xacro) | 旧 Gazebo ROS 差速 / joint-state 插件替换为 GZ Sim DiffDrive，删除旧 ground-truth 插件块；属于仿真适配，不能承诺旧传感器 / ground-truth 功能全部保留 |
| [Thymio `imu.urdf.xacro`](../../src/ros-thymio/thymio_description/urdf/imu.urdf.xacro)、[`proximity_sensor.urdf.xacro`](../../src/ros-thymio/thymio_description/urdf/proximity_sensor.urdf.xacro) | 移除对应旧 `gazebo_ros` 传感器插件块，不能据此称现代 GZ 已发布这些 ROS 传感器话题 |
| [Thymio `wheel.urdf.xacro`](../../src/ros-thymio/thymio_description/urdf/wheel.urdf.xacro) | 轮关节 effort 限制由 0 改为 10；是仿真模型参数，不是实际电机命令的统一上限 |
| [Thymio `model.launch.py`](../../src/ros-thymio/thymio_description/launch/model.launch.py) | 输出由 screen 改为 log，增加 `use_sim_time` 参数声明；但传给节点的值仍硬编码 `True`，声明值未实际用于节点。保留为待核验限制，不写成参数传递已修好；项目提交 `d377c77` 可定位这次修改 |

维护时区分 Aseba 编译兼容性修正、界面文字调整和 Thymio 仿真适配，不将这些改动统一视为性能优化。旧 `master` / 教程包含 ROS1 内容，更新依赖时须核对 ROS2 与 GZ 兼容性。

迁移时优先保留本项目整个 `src/`，不要直接用上游最新分支覆盖。确需更新时，先独立比较版本、保留或重做必要补丁，再构建并验证 Thymio 真机、仿真、话题与时钟行为；保留 [ROS-Aseba LICENCE](../../src/ros-aseba/LICENCE)、[ROS-Thymio LICENSE](../../src/ros-thymio/LICENSE)、[Aseba 许可](../../src/ros-aseba/asebaros/aseba/license.txt)和[Dashel 许可](../../src/ros-aseba/asebaros/dashel/license)，不将不同组件合并声明为同一许可。

## 6. 分层排障与日志

### 6.1 先确定故障层

先停止控制、记录时间和最短复现步骤，然后逐层检查。不要同时重装 Python、换蓝牙、改 BUSID 和改 YAML，否则无法知道哪一步有效。

| 层 / 症状 | 最小检查 | 如何解释与下一步 |
|---|---|---|
| Windows 设备 / 蓝牙不稳 | 电量、电脑充电器、设备管理器集成蓝牙状态、是否误用官方 Hybrid USB 蓝牙 | 先恢复物理连接；Thymio Dongle 与蓝牙模块分开辨认 |
| 设备解释器 / SDK 导入失败 | 用对应解释器执行第 3.1 节导入检查 | 缺包 / ABI / 授权问题还未到 ROS 层；Headband VS Code 与探针都要检查 |
| 总控不启动或 WSL 未就绪 | `launcher_server.log`、发行版名、`\\wsl$`、systemd | 确认实际配置与同步路径；不要因服务探测超时直接重装 WSL |
| EEG 总控连接不是绿色 | 对应 Windows LSL 探针与桥输出 | not-found、stalled、no-pylsl 按第 6.2 节区分 |
| EEG 绿色但图表没有数据 | 是否已校准 / Start；source_id；ROS 节点 / 话题；后端 subscriber_error | 只连接没有启动分析属正常；Windows 发现流不证明 WSL 也能发现 |
| 校准一直 Preparing | Windows 桥新鲜样本、WSL LSL 发现、source_id、节点报错 | 倒计时等首帧才开始；不是一律网络问题 |
| YAML 保存却运行值没变 | `/api/config` 的 source_files、ROS package prefix、实际节点参数 | 确认运行仓库和 source / install；不是重新构建前端就能解决 |
| Thymio 绿色却不动 | 先按用户指南做单角色 Keyboard 测试，再查最终速度及驱动 | USB 可见不等于配对、驱动与机器人动作均正常 |
| 双 EEG 只一路有数据 / 不动 | 两 source_id、角色、两个 partial 话题与 fuser | 缺一路时 watchdog 零速可能是正确行为，不关闭保护来“让它动” |
| 本机网页正常，其他电脑异常 | 5173 转发 / 防火墙、前端代理、WebSocket origin 与授权 | 先检查真实访问路径；不要直接关全部防火墙或放开所有后端端口 |

常见硬件与连接恢复见[排障手册](GUIDE_DEBUG_cn.md)。以下检查用于进一步定位桥、LSL、ROS 和网页服务问题。

### 6.2 Windows LSL 与 USB 检查

Windows PowerShell，切到 Windows 的 `windows_launcher` 目录，使用各设备实际解释器：

```powershell
python lsl_probe.py gtec_bci_core4 2
python lsl_probe.py gtec_hybrid_black 2
usbipd list
```

探针输出 `alive`、`stalled`、`not-found` 或 `no-pylsl`。其正常 CLI 退出码始终为 0，不能只看 exit code 判连接成功：

- `alive`：解析到流且拉到新鲜样本。
- `stalled`：流存在但没有新鲜样本，可能是桥仍在而设备没有数据。
- `not-found`：未找到流，或者解析过程异常；结合桥日志检查，不直接认定设备没开机。
- `no-pylsl`：探针解释器缺少 pylsl；不证明 VS Code 的桥环境也缺。

USB 状态按[排障第 4 节](GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)解释：`1-1` 为 Shared 可由 Connect attach；Attached 已接入；Not shared 先 bind；没有编号先重新插拔指定口。

WSL Bash，在 attach 后检查设备和权限：

```bash
ls -l /dev/ttyACM0
id
```

若存在但驱动报权限错误，检查设备所属组、当前用户和已配置的 udev 规则；不要用 `chmod 777` 当长期修复。实际串口名若改变，必须统一核对 launcher 验证命令、ROS device 配置与文档。

### 6.3 WSL、网页与 ROS 检查

实验网页顶部的 Running 是前端本地标记，后端 `/api/status` 的 `running` 也不是ROS子进程健康探测；请求失败或子进程退出时，标记可能与实际运行不一致。启动EEG控制后，用下面的节点、话题与消息检查确认对应EEG节点是否运行；双EEG还要检查融合器和两路partial话题。Keyboard测试不要求EEG节点运行，应检查最终速度话题及机器人驱动。不要仅凭按钮状态判断启动或停止成功。

WSL Bash，ROS / install 已 source 的终端中，以下均为诊断读取，不发布运动命令：

```bash
curl --fail http://127.0.0.1:8010/api/health
curl --fail http://127.0.0.1:8010/api/config
ros2 node list
ros2 topic list
ros2 topic info /cmd_vel --verbose
ros2 topic echo /eeg_analysis --once
```

双路改查 `/eeg_analysis/speed` 与 `/eeg_analysis/steering`，并检查 partial 话题；仿真改查最终话题 `/model/thymio/cmd_vel`。没有发布者时 echo 会等待，Ctrl+C 结束；不要把等待自动当成终端卡死。

查看 `ros2 param list <节点名>` 与需要的 `ros2 param get <节点名> <参数名>`，对比实际运行值，而非只读仓库 YAML。校准问题重点看 `CALIB:`、有效样本数量、写文件结果及两个文件各自参数。

安装目录定位（WSL Bash）：

```bash
ros2 pkg prefix thymio_control
```

随后检查该 prefix 下的 `share/thymio_control/config/` 与源码配置，及符号链接目标。`/api/config` 的 `source_files` 报告源码路径，不是所有正在使用的 ROS 安装文件。需要重新加载磁盘配置时才请求 `/api/config?reload=true`；旧配置迁移路径可能写第二份参数文件，先备份。

网络读取检查：Windows PowerShell 用 `netsh interface portproxy show all`；WSL 用 `hostname -I`、`ss -ltnp` 核对实际 IP、5173 / 8010 监听。IPv6 地址选择曾导致本项目 LSL 连接挂起，但禁用 IPv6 不是通用第一步：先证明 Windows 样本正常、WSL 发现 / 连接异常并保存日志，再审查现有网络配置。网络变更一次只做一项，记录原值和恢复方式。

### 6.4 日志位置与故障记录

| 来源 | 位置 / 入口 | 注意事项 |
|---|---|---|
| Windows 总控 | Windows `windows_launcher/launcher_server.log`；View Log | 先确认读取的是实际启动副本 |
| Hybrid Black | 同目录 `bridge_hybrid.log` | 启动、导入、采集 / 重连异常 |
| Headband | 手动运行脚本的 VS Code 终端 | 不承诺存在对应 bridge_headband 日志；Ctrl+C 后必要时复制文本 |
| WSL 网页后端 | `/tmp/launcher_backend.log` | 模板用覆盖重定向，重启前保存有用内容 |
| WSL 网页前端 | `/tmp/launcher_frontend.log` | npm / Vite 启动与端口错误 |
| ROS 节点 | ROS launch / 节点日志；手动 launch 的错误输出 | 网页 runner 将 ROS 子进程 stdout / stderr 设为 DEVNULL，不是所有 ROS 错误都进后端日志 |
| 构建 | 工作区 `log/` 下 colcon 日志 | 构建产物与日志不应当作源码提交 |

一份有效故障记录至少含：时间、运行提交、改动后的配置摘要、设备 / 角色 / 输出、复现步骤、期望 / 实际结果、关键日志、已尝试的一项变更及其结果。涉及参与者数据、token 或内部地址时先脱敏；不要把完整敏感日志提交 Git。

## 7. 修改与测试

### 7.1 现有测试入口

使用 WSL 仓库根 `.venv`，先确认依赖。按修改范围选择测试，缺失依赖按环境安装说明处理。

WSL Bash，仓库根：

```bash
source .venv/bin/activate
python -m pytest thymio_control/test -v
python -m pytest windows_launcher/tests -v
python -m pytest thymio_control/lsl_test -v
```

后端测试导入 `app.*`，从后端目录执行：

```bash
cd web_gui/backend
../../.venv/bin/python -m pytest app -v
```

前端构建从前端目录执行 `npm ci`、`npm run build`。仓库根直接运行 pytest 仅发现 `pytest.ini` 的三个目录，**不包含后端测试**。

| 范围 | 证明什么 | 不证明什么 |
|---|---|---|
| watchdog / fuser / policy / calibration 等纯逻辑测试 | 决策、映射、数值与边界条件 | 整机停车延迟、蓝牙 / USB 稳定性 |
| launcher tests | fake executor 下生命周期、命令及状态逻辑 | 真 Windows 命令、SDK、WSL 与网络实际可用 |
| 后端 tests | 模型、配置、runner、subscriber 等行为 | 全部真实 ROS 生命周期、物理执行 |
| lsl_test | 合成流、EDF / 流式处理等开发验证 | 真实跨系统网络与真人 EEG 有效性 |
| npm build | 前端可构建 | 界面交互正确、WebSocket 断网后停车 |
| 目标环境集成检查 | 实际环境下已执行场景的运行行为 | 未覆盖的环境、设备与故障场景 |

有些测试缺少依赖或数据会 skip，skip 不是通过。`gtec_bridge/test_*.py` 含真实设备 / SDK 调试脚本，不是可在任意环境无风险运行的纯单元测试，不要为了“全覆盖”直接批量执行。

快速回归入口，可在不需要 ROS 的开发环境运行：

```bash
python -m pytest thymio_control/test/test_watchdog.py thymio_control/test/test_cmd_vel_fuser.py thymio_control/test/test_calibration.py thymio_control/test/test_blink_metric.py -q
```

历史数据已移除，[test_verify_blink_clamp.py](../../thymio_control/test/test_verify_blink_clamp.py)依赖的归档数据缺失时会跳过，不是当前可用的回放功能。系统实际验证范围与结果见[技术档案的验证口径](DOSSIER_TECHNIQUE_cn.md#41-验证口径)；每次代码修改后仍需重新执行相关测试。

### 7.2 小修改的标准流程

1. 写清复现、期望结果和成功条件；检查 Git 状态，不覆盖操作者已有改动。
2. 从[代码导读](#5-代码与配置导读)确定负责层，先改最小范围。不要顺便重构驱动或历史模块。
3. 为行为变化增加 / 更新对应测试，先运行局部测试，再跑受影响套件；UI 修改增加构建和点击验证。
4. 在仿真或受控环境验证；涉及设备连接、校准、融合、看门狗、Teleop 或进程停止的改动，还要补真机场景。
5. 更新相关手册、配置迁移说明和版本记录，检查 diff 后提交。不能把临时校准值、私有路径、日志或真人数据顺手提交。

代码修改遵循项目约定与既有风格：纯逻辑尽量可测、阈值使用命名常量、失败明确。

### 7.3 扩展时不能漏掉的层

| 修改 | 至少核对的连接点 |
|---|---|
| 新指标 / 新策略 | processors 特征、policy 与 `POLICIES` 注册、节点校准指标选择、后端 policy 校验、前端选项 / 显示、YAML、数值与校准测试 |
| 改 EMA | 当前三个策略类的 `ema_alpha=0.35`；不是现有 YAML / UI 参数。调大更敏捷但更抖，调小更平滑但更慢；核对策略状态与回归测试 |
| 新设备 | Windows API / SDK、桥与 StreamInfo、唯一 source_id、通道 / 采样率 / 单位、device_profiles、adapter 滤波选择、前后端品牌 / 角色映射、launcher 与探针 |
| 改 USB / 电脑路径 | Windows 本地 JSON 中所有嵌入路径、attach / detach / verify 命令、ROS device，以及操作 / 排障手册中的路径与指定口说明 |
| 改停止或断流 | 节点 watchdog、fuser、runner 清理、Windows bridge 生命周期、网页 / WebSocket 异常与真实驱动停车 |

新增设备时同时核对流身份、元数据和处理链，具体注意事项见[第 5.4 节](#54-两类-eeg-的预滤波实现)。同型号双设备的跨层修改按[第 7.5 节实施路线](#75-首要开发任务同型号双-gtec-集成)进行。

### 7.4 优先保留并验证的安全边界

不要通过关闭保护掩盖问题。当前已识别的边界见[技术档案当前限制](DOSSIER_TECHNIQUE_cn.md#51-当前限制及优先验证事项)，修改相关功能时尤其检查：

- EEG 节点与融合器分别检查数据新鲜度，当前默认阈值均为 0.5 秒，不是整机停车时限；修改后实测断流与恢复，注意仍 Running 时数据恢复可能续动。
- Steering 使用 Alpha / TBR 时，自动校准不会刷新已创建眨眼检测器的上冲基线下限，Stop / Start 可重新读取。不要将此推广成所有校准值都须重启才生效；详见[校准设计](DOSSIER_TECHNIQUE_cn.md#校准结束后的控制状态)。
- 浏览器 Teleop WebSocket 断开时，后端没有明确自动补发零速度；前端松手时补发 Stop 不等于断网急停。
- dry-run / `WEB_GUI_ALLOW_REAL_COMMANDS=false` 不阻断直接 Teleop；做无硬件测试时仍需隔离真机输出。
- 进程清理可能按名称匹配其他 ROS / 网页任务；Stop System 默认终止整个配置发行版。复用工作站前先确认其他任务。

历史设计和 review 仅作定位线索；修改前仍需检查当前实现并复现问题。

### 7.5 首要开发任务：同型号双 g.tec 集成

当前尚未实现同型号双设备集成，也未完成相应真机验证。正式范围与通过条件见[技术档案 RF-NEXT-01～06](DOSSIER_TECHNIQUE_cn.md#25-下一阶段主要需求同型号双-gtec)，以下说明代码修改入口、实施顺序与回归测试。

#### 7.5.1 目标与可复用部分

目标组合、功能范围与兼容要求见[技术档案第 2.5 节](DOSSIER_TECHNIQUE_cn.md#25-下一阶段主要需求同型号双-gtec)。

已有 ROS launch 能运行两套 EEG 节点，两条 YAML 分别保存校准；`cmd_vel_fuser` 按角色合并速度与转向，后端和图表也按角色路由。这些可以复用。主要缺口在 **Windows 具体设备选择 → 唯一 LSL 流 → 配置绑定 → 连接状态**，不是重新设计控制算法。

#### 7.5.2 当前代码的限制与修改入口

| 层 / 代码入口 | 已核对的现状 | 本任务需处理的内容 |
|---|---|---|
| [Hybrid 桥](../../gtec_bridge/unicornpy_lsl_bridge.py) | `_connect_unicorn()` 取 `GetAvailableDevices(True)` 的第一台；重连再次调用；`source_id` 固定 | 明确选择序列号；首次连接与重连都固定原设备；每台流身份唯一，指定设备不可用时不得换另一台 |
| [Headband 桥](../../gtec_bridge/gpype_lsl_bridge.py) | `BCICore8(channel_count=4)` 未显式选择设备；`LSLSender` 固定名称；自检探针按名称扫描新鲜样本 | 核对已安装 SDK 的设备选择和 LSL 身份设置接口；桥重建保留指定设备，探针只查本实例；保留 IDE 手动运行方式 |
| [launcher 配置](../../windows_launcher/config.json)、[命令](../../windows_launcher/commands.py)、[server](../../windows_launcher/launcher_server.py)、[探针](../../windows_launcher/lsl_probe.py) | 配置只有一个 Headband 和一个 Hybrid 入口；进程字典按入口名管理；脚本启动未传入实例参数，探针选首个匹配流 | 复用按入口名管理的结构，为两台设备配置独立入口 / 参数 / 日志 / 探针；只停止指定实例，不把另一实例误显示为已连接 |
| [前端 App](../../web_gui/frontend/src/App.jsx) | 第二路同型号选项禁用，effect 自动切到另一型号；`buildPatch()` 按品牌生成固定 ID，加载也按 ID 反推品牌 | 解除型号互斥而保留角色互斥；增加具体设备选择；保存 / 加载真实身份，不能再用品牌覆盖唯一 ID |
| [后端模型](../../web_gui/backend/app/models.py)、[配置写回](../../web_gui/backend/app/config_store.py)与[两路 YAML](../../thymio_control/config/) | 已保存 `lsl_source_id`，但没有持久化型号 / 序列号；模型只校验角色不同 | 扩充最小身份字段和校验；双路拒绝同一物理设备 / 重复 ID，不能只依赖 UI；写回并验证重载、校准时也不丢身份 |
| [RawLslAdapter](../../thymio_control/thymio_control/adapters/lsl_raw.py) | 有 ID 时按 ID 找流，否则按 type；均使用 `streams[0]`；Hybrid 预滤波按 `info.name()` 判断 | 双路必须明确匹配；对冲突的有效流明确报错 / 阻止启动；将型号处理与唯一身份分开，保留单位、通道和滤波验证 |
| [ROS launch](../../thymio_control/launch/experiment_core.launch.py)、[EEG 节点](../../thymio_control/scripts/eeg_control_node.py)、[融合器](../../thymio_control/scripts/cmd_vel_fuser.py)、[RosBridge](../../web_gui/backend/app/signal_subscriber.py) | 双路节点、独立校准文件与 role 话题已经存在 | 核对新身份确实传到各节点；保留角色路由、融合及断流逻辑，避免无关重构 |

#### 7.5.3 最小身份设计

不要继续把“型号”当成“这一台设备”。至少分清下面四项，字段名由实现确定，并同步前后端和配置：

| 信息 | 用途与约束 |
|---|---|
| 型号 | 决定采集与滤波方式，如 Headband、Hybrid Black；不是唯一标识 |
| 物理设备序列号 | Windows SDK 明确连接哪台设备；两路的物理身份不得相同 |
| LSL source_id | Linux 与探针唯一绑定数据来源；可按型号 + 序列号生成，重连不能变，不能包含当前角色 |
| 角色 | `speed` / `steering`；用户可交换，交换不应改变具体设备身份 |

例如 `gtec_hybrid_black_<serial_A>` 与 `gtec_hybrid_black_<serial_B>` 是拟议的命名示例，**不是当前脚本已有参数或已发布的流名称**。设备标签 A / B 可辅助显示，但不能替代真实序列号核验。

LSL 流名称与 source_id 是两个字段：保持型号名称而使用唯一 source_id 是一种过渡方式，但仍须修改 Headband 按名称探测的逻辑。更稳健的方案是在配置 / 流元数据明确型号和已做的滤波，再按这些信息选择处理；使用哪种方式取决于已安装 g.Pype 的接口，不假设 `LSLSender` 已支持尚未核实的参数。不能只给 Hybrid 的流名称加后缀，否则当前 Linux 预滤波可能不再启用。

校准目前属于第一 / 第二条配置，不能因此当作具体设备的永久校准。更换物理设备或改变校准条件后清除 / 重新验证旧结果；角色交换后核对设备、指标与校准仍对应正确。不需要为此新增数据库。旧固定 ID 的单设备 / 混合配置须有明确兼容或迁移步骤，备份后转换，不能在加载时静默猜错型号或覆盖 ID。

#### 7.5.4 分阶段实施与验证

1. **保存基线并核实条件。** 向 Lucas 获取[授权信息](#hybrid-black-api-授权)，核对 SDK / Python / Suite 版本及两台设备序列号。停止控制并备份配置，在开发副本测试，不直接升级现有 SDK 来试错。
2. **先做 Windows 并发采集验证。** 不运行机器人控制，尝试按两个明确序列号同时采集；核实单进程 / 多进程可行性、API 限制、退出释放与重连。g.Pype [官方 FAQ](https://gpype.gtec.at/content/5_faq/index.html)说明可实例化多个采集源，但不是当前版本“两台 Headband 可独立启停”的保证。记录版本、运行方式、两路身份和数据、持续时间、失败 / 限制；若厂商能力不满足，先说明阻碍，不自行替换 API / 工作流。
3. **实现按实例配置的桥。** 提供设备选择和唯一流身份，固定重连目标，保证各自资源释放、自检和日志；先验证两路 LSL，不依赖 ROS。Hybrid 可优先复用按入口托管独立进程的方式，前提是并发验证通过；Headband 的实例配置 / IDE 启动方式要清晰，不能要求操作者每次手改代码常量，也不默认改成后台自动启动。
4. **贯通配置与 Linux。** 增加必要型号 / 序列号字段、重复身份校验及 YAML 写回；适配器、launcher 探针按明确身份匹配。处理重连残留流的过期 / 新鲜判断，若仍有多个冲突的有效流则明确报错，不能随便取第一条。核对每路滤波、采样率、通道和单位。
5. **更新两个页面。** EEG 控制页面允许相同型号的不同设备，正确保存、重新加载、交换角色与逐台校准；System Control 提供对应实例入口和独立状态。断开一路只影响该路采集，机器人则按现有双路断流保护停车。
6. **离线回归，再真实设备验证。** 扩展[双路合成流工具](../../thymio_control/lsl_test/dummy_dual_streams.py)，产生同型号元数据、不同 ID 和可区分数值；补桥选择 / 重连、配置、探针、滤波和界面测试。再做真实双设备、ROS 与 Thymio 验证，记录结果，更新操作 / 排障手册和迁移说明后才部署。

前两阶段决定厂商环境是否可行，后四阶段解决本项目的集成。没有设备时可以实现并验证配置和模拟流路径，但不能把 Windows SDK 并发、蓝牙稳定性或真机停车标为已通过。

#### 7.5.5 回归场景与结果记录

完成标准按[技术档案 RF-NEXT-01～06](DOSSIER_TECHNIQUE_cn.md#25-下一阶段主要需求同型号双-gtec)核对；本节组织具体回归操作。按对应需求编号登记 commit、环境 / 配置、步骤、期望、实测与证据，明确记录未测和失败项。

- **身份与配置**：用可区分的模拟数据检查两路绑定，再以真机逐台断开等操作确认来源，不能只看两条曲线。测试重复物理设备、重复 source_id、冲突的有效流及指定设备缺失；保存配置、刷新页面和重启后重新核对型号、身份与角色。
- **独立连接与重连**：分别连接 A、B，再同时连接；断开 / 断电、重连或停止 A，检查 B 的采集、设备绑定、状态及进程不被误影响。检查 A 的探针不会使用 B 的数据、重连仍指向 A，然后交换 A / B 重复测试。
- **校准与角色交换**：分别校准两路，检查参数文件是否只更新对应一路；交换角色、保存并重新加载，核对设备、指标、校准、曲线和运动输出的对应关系。更换物理设备后，检查旧校准结果的清除 / 重新验证流程。
- **控制与兼容回归**：核对各路滤波、采样率、通道、单位及角色融合输出；分别中断一路，实测停车与恢复，记录仍 Running 时是否续动。回归单 Headband、单 Hybrid、混合型号双 EEG、仿真、Keyboard 单独测试和停止流程。

单元测试 / 模拟流验证与真实双设备测试分开记录；既有测试不能自动覆盖新增功能，软件阈值不能代替实测停车结果。正式通过条件见[技术档案第 2.5 节](DOSSIER_TECHNIQUE_cn.md#25-下一阶段主要需求同型号双-gtec)，未完成真实双设备测试时，不将该功能标为已验收。

## 8. 更新与发布

### 8.1 更新前与 WSL 源码更新

先停止实验控制、手动 Headband 桥及相关服务，备份实际 JSON、三个 YAML 与必要数据。记录旧提交与回退方案；有其他 WSL 工作时先协调停机。

WSL Bash，仓库根，先读取：

```bash
git status --short --branch
git diff --stat
git rev-parse HEAD
```

工作区不干净时先辨认是开发改动还是运行配置变化，保留并决定如何处理。不要直接 `reset --hard`、强制覆盖或将所有文件无差别提交。

只有在确认工作区干净、目标分支及更新来源后，才执行拉取；下面是部署到 `main` 的入口，不是自动更新机制：

```bash
git switch main
git pull --ff-only origin main
git rev-parse HEAD
```

分支分叉 / 冲突时停止部署并检查原因，不用强推解决。部署时记录实际 commit；开发改动先在独立分支测试，再更新运行环境。

### 8.2 根据变化执行必要步骤

| 变化 | 部署动作 |
|---|---|
| Python 依赖声明 | 在目标 `.venv` 安装声明依赖，检查 ROS / SDK 兼容性并跑相关测试 |
| ROS 源码 / launch / 安装资源 | source ROS 后构建并检查安装版本；已有依赖工作区可 `colcon build --symlink-install --packages-select thymio_control`，跨包变化构建相关依赖 |
| 前端依赖 / 代码 | npm lockfile 更新时 `npm ci`；`npm run build` 验证；重启实际 Vite 进程并检查页面 |
| Windows launcher / bridge | Start System 同步文件；launcher 自身需退出并重新启动才加载新代码；桥也需按各自流程重新启动 |
| Windows 本地 config.json | 明确手动迁移并备份；同步不会替你更新此文件 |
| YAML / 校准 | 对比确认值；检查 source / install，重新启动控制节点，不随意覆盖已验证参数 |
| 纯文档 | 检查链接、命令、语言与使用流程；通常不需要重装依赖或重建系统 |

更新后至少核对：实际运行提交、Windows 同步副本、JSON 未被覆盖、网页来源、节点参数、一次 Keyboard 测试和受影响功能。完整更新失败时，不在持续运行的系统上不断尝试新配置；按备份恢复到已验证基线。

### 8.3 发布与提交检查

提交源码和必要文档 / lockfile。共享默认配置与机器本地配置分开处理；确需更新版本控制中的 YAML 时，检查变更是否为预期默认值，而非某次测试或个人校准残留。提交前看清暂存文件及 diff，不使用无差别 `git add .` 把实验数据和本地设置带入。

版本发布说明应包含：commit、依赖 / 配置迁移、测试范围与结果、真机是否验证、已知限制、回退方法。功能或操作发生变化时，同步更新对应文档及语言版本。

## 9. 备份与恢复

### 9.1 必须备份的内容

| 内容 | 为什么需要 | 保存方式 |
|---|---|---|
| 源码 commit 与未提交改动 | 只复制 Windows 桥不足以恢复整个项目 | Git 版本记录；必要本地改动独立保留 |
| 实际 Windows `config.json` 与入口位置 | 机器本地路径 / 解释器不会由同步恢复 | 受控副本，与日期和电脑对应 |
| 三个实际 YAML | 网页保存与校准会改运行配置 | 停止控制后复制；记录对应设备 / 角色 / 指标 |
| SDK、驱动、授权恢复信息 | 不包含在 pip / Git 完整依赖中 | 向 Lucas 获取 Hybrid API licence 信息；按[授权说明](#hybrid-black-api-授权)及机构 / 厂商要求受控保存 |
| 系统与依赖版本 | 浮动依赖和不同 ABI 可能无法复现 | WSL 与各 Windows 环境的版本清单，前端 lockfile |
| 运行日志与需保留的分析数据 | 故障定位与数值验证可能需要原始文件 | 按实际输出路径备份，不将敏感数据提交 Git |
| WSL 整体导出（迁移优先考虑） | 保留原有 Linux 软件、工作区与配置，降低从头重建成本 | 停止控制与相关服务后制作；按[第 9.3 节](#93-推荐迁移方式导出与导入整套-wsl)验证恢复，不能替代 Windows SDK / 配置备份 |

可读取并保存 `python -m pip freeze`、`npm ls --depth=0` 及必要 ROS / 系统包版本。它们记录当前环境，不保证每个包都能从公开源恢复，也不能替代 SDK 安装来源与授权说明。

分析数据默认写入仓库下 `experiment_data/`，可由后端环境变量 `EXPERIMENT_DATA_DIR` 指定其他位置；备份时以实际配置为准。历史数据已从当前工作区移除，但数据收集代码仍可生成新文件，功能范围见[README 使用注意](README_cn.md#使用注意)。默认目录已加入 `.gitignore`，忽略规则不清除已有 Git 历史，也不覆盖自定义输出路径；自定义目录须单独检查权限和忽略规则。

### 9.2 恢复步骤

1. 在新目录 / 受控环境恢复已记录的源码版本，不覆盖尚未备份的工作区。
2. Linux 优先评估[整套 WSL 导入](#93-推荐迁移方式导出与导入整套-wsl)；没有可用镜像或需要干净安装时按[环境重建](#3-环境安装与重建)恢复。干净安装重新建 venv，不单独复制；完整导入时先检查保留环境。Windows SDK / Python 环境始终单独准备。
3. 恢复 Windows 实际配置，并按新电脑修改路径、发行版名、解释器和嵌入命令；不是盲目替换为模板。
4. 恢复三个 YAML，对照角色、source_id、运动参数与校准条件；必要时重新对真人校准，不能使用合成流校准值。
5. 核对工作区安装路径，必要时重新构建；恢复 USB 共享与网络访问范围。
6. 先本地网页、再 Keyboard 单独机器人测试、再单 EEG、再双 EEG，最后验证停止、断流 / 恢复与网络故障。
7. 记录恢复使用的版本、配置、缺失依赖与运行检查结果，区分归档文件已保存和恢复流程已验证。

以上是通用恢复顺序，下面给出整套 WSL 迁移的具体命令。

### 9.3 推荐迁移方式：导出与导入整套 WSL

有原电脑可访问且机构允许备份时，建议先导出已能运行的 WSL 发行版，将归档复制到新电脑后导入。它保存 Linux 文件系统内的 ROS、源码、配置、依赖、用户目录和其中的 venv；不是只复制仓库，也不是只复制虚拟环境。命令依据 [Microsoft WSL 基本命令](https://learn.microsoft.com/en-us/windows/wsl/basic-commands#export-a-distribution)与[发行版导入说明](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro)。

**不能随 Linux 导出一起恢复的内容：** Windows 上的 g.tec Suite / API / licence、Windows Python / venv、VS Code、蓝牙配对、usbipd 工具与共享设置、Windows launcher 副本 / 本地 JSON、防火墙 / 端口转发、主机 `.wslconfig`，以及 `/mnt/c` 等挂载的 Windows 文件。分别按[第 3 节](#3-环境安装与重建)配置并受控备份；不认为 Linux tar 包含这些主机资料。

#### 9.3.1 原电脑导出

先按[停止顺序](#41-正常启动与停止)停车、停服务并手动结束 Headband 桥；保存其他 WSL 任务。用 `wsl -l -v` 查**注册发行版名**，不是填“WSL2”或 Ubuntu 系统版本。准备一个有足够空间的备份目录，下面示例目录 `D:\BCI-transfer` 必须已存在；盘符、名称与日期按实际修改。

Windows PowerShell；替换占位符后逐段执行，任何失败都停止，不继续把旧文件当作新备份：

```powershell
wsl -l -v
$sourceDistro = "<原电脑查到的发行版名>"
$backupFile = "D:\BCI-transfer\TelekineRob-WSL-20261009.tar"
if (Test-Path -LiteralPath $backupFile) { throw "备份文件已存在，请换一个新文件名" }
wsl --terminate $sourceDistro
if ($LASTEXITCODE -ne 0) { throw "停止发行版失败，先查明原因" }
wsl --export $sourceDistro $backupFile
if ($LASTEXITCODE -ne 0) { throw "导出失败，不能使用此备份" }
Get-Item -LiteralPath $backupFile
Get-FileHash -LiteralPath $backupFile -Algorithm SHA256
```

`--terminate` 只停止指定发行版，但其中所有任务仍会中断；不使用 `--shutdown` 误停其他发行版。导出记录包括实际发行版名、Linux 用户 / 路径、架构、源码 commit / 未提交改动、版本与校验值。归档可能包含账号凭据、SSH 文件、个人数据和日志，按机构权限保存，不提交 Git 或公开网盘。

#### 9.3.2 新电脑导入与 Linux 检查

新电脑先准备 WSL2，确认 CPU 架构与原 Linux 环境兼容；不同架构应走[从源码重建](#3-环境安装与重建)，不要假设重建 venv 就能运行原镜像。将 tar 文件通过受控渠道复制过来，计算 SHA256 并与原机记录比较。选择**未注册的新发行版名**和**专用空安装目录**；示例 `TelekineRob-BCI` 只是注册名称，可按实际修改，不覆盖已有 Ubuntu。以下路径须存在且符合这个要求，失败时保留原环境，不用删除旧发行版来重试。

Windows PowerShell：

```powershell
wsl -l -v
Get-FileHash -LiteralPath "D:\BCI-transfer\TelekineRob-WSL-20261009.tar" -Algorithm SHA256
wsl --import "TelekineRob-BCI" "D:\WSL\TelekineRob-BCI" "D:\BCI-transfer\TelekineRob-WSL-20261009.tar" --version 2
if ($LASTEXITCODE -ne 0) { throw "导入失败，先查明原因" }
wsl -l -v
wsl -d "TelekineRob-BCI" -u "<原Linux用户名>" -- whoami
```

确认新条目的 VERSION 为 2，Linux 用户、仓库路径和文件权限正确。导入发行版可能默认以 root 启动；根据实际 `/etc/wsl.conf` 保留已有内容，必要时设置 `[user]` 的 `default=<原Linux用户名>`，用户必须已存在；按[Microsoft 导入说明](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro#add-wsl-specific-components-like-a-default-user)重启该发行版后，用不带 `-u` 的 `wsl -d "TelekineRob-BCI" -- whoami` 验证默认用户。不要不加检查地用 root 启动 launcher，造成权限 / 路径差异。

进入该发行版的实际仓库后，执行[第 2.1 节环境检查](#21-环境基线与检查)与[第 3.4 节导入检查](#34-wsl-python-与前端环境)，检查 systemd、ROS 环境、`.venv`、Node / npm 及 install 指向。完整 Linux 镜像保持相同架构、路径和依赖时原 venv 可能继续可用，不必先重建；解释器 / 路径失效或本机库缺失时再按第 3 节恢复。Windows venv 则不能因此复用。必要时重新 colcon 构建，保留[第三方源码修改](#55-第三方源码与本项目修改)。

#### 9.3.3 新电脑 Windows 配置与运行检查

1. 按[SDK 安装入口与使用条件](#37-官方资料与依赖来源)准备 g.tec 软件、API、驱动及各 Windows Python 环境；向 Lucas 核实授权迁移，不因已经导入 WSL 就认定 UnicornPy 已授权。
2. 安装 VS Code、usbipd-win，配对 EEG，检查集成蓝牙及电源管理。原电脑的稳定性经验需要在新电脑复验；Thymio / Dongle 仍按既有配对和指定口流程处理。
3. 重新部署 Windows launcher，备份并修改本地 JSON：`wsl.distro`、WSL 仓库路径、`sync.src_wsl_root`、Windows 同步目标、设备解释器、`open_cmd`，以及 attach / verify / 服务命令中所有嵌入的发行版名和路径。只改 `wsl.distro` 不足以迁移；当前模板多处写着 `Ubuntu`。
4. 检查新电脑实际 USB BUSID；当前运行配置仍约定 `1-1`，先插指定口并重新插拔检查。若新电脑确实无法保持这个编号，由开发者统一验证 / 更新 attach、detach 与手册，不让操作者任意选另一个设备；首次共享依[排障步骤](GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)。
5. 重新核对网络、端口转发和防火墙允许范围，按[通用恢复步骤](#92-恢复步骤)从网页、Keyboard、单 EEG、混合双 EEG到停止 / 断流逐层验证；同型号双设备须先完成[第 7.5 节开发与验证](#75-首要开发任务同型号双-gtec-集成)，不能直接作为当前恢复基线。
