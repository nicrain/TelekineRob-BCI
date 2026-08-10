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
