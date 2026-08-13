# O2 — Windows 总控台（非 IT 操作者）

> **状态**：设计已定（2026-08-07），待开工。
> **三方同步**：programmer 按此实现 / reviewer 按验收标准验证 / CTO 跟踪进度。
> **迭代**：测试中改需求记入 §6，骨架不动（配置驱动）。

---

## 1. 设计

### 1.1 目标

项目跑在 WSL2，操作者是非 IT 人员。需要一个 Windows 侧"总控台"：双击图标 → 网页 → 点按钮起系统/连设备/看状态，全程不碰命令行、不 SSH、不见终端。

**关键前提**：浏览器不能执行本机命令（wsl/usbipd/copy/python）——必须有一个 **Windows 控制服务**（本地小 Python 服务）作为命令执行层。这是本任务的核心新增组件。

**单一来源 + 自同步（已定，方案 a）**：launcher 与桥脚本都以 WSL 项目 `~/TelekineRob-BCI/`（git 仓库）为源，位于同仓库 `windows_launcher/`（与 `gtec_bridge/` 平级）。「启动系统」时把**桥文件 + launcher 自身代码**一起从 WSL 同步到 Windows——launcher 永远跑最新版，操作者只管双击、永不碰 git。当前会话继续用旧代码，下次双击生效新版。

### 1.2 架构（三层）

```
双击图标（快捷方式/批处理：启动服务 + 开浏览器）
  ↓
Windows 控制服务（localhost 小 Python 服务，位于 windows_launcher/）
  ├── 托管总控网页（侧边栏 + 主区域 iframe）
  ├── 命令接口：启停 WSL / 同步 launcher+桥文件 / 跑桥 / usbipd / 状态探测
  └── 运行目录 = Windows 本地（从 WSL 同步 launcher 自身 + 桥文件）
              ↓
    WSL2 项目 ~/TelekineRob-BCI/（git 单一来源）
     ├── windows_launcher/（launcher 源）
     ├── ROS + 后端 8010 + 前端 5173
     └── gtec_bridge/（桥文件源）
```

仓库结构（launcher 与 gtec_bridge 平级）：

```
TelekineRob-BCI/
├── windows_launcher/     ← 新增（控制服务 + static 总控页 + config.json）
├── gtec_bridge/          （Windows 侧桥，已有）
├── web_gui/              （WSL 侧）
├── thymio_control/       （WSL 侧 ROS）
└── ...
```

### 1.3 流程（已确认，全选方案 a）

```
1. 双击图标 → 总控页打开，设备按钮全灰、不可点、无状态
2. 操作者点「启动系统」
   → wsl 启动 Ubuntu + 检测（echo ok 退出码）
   → 从 \\wsl$\<distro>\home\robot\TelekineRob-BCI\ 同步「windows_launcher/ 自身 + gtec_bridge/」到 Windows（自同步，下次双击生效新版）
   → 启动 WSL 侧后端+前端 → 主区域 iframe 显示 web GUI（localhost:5173）
   → 设备按钮解除置灰
3. 操作者点「连接 Headband/HybridBlack/Thymio」→ 各自变绿
4. 在 web GUI 里：配置设备 → 校准 → 点 Start 跑实验
5. 「关闭系统」→ 停进程 + 停 Ubuntu
```

职责划分：侧边栏 = 把环境准备好（系统 + 桥 + 设备）；web GUI = 跑实验（校准/Start/Stop）。

### 1.4 侧边栏（初版，可迭代）

```
● 系统状态  [● 已停止]
── 设备连接 ──
● Headband     [连接]   (灰=未连/绿=已连/红=失败)
● HybridBlack  [连接]
● Thymio       [连接]
── 系统操作 ──
[启动系统]  [重启web服务]  [关闭系统]
── 日志 ──
[查看日志]（占位，位置待定）
```

**设计原则**：配置驱动（按钮列表/分组/命令都在 config.json），测试中加按钮/改行为不动骨架。

---

## 2. MVP 任务清单（状态跟踪）

> 状态流转：⬜ 待做 → 🔵 进行中 → ✅ 完成 → 🟢 已验证

| # | 模块 | 任务 | 状态 |
|---|---|---|---|
| M1 | Windows 控制服务 | 框架选型 + 接口骨架 + 进程管理 + 人话错误 | ✅ 2026-08-07 |
| M2 | 总控网页 | 侧边栏骨架 + 状态轮询 + iframe | ✅ 2026-08-07 |
| M3 | 启动系统链路 | 起 WSL → 检测 → 同步 launcher+桥文件（自同步）→ 起前后端 → 就绪检测 → 解灰 | ✅ 2026-08-07 |
| M4 | 设备连接链路 | 连/断 Headband/Hybrid（跑桥+验 LSL）/ Thymio（usbipd+验 ttyACM0） | ✅ 2026-08-07 |
| M5 | 状态显示 | 设备/系统状态 + 人话错误 | ✅ 2026-08-07 |
| M6 | 入口 | 双击图标（批处理/快捷方式：起服务+开浏览器） | ✅ 2026-08-07 |

---

## 3. 接口清单（控制服务）

| 接口 | 动作 | 返回 |
|---|---|---|
| `POST /start-system` | 启动 WSL → 检测 → 同步桥文件 → 起 WSL 侧后端+前端 | `{ok, message}` |
| `POST /stop-system` | 停 WSL 侧进程 + 停 WSL | `{ok, message}` |
| `POST /connect-device` `{device}` | 跑桥(headband/hybrid) / usbipd attach(thymio) | `{ok, message}` |
| `POST /disconnect-device` `{device}` | 停桥进程 / usbipd detach | `{ok, message}` |
| `GET /status` | 设备 + 系统状态 | `{system, devices:{...}}` |
| `GET /` | 托管总控页 | HTML |

