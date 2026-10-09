# TelekineRob-BCI 简单操作与排障手册（中文版）

[返回中文项目总览](../README_cn.md) · [法语版（尚未同步当前中文版）](GUIDE_DEBUG.md)

> 简单操作与排障清单。先检查电脑和设备，再通过总控页面（System Control）和实验网页启动实验。总控页面就是双击 `launcher.bat` 后打开的页面，用于启动系统、连接设备和重启网页服务。
> 适用于已安装好的实验电脑。按钮保持英文，日常排障不需要安装软件、修改程序或重新创建 Python 环境。

快速跳转：[先停车](#排查前先停车) · [实验前检查](#1-每次实验前检查) · [正常操作](#2-正常操作) · [EEG 连接与断开](#eeg-设备的连接与断开) · [EEG 没有数据](#a-校准卡在-preparing--启动后没有波形) · [Thymio / Keyboard 测试](#b-thymio-没有动作) · [系统 / 网页问题](#c-总控页面的系统状态不是绿色--网页打不开) · [校准 / 按钮问题](#d-校准提示没有新数值--按钮不能点击) · [设备断流](#e-设备断流--状态变灰或-failed) · [新 Thymio Dongle](#4-第-7-项怎么做检查并共享新的-thymio-dongle)

### 排查前先停车

先点**实验网页顶部的 Stop**，确认机器人实际停下，再重新连接、拔插 Dongle 或重启网页。若网页无响应或机器人仍在动，在能够安全操作的情况下关闭 Thymio 电源，再排查。

刷新 / 关闭网页不等于停车。断流时即使程序有保护，也要确认实际停车；系统仍在运行时，设备数据恢复后可能重新产生动作。

## 1. 每次实验前检查

启动前先检查蓝牙、电量和 USB 口；角色选择在实验网页打开后检查。只检查本次使用的设备；仿真不需要真实 Thymio、Dongle 或共享步骤。

| 检查项 | 怎样确认 | 不通过时 |
|---|---|---|
| 1. 电脑的 Bluetooth 模块 | 右键 Windows 开始按钮，打开 **设备管理器（Gestionnaire de périphériques）**，展开 Bluetooth，检查[电脑自带的蓝牙模块](#eeg-设备使用哪个蓝牙模块)没有黄色或红色叹号、警告。 | 有警告时，右键该蓝牙模块，先 **Désactiver**，再 **Activer**。 |
| 2. 设备电量和电脑电源 | Headband、Hybrid Black、Thymio 都已充好电；电脑连接着充电器使用，以减少 Windows 省电 / 电源管理可能对 EEG 蓝牙连接造成的影响。 | 给设备充电，并接好电脑充电器。 |
| 3. Thymio USB Dongle | Dongle 插在指定的 USB 口。 | 插回指定的 USB 口。 |
| 4. Thymio 配对 | 默认每对 Thymio / Dongle 都已配对，通常无需重新配对。 | 只有怀疑未配对时，才按[官方配对说明（法语）](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/)尝试重新配对。 |
| 5. 角色（Role） | **1 EEG：** 第一行选 `Speed` 或 `Steering`，第二行选 `None`。**2 EEG：** 当前支持一台 Headband＋一台 Hybrid Black，两行分别选 `Speed` 和 `Steering`；目前不能直接使用两台同型号设备。 | 在网页中调整角色后再校准。 |
| 6. Headband 的 Python 环境（仅使用 Headband 时） | 在 **VS Code** 中确认所选的 Python 解释器是实验使用的 **venv 环境**。 | 按[venv 选择步骤](#在-vs-code-中选择-venv)切换解释器，再运行桥接脚本。 |
| 7. 如果需要使用新的 / 其他的 Thymio | 按[第 4 节](#4-第-7-项怎么做检查并共享新的-thymio-dongle)打开 PowerShell，查看默认 **BUSID `1-1`** 的状态：`Shared` 或 `Attached` 表示已共享。 | 没有 `1-1` 时，重新插拔 Dongle 后再检查；若为 `Not shared`，按[第 4 节](#4-第-7-项怎么做检查并共享新的-thymio-dongle)设为共享。 |

### EEG 设备使用哪个蓝牙模块？

- **Headband：** 连接电脑自带的集成蓝牙模块。
- **Hybrid Black：** 官方附带一个 USB 蓝牙模块，但在本项目的实际使用中，这个模块经常断连，尽量不要使用。本项目默认让 Hybrid Black 也连接电脑自带的集成蓝牙模块，实际连接更稳定。

因此，上面第 1 项检查的是**电脑自带的集成蓝牙模块**。Hybrid Black 附带的 USB 蓝牙模块不要插入；**Thymio 的 USB Dongle 仍需插入指定 USB 口**。

## 2. 正常操作

1. 在 Windows 双击 `launcher.bat`。
2. 在总控页面（System Control）查看系统状态：**Stopped** 时点 **Start System**，等状态变成 **Running**（绿色）；已经 Running 时直接继续，不点 **Restart System**。**Starting… / Stopping…** 时等待完成；**Error** 时按[系统排查步骤](#c-总控页面的系统状态不是绿色--网页打不开)处理。
3. 按下面的[连接与断开说明](#eeg-设备的连接与断开)连接 EEG 设备；使用真实机器人时，Thymio 在总控页面点 **Connect**。等待所需设备显示绿色 **Connected**。
4. 在实验网页的 **01 — Input Source** 中按[检查项第 5 项](#1-每次实验前检查)设置 Role；启用的每行 **Device** 选 **EEG**，**Brand** 选实际使用的设备型号，**Metric** 选本次实验的指标。在 **02 — Output Target** 中，真机选 **Thymio**，仿真选 **Thymio Simu**。
5. 点击 **Calibrate** 前，把 Thymio 放在平坦、安全的位置，周围留出活动空间，远离桌边、台阶和障碍物；校准结束时可能短暂产生运动命令，双 EEG 自动停止也不能保证完全没有动作。点设备的 **Calibrate**，无需先点顶部 Start。先显示 **Preparing…**，收到数据后开始 30 秒倒计时；期间不移动头戴。双 EEG 时，第一台校准完成后，再校准第二台。中途取消或出现提示时，按[校准问题](#d-校准提示没有新数值--按钮不能点击)处理。
6. 校准完成后，若顶部仍显示 **Running…**，先点 **Stop**，确认机器人实际停下；再点顶部 **Start** 启动 EEG 控制。校准完成后曲线会清空，这本身不表示断连；点 Start 后随新数据重新更新。详细说明见[操作手册的校准章节](MANUEL_OPERATEUR_cn.md#校准)。
7. 结束时先点实验网页顶部的 **Stop** 并确认停车。使用 Headband 时，按下面的[断开步骤](#eeg-设备的连接与断开)中断桥接脚本；最后在总控页面点 **Stop System**，等待 Stopped 后点 **Exit Launcher**。完整收尾见[操作手册](MANUEL_OPERATEUR_cn.md#7-停止系统)。

总控页面的 **Start System / Stop System** 用于启停整套系统；实验网页顶部的 **Start / Stop** 用于启停实验控制。系统 Running 表示网页服务准备好，不表示机器人正在控制。EEG 绿色表示检测到设备数据；Thymio 绿色表示 Dongle 已能被系统访问，仍需通过动作确认。分析图在校准或点 **Start** 后更新，**仅连接时没有图表属于正常情况**。

使用中不要拔 USB Dongle、关闭 Bluetooth、移动设备或拔掉电脑充电器。详细使用流程见[操作手册](MANUEL_OPERATEUR_cn.md)。

### EEG 设备的连接与断开

**本项目的 Headband 桥接脚本需要在 Windows 的 VS Code 中手动运行和中断。**

连接时：

1. 在总控页面点 Headband 的 **Connect**，桥接脚本 `gpype_lsl_bridge.py` 会在 VS Code 中打开。
2. 按[venv 选择步骤](#在-vs-code-中选择-venv)确认 Python 环境。
3. 点击 VS Code **右上角的三角形运行按钮（▶）**，运行当前桥接脚本。脚本开始传输数据后，总控页面的 Headband 状态会变为绿色。

断开时：

1. 先点实验网页顶部的 **Stop**。
2. 在 VS Code 中点击运行脚本的终端，按 **Ctrl+C**，中断桥接脚本。
3. 回到总控页面，若 Headband 仍显示可点击的 **Disconnect**，点它。

总控页面的 **Disconnect** 或 **Stop System** 不会替你中断 VS Code 中的 Headband 桥接脚本。

需要重新运行时，先在原脚本终端 Ctrl+C，确认旧脚本已停止，再点 ▶；不要连续点击运行按钮启动多份脚本。

**Hybrid Black：在总控页面直接点 Connect / Disconnect 即可。** 连接时点 **Connect**，断开时先停止实验，再点 **Disconnect**，无需在 VS Code 中手动运行或中断脚本。

### 在 VS Code 中选择 venv

1. 在 Windows 的 VS Code 中打开 Headband 桥接脚本 `gpype_lsl_bridge.py`。
2. 按 **Ctrl+Shift+P**，输入并选择 **Python: Select Interpreter**。
3. 在列表中选择实验使用的现有 **venv** 环境，并在窗口底部确认当前环境。现有实验电脑记录的解释器路径为 `C:\Users\Robot\Desktop\gpype_test\venv\Scripts\python.exe`；换电脑后选择该电脑实际配置的环境，不照搬这条路径。
4. 如果脚本已经在运行，先在其终端按 **Ctrl+C**，再用新选择的环境重新运行。

不要点 **Create Environment** 重新创建环境。若现有环境找不到、Python 命令没有出现或脚本立即报错，保留提示；不要在未确认环境前反复运行或自行安装缺少的模块。

选择和运行方式见 [VS Code 官方说明](https://code.visualstudio.com/docs/python/environments#select-an-environment)及[脚本运行说明](https://code.visualstudio.com/docs/python/run)。

## 3. 出现小问题时

先按[停车步骤](#排查前先停车)停止控制，再选与现象对应的一节。每完成一步检查状态是否恢复，不要同时改多处设置。

### A. 校准卡在 Preparing / 启动后没有波形

先区分以下正常情况，再排查连接：

- 只是连接了设备，还没有点 Calibrate 或顶部 Start，没有分析图属正常情况；按[正常操作](#2-正常操作)继续。
- 校准刚完成时曲线会清空，这本身不表示断连；点顶部 Start 后应随新数据重新更新。

若校准一直停在 Preparing，或启动后图表仍不更新，再按下面步骤处理：

1. 按[实验前检查](#1-每次实验前检查)检查电脑的蓝牙模块、设备电量和电脑充电器是否已连接，再检查 Role 和 Brand；使用 Headband 时，还要检查[VS Code 的 venv](#在-vs-code-中选择-venv)。
2. 点实验网页顶部的 **Stop**，再按[连接与断开步骤](#eeg-设备的连接与断开)重新连接对应设备。Headband 需要在 VS Code 中中断脚本后重新运行；Hybrid Black 使用总控页面的 **Disconnect / Connect**。等待设备变绿。
3. 回网页确认启用行的 **Device = EEG**、**Brand** 与实际设备一致，重新点 **Calibrate**。双 EEG 逐台校准，结束后 Stop / Start 正式运行。

设备已绿但仍没有图表时，不只看颜色判断成功；保存页面提示，按[问题仍未恢复](#5-问题仍未恢复时)记录实际现象。

### B. Thymio 没有动作

1. 先点实验网页顶部的 **Stop**，确认 Thymio 已开机，Dongle 在指定 USB 口；若使用新的 / 其他的 Thymio，按[第 4 节](#4-第-7-项怎么做检查并共享新的-thymio-dongle)检查共享状态。
2. 在总控页面中确认 **Thymio** 是绿色。需要重新连接且显示 **Disconnect** 时，先点它再点 **Connect**；只有 **Connect** 时直接点 Connect。
3. 检查 **02 — Output Target** 是否选择了真机 **Thymio**，以及 Role 是否符合[检查项第 5 项](#1-每次实验前检查)。
4. **用 Keyboard 单独测试 Thymio（不使用 EEG），先判断机器人链路是否正常：**

   - 先点顶部 **Stop**。在 **01 — Input Source** 中，第一行 **Role** 选 **Speed**、**Device** 选 **Keyboard**，第二行 **Role** 选 **None**，只保留一个角色；**02 — Output Target** 保持 **Thymio**。
   - 点顶部 **Start**，在 **03 — Teleop Controls** 中确认显示 **WS connected**，用鼠标短暂按住前进或转向按钮，观察 Thymio 是否移动。虽然选项名是 Keyboard，这里使用的是网页按钮，不需要按电脑键盘方向键。
   - 松开按钮时程序会发送停止命令，确认机器人实际停下；需要时点面板中间的 **■** 或网页顶部 **Stop**。若显示 **WS disconnected**，先不要测试运动，按[网页问题](#c-总控页面的系统状态不是绿色--网页打不开)恢复。
   - 如果能够移动，说明 Thymio 的连接和基本控制正常，再检查 EEG 是否持续传数据、角色与指标是否正确、校准是否完成；没有波形时按[EEG 排查步骤](#a-校准卡在-preparing--启动后没有波形)处理。有数据但没有动作，也可能是当前指标没有产生运动命令，不直接判定设备故障。如果 Keyboard 仍不能控制移动，继续检查 Dongle、共享状态和配对。
   - 测试结束后点顶部 **Stop**，将 **Device** 改回 **EEG**，恢复本次使用的角色与设备选择，再校准并启动 EEG 控制。

如果怀疑 Thymio 和 Dongle 没有配对，可按[检查项第 4 项的官方配对说明](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/)尝试重新配对。

如果机器人有异常动作，按[停车步骤](#排查前先停车)处理。Keyboard 测试能区分基本机器人链路和 EEG 问题，但一次能动不代表所有停止 / 断网场景都已通过。

### C. 总控页面的系统状态不是绿色 / 网页打不开

1. 先停止控制并确认机器人停下；实验网页打不开或 Stop 无响应时，先按[停车步骤](#排查前先停车)处理，不直接刷新来停车。
2. 若显示 **Starting… / Stopping…**，等待完成，不连续点击；显示 **Stopped** 时点 **Start System**。若为 **Error**，先看底部提示，用 **View Log** 查看信息，再重试一次 Start System。
3. 系统已为绿色 **Running** 但实验网页不显示时，点 **↻ Refresh**；仍不显示时点 **Restart Web**，等待页面重载。也可用 **Open in new tab** 检查网页是否能单独打开。
4. 网页恢复后重新确认 Role、Device、Brand、Metric 与 Output Target，再按[正常操作](#2-正常操作)校准和启动。不要因为页面重新出现就认为之前的控制状态也正确恢复。

重复失败时保留提示与日志，不连续重启系统。电脑充电器主要与 EEG 蓝牙供电有关，不是系统状态变绿的修复步骤。

### D. 校准提示没有新数值 / 按钮不能点击

1. Role、Brand、Metric、Calibrate 等不能点击时，先看顶部是否为 **Running… / Preparing… / Calibrating…**。运行或校准期间部分设置会锁住；需要调整时先点 **Stop**。
2. 更换佩戴者、设备或指标，或者中途 Stop 取消校准后，重新逐台校准，不直接使用中断的结果。
3. 若显示 **Calibration produced no new values (see node log)**，先 Stop，检查设备是否持续传数据，按[EEG 排查](#a-校准卡在-preparing--启动后没有波形)恢复后再校准一次。倒计时结束、数字没有变化，都不能单独确认本次校准成功；重复出现时保留完整提示。
4. 双角色模式下，若 Start 时提示 **not calibrated. Start anyway?**，点取消，先完成校准。这个提示只用于双角色；没有弹窗不代表校准已成功。

不要靠手动改 **min / max** 数字绕过校准错误或数据故障。已完成自动校准、仅需要微调控制映射时，按[操作手册的手动微调步骤](MANUEL_OPERATEUR_cn.md#手动微调参考值可选)处理。

### E. 设备断流 / 状态变灰或 Failed

下面的恢复步骤针对 **EEG设备**。如果变灰或显示 Failed 的是 **Thymio**，先按[停车步骤](#排查前先停车)确认停车，再按[Thymio排查步骤](#b-thymio-没有动作)检查连接和Dongle，不操作EEG桥接脚本。

1. 先点网页顶部 **Stop** 并确认停车，尤其双 EEG 不要只等待一台设备自己恢复。
2. 按[实验前检查](#1-每次实验前检查)确认开机、电量、电脑充电器与集成蓝牙；Headband 再确认原脚本是否仍在运行、是否报错。
3. 按[连接与断开步骤](#eeg-设备的连接与断开)重新连接对应设备。Headband 先 Ctrl+C 再 ▶；Hybrid Black 能点 Disconnect 时先断开再 Connect，只有 Connect 时直接点它。
4. 确认设备重新传数据，Role、Brand 和 Metric 仍正确后，按[正常操作](#2-正常操作)重新完成校准，再点顶部 **Start**。不要把状态变绿当成可以在未确认停车的情况下继续实验。

## 4. 第 7 项怎么做：检查并共享新的 Thymio Dongle

这里的“共享”，是把插在 Windows 电脑上的 Thymio USB Dongle 共享给 Linux（WSL）使用，让运行在 Linux 中的机器人控制程序能够访问它。

首次使用新的 / 其他的 Thymio 时，按下面步骤操作。**当前总控页面的连接和断开配置都使用 BUSID `1-1`**，因此需要检查并共享这个编号。

### 查看是否已经共享

1. 确认实验已停止，将这个 Thymio 的 USB Dongle 插入指定 USB 口。
2. 点击 Windows 的 **开始菜单**，输入 `PowerShell`。
3. 右键 **Windows PowerShell**，选择 **以管理员身份运行（Exécuter en tant qu’administrateur）**；若弹出确认窗口，点 **是（Oui）**。
4. 在打开的窗口里复制下面这一行，按 **Enter**：

   ```powershell
   usbipd list
   ```

5. 窗口会显示 USB 设备列表。先在 **BUSID** 列找到默认编号 **`1-1`**，查看这一行的 **STATE**（状态）。

   **如果没有 `1-1`：** 确认使用的是指定 USB 口，拔下 Dongle 后重新插回，再输入 `usbipd list` 并按 Enter，检查该编号是否出现。

6. 看这一行的 **STATE**，决定下一步：

   | 显示的状态 | 含义 | 下一步 |
   |---|---|---|
   | `Shared` | 已经共享 | 回到总控页面点 **Connect**。 |
   | `Attached` | 已经共享，而且已连接到 WSL | 无需再设置共享；返回总控页面确认 Thymio 的连接状态。 |
   | `Not shared` | 还没有共享 | 按[下面的共享步骤](#如果显示-not-shared)操作。 |

在总控页面（System Control）点 Thymio 的 **Connect**，就是把 BUSID 为 **`1-1`** 的 USB 设备（Thymio 的 USB Dongle）从 **Shared** 状态变为 **Attached** 状态，即连接到 Linux（WSL）；连接成功后，可再次用 `usbipd list` 确认。

### 如果显示 Not shared

1. 如果 **BUSID `1-1`** 的状态为 `Not shared`，在刚才的 PowerShell 窗口中输入下面的命令，然后按 **Enter**：

   ```powershell
   usbipd bind --busid 1-1
   ```

2. 再输入下面这一行，按 **Enter**：

   ```powershell
   usbipd list
   ```

3. 再次找到 **BUSID `1-1`** 这一行。它的 **STATE** 应变成 **Shared**，这就说明设置成功。
4. 回到总控页面点 Thymio 的 **Connect**。

若命令报错、编号仍未出现，或状态没有变成 Shared，先保留完整提示，不继续反复 bind，也不要改成另一行的编号。共享成功只表示 Dongle 可以交给 Linux 使用；Thymio 本身是否能动，仍按[Keyboard 单独测试](#b-thymio-没有动作)确认。

状态与命令说明参考 [usbipd-win 官方文档](https://github.com/dorssel/usbipd-win/wiki/WSL-support)。

## 5. 问题仍未恢复时

保持控制停止，保留以下少量信息，方便再次复现与定位，不需要阅读程序源码：

- 出现问题的步骤，以及页面上的完整提示 / 截图。
- System State、三个设备状态，以及本次实际使用的设备、Role 和 Output Target。
- 使用 Headband 时，VS Code 所选解释器与脚本终端最后的报错；系统 / 网页问题保留 View Log 的相关内容。
- 新 Dongle 问题保留 `usbipd list` 中 `1-1` 的状态或命令报错。

不要为了消除提示而改程序、删除文件、重建 venv 或手动更换 USB 编号。暂时不用系统时，按[停止与收尾步骤](MANUEL_OPERATEUR_cn.md#7-停止系统)关闭，别只关浏览器。
