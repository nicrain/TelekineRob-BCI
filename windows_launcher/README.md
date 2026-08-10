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
   | `web.backend_cmd` / `frontend_cmd` | WSL 内起前后端的 shell 命令（**前台**执行，日志落 `/tmp/launcher_*.log`；后端 venv 默认仓库根 `.venv`，若缺依赖改 `web_gui/backend/.venv`） | 确认/可调 |
   | `devices.*.verify_cmd` | 连上后的自检命令（null = 只查进程存活） | 可选 |

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
   主区域、设备按钮解灰。任一失败会弹一句中文提示（无堆栈）。
3. 点「**连接 Headband / HybridBlack / Thymio**」→ 各自变绿；
   再点变「断开」→ 变灰。
4. 在 web GUI 里：配置设备 → 校准 → 点 Start 跑实验。
5. 点「**关闭系统**」→ 桥进程、web 进程、WSL 全部停干净。

## 真机验收（对照 docs/O2_LAUNCHER.md §4）

- [ ] 双击图标 → 总控页打开，设备按钮全灰、不可点
- [ ] 点「启动系统」→ Ubuntu 起、检测通过、桥文件同步、前后端起、
      GUI 出现在 iframe、设备解灰
- [ ] 点「连接 Headband/HybridBlack/Thymio」→ 各自变绿（LSL 流 / ttyACM0）
- [ ] 点「断开」→ 各自变灰
- [ ] 点「关闭系统」→ 进程清干净 + WSL 停
- [ ] 任一步失败 → 一句人话中文提示（无堆栈）
- [ ] 断桥后（拔 USB / 关桥进程）状态变红/灰，不残留"已连接"
- [ ] 桥文件用的是同步后的最新版（改仓库后重新「启动系统」生效）
- [ ] 重复点击幂等（已启动则跳过）

## 故障排查

| 现象 | 检查 |
|---|---|
| 双击 bat 报"未找到 Python" | 装 Python 并勾选 Add to PATH |
| 启动系统报"WSL 未就绪" | `wsl -l` 确认发行版名与 config 一致 |
| 连 Thymio 报 usbipd 失败 | busid 是否正确；终端管理员权限试 `usbipd bind --busid=…` |
| 连桥报"桥进程已退出" | 设备是否开机、是否被别的程序占用、桥依赖是否装齐 |
| 网页服务连不上 | WSL 内手动 `npm run dev` 试；config `web.url` 端口是否对；前后端日志在 WSL `/tmp/launcher_backend.log` / `/tmp/launcher_frontend.log` |
| 总控页打不开 | 看最小化窗口日志；`last_url.txt` 是否生成 |

## 开发 / 测试（macOS 也可）

控制服务逻辑不依赖 Windows：`pytest windows_launcher/tests` 即可跑
（wsl/usbipd/copy 全走 fake executor）。真机链路在 Windows 侧按上文验收。