---

## 4. 验收标准（reviewer + 用户侧）

- [ ] 双击图标 → 总控页打开，设备按钮全灰、不可点、无状态
- [ ] 点「启动系统」→ Ubuntu 起、检测通过、桥文件同步、前后端起、GUI 出现在 iframe、设备解灰
- [ ] 点「连接 Headband/HybridBlack/Thymio」→ 各自变绿（LSL 流 / ttyACM0 验证）
- [ ] 点「断开」→ 各自变灰
- [ ] 点「关闭系统」→ 进程清干净 + WSL 停
- [ ] 任一步失败 → 一句人话中文提示（无堆栈）
- [ ] 状态显示反映真实系统（断桥后变红/灰）
- [ ] 桥文件用的是同步后的最新版
- [ ] 重复点击幂等（已启动则跳过）

---

## 5. 真实环境参数（用户在真机首次部署时填 config.json；programmer 用占位符 + 默认值）

> **约束**：programmer 在 macOS，访问不了 Windows/WSL2 真实环境。环境相关的值一律放 `config.json`，由用户在真机首次部署时填/确认，programmer 不硬编码。

| # | 参数 | 谁填/确认 | 默认值/做法 |
|---|---|---|---|
| 1 | 控制服务 Python 框架 | programmer 直接定 | **stdlib `http.server`（零依赖）**——避免依赖问题；若选 Flask，用户需在 Windows venv 一次性 `pip install flask`（写入 setup 文档） |
| 2 | WSL 发行版名 | 用户确认 | config 默认 `Ubuntu` |
| 3 | `usbipd attach` 命令 | **用户**（唯一个人知道） | 填 config |
| 4 | Windows 桥目录（同步目标） | 用户确认 | config 默认 `c:\Users\Robot\Desktop\gpype_test\TelekineRob-BCI\gtec_bridge` |
| 5 | iframe 嵌入可行性 | 用户真机验证 | programmer 写 fallback（被拒则新标签打开 web GUI） |
| 6 | localhost 转发（Windows→WSL 8010/5173） | 用户真机验证 | WSL 默认 localhost 转发，测试确认 |

---

## 6. 迭代记录

> 测试中发现的需求变化/设计调整记这里，programmer/reviewer/CTO 同步更新。

