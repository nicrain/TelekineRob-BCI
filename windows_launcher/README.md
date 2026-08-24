# O2 Windows 总控台（非 IT 操作者）

Windows 侧总控台：**双击图标 → 网页 → 点按钮起系统/连设备/看状态**，
全程不碰命令行、不 SSH、不见终端。设计见 `docs/O2_LAUNCHER.md`。

## 目录

```
windows_launcher/
├── launcher_server.py   # 控制服务（stdlib http.server，零 pip 依赖）
├── config.json          # 所有环境值 + 侧边栏按钮定义（真机首次部署时填）
├── launcher.bat         # 入口：双击即用（起服务 + 开浏览器）
├── static/index.html    # 总控网页（侧边栏 + 状态轮询 + web GUI iframe）
└── tests/               # 纯逻辑单测（macOS 可跑，wsl/usbipd 用 fake）
```

## 首次部署（用户在真机做一次）

1. **把 `windows_launcher/` 从 WSL 仓库首次拷到 Windows 目标目录**（仅这一次；
   之后的更新由「启动系统」自同步完成）。也可以在 WSL 里执行
   `xcopy /E /I /Y \\wsl$\<distro>\home\robot\TelekineRob-BCI\windows_launcher <目标>`。
2. **确认环境**：Windows 已装 Python 3（勾选 "Add Python to PATH"）；
   `wsl -l` 里发行版名；桥脚本依赖已装（`gpype` / `UnicornPy` / `pylsl`）。
3. **填 Windows 侧的 `config.json`**（以下字段）：

   | 字段 | 含义 | 谁来填 |
   |---|---|---|
   | `service.allowed_origins` | 额外的浏览器来源白名单（默认自动含本机 `127.0.0.1`/`localhost`+端口） | 一般不用动 |
   | `wsl.distro` | WSL 发行版名 | 确认（默认 `Ubuntu`） |
   | `wsl.repo_path` | WSL 内仓库路径 | 确认（默认 `/home/robot/TelekineRob-BCI`） |
   | `sync.src_wsl_root` | 同上的 Windows 侧 UNC 写法 | 确认 |
   | `sync.dst_root` | 同步目标目录（launcher+桥文件拷到这） | 确认（默认桌面 `gpype_test\TelekineRob-BCI`） |
   | `devices.thymio.attach_cmd` | **usbipd attach 命令**（含 busid，只有你知道） | **必须填** |
   | `devices.thymio.detach_cmd` | usbipd detach 命令 | 填 |
   | `web.backend_cmd` / `frontend_cmd` | WSL 内起前后端的 shell 命令（**前台**执行，日志落 `/tmp/launcher_*.log`；后端 venv 默认仓库根 `.venv`，backend_cmd 会自动 `source ../../.venv/bin/activate` 让子节点 `eeg_control_node` 用 venv python，若缺依赖改 `web_gui/backend/.venv`） | 确认/可调 |
   | `devices.*.verify_cmd` | 连上后的自检命令（null = 只查进程存活） | 可选 |
   | `devices.*.python_cmd` | 跑桥/探针的 Python（机器本地 venv 路径，默认 `python`）。headband 走 open_in_ide 时**在 VS Code 里也用同一个 venv 解释器跑桥**（与 launcher/hybrid 一致，避免行为不一致） | 填 venv 路径 |
   | `devices.*.lsl_source_id` | LSL 流 source_id——连接/状态**活性验证**用（绿 = 流**有数据** alive，不是流存在/进程活着；设备断电但桥还在时空流仍发布 → 灰） | 确认（`gtec_bci_core4` / `gtec_hybrid_black`） |
   | `devices.headband.connect_mode` | `open_in_ide` = launcher 打开脚本、操作者在 VS Code 点 Run（g.Pype 免费版授权闸门） | 已设默认 |
   | `devices.headband.open_ide_timeout_sec` | open_in_ide 连接等待 LSL 超时（默认 120s——操作者手动去 VS Code 跑桥需要时间，别用 30s 的 spawn 超时） | 可调 |
   | `devices.thymio.reconcile_sec` | usbipd 状态 reconcile 节流（默认 10s；`usbipd attach` 跨重启持久，已 attach → 重启后直接显示 connected） | 可调 |
   | `web.health_interval_sec` | 系统健康 reconcile 节流（默认 10s；状态为 running 但 web 服务不可达 → 标 error + 提示 Restart Web） | 可调 |
   | `web.backend_url` | 后端健康检查地址（默认 `http://localhost:8010`；健康检查同时探前端 5173 + 后端 `/api/status`，**任一挂 → error**——只探前端不够，vite 独立于后端） | 确认（Windows→WSL localhost 转发） |

   ⚠️ **这个 config.json 是"机器本地配置"**：同步时被排除（`sync.items`
   里 `windows_launcher` 排除 `config.json`），永远不会被 WSL 仓库版覆盖——
   你填的 usbipd busid 等一直保留。WSL 仓库里的 config.json 只是出厂默认。
4. **自同步**：每次点「启动系统」，launcher 用 `robocopy` 把
   `windows_launcher/`（**不含 config.json**）+ `gtec_bridge/` 从 WSL 仓库
   拷到 `sync.dst_root`——**你永远不用碰 git**，launcher 跑的是仓库最新版
   （本次双击用旧版，下次双击生效新版）。

