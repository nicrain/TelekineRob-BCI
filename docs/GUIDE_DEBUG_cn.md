# GUIDE_DEBUG

[Version française](GUIDE_DEBUG.md)

> 简单操作与排障清单。先检查电脑和设备，再通过总控页面（System Control）和实验网页启动实验。总控页面就是双击 `launcher.bat` 后打开的页面，用于启动系统、连接设备和重启网页服务。

快速跳转：[实验前检查](#1-每次实验前检查) · [正常操作](#2-正常操作) · [EEG 连接与断开](#eeg-设备的连接与断开) · [问题排查](#3-出现小问题时) · [新 Thymio Dongle](#4-第-7-项怎么做检查并共享新的-thymio-dongle)

## 1. 每次实验前检查

启动前先检查蓝牙、电量和 USB 口；角色选择在实验网页打开后检查。

| 检查项 | 怎样确认 | 不通过时 |
|---|---|---|
| 1. 电脑的 Bluetooth 模块 | 右键 Windows 开始按钮，打开 **设备管理器（Gestionnaire de périphériques）**，展开 Bluetooth，检查[电脑自带的蓝牙模块](#eeg-设备使用哪个蓝牙模块)没有黄色或红色叹号、警告。 | 有警告时，右键该蓝牙模块，先 **Désactiver**，再 **Activer**。 |
| 2. 设备电量和电脑电源 | Headband、Hybrid Black、Thymio 都已充好电；电脑连接着充电器使用，以减少 Windows 省电 / 电源管理可能对 EEG 蓝牙连接造成的影响。 | 给设备充电，并接好电脑充电器。 |
| 3. Thymio USB Dongle | Dongle 插在指定的 USB 口。 | 插回指定的 USB 口。 |
| 4. Thymio 配对 | 默认每对 Thymio / Dongle 都已配对，通常无需重新配对。 | 只有怀疑未配对时，才按[官方配对说明（法语）](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/)尝试重新配对。 |
| 5. 角色（Role） | **1 EEG：** 第一行选 `Speed` 或 `Steering`，第二行选 `None`。**2 EEG：** 两行分别选 `Speed` 和 `Steering`。 | 在网页中调整角色后再校准。 |
| 6. Headband 的 Python 环境 | 在 **VS Code** 中确认所选的 Python 解释器是实验使用的 **venv 环境**。 | 按[venv 选择步骤](#在-vs-code-中选择-venv)切换解释器，再运行桥接脚本。 |
| 7. 如果需要使用新的 / 其他的 Thymio | 按[第 4 节](#4-第-7-项怎么做检查并共享新的-thymio-dongle)打开 PowerShell，查看默认 **BUSID `1-1`** 的状态：`Shared` 或 `Attached` 表示已共享。 | 没有 `1-1` 时，重新插拔 Dongle 后再检查；若为 `Not shared`，按[第 4 节](#4-第-7-项怎么做检查并共享新的-thymio-dongle)设为共享。 |

### EEG 设备使用哪个蓝牙模块？

- **Headband：** 连接电脑自带的集成蓝牙模块。
- **Hybrid Black：** 官方附带一个 USB 蓝牙模块，但在本项目的实际使用中，这个模块经常断连，尽量不要使用。本项目默认让 Hybrid Black 也连接电脑自带的集成蓝牙模块，实际连接更稳定。

因此，上面第 1 项检查的是**电脑自带的集成蓝牙模块**。Hybrid Black 附带的 USB 蓝牙模块不要插入；**Thymio 的 USB Dongle 仍需插入指定 USB 口**。

## 2. 正常操作

1. 在 Windows 双击 `launcher.bat`。
2. 在总控页面（System Control）点 **Start System**，等状态变成 **Running**（绿色）。
3. 按下面的[连接与断开说明](#eeg-设备的连接与断开)连接 EEG 设备；Thymio 在总控页面点 **Connect**。等待所需设备状态变为绿色。
4. 在实验网页的 **01 — Input Source** 中按[检查项第 5 项](#1-每次实验前检查)设置 Role；启用的每行 **Device** 选 **EEG**，**Brand** 选实际使用的设备型号，**Metric** 选本次实验的指标。在 **02 — Output Target** 中，真机选 **Thymio**，仿真选 **Thymio Simu**。
5. 点设备的 **Calibrate**。先显示 **Preparing…**，收到数据后开始 30 秒倒计时。双 EEG 时，第一台校准完成后，再校准第二台。
6. 校准完成后，若顶部仍显示 **Running…**，先点 **Stop**；再点顶部 **Start** 启动 EEG 控制。
7. 结束时先点实验网页顶部的 **Stop**。使用 Headband 时，按下面的[断开步骤](#eeg-设备的连接与断开)中断桥接脚本；最后在总控页面点 **Stop System**。

总控页面的 **Start System / Stop System** 用于启停整套系统；实验网页顶部的 **Start / Stop** 用于启停实验控制。设备变绿表示连接成功，分析图在校准或点 **Start** 后更新。

使用中不要拔 USB Dongle、关闭 Bluetooth、移动设备或拔掉电脑充电器。详细使用流程见[操作手册](MANUEL_OPERATEUR_cn.md)。

### EEG 设备的连接与断开

**Headband：由于官方 API 的限制，桥接脚本需要在 VS Code 中手动运行和中断。**

连接时：

1. 在总控页面点 Headband 的 **Connect**，桥接脚本 `gpype_lsl_bridge.py` 会在 VS Code 中打开。
2. 按[venv 选择步骤](#在-vs-code-中选择-venv)确认 Python 环境。
3. 点击 VS Code **右上角的三角形运行按钮（▶）**，运行当前桥接脚本。脚本开始传输数据后，总控页面的 Headband 状态会变为绿色。

断开时：

1. 先点实验网页顶部的 **Stop**。
2. 在 VS Code 中点击运行脚本的终端，按 **Ctrl+C**，中断桥接脚本。
3. 回到总控页面，若 Headband 仍显示可点击的 **Disconnect**，点它。

总控页面的 **Disconnect** 或 **Stop System** 不会替你中断 VS Code 中的 Headband 桥接脚本。

**Hybrid Black：在总控页面直接点 Connect / Disconnect 即可。** 连接时点 **Connect**，断开时先停止实验，再点 **Disconnect**，无需在 VS Code 中手动运行或中断脚本。

### 在 VS Code 中选择 venv

1. 在 Windows 的 VS Code 中打开 Headband 桥接脚本 `gpype_lsl_bridge.py`。
2. 按 **Ctrl+Shift+P**，输入并选择 **Python: Select Interpreter**。
3. 在列表中选择实验使用的现有 **venv** 环境(当前为 c:\Users\Robot\Desktop\gpype_test\venv\Scripts\python.exe)，并在窗口底部确认当前显示的是这个环境。
4. 如果脚本已经在运行，先在其终端按 **Ctrl+C**，再用新选择的环境重新运行。

选择和运行方式见 [VS Code 官方说明](https://code.visualstudio.com/docs/python/environments#select-an-environment)及[脚本运行说明](https://code.visualstudio.com/docs/python/run)。

## 3. 出现小问题时

重新连接设备前，先点实验网页顶部的 **Stop** 停止控制。

### A. 校准卡在 Preparing / 启动后没有波形

1. 按[实验前检查](#1-每次实验前检查)检查电脑的蓝牙模块、设备电量和电脑充电器是否已连接，再检查 Role 和 Brand；使用 Headband 时，还要检查[VS Code 的 venv](#在-vs-code-中选择-venv)。
2. 点实验网页顶部的 **Stop**，再按[连接与断开步骤](#eeg-设备的连接与断开)重新连接对应设备。Headband 需要在 VS Code 中中断脚本后重新运行；Hybrid Black 使用总控页面的 **Disconnect / Connect**。等待设备变绿。
3. 回网页重新点 **Calibrate**。

### B. Thymio 没有动作

1. 先点实验网页顶部的 **Stop**，确认 Thymio 已开机，Dongle 在指定 USB 口；若使用新的 / 其他的 Thymio，按[第 4 节](#4-第-7-项怎么做检查并共享新的-thymio-dongle)检查共享状态。
2. 在总控页面中确认 **Thymio** 是绿色；不是绿色时，先 **Disconnect** 再 **Connect**。
3. 检查 **02 — Output Target** 是否选择了真机 **Thymio**，以及 Role 是否符合[检查项第 5 项](#1-每次实验前检查)。
4. 重新点实验网页顶部的 **Start**。
5. **如果仍没有动作，用 Keyboard 单独测试 Thymio（不使用 EEG）：**

   - 先点顶部 **Stop**。在 **01 — Input Source** 中，第一行 **Role** 选 **Speed**、**Device** 选 **Keyboard**，第二行 **Role** 选 **None**，只保留一个角色；**02 — Output Target** 保持 **Thymio**。
   - 点顶部 **Start**，在 **03 — Teleop Controls** 中用鼠标按住前进或转向按钮，观察 Thymio 是否移动；松开按钮即停止。
   - 如果能够移动，说明 Thymio 的连接和基本控制正常，接下来按[EEG 排查步骤](#a-校准卡在-preparing--启动后没有波形)检查 EEG；如果仍不能移动，继续检查 Dongle、共享状态和配对。
   - 测试结束后点顶部 **Stop**，将 **Device** 改回 **EEG**，恢复本次使用的角色与设备选择，再校准并启动 EEG 控制。

如果怀疑 Thymio 和 Dongle 没有配对，可按[检查项第 4 项的官方配对说明](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/)尝试重新配对。

如果机器人有异常动作，立即点实验网页顶部的 **Stop**，再点总控页面的 **Stop System**。

### C. 总控页面的系统状态不是绿色 / 网页打不开

1. 若显示 **Starting…**，等待启动完成；若显示 **Stopped** 或 **Error**，点 **Start System** 重试。
2. 若系统已为绿色 **Running** 但实验网页不显示，先点 **↻ Refresh**；仍不显示时点 **Restart Web**，等待页面重载。

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
   | `Attached` | 已经共享，而且已连接到 WSL | 无需再设置共享。 |
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

状态与命令说明参考 [usbipd-win 官方文档](https://github.com/dorssel/usbipd-win/wiki/WSL-support)。