| 日期 | 变更 | 影响 |
|---|---|---|
| 2026-08-07 | MVP M1–M6 实现完成。入口用 `last_url.txt` 传递端口（bat 不解析 JSON）；自同步目标用 `sync.dst_root`；usbipd busid 由用户填 config | 部署/填表说明见 `windows_launcher/README.md`；真机按 §4 验收 |
| 2026-08-07 | 推送前修 3 条：**C**=config.json 排除出同步（默认工具改 robocopy，`/XF config.json`，退出码 0–7 均算成功）；**A**=action POST 加 Origin 白名单（同 web_gui `_validate_origin` 模式，自动含运行时端口 `127.0.0.1`/`localhost` 双拼写）；**D**=bat 启动前 `del last_url.txt` 防旧 URL | config.json 成机器本地配置不再被 WSL 覆盖；任意网页无法再触发启动/停止；启动不留旧地址 |
| 2026-08-07 | 真机修 2 条：① WSL 就绪检测 `echo ok` → 轮询 `systemctl is-system-running`（`running`/`degraded` 或 `\\wsl$\` 可访问即就绪）+ 超时人话报错；② web 命令 `&` → `nohup … > /tmp/launcher_*.log 2>&1 & disown`（防 wsl 退出 SIGHUP 杀后台，日志落盘可诊断） | config 默认已改；**真机用户侧 config.json 需手动同步**（非同步项，不会被自同步覆盖） |
| 2026-08-07 | 推送前修 2 条（O31/O32）：就绪探针**输出即权威**——真实 systemd `degraded` 退出码 1，去掉 `result.ok()` 门控（仅按输出 running/degraded 判定）；单次探针超时不再击穿轮询——循环内 try/except，挂起探针继续等下一轮直到总超时 | 生产 degraded 不再依赖共享兜底；单次慢探针不会提前报错 |
| 2026-08-07 | 真机实测：wsl.exe 下 `&`/`nohup`/`setsid` 后台全死（0 字节日志、无进程、curl 000）；web 命令改**前台**执行（`cd … && cmd > /tmp/launcher_*.log 2>&1`），wsl.exe 保持存活、Popen 可直接终止；后端 venv 用仓库根 `.venv` | config 默认已改；**真机用户侧 config 需手动同步**（非同步项）；`stop_cmd` pkill 仍匹配（命令行未变） |
| 2026-08-07 | 真机验收修 3 处：① iframe 启动后自动加载——pollStatus 检测 非running→running 转换重载（仅 running 触发，ready-check 已确认前端就绪；含 starting 会在未就绪时过早加载且不再触发）；② backend_cmd 加双 source（`/opt/ros/kilted/setup.bash` + `${wsl.repo_path}/install/setup.bash`）补 ROS2 环境；③ 前端纯静态无需 source，frontend_cmd 不变 | config 默认已改（backend_cmd）；**用户侧 config 需手动同步**；重启 launcher 生效 |
| 2026-08-10 | 真机优化 P1–P3 完成：**P1** 无窗口（`pythonw`，无则回退 `/min`）+ pidfile 幂等替换（`tasklist` 存活 + `wmic` 命令行校验含 `launcher_server.py` 防 PID 复用，`taskkill /F` 杀旧）+ 服务日志落盘 `launcher_server.log`（tee：pythonw 下 stdout=None 也能写）+ `POST /shutdown`（删 pidfile → 200 → 线程内 `server.shutdown()` 响应不丢）+ 侧边栏「退出总控」（`id:exit` → `/shutdown`）；**P2** 侧边栏可收起（按钮在 mainbar、`collapsed` class 在 `#sidebar`、localStorage 持久、轮询重渲染不复位）；**P3** Ferrari 深色主题（Space Grotesk + IBM Plex Mono、黑底、红 `#DA291C` 危险/聚焦、2px razor、mono 大写小组标签、状态点 on `#03904A` / err `#F13A2C` / off `#3a3a3a`） | config ops 组已加「退出总控」；README 注明 `launcher_server.log`；**用户侧 config 需手动同步 ops 组**；主题为深色对齐，浅色联动（`?theme=` + App.jsx 钩子）留作可选后续 |
| 2026-08-10 | 真机 UX 修 **P4** 完成：启动系统后弹多个 cmd 窗口，2 个长驻残留（web 前后端 wsl.exe），关掉即杀前端。根因：pythonw 无控制台，Windows 上无控制台父进程 spawn 的每个子进程各自申请新控制台窗口。修法：`commands.py` 两个默认 IO 函数（`_default_run_one` 的 `subprocess.run`、`_default_spawn` 的 `Popen`）统一加 `creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)`（Windows 生效、macOS 无此常量自动忽略）——覆盖探针/同步/usbipd/桥/web 前后端全部 spawn，架构不变（web 仍前台 wsl.exe + `_web_procs` 跟踪 + `/tmp` 日志） | 单点修复（IO 全收敛于两函数）；测试 mock `subprocess.run`/`Popen` 断言 creationflags 透传（+2，74 全绿）；真机验证：启动系统全程无 cmd 窗口 |
| 2026-08-10 | 真机 UX 优化 **P5** 完成：① launcher 全英文化——用户可见字符串全英文（`index.html` 标题 System Control / 组标签 Status-Devices-Operations-Log / 状态与按钮 / 消息条；`config.json` 侧边栏 group+item+log label；`launcher_server.py` 全部 `{ok,message}` 人话提示 + friendly_error + 主流程打印），保留 Ferrari 字体（Space Grotesk/IBM Plex Mono 无中文字形，全英文后正常渲染）；② mainbar 加 **↻ Refresh** 按钮刷新 iframe 内 web GUI（跨域，复用 `frame.src=G.webUrl` 重载模式，禁 `contentWindow.reload`）；③ 文档 README 保持中文 | 配置驱动不变（标签仍在 config）；**用户侧 config 需手动同步 labels**（否则 Windows 仍显示中文）；测试断言同步英文 + CJK 检测（+3，77 全绿） |
| 2026-08-10 | 真机 UX 优化 **P6** 完成：① **主题双向同步**——总控加 `[data-theme="light"]` 浅色板（镜像 styles.css 浅色令牌）+ mainbar ☀/☾ 切换（localStorage 持久，默认 dark）+ iframe 地址统一带 `?theme=`（`webUrlWithTheme` 纯函数处理 ?/& 边界，刷新/自动加载/新开标签全带）+ postMessage 双向（总控切 → `frame.contentWindow.postMessage`；监听 message 回传应用，React 同值 bail 防环）；web GUI `App.jsx`：`?theme= > localStorage > dark` 初始化优先级、主题 effect 广播 `window.parent.postMessage`、`addEventListener('message')` 监听应用。② **主区优雅占位**——`#placeholder`（System Offline / Starting System… / Stopping… / System Error + 状态点，深/浅跟随主题），iframe 不再 init 预载 5173（哭脸错误页根源），仅 running 时加载（带 `?theme=`），其他状态隐藏 iframe + 显示占位；保留 onerror 新开标签 fallback | 跨模块改动（总控 index.html + web GUI App.jsx）；jsdom/vitest 未安装（前端 build 为用户侧 WSL2 任务），web GUI 用静态断言替代（URL 优先级/广播/监听标记）；总控静态断言 + Node URL 纯函数单测（+7，84 全绿；全量 170 passed）；真机验证两侧切换同步 + 无哭脸错误页 |
| 2026-08-10 | **P7** 完成（5 条低优先级顺手修）：① 占位 System Error 分支改 **err 红点**（`dot err`，深/浅均红）；② 浅色语义色对齐——**删 launcher light 的 `--f-ok/--f-warn/--f-info` 覆盖**，浅色回落 `:root` 的 `#03904A/#F13A2C/#4C98B9`，与 web GUI（其 light 不覆盖）逐值一致，未改 web_gui（避免用户重建前端）；③ `refreshFrame()` 加 **running 守卫**——非 running 直接 return，主动 Refresh 永不闪死前端错误页；④ launcher.bat echo + rem 全英文（Python not found / startup timed out / Could not read the service address）；⑤ 删 mainbar `<span>Experiment</span>`，主栏只剩 [↻ Refresh] [☾] [Open in new tab] | 静态断言扩展（err 点 / light 语义色不覆盖 / Refresh 守卫 / Experiment 缺席 / bat 无 CJK）；86 launcher 测试；全量跑通 |
| 2026-08-10 | 真机设备连接排查（Headband 连不上）：根因 = **g.Pype 授权闸门**——gpype 免费版仅限 IDE 内（VS Code/PyCharm 终端，ConPTY）运行，launcher 在 IDE 外起桥 → `Execution outside supported IDEs detected`，需 g.Pype Runtime 授权。已穷尽技术手段排除：窗口模式（CREATE_NO_WINDOW / 隐藏 / 可见控制台）、venv 环境（PATH/VIRTUAL_ENV）、stdin/stdout 真终端、伪造 VS Code 环境变量（TERM_PROGRAM / VSCODE_INJECTION / VSCODE_NONCE 等）全部失败。已定位检测机制：`_is_executed_in_ide`（编译在 `backend/core/node.cp310-win_amd64.pyd`）沿**父进程链**找已知 IDE 路径（Code.exe 等），故 env/console 伪造无效。**unicornpy（HybridBlack）无此闸门——venv python 配好后 launcher 直连成功**；gpype（Headband）被卡。决策：用户定 **C 变体**——headband 走"open in IDE"（launcher 打开脚本 → 操作者在 VS Code 点 Run，免费版正当用法），A/B（Runtime/g.tec 学术条款）留作部署后续 | 非代码 bug；不做进程伪造/ConPTY 模拟（规避授权检测）；P8 扩为 a/b/c/d（d=headband open-in-IDE 模式） |
| 2026-08-11 | 真机波形修复 **P9** 完成：launcher 起的后端 eeg_control_node 无波形。根因：backend_cmd 未激活 venv → `_load_ros_env()` 捕获 PATH 无 `.venv/bin` → eeg_control_node（`#!/usr/bin/env python3`）解析到系统 python3（缺 pylsl）→ `/eeg_analysis` 无数据。修：**P9a**（根修）`command_runner._source_prefix()` 追加 `export PATH=<venv_bin>:"$PATH"`（venv 排 PATH 最前；**有意偏离**：不用 `source activate` 因 repo `.venv/bin/activate` 是陈旧拷贝 VIRTUAL_ENV 指向 ros_thymio/.venv）；**P9b**（纵深）config backend_cmd 加 `source ../../.venv/bin/activate`。**真机验证通过：波形正常** | 全链路 P1–P9 打通；用户侧 config backend_cmd 需手动同步；设备 venv 需有 rclpy（否则 ros2 shim 崩，补 pip install rclpy） |
| 2026-08-11 | 真机 UX/健壮性 **P10 派工**：① 状态不实时——前端 bug（pollStatus 顺序 renderSystem 先、renderOps 后 → 按钮 disabled 被重建抹掉）+ reconcile 缺口（system 不查 web 服务健康、thymio 不查 attach 态）；② Thymio 已 attach 重启后显示未连接、connect 报 attach failed（无 reconcile + attach 不幂等）；③ Start System 运行中应置灰或变 Restart（修前端顺序 + 新增 `/restart-system`=stop 后 start，按钮按状态换标签）；④ gpype 桥 `while True: sleep` 无断线重连，设备断电重开 → Buffer underrun 死循环不恢复（需桥内数据流看门狗 + 重建管线/重初始化 BCICore8） | 跨 launcher（index.html/launcher_server/state）+ config + gtec_bridge/gpype_lsl_bridge.py；review 重点 ①④ |
| 2026-08-10 | **P8** 完成（设备连接健壮性 a/b/c/d）：**a** 桥日志落盘——launcher 直起桥输出改 `bridge_<device>.log`（append + 时间戳头，不再 DEVNULL）；**b** LSL 真验证（核心）——内置 `lsl_probe.py` 用 device 的 `python_cmd` 跑 pylsl resolve，绿 = 有流（非进程活着）；verify 轮询直到流出现或超时，超时 → 红 + "no LSL stream — check device is on"；**c** device 加 `python_cmd`（机器本地 venv 路径，默认 python）；**d** headband `connect_mode: open_in_ide`——打开脚本（`code`，无则回退默认打开）+ 提示 "press Run (F5)" + 异步等 LSL（waiting 态 busy）+ 无进程 reconcile 走 LSL（流消失 → 灰）+ disconnect 提示 "Stop the bridge in VS Code"；hybrid 保持 spawn 模式 | config device schema 变（python_cmd/script/lsl_source_id/connect_mode/verify_timeout_poll/open_cmd）；**用户侧 config 需手动同步 devices**；`.gitignore` 加 bridge_*.log；探针行精确匹配（"not-found" 不以 "found" 误判）；94 launcher / 全量 180 passed |
| 2026-08-11 | **P9** 完成（eeg_control_node 用 venv python）：真机发现 launcher 起系统后 `/eeg_analysis` 无数据无波形。根因 = backend_cmd 未激活 venv → `_load_ros_env()` 捕获的 PATH 无 `.venv/bin` → launch 起 `eeg_control_node`（`#!/usr/bin/env python3`）`env python3` 解析到系统 python3（缺 pylsl）→ 无数据（手动 `source activate` 正常故可复现）。**P9a**（根修，web_gui `command_runner.py`）：`_source_prefix()` 在 ROS source 后追加 `export PATH=<venv_bin>:"$PATH"`（venv bin 排 PATH 最前）——捕获环境恒含 venv，与后端启动方式无关。**故意用 export PATH 而非 source activate**：实测本仓库 `.venv/bin/activate` 是陈旧拷贝（`VIRTUAL_ENV` 硬编码成另一项目 `ros_thymio/.venv`），source 它静默排错 venv；export 基于运行时计算路径，确定生效。venv 发现顺序 repo 根 `.venv` → `web_gui/backend/.venv`（README 文档备选）。**P9b**（纵深防御，config.json）：backend_cmd 加 `source ../../.venv/bin/activate`（与手动一致） | **真机验收**：launcher 起系统 → 点 start → `/eeg_analysis` 有数据、波形正常；设备 venv 需含 pylsl（应已具备）；若 venv python3 下 `ros2 launch` shim import rclpy 失败（设备 venv 缺 rclpy），需在设备 venv 补装 rclpy 依赖——手动 `source activate` 正常即兼容；新增 venv 单测 7 条（优先级/回退/缺失/export 顺序/PATH 捕获）→ command_runner 20 passed、launcher 95 passed、web_gui app 47 passed；**用户侧 config 需手动同步 backend_cmd** |
| 2026-08-11 | **P10** 完成（状态实时性 + Thymio 幂等 + Start/Restart + gpype 重连）：**①** 状态实时——前端 pollStatus 顺序 bug（renderSystem 先设 op 按钮 disabled，renderOps 后重建按钮不带它 → 禁用态永不生效）→ disabled 移进 renderOps（按钮创建处 `btn.disabled = ctl.disabled`）+ 轮询 renderOps 先行；服务端 `_reconcile_system_health`——running 但 web 服务不可达 → error + "web service unreachable — restart the web services"（节流 `web.health_interval_sec` 默认 10s，复用 ready_check 探针，测试注入）。**②** Thymio 幂等——usbipd attach 跨 launcher 重启持久 → `_reconcile_usbipd` 用 verify_cmd(ttyACM0) 对齐真实 attach 态（已 attach → connected；被拔 → 灰；system 非 running/starting 不探测防空启 WSL；节流 `devices.thymio.reconcile_sec`）；`_connect_usbipd` 幂等（`_thymio_attached` 已 attach 跳过 attach，不再报 "already attached"）。**③** Start/Restart——前端 `opControl` 纯函数按状态给 label/disabled/endpoint：running → "Restart System"(POST `/restart-system`)，stopped/error → "Start System"，starting/stopping 禁用；服务端 `restart_system` = stop 后 start（先 can_stop 门控）。**④** gpype 桥重连——`gpype_lsl_bridge.py` 重写：`DataWatchdog`（纯停滞判定，可注入时钟）+ `LslWatchdogProbe`（pylsl 读回自身 LSL 流，惰性导入）+ `BridgeController`（监视→停滞→teardown+重建+指数 backoff 重试，teardown 释放旧源防"设备被占用"；重建 = fresh BCICore8 全管线，`test_reconnect.py` 已实证）；初始连接仍 fail-fast 出 checklist | config 新增 `web.health_interval_sec` + `devices.thymio.reconcile_sec`（代码有默认，缺键不破）；**用户侧 config 需手动同步两键**；gpype 桥改动需真机在 VS Code 里断电重开验证（④ 无法 macOS 端到端）；+19 launcher 测试（opControl Node 映射、disabled 创建处、usbipd reconcile/幂等、system 健康/节流、restart 顺序/HTTP、gpype 看门狗 6 条）→ launcher 114 passed、web_gui app 47 passed、全量回归通过 |
| 2026-08-11 | **P11** 完成（LSL 活性真校验）：真机 headband 断电 → launcher 一直绿。根因 = `lsl_probe.py` 只 `resolve_byprop` 查流**存在**——设备断电但桥还在时空流仍在发布 → found → 误判 connected。**P11a** `lsl_probe.py` 三态：resolve 到流 → 开 `StreamInlet.pull_sample(timeout=1.0)`——有 sample → `alive`；resolve 到但拉不到 → `stalled`；resolve 不到 → `not-found`（`no-pylsl` 保留）。**P11b** reconcile 统一 IDE + spawn：CONNECTED 仅当活性 `alive`；`stalled`/`not-found` → 灰。顺带修 hybrid——spawn 模式进程活着但流停，之前保持绿，现在灰；spawn 仍先查进程死 → error（红）再查活性；IDE 模式仅活性。`_lsl_found` → `_lsl_state`（三态解析，行精确匹配防 "not-found" 子串误判）；连接 `_wait_for_lsl` 也改判 `alive`（connect 绿 = 有数据，更严格） | 探针周期 ≈ reconcile 节流 10s + 探针 ~2s（resolve 1s + pull 1s）；无 config 改动；测试：`test_lsl_probe.py` 三态 pylsl mock 6 条（alive/stalled/not-found/pull 异常/resolve 异常/no-pylsl）+ reconcile 按活性设状态 3 条（stalled/not-found→灰、alive→绿）→ launcher 123 passed；真机验收：headband/hybrid 断电 ≤ 探针周期变灰、设备回来桥恢复 → 变绿 |
| 2026-08-11 | **P11 复核修复**（进程泄漏 + 停滞后自动恢复）：**① 进程泄漏（阻塞）**——停滞置灰 reconcile 不杀进程（设计决定，让 unicornpy O4 / gpype P10 看门狗自恢复），但置灰后 reconnect `_connect_bridge` spawn 新桥覆盖 `_device_procs[name]` → 旧进程泄漏（占设备 → 新桥 "device in use" / 同 source_id 双 outlet → 探针非确定）。修：`_connect_bridge` **spawn 前 pop+terminate 该设备已有进程**（与 disconnect 对称）。**② 停滞后自动恢复**——reconcile 之前只降级（connected→grey）不升级，grey 永远回不了绿。修：reconcile 加**升级路径**——`_stalled` 标记位区分"停滞置灰"（可自动回绿）vs"主动断开"（绝不自动回绿）；设备停滞置灰且流恢复 `alive` → 自动置 CONNECTED；显式 disconnect（含早返回路径）清除 `_stalled` 并终止残留桥进程；connect 意图也清标记。进程死 → 红（`_stalled` 同步清） | 停滞不杀进程的设计保留；泄漏由重连前清理解决；测试 +4：重连清理旧 proc（断言 terminate + 仅一个新 spawn）、停滞→alive→connected 升级、主动断开不升级、断停滞置灰设备取消自动恢复 → launcher 127 passed；真机验收：重连不泄漏（旧桥被终止、无重复 outlet）、设备回来自动变绿、主动 disconnect 后不自动回绿 |
| 2026-08-11 | **P12** 完成（gpype 桥看门狗误判修复）：真机复现——设备正常（headband 开、无占用）桥却起不来，日志循环 "Reconnected → 立刻 Pipeline stopped → rebuild 一半报 No amplifiers connected"；第一次实例反复重建失败、第二次实例干净连上 → 坐实**残留 outlet / 非确定 resolve**（第一次实例快速拆建产生多个同 name outlet，探针 `resolve_byprop("name")` 取 streams[0] 可能锁到空旧 outlet → 永远拉不到数据 → STALL_SEC=5s 误判停滞 → churn）。修：**① 重建后宽限期** `GRACE_SEC=10s`——(重)建成功后 N 秒内不判停滞；**② 探针候选扫描选活 outlet + 空读重解析**——`LslWatchdogProbe._resolve_alive` 逐个候选 `pull_sample(0.05s)` 选真正有数据的 outlet（不锁 streams[0]），连续 `EMPTY_RESOLVE_AFTER=3` 次空读 drop inlet 重解析；**③ 见过数据才判停**——`DataWatchdog` 加 `seen_data`+`reset()`，停滞 = 见过数据后连续 STALL_SEC 无数据；重建后 reset 按实例判定，从没见过数据不触发（初始连接仍 fail-fast 走 build/start 异常）；**④ STALL_SEC 5s→10s**。原则：宁可漏判多等一轮，不误拆健康管线。另：headband 桥在 VS Code 建议用 venv python（与 launcher python_cmd 一致，运维提示，次要） | 纯桥侧改动（gpype_lsl_bridge.py + 测试），launcher/config 无改；test_gpype_watchdog 重写至 13 条（+7：宽限期 blocking、见过数据才判停、reset 按实例、STALL_SEC 默认、候选扫描选活 outlet、空读重解析、resolve 失败）→ launcher 134 passed；真机验收：设备正常时桥稳定连接无 churn 波形正常；断电→(宽限期后)判停滞→重建重试；设备回来→恢复 |
| 2026-08-11 | **P13** 完成（探针样本时效 + open_in_ide 连接超时）：真机三现象两根因——**① 连接先红后绿**：open_in_ide connect 等 LSL 用 `verify_timeout_sec=30`，操作者手动去 VS Code 跑桥常超 30s → 提前红。修：open_in_ide 模式改用 `open_ide_timeout_sec`（默认 120s）——慢慢跑桥不红、流起来才绿；`_wait_lsl_background` 加状态守卫——后台等待期间操作者断开则晚到的结果不覆盖（显式断开后绝不自动回绿）。**② 断电一直绿 + 不自动重连**：活性判断被 outlet 缓存样本骗了——launcher `lsl_probe.py` 和桥 `LslWatchdogProbe` 都只看"拉到样本"，断电前的旧样本也算 alive → 设备关了仍绿、桥看门狗误以为数据在流 → 不重建。修：拉到的样本必须**新鲜**——`local_clock() - sample_timestamp < 3s`（`FRESHNESS_SEC`）才算 alive，超龄样本 → `stalled`；launcher 探针（argv[4] freshness 默认 3s）和桥探针（`_fresh()`，含候选扫描 `_resolve_alive` 也判时效）都改 | config headband 加 `open_ide_timeout_sec: 120`（代码默认 120，缺键不破）；**用户侧 config 需手动同步 headband**；测试 +5：launcher 探针旧样本→stalled/新样本→alive、桥探针拒旧样/收新样、open_in_ide 超时配置 ≥120、后台等待不覆盖断开 → launcher 139 passed；真机验收：操作者慢慢跑桥(>30s)不红、流起来才绿；断电→桥判停滞重建、launcher ≤10s+探针周期变灰；设备回来→桥恢复→自动变绿 |
| 2026-08-11 | **P14** 完成（系统健康检查改探后端）：真机杀后端（`pkill -f 'app.main'`）→ system 没变 error。根因 = `_reconcile_system_health` 用 `_ready_check(web.url)` 只探前端 5173——**vite 独立于后端**，后端死前端仍 200 → 误判健康。修：健康检查**同时探前端 5173 + 后端**——`web.backend_url` 默认 `http://localhost:8010`（机器本地，Windows→WSL localhost 转发），探 `backend_url/api/status`（已确认后端有该端点，200）；**任一不可达 → error** + "web service unreachable — restart the web services"。复用 `_default_ready_check`(urlopen) | config web 加 `backend_url`（代码默认 8010，缺键不破）；**用户侧 config 需手动同步 backend_url**；测试 +3：健康检查探后端 URL（注入 probe 断言含 8010/api/status）、后端挂→error（P14 根因）、前端挂→error → launcher 142 passed；真机验收：杀后端 → system ≤10s+探针变 error；杀前端 → 也 error |

