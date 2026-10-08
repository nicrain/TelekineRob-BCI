# TelekineRob-BCI 操作手册（中文版）

[返回中文项目总览](../README_cn.md) · [法语版（待同步本次修订）](MANUEL_OPERATEUR.md)

> 操作者手册：从使用前检查、连接和校准，到启动 EEG 控制、日常排障与收尾。按钮名称保留网页上的英文，便于对照操作。
> 适用于已经安装好的实验电脑。2026-10-08 对照当前代码与已确认使用流程修订；实际电脑的入口位置、USB 口照片及现场演练仍需在交接时补齐。安装、改代码与恢复环境不属于本手册的日常操作。

快速跳转：[异常时先停车](#异常时先停车) · [实验前检查](#实验前检查) · [启动系统](#2-启动系统) · [连接与校准](#3-连接设备与校准) · [启动 EEG 控制](#4-启动-eeg-控制) · [Keyboard 单独测试](GUIDE_DEBUG_cn.md#b-thymio-没有动作) · [故障排查](#6-故障排查) · [停止系统](#7-停止系统)

## 1. 简介与安全

### 认识两个页面

**总控页面（System Control）** 是双击 Windows 的 `launcher.bat` 后打开的页面。侧边栏用于启动系统、连接设备和重启网页服务。

**实验网页（Thymio EEG Control）** 显示在总控页面的主区域，也可通过 **Open in new tab** 单独打开。它用于选择设备与角色、校准、观察信号和控制机器人。

| 按钮位置 | 按钮 | 用途 |
|---|---|---|
| 总控页面侧边栏 | Start System / Stop System | 启动 / 停止整套系统 |
| 实验网页顶部 | Start / Stop | 启动 / 停止 EEG 处理与机器人控制 |

连接设备并校准后，点实验网页顶部的 **Start** 即可启动 EEG 控制，见[第 4 节](#4-启动-eeg-控制)。

### 异常时先停车

1. 机器人动作异常、设备断流或需要排查问题时，先点**实验网页顶部的 Stop**，并确认机器人实际停下。
2. 网页无响应或机器人仍没有停下时，在能够安全操作的情况下关闭 **Thymio 电源**；再停止系统并排查。
3. 不要把刷新页面、关浏览器或设备状态变灰当成已经停车。恢复连接后也不要直接继续，先确认控制已停止，再按正常步骤重新启动。

机器人周围留出空地，不在容易跌落的桌边测试。断流保护不能代替实际停车确认；系统仍在运行时，数据恢复后可能重新产生运动。

### 实验前检查

1. **设备电量和电脑电源：** Headband、Hybrid Black、Thymio 充好电；电脑连接着充电器使用，以减少 Windows 省电 / 电源管理可能对 EEG 蓝牙连接造成的影响。打开本次使用的设备。
2. **电脑蓝牙：** 右键 Windows 开始按钮，打开 **设备管理器（Gestionnaire de périphériques）**，展开 Bluetooth。电脑自带的集成蓝牙模块应没有黄色或红色叹号、警告；有警告时右键该模块，先 **Désactiver**，再 **Activer**。
3. **EEG 蓝牙模块：** Headband 和 Hybrid Black 都默认连接电脑自带的集成蓝牙。Hybrid Black 官方附带的 USB 蓝牙模块在本项目实际使用中经常断连，尽量不要使用。
4. **Thymio Dongle：** 真机实验时，将 USB Dongle 插入指定 USB 口。默认每对 Thymio / Dongle 都已配对，通常无需重新配对；只有怀疑未配对时才按[官方配对说明（法语）](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/)尝试重新配对。
5. **新的 / 其他的 Thymio：** “共享”是把 Windows 上的 USB Dongle 共享给 Linux（WSL）中的机器人控制程序使用。当前连接配置使用 BUSID **`1-1`**，首次使用其 Dongle 时按[新 Dongle 的检查步骤](GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)确认共享状态。没有该编号时，重新插拔到指定 USB 口，再检查一次。
6. **Headband 的 Python 环境：** 在 VS Code 中选择实验使用的现有 venv，具体点击步骤见[Headband 连接与断开](#headband-连接与断开)。

Hybrid Black 附带的 USB 蓝牙模块与 Thymio 的 USB Dongle 是不同设备；**真机实验仍需插入 Thymio 的 Dongle**。

### 佩戴和实验角色

- 按本次使用设备的随附说明佩戴和处理电极；不要把两种设备的佩戴方式混用。校准和使用中保持头戴位置不变。
- 单 EEG：一个人使用一台设备，选择 **Speed**（前进 / 停止）或 **Steering**（转向）；网页第二行 Role 设为 **None**。
- 双 EEG：两台设备分别选择 **Speed** 和 **Steering**，一人负责前进 / 停止，另一人负责转向与眨眼切换方向。
- 负责 **Steering** 的操作者通过眨眼切换左 / 右方向；避免频繁、用力眨眼造成多次切换。
- 实验中不要移动头戴或电极、关闭 Bluetooth、拔 Dongle 或断开电脑充电器。机器人出现异常动作时，按[异常停车步骤](#异常时先停车)处理。

## 2. 启动系统

1. 使用交接好的 Windows 快捷方式，或双击实验电脑上已有的 `launcher.bat`，浏览器打开 **System Control**。入口位置见[本电脑使用信息](#8-本电脑使用信息)。
2. 如果系统为 **Stopped**，在侧边栏 **Operations** 中点 **Start System**。
3. 等待 **Starting…** 变为绿色 **Running**，主区域出现实验网页，设备连接按钮可以点击。
4. 按[第 3 节](#3-连接设备与校准)连接本次使用的设备。

| 系统状态 | 含义 | 操作 |
|---|---|---|
| Stopped | 系统未启动 | 点 Start System |
| Starting… / Stopping… | 正在启动 / 停止 | 等待完成 |
| Running | 网页服务就绪 | 可以连接设备；EEG 控制需另点网页顶部的 Start |
| Error | 启动或服务出错 | 查看页面提示，按[故障排查](#6-故障排查)处理 |

系统为 **Running** 时，原来的 Start System 按钮会显示 **Restart System**。它会重启整套系统，实验进行中不要点击。

## 3. 连接设备与校准

系统为 **Running** 后，在侧边栏 **Devices** 中连接本次使用的设备。Headband 与 Hybrid Black 的连接方式不同。

### Headband 连接与断开

由于官方 API 的限制，Headband 桥接脚本需要在 **Windows 的 VS Code** 中手动运行和中断。

连接时：

1. 在总控页面点 Headband 的 **Connect**，脚本 `gpype_lsl_bridge.py` 会在 VS Code 中打开。
2. 按 **Ctrl+Shift+P**，输入并选择 **Python: Select Interpreter**，选择实验使用的现有 **venv**；在窗口底部确认当前环境。
3. 点击 VS Code **右上角的三角形运行按钮（▶）**，运行当前桥接脚本。
4. 等待总控页面的 Headband 状态变成 **Connected**（绿色）。

断开时：

1. 先点实验网页顶部的 **Stop**。
2. 在 VS Code 中点击运行该脚本的终端，按 **Ctrl+C**，中断脚本。
3. 回到总控页面，若 Headband 仍显示可点击的 **Disconnect**，点它。

总控页面的 **Disconnect** 或 **Stop System** 不会替你中断 VS Code 中的 Headband 脚本。重新运行前先中断旧脚本。

### Hybrid Black 和 Thymio 连接与断开

- **Hybrid Black：** 在总控页面点 **HybridBlack** 的 **Connect**，等待 **Connected**（绿色）；断开时点 **Disconnect**，无需在 VS Code 中手动操作脚本。
- **Thymio：** 真机实验时确认机器人开机、Dongle 在指定 USB 口，然后点 **Thymio** 的 **Connect**。仿真不需要连接真实 Thymio。
- 断开设备前，先点实验网页顶部的 **Stop**。

Thymio 的 **Connect** 会把 BUSID 为 **`1-1`** 的 USB Dongle 从 **Shared** 状态变为 **Attached** 状态，即连接到 Linux（WSL）。

EEG 显示绿色 **Connected**，表示程序检测到设备正在传数据；Thymio 显示绿色，表示 Dongle 已能被控制系统访问，还要通过实际动作确认机器人链路正常。**只连接设备时没有分析图，属于正常情况**；图表在校准或点网页顶部 Start 后更新。

### 选择设备、角色和输出

在实验网页的 **01 — Input Source** 中设置：

| 字段 | 选择 |
|---|---|
| Role | 单 EEG：第一行 Speed 或 Steering，第二行 None；双 EEG：两行分别 Speed 和 Steering |
| Device | 启用的每行都选 EEG |
| Brand | 选择该行实际使用的 g.tec Headband 或 g.tec Hybrid Black |
| Source | LSL Stream |
| Metric | 选择本次实验规定的 Alpha / TBR / EI |

在 **02 — Output Target** 中，真机选 **Thymio**，仿真选 **Thymio Simu**。

单设备选 **Speed** 时只控制前进，选 **Steering** 时只控制原地转向；不是一台 EEG 同时负责两种动作。双设备时，对照每一行的 Brand 和 Role 确认谁负责前进、谁负责转向。其他字段保持本次实验已确认的设置。

### 校准

1. 确认控制已停止、设备 / 角色 / 指标已选好。在 **03 — Real-time Signals** 中找到对应设备的 **Calibrate**，点击一次，无需先点顶部 Start。
2. 先显示 **Preparing…**；收到分析数据后，开始 **Calibrating… Ns** 的 30 秒倒计时。
3. 这段时间按本次实验要求保持正常状态，不移动头戴。等待校准结束，设备栏中显示 **min / max** 校准参考；日常使用不需要手动修改这些数字。一直停在 Preparing 时，按[EEG 排查步骤](GUIDE_DEBUG_cn.md#a-校准卡在-preparing--启动后没有波形)处理。
4. 双 EEG 时先完成第一台，再校准第二台；两台的校准结果分别保存。
5. 校准结束后，若网页顶部仍显示 **Running…**，点顶部的 **Stop**，再按[第 4 节](#4-启动-eeg-控制)启动 EEG 控制。

双 EEG 校准结束后系统通常会自动停止；单 EEG 可能仍在 Running。无论哪种情况，正式控制从一次新的 Start 开始。更换佩戴者、设备或指标后重新校准；中途点 Stop 取消的校准也需要重新完成。若出现 **Calibration produced no new values** 提示，不把倒计时结束当成校准已成功，按[校准提示排查](GUIDE_DEBUG_cn.md#d-校准提示没有新数值--按钮不能点击)处理。

## 4. 启动 EEG 控制

1. 确认已完成[设备与角色选择](#选择设备角色和输出)和[校准](#校准)。
   若跳出 **not calibrated. Start anyway?**（未校准，仍要启动吗？），点取消，先完成校准，不直接跳过。
2. 点**实验网页顶部**的 **Start**，等待状态为 **Running…**。
3. 在 **03 — Real-time Signals** 中确认各设备的信号与指标持续更新，并观察机器人动作。
4. 需要休息时，点网页顶部的 **Stop**；继续时重新点顶部 **Start**。

## 5. 控制进行中

- **Speed：** EEG 指标控制前进 / 停止。
- **Steering：** EEG 指标控制原地转向，眨眼切换左 / 右方向。
- **双 EEG：** 两人分别负责速度与转向；任一设备断流时程序会尝试零速度保护，仍需确认实际停车并点 Stop。
- **03 — Real-time Signals：** 观察图表是否持续更新、设备是否正常。图中 alpha / theta / beta 是分析后的频带功率，不是逐点原始 EEG 电压；箭头表示控制方向 / 强度，不能单凭箭头确认机器人已经移动。

控制运行期间不要重新校准、改设备或重启网页服务。需要调整时先点网页顶部的 **Stop**；使用结束后按[停止系统](#7-停止系统)收尾。

## 6. 故障排查

调试操作的详细点击步骤见[调试说明书](GUIDE_DEBUG_cn.md)。重新连接设备或重启服务前，先点实验网页顶部的 **Stop** 停止控制。

| 现象 | 检查与处理 |
|---|---|
| 校准卡在 Preparing / 启动后无波形 | 按[EEG 排查步骤](GUIDE_DEBUG_cn.md#a-校准卡在-preparing--启动后没有波形)检查蓝牙、电源、角色与设备，再重新连接和校准。 |
| Headband 点 Connect 后一直 Connecting | Connect 只会打开脚本；按[Headband 连接步骤](#headband-连接与断开)选对 venv 并点右上角 ▶。 |
| 设备断流、状态变灰或 Failed | 先 Stop 并确认停车，再按[设备断流处理](GUIDE_DEBUG_cn.md#e-设备断流--状态变灰或-failed)恢复；不要只等待自动重连。 |
| Thymio 没动作 | 按[Thymio 排查与 Keyboard 单独测试](GUIDE_DEBUG_cn.md#b-thymio-没有动作)，区分机器人链路和 EEG 问题。 |
| 已是绿色 Running，但实验网页不显示 | 先停止控制 / 确认停车，再按[网页恢复步骤](GUIDE_DEBUG_cn.md#c-总控页面的系统状态不是绿色--网页打不开)。 |
| Start System 失败，状态为 Error | 按[系统启动排查](GUIDE_DEBUG_cn.md#c-总控页面的系统状态不是绿色--网页打不开)，查看提示与 View Log，不连续点击。 |
| 校准提示没有新数值，或选项 / 按钮不能点 | 按[校准与按钮排查](GUIDE_DEBUG_cn.md#d-校准提示没有新数值--按钮不能点击)，先检查是否仍在运行。 |

## 7. 停止系统

1. **停止 EEG 控制：** 点实验网页顶部的 **Stop**，确认机器人已经停下；网页无响应时按[异常停车步骤](#异常时先停车)。
2. **停止 Headband 脚本：** 使用 Headband 时，在 VS Code 的脚本终端按 **Ctrl+C**。总控页面不会替你中断它。
3. **停止整套系统：** 点总控页面侧边栏的 **Stop System**，等待 **Stopping… → Stopped**。
4. **退出总控页面服务：** 最后点 **Exit Launcher**。这个按钮只退出总控服务，不代替 Stop 或 Stop System。
5. **设备收尾：** 关闭设备电源，按各设备说明清理和收纳电极，收好头戴与 Dongle，按需充电。

关闭浏览器标签页不等于停止系统。Stop System 默认还会关闭此实验使用的 Linux 环境；其中有其他工作未保存时，先保存再停止。

## 8. 本电脑使用信息

交接前在实际电脑补齐以下信息，供操作者直接使用，不从代码模板猜路径：

| 信息 | 当前记录 |
|---|---|
| 启动快捷方式 / launcher.bat 的位置 | 待在实验电脑填写 |
| Thymio Dongle 指定 USB 口 | 待补电脑 USB 口照片或明确位置说明；当前 BUSID 为 `1-1` |
| Headband 的现有 venv | 当前记录与选择步骤见[排障手册](GUIDE_DEBUG_cn.md#在-vs-code-中选择-venv)；换电脑后需核对 |

实际界面截图应来自交付电脑，不用示意图代替确认。英文按钮在两份中文手册中保持一致。