## 使用流程（操作者）

1. 双击 `launcher.bat` → 浏览器打开总控页（设备按钮全灰不可点）。
2. 点「**启动系统**」→ WSL 起来、桥文件同步、前后端起、web GUI 出现在
   主区域、设备按钮解灰。任一失败会弹一句中文提示（无堆栈）。系统运行中
   该按钮变「**Restart System**」——点它执行一次 stop+start。
3. 点「**连接 Headband / HybridBlack / Thymio**」→ 各自变绿；
   再点变「断开」→ 变灰。
4. 在 web GUI 里：配置设备 → 校准 → 点 Start 跑实验。
5. 点「**关闭系统**」→ 桥进程、web 进程、WSL 全部停干净。
6. 用完点「**退出总控**」→ 关闭控制服务（无窗口运行，日志在 `launcher_server.log`）。这**不影响** WSL 侧实验——它只是编排层。

> **无窗口 + 幂等**：双击 `launcher.bat` 用 `pythonw` 无窗口启动（无 pythonw 时回退最小化窗口）；若旧实例还活着会自动先杀掉再起新版（`launcher_server.pid` + 命令行校验），所以每次双击 = 单实例 + 最新代码 + 一个浏览器标签。

## 真机验收（对照 docs/O2_LAUNCHER.md §4）

- [ ] 双击图标 → 总控页打开，设备按钮全灰、不可点
- [ ] 点「启动系统」→ Ubuntu 起、检测通过、桥文件同步、前后端起、
      GUI 出现在 iframe、设备解灰
- [ ] 点「连接 Headband/HybridBlack/Thymio」→ 各自变绿（LSL 流 / ttyACM0）
- [ ] 点「断开」→ 各自变灰
- [ ] 点「关闭系统」→ 进程清干净 + WSL 停
- [ ] 任一步失败 → 一句人话中文提示（无堆栈）
- [ ] 断桥后（拔 USB / 关桥进程）状态变红/灰，不残留"已连接"
- [ ] **运行中 Start 显示「Restart System」且可点**（点它 stop+start）；stopped 显示「Start System」
- [ ] **web 服务挂 → system 变 error**（提示 restart web services），不再残留 running
- [ ] **Thymio 已 attach → 重启 launcher 后显示 connected**；点 connect 幂等（不报 already attached）
- [ ] **gpype 桥断电重开 → 数据流/波形恢复**（不再 Buffer underrun 死循环；VS Code 里跑桥验证）
- [ ] **headband/hybrid 设备断电 → 主控 ≤ 探针周期内变灰**（不是一直绿）；设备回来桥恢复 → 变绿
- [ ] **设备正常时桥稳定连接、无 churn、波形正常**（不再 "Reconnected → Pipeline stopped → No amplifiers" 循环）；断电 → 宽限期后判停滞 → 重建重试；设备回来 → 恢复
- [ ] **open_in_ide 连接：操作者慢慢跑桥（>30s）不红**，流起来才绿
- [ ] **设备断电 → 桥判停滞重建 + launcher 变灰**（样本时效：断电前缓存的旧样本不算 alive）；设备回来 → 桥恢复 → launcher 自动变绿
- [ ] **杀后端（`pkill -f 'app.main'`）→ system ≤10s+探针变 error**；杀前端 → 也 error（健康检查同时探前后端）
- [ ] **停系统后设备不再自动误回绿**（IDE 桥在 VS Code 跑、stop 杀不到——stop 清 _stalled，流恢复仍灰）
- [ ] **快速断开→重连不串代**（旧连接晚到的成功/失败不覆盖新连接的等待；连接代计数）
- [ ] **浅色 danger 边框与 web_gui 一致**（`--f-red-dark:#B01E0A`）
- [ ] 桥文件用的是同步后的最新版（改仓库后重新「启动系统」生效）
- [ ] 重复点击幂等（已启动则跳过）
- [ ] **View Log 按钮可点** → 弹出 `launcher_server.log` + `bridge_<device>.log` 尾部（P17②）

## 故障排查

| 现象 | 检查 |
|---|---|
| 双击 bat 报"未找到 Python" | 装 Python 并勾选 Add to PATH |
| 启动系统报"WSL 未就绪" | `wsl -l` 确认发行版名与 config 一致 |
| 连 Thymio 报 usbipd 失败 | busid 是否正确；终端管理员权限试 `usbipd bind --busid=…` |
| 连桥报"桥进程已退出" | 设备是否开机、是否被别的程序占用、桥依赖是否装齐 |
| 网页服务连不上 | WSL 内手动 `npm run dev` 试；config `web.url` 端口是否对；前后端日志在 WSL `/tmp/launcher_backend.log` / `/tmp/launcher_frontend.log` |
| 总控页打不开 | 看 `launcher_server.log`（控制服务日志，同目录）；`last_url.txt` 是否生成 |

## 开发 / 测试（macOS 也可）

控制服务逻辑不依赖 Windows：`pytest windows_launcher/tests` 即可跑
（wsl/usbipd/copy 全走 fake executor）。真机链路在 Windows 侧按上文验收。