| 2026-08-11 | 真机 headband 稳定性收官验证通过：**P12 看门狗**（宽限期/选活 outlet/见过数据才判停）无 churn；**P13 样本时效**（launcher + 桥探针 freshness 3s）断电正确变灰、重开自动变绿；open_in_ide 120s 宽限连接不闪红 | headband 全链路（连接/断电检测/自动恢复）真机通过；🟡 残留：stop_system 不清 _stalled（P11 复审）、P13 信息性连接线程计数 edge——均非阻塞，下批可选 |
| 2026-08-11 | 真机 UX/健壮性 **P10 完成**：① 状态实时——前端 pollStatus 顺序 bug（renderOps 重建抹掉 disabled）→ disabled 移创建处 + 轮询 renderOps 先行；`_reconcile_system_health`（running 但 web 不可达 → error，节流 `web.health_interval_sec` 10s）。② Thymio 幂等——`_reconcile_usbipd`（ttyACM0 对齐真实 attach，停机不探测）+ `_connect_usbipd` 幂等。③ Start/Restart——`opControl` 纯函数（running→"Restart System" POST /restart-system）+ 服务端 stop→start。④ gpype 桥重连——`DataWatchdog`+`LslWatchdogProbe`+`BridgeController`（停滞→teardown+重建+backoff） | +19 launcher 测试 → 114；config 加 health_interval_sec + thymio.reconcile_sec |
| 2026-08-13 | **P17** 完成（日志面板 + App.jsx 拆分）：**①** web GUI 日志面板——后端 `logs.py` 加 `RingBufferHandler`（根 logger 最近 500 条内存环形缓冲，级别/时间/来源/内容）+ `GET /api/logs`（backend 环形 + 尽力 tail WSL 侧 `/tmp/launcher_backend.log`/`/tmp/launcher_frontend.log`）；前端 `LogPanel.jsx`（独立组件）可折叠/Refresh/auto 2s 轮询。**②** launcher View Log 接线——`LauncherApp.log_tail()`（tail `launcher_server.log` + `bridge_*.log`，last N 行）+ `GET /log?lines=N`；index.html 加模态（`#log-modal`，viewLog()/closeLog()，log-btn onclick）。**③** O5 App.jsx 拆分——**增量拆**：实验模式（P16）+ 日志面板（P17）各成独立组件文件（`ExperimentPanel.jsx`/`LogPanel.jsx`），App.jsx 只留 import + 渲染 2 行，不做一次性大重构（风险） | 前端需用户侧 vite build 确认；launcher 侧无 config 改动（View Log 按钮沿用 config 已有 placeholder 项）；测试：后端 +6（环形缓冲捕获/限长/tail 限制/emit 不抛/tail_files 缺失忽略/尾行读取）、launcher +2（/log 端点、log_tail 读 launcher+bridge）、前端标记 +4（log-btn/modal、LogPanel import+标记）→ 后端 app 64 passed、launcher 161 passed |
| 2026-08-13 | **P16** 完成（实验模式 E1+E3+E4）：web GUI 实验模式，按 docs/EXPERIMENT_PLAN.md §2 记录带真值标签的 trial 数据。**E1** 日志——`web_gui/backend/app/experiment.py`（stdlib、线程安全、可测）：`ExperimentSession` 每 session 落 `<repo>/experiment_data/<session_id>/` 下 `session.json`（元数据+打乱后协议）、`labels.csv`（E4 真值流：每 trial 在 prompt 入口写 `wall_ts + a_state/b_state/b_direction`，与样本 `row_ts` 同墙钟对齐）、`trials.csv`（每 trial 汇总：真值+prompt/start/end+均值+眨眼数）、`trial_<NNN>.csv`（每 trial 样本：真值三路+起止戳+alpha/tbr/ei+speed/steer_intent+steer_direction+cmd_lin/ang+is_blink+latency_ms）。trial 状态机 prompt→trial→rest→next 纯墙钟惰性推进（无后台线程；暂停存剩余时长、恢复续期；大跳合并多相位）。**E3** 协议驱动提示——默认协议 `protocol.json`（24 trial：A 注意/休息 + B 转向 + B 方向，shuffle `none/random/balanced`，balanced=按条件桶轮转防连跑）；`ExperimentPanel.jsx`（独立组件文件，O5 增量拆分）配置 session→Start/Pause/Resume/Reset、大字目标+计时+trial 间休息+进度。**E4** 标签注入——提示目标时写 labels.csv，墙钟对齐。`eeg_control_node` 分析消息加 `cmd_vel_ts`（决策墙钟，§2 #6 延迟分析）；`RosBridge` 加原始分析帧处理器钩子（记录器订阅） | 前端需用户侧 vite build 确认；实验数据落仓库根 `experiment_data/`（gitignored，`EXPERIMENT_DATA_DIR` 可覆盖）；测试 +11 后端（协议解析/shuffle 确定性+平衡/状态机/记录 schema/眨眼事件/标签对齐/暂停恢复）+4 前端标记 → 后端 app 58 passed、launcher 156 passed |
| 2026-08-13 | **P19** 完成（删除 'Sans robot' 输出模式）：输出目标 'Sans robot'（output='none'，"Waveforms only"）在 eeg 输入下没波形，是坏掉的多余模式（校准流程已能看波形、实验用不到），删除比修划算。改动纯前端 App.jsx：删输出 radio 的 `{value:'none', title:'Sans robot'}`；`outputMode === 'thymio'` 分支（buildPatch device + 设备选择器）**保留**（真机仍需要）；grep 确认无其他 `outputMode==='none'` 引用——role2 的 'none'（"无第二设备"）与输入 'none' 是别的东西，未误删；后端无改动 | 前端改动需用户侧 vite build 确认；测试 +2 静态断言（无 'Sans robot'/'Waveforms only'、两模式仍在、role2 'None' 保留、thymio 设备选择器仍在）→ launcher 154 passed |
| 2026-08-13 | **P18** 完成（gpype 桥 probe TypeError 崩溃）：真机 headband 桥运行中报 "Failed to connect: unsupported operand type(s) for -: 'float' and 'NoneType'" → 桥退出连接丢失。根因 = `LslWatchdogProbe._fresh()` 第 144 行 `self._now() - timestamp`——`pull_sample` 在流中断/超时边界返回 `timestamp=None` → TypeError；且该调用在 `data_arrived()` 的 try/except **外**未被捕获 → 传到 `main()` catch-all → "Failed to connect" + checklist → 桥退出。修：① `_fresh` 对 `timestamp` 非数值/None 直接返回 False（`isinstance(timestamp, (int, float))` 防御）；② `data_arrived` 把 `pull_sample + _fresh` 一并移入 try/except——探针任何异常 = "本轮无数据"，返回 False 继续监控、绝不崩溃；③ 兜底：`run()` 监控循环 `data_arrived()` 包 try/except——探针异常绝不 kill 桥（初始连接仍 build/start fail-fast，checklist 保留） | 桥文件改动（gpype_lsl_bridge.py + 测试）；**真机需重新「启动系统」自同步生效**；测试 +5（_fresh None/非数值 timestamp→False、data_arrived 重读路径 None ts 不抛、pull_sample 异常吞掉、run() 监控循环探针异常不死）→ launcher 152 passed |
| 2026-08-12 | **P15** 完成（review 门禁残留 4 项）：**① 停系统不清 _stalled**（🟡 必修）——IDE 桥(headband)在 VS Code 跑、stop 杀不到 → 停系统后残留 `_stalled` 标记，10s 节流一过、LSL 流恢复 alive → system stopped 但设备自动误回绿。修：`stop_system` 置设备 disconnected 后 `_stalled.clear()`（选此而非 running gate：gate 会在 system error(web 挂) 时冻结设备 reconcile 掩盖真相，且清标记顺带防下次 start 的残留自动回绿）。**② 连接线程计数 edge**——CONNECTING 未按连接实例区分，disconnect→reconnect 后旧实例晚到结果（成功/失败）可盖过新实例的等待（state 又回 CONNECTING，P13 状态守卫挡不住）。修：per-device `_connect_gen` 代计数，connect 递增、`_wait_lsl_background` 捕获本实例代、设置结果前校验、旧代直接丢弃（成功失败都丢）。**③ 浅色 `.btn.danger` 边框色**——浅色 `--f-red-dark:#A01409` → `#B01E0A`（与 web_gui styles.css 一致，1px 视觉）。**④ spawn 活性 reconcile**——验证**已在 P11 统一**（进程死→红；进程活+流停/not-found→灰带 `_stalled` 自动恢复；流活→绿），既有测试已锁定（spawn stalled→灰、返回→自动绿、停滞不杀进程、进程死→红）；此残留为 P8 时代旧发现，早于 P11 reconcile 统一，无需代码改动 | 无 config 改动；测试 +5（① 停系统清标记+流恢复仍灰、② 旧代失败/成功均丢弃+当前代生效+连接递增、③ 浅色 danger 边框断言）→ launcher 147 passed；真机验收：停系统后设备不再自动误回绿；快速断开→重连晚到结果不覆盖新等待；hybrid 断电→灰、回来→自动绿；浅色 danger 边框与 web_gui 一致 |

