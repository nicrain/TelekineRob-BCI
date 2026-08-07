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
