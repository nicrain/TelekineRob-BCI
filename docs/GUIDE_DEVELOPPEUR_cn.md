# TelekineRob-BCI 开发者交接手册（中文版）

> 面向接手项目的新实习生 / 开发者，整合部署、代码导读、调试、修改验证和恢复。
> 编写日期：2026-10-08；实现核对基线：`main` 的 `bb71122`。这个提交号用于说明核对范围，不代表之后的最新版本。
> 本文基于仓库代码与已确认使用流程；新电脑重装、Windows + WSL 网络和真机验收尚未在本次文档工作中执行。交付电脑实值与验收结果分别填入第 2、10 节。

产品、需求及算法设计见[技术档案](DOSSIER_TECHNIQUE_cn.md)；日常点击操作见[操作手册](MANUEL_OPERATEUR_cn.md)，用户常见问题见[排障手册](GUIDE_DEBUG_cn.md)。本文不是要求非技术操作者学习全部开发命令。

## 阅读导航

- [1. 接手路线](#1-接手路线)：先运行现有系统，再理解和修改。
- [2. 当前部署登记](#2-当前部署登记)：交付电脑、版本、路径、配置与权限。
- [3. 环境安装与重建](#3-环境安装与重建)：Windows 与 WSL 分开准备。
- [4. 启动与开发调试](#4-启动与开发调试)：正常启动、分开启动网页、离线双流。
- [5. 代码与配置导读](#5-代码与配置导读)：修改应该落在哪一层。
- [6. 分层排障与日志](#6-分层排障与日志)：从设备逐层查到机器人。
- [7. 修改与测试](#7-修改与测试)：现有测试、验证范围与扩展注意事项。
- [8. 更新与发布](#8-更新与发布)：Git、构建、Windows 同步的不同边界。
- [9. 备份与恢复](#9-备份与恢复)：源码之外还需要交接什么。
- [10. 交付清单与接手验收](#10-交付清单与接手验收)：可填写的完成记录。

命令块标明执行环境。Windows PowerShell 命令不能直接放进 WSL Bash；`<…>` 是必须替换的占位符，不要原样执行。安装、校准、网页保存配置、更新及恢复都会改变状态，先停止控制并备份。本文列出的是操作入口，不是已执行成功的证明。

## 1. 接手路线

按以下顺序接手，不必先读完所有历史文档。

1. 与交接者一起确认硬件、指定 USB 口、启动快捷方式和实际配置，填写[部署登记](#2-当前部署登记)。先保留可运行基线。
2. 按[操作手册](MANUEL_OPERATEUR_cn.md)完成一次启动、Keyboard 单独测试 Thymio、EEG 连接、校准、运行和停止；遇到常见问题先按[用户排障手册](GUIDE_DEBUG_cn.md)。
3. 阅读[技术档案的系统设计](DOSSIER_TECHNIQUE_cn.md#3-系统设计)，沿[代码导读](#5-代码与配置导读)追踪一个设备从 LSL 到 `/cmd_vel` 的路径。
4. 在开发环境运行[分层测试](#7-修改与测试)，理解纯逻辑、模拟服务和真机验证的区别。
5. 完成一个范围明确的小修改，补充相关验证；与交接者复核后，再按[更新流程](#8-更新与发布)部署。
6. 实际演练备份恢复，填写[交付清单](#10-交付清单与接手验收)。能启动原电脑，不等于能恢复一台新电脑。

接手前应认识的三个区别：

- **System Control 与实验控制网页不同**：前者管理系统、设备桥和 USB；后者选择角色 / 输出、校准、Start / Stop 和 Teleop。
- **连接与控制不同**：EEG 绿色表示探针收到新鲜样本；图表要在校准或控制管线运行时才更新。Thymio 绿色主要表示 `/dev/ttyACM0` 可见，不证明机器人已经响应。
- **代码与运行配置不同**：网页保存、校准会改 YAML；Windows 本地 `config.json` 不随同步覆盖。交付前必须记录经过确认的配置，而不是沿用仓库中某次运行残留。

## 2. 当前部署登记

### 2.1 项目基线与交付电脑

| 项目 | 仓库可确认的信息 | 交付电脑实值 / 证据 |
|---|---|---|
| 源码与分支 | `https://github.com/nicrain/TelekineRob-BCI.git`；目前文档工作在 `main` | 待填写：运行提交、是否存在本地修改、访问权限 |
| Windows / WSL | 目标工作流为 Windows + WSL2 | 待填写：Windows 版本、WSL 版本、网络模式 |
| Ubuntu / ROS | 项目基线 Ubuntu 24.04 / ROS2 Kilted | 待填写：实际发行版名、系统版本与 ROS 包版本 |
| WSL Python | 基线 Python 3.12；仓库根 `.venv` | 待填写：版本、解释器实际路径、`rclpy` 导入结果 |
| Windows Python | launcher 模板与两台设备的 `python_cmd` 为 `python` | 待填写：launcher / 各桥 / 探针 / VS Code 各自解释器及位数 |
| SDK | Headband 用 `gpype`；Hybrid Black 用 `UnicornPy` | 待填写：版本、安装包来源、授权及恢复方式 |
| Node / npm | 前端使用 Vite 5、React 18；有 npm lockfile | 待填写：已验证版本，不直接改成最新版 |
| USB 与机器人 | usbipd-win；Thymio Dongle 默认 BUSID `1-1`；Linux 路径 `/dev/ttyACM0` | 待填写：usbipd 版本、指定 USB 口照片、Thymio / Dongle 对应关系 |
| Gazebo / Aseba | 仿真使用 ROS Gazebo 包；真机依赖仓库内 ROS Thymio / Aseba 驱动 | 待填写：构建依赖、实际版本、仿真是否作为交付项 |
| 网络与数据 | 端口、配置与日志入口见下文 | 待填写：允许访问的客户端、数据范围、备份位置 |

以下只读命令用于收集基线，不用于替代设备验收。输出若包含用户名、设备名或内网地址，按交接范围保存；账号凭据与 token 不写进公开仓库。

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

Windows 的 `python --version` 仅代表当前终端默认解释器；还要用配置中每一个实际 `python_cmd` 检查。Headband 在 VS Code 选中的解释器要单独登记。

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

`config.json` 的字段和占位符解析见[launcher 配置说明](../windows_launcher/README.md)。手改 JSON 时注意 Windows 路径中的反斜杠需要转义。该文件包含可执行命令，只允许可信维护者修改。

### 2.3 硬件与默认使用约定

- Headband 与 Hybrid Black 均使用电脑自带集成蓝牙。Hybrid Black 官方 USB 蓝牙模块在本项目使用中经常断连，默认不使用；它不是 Thymio 的 USB Dongle。
- 在 Windows 设备管理器检查集成蓝牙模块，警告时先禁用再启用。设备充好电；电脑连充电器使用，主要为降低蓝牙供电 / 省电影响，不是网页绿色状态的充分条件。
- 每对 Thymio / Dongle 通常已经配对，不要例行重配。仅在怀疑配对异常时，按[用户排障手册](GUIDE_DEBUG_cn.md)检查和重新配对。
- 当前约定使用指定 USB 口、BUSID `1-1`。没有 `1-1` 时先重新插拔该口的 Dongle；不引导操作者随意换 BUSID。若更换电脑导致编号无法保持，开发者要验证并统一更新本地连接命令、断开命令、检查流程与两份用户手册。
- 标准组合是 1 个 EEG 对应 1 个角色、另一个 None；2 个 EEG 分配 Speed 与 Steering。角色不是固定绑定某个品牌。

## 3. 环境安装与重建

本节供新电脑或恢复环境使用。已有可运行电脑先做[备份](#9-备份与恢复)，不要为了“统一环境”直接重装或升级。系统安装参考官方文档，项目特定命令以下文及实际配置为准。

### 3.1 Windows 前置条件

1. 准备 WSL2 与 Ubuntu 24.04；登记注册发行版名。不要因为新安装默认版本变化，就替换项目已验证的 Ubuntu / ROS 组合。
2. 安装 usbipd-win 并检查命令可用。USB 共享不是 WSL 内置能力；安装及权限要求参考 [Microsoft USB 连接文档](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)。官方文档的 BUSID 是示例，本项目仍使用 `1-1`。
3. 准备 Python / Pythonw 与 VS Code，确认 `code` 命令可用。按 g.tec 随设备提供的 SDK 资料恢复 `gpype`、`UnicornPy` 和所需驱动 / 授权；Windows Python 版本、位数及 `.pyd` 兼容性须匹配 SDK。
4. 分别检查桥和探针使用的 Python。根 `requirements.txt` 不包含两个厂商 SDK，也不是 Windows 两个桥的完整安装清单。
5. 先用内置蓝牙和已配对设备复现现有桥；不要同时运行同一设备的多个桥，也不要自动替换 SDK 版本来试错。

Windows PowerShell，下面的命令以当前 `python` 确实是该设备解释器为前提；否则替换为已登记路径：

```powershell
python -c "import sys; print(sys.executable); print(sys.version)"
python -c "import pylsl; import gpype; print('Headband imports OK')"
python -c "import pylsl; import numpy; import UnicornPy; print('Hybrid imports OK')"
```

两个设备可以使用不同环境，导入检查也应分别执行。路径含空格时，PowerShell 使用 `& "C:\实际路径\python.exe" ...`；不要把这个 PowerShell 写法直接填入 launcher 的 `python_cmd`，其执行规则见[配置实现](../windows_launcher/config.py)与[命令实现](../windows_launcher/commands.py)。

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

首次构建包含 `src/` 的 Thymio / Aseba 等依赖，不仅是 `thymio_control`。后两条应能找到本工作区的包及 `eeg_control_node.py`、`cmd_vel_fuser.py`。若构建失败，保留完整错误和构建日志，解决依赖后重试；当前手册不宣称在空白电脑上已验证所有第三方构建步骤。

构建用系统 ROS 对应的 Python，不让其他版本的 Python / Conda 环境抢占解释器。特别不要把文档核对电脑上的 Python 版本误当成目标 ROS 的兼容版本。

### 3.4 WSL Python 与前端环境

WSL Bash，在仓库根创建项目环境。已有 `.venv` 时先核对，不覆盖；新电脑重新创建，不复制旧电脑的 venv：

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
5. 对新 Dongle 按[共享检查流程](GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)处理。管理员 PowerShell 用 `usbipd list` 查看 `1-1`；只有 Not shared 才执行 `usbipd bind --busid 1-1`，再确认 Shared。
6. 双击 launcher，按[操作手册](MANUEL_OPERATEUR_cn.md)启动与验收；把实际配置副本受控备份。

共享是使 Windows USB 设备可供 Linux / WSL 使用；Shared 还不等于已接入。System Control 的 Thymio Connect 按当前配置对 `1-1` 执行 attach，使状态成为 Attached，再检查 `/dev/ttyACM0`。正常情况下不需要操作者重复手动 attach。

每次 Start System 同步 WSL 的 `windows_launcher/`（排除 `config.json`）与 `gtec_bridge/` 到 Windows。它不安装 SDK、不安装依赖、不构建 ROS、不执行 Git pull，也不替换机器本地配置。

### 3.6 网络与访问范围

先确保同一电脑的本地访问能工作，再考虑局域网。仓库默认 launcher 监听 `127.0.0.1:8020`，后端监听 `127.0.0.1:8010`，Vite 前端监听 `0.0.0.0:5173` 并代理后端的 `/api`、`/ws`。

launcher 会尝试更新 Windows 的 5173 端口转发；失败并不必然阻止 System State 进入 Running。交付电脑实际使用 NAT 还是其他网络模式、端口转发 / 防火墙权限，都要登记；不要把这台电脑的网络处理办法推广为所有 WSL 配置。

| 后端变量 | 当前默认 / 模板 | 注意事项 |
|---|---|---|
| `WEB_GUI_HOST` / `WEB_GUI_PORT` | `127.0.0.1` / `8010` | 回环绑定仍可能经 Vite 代理被局域网访问 |
| `WEB_GUI_FRONTEND_ORIGIN` | 后端默认本地 origin；launcher 模板设为 `*` | `*` 放宽 origin 校验，不是授权机制 |
| `WEB_GUI_CONTROL_TOKEN` | 默认空 | 部分控制接口支持 token，但不构成全站权限体系 |
| `WEB_GUI_ALLOW_REAL_COMMANDS` | 默认 `true` | 设 `false` 限制进程启动 / 清理；不阻断直接 Teleop 发布 |
| `EXPERIMENT_DATA_DIR` | 仓库下 `experiment_data` | 研究数据目录；不属于操作者日常必学流程 |

仅在经过确认的可信网络范围使用。不能因为后端只监听 loopback、设置了 token 或开启 dry-run，就认为所有控制 / 配置接口受到完整保护。具体代码边界和代理风险见[技术档案的网络边界](DOSSIER_TECHNIQUE_cn.md#312-网络命令与数据边界)。互联网部署不在当前交付承诺内。

## 4. 启动与开发调试

### 4.1 正常启动与停止

交付电脑优先沿用户流程，不要同时手动启动第二套网页或 ROS 管线：

1. 启动 launcher，Start System。
2. 按需连接 EEG 和 Thymio；Headband 打开 VS Code 后选对 venv，点右上角 ▶；Hybrid Black 由 Connect 启动。
3. 在实验控制网页选择设备、角色、输出与指标，校准；校准结束后 Stop，再 Start 正式运行，使节点与眨眼参考读取新配置。
4. 结束时先网页顶部 Stop，再在 Headband 的 VS Code 终端 Ctrl+C，必要时 Disconnect，然后 Stop System / Exit Launcher。

Stop System 默认会终止配置中的整个 WSL 发行版，影响其其他任务；VS Code 启动的 Headband 不属于 launcher 管理的子进程。Restart Web 也不应代替网页 Stop：重启前先停止控制，之后核对残留进程。

### 4.2 分开启动前后端

只在 launcher 没有管理这些服务时使用。以下后端命令会启动实际服务，真实命令默认开启；先确保真机未处于控制状态。

WSL Bash 终端 A，从仓库根开始：

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
cd web_gui/backend
python -m app.main
```

WSL Bash 终端 B，从仓库根开始：

```bash
cd web_gui/frontend
npm run dev -- --port 5173 --strictPort
```

前端访问 `http://localhost:5173`。后端健康入口是 `http://localhost:8010/api/health`，不是 `/health`。`subscriber_ready` 为真仍需检查 `subscriber_error`；服务响应、ROS 就绪、收到 EEG 和机器人动作是不同验收项。

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

### 5.1 从哪里开始读代码

| 层 / 路径 | 职责与阅读重点 |
|---|---|
| [windows_launcher/](../windows_launcher/) | `launcher.bat` 入口；`launcher_server.py` 系统生命周期；`state.py` 状态；`commands.py` 命令；`config.py` 配置；`lsl_probe.py` 新鲜样本检测 |
| [gtec_bridge/](../gtec_bridge/) | Windows 设备 API → LSL；Headband 的重连 watchdog；Hybrid 的采集与重连；厂商依赖从这里排查 |
| [experiment_core.launch.py](../thymio_control/launch/experiment_core.launch.py) | 真机 / 仿真、单 / 双 EEG、角色与话题；终端 teleop 与 EEG 启动条件 |
| [pipeline.py](../thymio_control/thymio_control/pipeline.py) | LSL adapter、特征处理、`POLICIES` 注册，不是整个系统启动入口 |
| [adapters/lsl_raw.py](../thymio_control/thymio_control/adapters/lsl_raw.py) | source_id 解析、StreamInfo、预滤波、窗口提取、单位 |
| [processors/](../thymio_control/thymio_control/processors/) | Welch 频带功率、特征、指标眨眼检测；旧 `blink.py` 不等同当前 `blink_metric.py` 路径 |
| [policies/](../thymio_control/thymio_control/policies/) | EI / TBR / Alpha、归一化、EMA、意图输出 |
| [eeg_control_node.py](../thymio_control/scripts/eeg_control_node.py) | 20 Hz tick、角色运动映射、校准、分析 JSON、LED、断流处理 |
| [cmd_vel_fuser.py](../thymio_control/scripts/cmd_vel_fuser.py) / [watchdog.py](../thymio_control/thymio_control/watchdog.py) | 双路融合与纯逻辑看门狗；缺失一路时不沿用旧动作 |
| [web_gui/backend/app/](../web_gui/backend/app/) | `models.py` 数据校验；`config_store.py` YAML；`command_runner.py` ROS 进程；`signal_subscriber.py` ROS / WebSocket；`main.py` API |
| [web_gui/frontend/src/](../web_gui/frontend/src/) | `App.jsx` 主流程；`api.js` API；组件、hooks 中角色 / 校准 / Teleop 逻辑 |
| [src/](../src/) | ROS Thymio / Aseba 等第三方代码；先查来源和依赖，不为普通 UI 修改重构底层驱动 |

算法公式、滤波、采样、单位、运动映射与校准详见[技术档案 3.5～3.8 节](DOSSIER_TECHNIQUE_cn.md#35-eeg信号处理设计)，本手册不重复维护第二份算法定义。

### 5.2 主链路与接口

Windows 桥 → LSL → RawLslAdapter / Welch → enrich_features → Policy → EEG 节点意图 / Twist。单 EEG 直接发布最终速度；双 EEG 分别发布部分速度，由 fuser 合并：

| 接口 | 语义 |
|---|---|
| `gtec_bci_core4` / `gtec_hybrid_black` | 按 source_id 绑定流；不是用户可见品牌文字 |
| `/eeg_cmd_vel/speed` / `/eeg_cmd_vel/steering` | 双路部分 Twist，后缀是角色；不是 `/steer` |
| `/cmd_vel` | 真机最终速度；仿真最终速度为 `/model/thymio/cmd_vel` |
| `/eeg_analysis` / `/eeg_analysis/speed` / `/eeg_analysis/steering` | 单路 / 双路分析 JSON，后端订阅三条 |
| `/ws/stream` | 最新分析快照 / 状态，不是无损原始 EEG 录像接口 |
| `/ws/teleop` | 网页 Teleop → RosBridge → 最终速度 |
| `/api/config` | 配置及源码文件位置；PUT 使用 `{"patch": {...}}` |
| `/api/system/start` / `/api/system/stop` | 控制管线启动 / 停止；不是 Windows Start System / Stop System |

角色映射：Speed 控制前进，Steering 控制原地转向，眨眼切换转向方向。单设备并不自动兼任两种运动。

网页 Keyboard 是鼠标 / 触摸 Teleop 按钮路径，不依赖 EEG。launch 的 `use_teleop=true` 则启动终端键盘节点并抑制 EEG；网页启动器固定传 `use_teleop=false`。两者不要混为同一个开关。

### 5.3 三套配置边界

1. **Windows 本地 launcher JSON**：路径、解释器、服务、attach / detach 命令；同步排除，不由网页配置 API 管理。
2. **WSL 源码 YAML**：`launch_args.yaml`、`eeg_control_node.params.yaml`、`eeg_control_node.eeg2.params.yaml`；网页保存配置主要写这里。
3. **ROS 安装目录 YAML**：launch 默认从 ROS package share 读取；校准代码会尝试写回源码及安装目录。是否为 symlink 必须实际检查，不能假设两个目录永远一致。

第二份 EEG 文件对应第二条设备配置，不固定等于 Hybrid Black 或 Steering。关闭第二角色以 `run_eeg2` 等配置为准，不要求删除第二份 YAML。

校准在首帧到达后计时 30 秒，至少 50 个有效指标样本；策略参数原位更新，保留 EMA。新校准不会立即刷新已建立的眨眼检测器参考，因此正式运行前 Stop / Start。源码与安装参数不一致时，先查写入结果和路径；不要通过删除整个 `thymio_control/` 目录解决。

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

用户能处理的问题继续沿[排障手册](GUIDE_DEBUG_cn.md)，开发者才进入以下命令与代码检查。

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

使用 WSL 仓库根 `.venv`，先确认依赖。以下是执行入口，不是本次完整测试已通过的记录。

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
| 目标电脑演练 | 真实部署与指定场景 | 未执行的其他场景或临床 / 科研有效性 |

有些测试缺少依赖或数据会 skip，skip 不是通过。`gtec_bridge/test_*.py` 含真实设备 / SDK 调试脚本，不是可在任意环境无风险运行的纯单元测试，不要为了“全覆盖”直接批量执行。

快速回归入口，可在不需要 ROS 的开发环境运行：

```bash
python -m pytest thymio_control/test/test_watchdog.py thymio_control/test/test_cmd_vel_fuser.py thymio_control/test/test_calibration.py thymio_control/test/test_blink_metric.py -q
```

这四个已有文件的 30 项测试在本轮前序文档核对中通过；详见[技术档案的验证口径](DOSSIER_TECHNIQUE_cn.md#41-验证口径)。它们不是整套测试报告，更不是真机验收。

本手册编写时另在 2026-10-08 的 macOS 文档工作环境运行已有 `windows_launcher/tests/test_config.py`、`test_lsl_probe.py`（15 项），以及后端 `app/test_config_store.py`、`test_models.py`（15 项），均通过，用于复核文中配置和探针语义。检查了本地文档链接 / 章节锚点与 Bash 命令块语法；没有执行 Windows 部署、ROS 构建、SDK 导入或真机步骤。

### 7.2 小修改的标准流程

1. 写清复现、期望结果和成功条件；检查 Git 状态，不覆盖操作者已有改动。
2. 从[代码导读](#5-代码与配置导读)确定负责层，先改最小范围。不要顺便重构驱动或历史模块。
3. 为行为变化增加 / 更新对应测试，先运行局部测试，再跑受影响套件；UI 修改增加构建和点击验证。
4. 在仿真或受控环境验证；涉及设备连接、校准、融合、看门狗、Teleop 或进程停止的改动，还要补真机场景。
5. 更新相关手册、配置迁移说明和版本记录，检查 diff 后提交。不能把临时校准值、私有路径、日志或真人数据顺手提交。

代码约定以当前仓库指导与既有风格为准：纯逻辑尽量可测、阈值使用命名常量、失败明确。沿用现有开发指南的代码文件零字面中文约定（Markdown 不受此限）。

### 7.3 扩展时不能漏掉的层

| 修改 | 至少核对的连接点 |
|---|---|
| 新指标 / 新策略 | processors 特征、policy 与 `POLICIES` 注册、节点校准指标选择、后端 policy 校验、前端选项 / 显示、YAML、数值与校准测试 |
| 改 EMA | 当前三个策略类的 `ema_alpha=0.35`；不是现有 YAML / UI 参数。调大更敏捷但更抖，调小更平滑但更慢；核对策略状态与回归测试 |
| 新设备 | Windows API / SDK、桥与 StreamInfo、唯一 source_id、通道 / 采样率 / 单位、device_profiles、adapter 滤波选择、前后端品牌 / 角色映射、launcher 与探针 |
| 改 USB / 电脑路径 | Windows 本地 JSON 中所有嵌入路径、attach / detach / verify 命令、ROS device、操作 / 排障手册及指定口照片 |
| 改停止或断流 | 节点 watchdog、fuser、runner 清理、Windows bridge 生命周期、网页 / WebSocket 异常与真实驱动停车 |

新增设备不仅是登记通道数：RawLslAdapter 会读取 StreamInfo，但 Hybrid 额外滤波选择还与流名称有关。单位应在桥的元数据中明确并实测；当前 Hybrid 桥缺少 `source_unit`，适配器回退到 µV 并告警，实际 SDK 单位仍是待核验项。两个相同型号不能直接共用固定 source_id 来支持任意多设备。

### 7.4 优先保留并验证的安全边界

不要通过关闭保护掩盖问题。当前已识别的边界见[技术档案当前限制](DOSSIER_TECHNIQUE_cn.md#51-当前限制及优先验证事项)，接手时尤其复验：

- 两级 watchdog 的 0.5 秒阈值不是整机实测停车保证；系统仍 Running 时数据恢复可能自动恢复动作。
- 单设备校准后继续运行可能保留旧眨眼参考，正式运行前 Stop / Start。
- 浏览器 Teleop WebSocket 断开时，后端没有明确自动补发零速度；前端松手时补发 Stop 不等于断网急停。
- dry-run / `WEB_GUI_ALLOW_REAL_COMMANDS=false` 不阻断直接 Teleop；做无硬件测试时仍需隔离真机输出。
- 进程清理可能按名称匹配其他 ROS / 网页任务；Stop System 默认终止整个配置发行版。复用工作站前先确认其他任务。

历史设计和 review 只是定位线索，不是当前缺陷清单或已修复证明；本次文档编写没有顺带修复这些运行代码。

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

分支分叉 / 冲突时停止部署并检查原因，不用强推解决。交付版本要记录实际 commit；测试环境可以单独分支开发，但运行版本须经过确认。

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

提交源码和必要文档 / lockfile；运行配置是否纳入提交由交付基线决定。提交前看清暂存文件及 diff，不使用无差别 `git add .` 把实验数据和本地设置带入。

正式发布记录应包含：commit、依赖 / 配置迁移、测试范围与结果、真机是否验证、已知限制、回退方法。中文版先完成后再翻法语，两种语言必须对应同一确认后的实现，而非各自累积不同操作步骤。

## 9. 备份与恢复

### 9.1 必须备份的内容

| 内容 | 为什么需要 | 保存方式 |
|---|---|---|
| 源码 commit 与未提交改动 | 只复制 Windows 桥不足以恢复整个项目 | Git 版本记录；必要本地改动独立保留 |
| 实际 Windows `config.json` 与入口位置 | 机器本地路径 / 解释器不会由同步恢复 | 受控副本，与日期和电脑对应 |
| 三个实际 YAML | 网页保存与校准会改运行配置 | 停止控制后复制；记录对应设备 / 角色 / 指标 |
| SDK、驱动、授权恢复信息 | 不包含在 pip / Git 完整依赖中 | 按机构及厂商允许的方式受控交接 |
| 系统与依赖版本 | 浮动依赖和不同 ABI 可能无法复现 | WSL 与各 Windows 环境的版本清单，前端 lockfile |
| 必要研究数据 / 日志 | 不一定能重新生成；可能含参与者信息 | 明确范围、权限、备份位置与保留期限 |
| WSL 导出（可选） | 为恢复现有环境提供另一路径 | 停机窗口制作；不能替代 Windows SDK / 配置备份 |

可读取并保存 `python -m pip freeze`、`npm ls --depth=0` 及必要 ROS / 系统包版本。它们记录当前环境，不保证每个包都能从公开源恢复，也不能替代 SDK 安装来源与授权说明。

仓库当前 `.gitignore` 只忽略 `experiment_data/analysis/` 等再生成内容，不保证原始研究数据不被 Git 跟踪；已跟踪文件不会因为后来加 ignore 就自动退出历史。数据交付范围由负责人确认，开发者不能自行删历史数据来“清理项目”。

### 9.2 恢复步骤

1. 在新目录 / 受控环境恢复已记录的源码版本，不覆盖尚未备份的工作区。
2. 按[环境重建](#3-环境安装与重建)恢复 ROS、Python、前端和 Windows SDK；新建 venv，不跨电脑直接复制。
3. 恢复 Windows 实际配置，并按新电脑修改路径、发行版名、解释器和嵌入命令；不是盲目替换为模板。
4. 恢复三个 YAML，对照角色、source_id、运动参数与校准条件；必要时重新对真人校准，不能使用合成流校准值。
5. 重建工作区，核对安装路径；恢复 USB 共享与网络访问范围。
6. 先本地网页、再 Keyboard 单独机器人测试、再单 EEG、再双 EEG，最后验证停止、断流 / 恢复与网络故障。
7. 写下恢复耗时、缺失资料、实际版本、验收结果；没有完成这些步骤的备份只能标为“已保存，未验证恢复”。

需要 WSL 整体导出时，按已安装 WSL 的帮助与机构备份流程使用 `wsl --export`，登记发行版名与目标备份文件。导出前停止相关工作；涉及 shutdown / terminate 会中断 WSL 任务。本文不提供自动覆盖 / 删除发行版的恢复脚本。

## 10. 交付清单与接手验收

### 10.1 交付资料

- [ ] 源码访问权限、确认的运行 commit、未提交改动处理结果。
- [ ] 五类正式文档入口；当前中文版优先，法语版及 README 汇总后统一导航。旧安装 / 开发文档仅作参考，避免多份“正式安装指南”并行维护。
- [ ] 第 2 节部署表已填写，包含 Windows 本地 JSON、WSL 路径与所有实际解释器。
- [ ] SDK、驱动、授权恢复渠道、依赖版本与第三方来源 / 许可证资料可获取。
- [ ] Headband / Hybrid Black / Thymio / Dongle / 充电器齐全，指定 USB 口照片和配对关系明确。
- [ ] 已确认的默认设备、角色、指标、速度、真机 / 仿真安排与 YAML 备份。
- [ ] 必要数据、日志、备份位置及访问权限明确；敏感账号 / token 在受控渠道交接，不写进公开文档。
- [ ] 操作者和接手开发者均能凭各自文档完成一轮演练，疑问已回写手册。

### 10.2 现场验收记录

每项记录实测结果、日期、执行人和证据位置；未执行写“未执行”，失败写原因与下一步，不因单元测试通过而勾选真机项。详细需求编号与场景见[技术档案验收](DOSSIER_TECHNIQUE_cn.md#42-目标电脑验收场景)。

| 场景 | 应观察到的结果 | 状态 / 日期 / 执行人 / 证据 |
|---|---|---|
| 冷启动 | 正确 launcher 副本、WSL、同步及前后端可用 | 待执行 |
| Headband | VS Code 正确解释器、手动 ▶ 运行、新鲜 LSL、Ctrl+C 后桥结束 | 待执行 |
| Hybrid Black | Connect / Disconnect 管理桥，新鲜 LSL 和重连行为可观察 | 待执行 |
| 新 Thymio Dongle | `1-1` 的 Not shared → Shared → Attached、`ttyACM0` 可见 | 待执行或注明已有共享基线 |
| Keyboard 单独测试 | 单角色 Keyboard、另一 None、Thymio 输出可控，松手 / Stop 停车 | 待执行 |
| 单 EEG | Speed / Steering 分别符合单角色运动语义 | 待执行 |
| 双 EEG | 两设备 / 两角色、partial 话题及融合；缺一路处理正确 | 待执行 |
| 校准 | 首帧后 30 秒、有效样本、正确文件写入，Stop / Start 后新值生效 | 待执行 |
| 断流与恢复 | 记录真实停车延迟及恢复行为；确认 Running 时是否自动续动 | 待执行 |
| 浏览器 / 网络异常 | 真机 Teleop / 控制异常下的停车行为经过实测，限制已告知 | 待执行 |
| 停止与退出 | 控制、Hybrid、手动 Headband、网页服务的生命周期均确认，无意外残留 | 待执行 |
| 更新与恢复 | JSON 未被同步覆盖、正确新版本生效、备份恢复后能再次使用 | 待执行 |
| 用户 / 开发者独立演练 | 用户按手册使用和排障；开发者定位问题、小修改、测试与恢复 | 待执行 |

### 10.3 尚不能标为完成的事项

目前文档无法代填交付电脑实际配置、SDK / 系统版本、指定 USB 口照片、真实数据单位、完整停车 / 网络故障实测或备份恢复结果。以上必须由交接者与接手者在目标电脑补齐。

本文整合安装与开发交接流程；后续仍需完善用户两份中文版手册及 README 导航，再统一翻译法语。文档齐全、单元测试通过与项目完全验收是三件不同的事。