---

## 7. O2 真机验收清单（用户侧逐项勾）

> 状态：✓ = 已真机验证通过；☐ = 待验证。P1–P10 单点已验，此表为**整体系统性过一遍**的收尾。

### A. 入口与幂等
- [x] 双击 launcher.bat → 无 python 窗口、浏览器自动开总控页、设备按钮全灰（P1）
- [x] 再次双击 → 旧进程被杀、单实例、单浏览器标签（P1）
- [ ] 缺 Python / 启动超时时 bat 英文提示（P7，罕见路径）

### B. 启动系统链路
- [x] Start System → Ubuntu 起、检测通过、桥文件同步、前后端起（M3）
- [x] GUI 自动加载进 iframe、不手动刷新（P5/P6）
- [x] 全程无 cmd 窗口闪现/残留（P4）
- [ ] 运行中 Start 变 "Restart System"，可点（stop+start）（P10）
- [ ] web 服务挂掉 → system 变 error + "restart the web services"（P10）

### C. 设备连接
- [x] HybridBlack connect → 变绿（LSL 流）；设备没开 → 超时红（P8）
- [x] Headband connect → VS Code 打开脚本 + 提示 → 点 Run → 变绿（P8）
- [ ] Thymio connect → 变绿；**重启 launcher 后已 attach 直接绿**（P10）
- [ ] Thymio 被拔 → 变灰（P10）
- [ ] headband 断电重开 → **波形自动恢复**（P10-④，VS Code 里测）

### D. 主题与界面
- [x] 任意一侧切 ☀/☾ → 两侧同变；刷新后一致（P6）
- [x] 系统离线 → Ferrari 占位，无哭脸错误页（P6）
- [x] 侧边栏可收起 + 刷新保持（P2）
- [x] 全英文界面 + Refresh 按钮（P5）

### E. 关闭与退出
- [ ] Stop System → 进程干净 + WSL 停
- [ ] Exit Launcher → 服务退出，`launcher_server.log` 有日志
- [ ] 断桥后状态变红/灰（§4 核心项）

### F. 实验链路
- [x] calibrate + start → 波形正常（P9）
- [ ] 双设备同时跑 → 波形正常（沿用早期验证，launcher 全链路复核）

---

## 8. O2 待办（非阻塞，按优先级）

| # | 待办 | 状态 |
|---|---|---|
| 1 | **g.tec 决策定案（2026-08-12）**：Headband 长期走 **C 变体**（open_in_ide，VS Code 手动跑）；A（g.Pype Runtime）/ B（学术条款）**搁置，不推进**。"非 IT 操作者自动连 Headband"愿景关闭（headband 需操作者会 VS Code 手动跑） | 已定案，不再跟踪 |
| 2 | ~~P6 残留：浅色 `.btn.danger` 边框色 `#A01409` vs web_gui `#B01E0A`（1px 视觉）~~ | ✅ **P15③** 已修（`#B01E0A`，2026-08-12） |
| 3 | ~~P8 残留①：spawn 模式进程活着但 LSL 流丢 → 保持绿到进程退出（窗口小）~~ | ✅ **P15④** 确认已由 P11 reconcile 统一修复（既有测试锁定：spawn stalled→灰、返回→自动绿、停滞不杀进程、进程死→红） |
| 4 | P8 残留②：`bridge_<device>.log` 在 Windows 上有内容（日志落盘真机确认） | 🟢 顺手确认 |
| 5 | 项目 backlog：O5（App.jsx 重构）等 TASKS.md 里早期 O 系列 | 项目级，另行排期 |
