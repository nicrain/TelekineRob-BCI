# GUIDE_INSTALLATION

> 安装指南 — 中文源文(将翻译为法语)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。
> **受众 = 技术人员(安装者)**:本文档允许命令行,与操作手册(MANUEL_OPERATEUR,全程 GUI)相反。

## 1. 概览与前置要求

**整栈组件。**

```
Windows 主机:
  windows_launcher/   O2 总控台(非 IT 操作者用;双击 launcher.bat)
  gtec_bridge/        设备桥:gpype_lsl_bridge.py(Headband) / unicornpy_lsl_bridge.py(Hybrid Black) → LSL
        ↓ LSL (raw EEG)
WSL2 / Ubuntu 24.04:
  thymio_control/     ROS2 处理:eeg_control_node → /eeg_analysis → /cmd_vel
  web_gui/            FastAPI 后端(8010) + React 前端(5173)
        ↓ usbipd attach
  Thymio (ttyACM0)
```

**前置要求。**

| 项 | 版本 |
|---|---|
| Windows | 10/11,WSL2 启用 |
| WSL2 发行版 | Ubuntu 24.04 |
| Python | 3.12+(Windows 侧跑 launcher;WSL 侧 venv) |
| ROS2 | Kilted(Ubuntu 24.04 对应版) |
| Node.js / npm | 18+(前端 Vite 5 需要) |
| g.tec 驱动 | gpype(Headband)/ UnicornPy(Hybrid Black) |
| Thymio | 真机 + Aseba(ros-aseba 驱动) |

## 2. Windows 主机准备

1. **安装 Python 3**,安装时勾选 **"Add Python to PATH"**(`launcher.bat` 依赖 `python` / `pythonw`)。
2. **安装 g.tec 驱动**:Headband 用 g.Pype(`gpype`);Hybrid Black 用 `UnicornPy`。设备桥经 `pylsl` 发布 LSL 流,三者在跑桥的 Python 环境里都要能 `import`。
3. **安装 VS Code**:头戴桥走 `open_in_ide`(g.Pype 免费版授权闸门——桥只能在 IDE 内运行),需要在 VS Code 里打开桥脚本点 Run;确认 `code` 命令可用。
4. **首次把 `windows_launcher/` 从 WSL 仓库拷到 Windows 目标目录**(仅这一次;之后每次 **Start System** 自动自同步,你不再碰它):
   ```
   xcopy /E /I /Y \\wsl$\<distro>\home\robot\TelekineRob-BCI\windows_launcher <目标目录>
   ```
5. **填 Windows 侧的 `config.json`**(机器本地配置,同步时被排除、永不被仓库版覆盖):
   - `devices.thymio.attach_cmd` / `detach_cmd`(usbipd busid,只有你知道,**必须填**)
   - `wsl.distro`(发行版名)、`wsl.repo_path`(WSL 内仓库路径)
   - `sync.dst_root`(同步目标目录)、`web.backend_cmd` / `frontend_cmd`(可调)
   - 字段含义见 `windows_launcher/README.md`「首次部署」表。

## 3. WSL2 环境

1. **安装 Ubuntu 24.04** 为 WSL 发行版(如 `wsl --install -d Ubuntu-24.04`);确认发行版名与 config `wsl.distro` 一致。
2. **启用 systemd**:编辑 WSL 内 `/etc/wsl.conf`:
   ```
   [boot]
   systemd=true
   ```
   launcher 用 `systemctl is-system-running` 探测就绪(systemd 会在每次 WSL 启动自动应用配置)。
3. **安装 ROS2 Kilted**(按 ROS2 官方文档 apt 安装;路径 `/opt/ros/kilted/setup.bash`)。
4. **clone 仓库 + colcon 构建**:
   ```
   cd ~/TelekineRob-BCI
   source /opt/ros/kilted/setup.bash
   colcon build --symlink-install
   source install/setup.bash
   ```
5. **创建仓库根虚拟环境**并装依赖:
   ```
   cd ~/TelekineRob-BCI
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   (后端与 eeg_control_node 走 `.venv/bin/python`,见 `requirements.txt`。)

## 4. 网络配置

**① 禁用 eth0 IPv6(防 LSL 连接挂起)。** g.tec 的 LSL 流在 WSL2 上发现时,liblsl 可能选中不可达的 IPv6 link-local 地址(`fe80::...`)建立数据连接,导致 eeg 节点连接挂起、无波形、校准卡在 preparing。在 WSL2 内:
```
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl --system
```
启用 systemd 后,该配置在每次 WSL 启动自动应用;若未启用 systemd,改用 `/etc/wsl.conf` 的 `[boot] command` 每次启动执行上述 sysctl。

**② 局域网访问(Windows 主机)。**
- **确认 `.wslconfig` 文件名正确**(`C:\Users\<用户>\.wslconfig`,不是 `.wksconfig`);**保持默认 NAT 网络**——镜像网络(`networkingMode=mirrored`)会破坏 host→WSL 的 `\\wsl$` 连通,勿用。
- **端口转发**:launcher 每次 **Start System** 后自动执行(监听 `0.0.0.0:5173` → WSL IP,只转前端 5173,后端 8010 保持 loopback)。手动执行(需管理员 CMD):
  ```
  netsh interface portproxy delete v4tov4 listenport=5173 listenaddress=0.0.0.0
  netsh interface portproxy add v4tov4 listenport=5173 listenaddress=0.0.0.0 connectport=5173 connectaddress=<WSL-IP>
  ```
  `<WSL-IP>` = `wsl -d <distro> -e bash -lc "hostname -I"` 的首段(重启会变,launcher 每次现查)。`netsh interface portproxy show all` 可查当前规则。
- **防火墙放行入站 5173**(否则 LAN 浏览器连不上):
  ```
  netsh advfirewall firewall add rule name="O2-vite" dir=in action=allow protocol=TCP localport=5173
  ```
- **前提**:config `web.backend_cmd` 已含 `export WEB_GUI_FRONTEND_ORIGIN=*`——否则 LAN 浏览器 WebSocket 被后端 origin 白名单拒(页面能加载,波形/意图流不推)。
- **localhost 转发**:Windows→WSL 默认 localhost 转发可用——浏览器访问 `localhost:5173`、健康检查探 `http://localhost:8010`,后端经 vite 代理可达,无需直连。
- **安全**:`0.0.0.0` 监听暴露所有网卡(WiFi / VPN / 虚拟接口)。untrusted 环境设 `WEB_GUI_CONTROL_TOKEN` 或关闭转发;转发状态 ≠ 系统状态,失败不阻塞 Start System。

## 5. Web GUI 安装

**后端**(默认 `http://localhost:8010`):
```
cd web_gui/backend
source ../../.venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

**前端**(默认 `http://localhost:5173`):
```
cd web_gui/frontend
npm install
npm run dev
```

**环境变量表**(后端;默认锁 loopback,真实命令默认开):

| 变量 | 默认 | 说明 |
|---|---|---|
| `WEB_GUI_ALLOW_REAL_COMMANDS` | `true` | 真实命令门禁。默认即真执行;设 `false` → Start 是 dry-run、Stop 不 pkill 真实进程。仅 mock 时设 `false` |
| `WEB_GUI_HOST` | `127.0.0.1` | 绑定地址。设 `0.0.0.0` 暴露局域网(建议同时配 token) |
| `WEB_GUI_PORT` | `8010` | 绑定端口 |
| `WEB_GUI_FRONTEND_ORIGIN` | `http://127.0.0.1:5173` | origin 白名单(local `localhost:5173`/`127.0.0.1:5173` 恒放行);`"*"` 放开校验(仅研究) |
| `WEB_GUI_CONTROL_TOKEN` | *(空)* | 控制接口 token:REST `Authorization: Bearer`、teleop WS `?token=`。非 loopback 绑定建议设置 |
| `EXPERIMENT_DATA_DIR` | `<repo>/experiment_data` | 实验数据目录(session.json / labels.csv / trials.csv / trial_<NNN>.csv) |

示例——真机实验、LAN 暴露 + token:
```bash
WEB_GUI_HOST=0.0.0.0 \
WEB_GUI_CONTROL_TOKEN=change-me \
python -m app.main
```

## 6. 真机验证清单

装完按此确认能用:

- [ ] 双击 `launcher.bat` → 总控页 **System Control** 打开,设备按钮全灰、不可点
- [ ] 点 **Start System** → 状态变 **Running**,web GUI 出现在主区
- [ ] 设备桥出 LSL 流:Windows 起桥(Headband 在 VS Code 里 Run;Hybrid Black 由 launcher spawn),侧边栏对应设备变 **Connected**(绿 = 流有数据)
- [ ] eeg 节点连上:WSL 端 `ros2 launch thymio_control experiment_core.launch.py use_sim:=false run_eeg:=true use_teleop:=false input:=lsl`,web GUI **03 — Real-time Signals** 有波形
- [ ] 校准可跑:点 **Calibrate** → 30 秒倒计时 → p5/p50 写入参数文件
- [ ] Thymio 响应:侧边栏 Connect Thymio(绿 = ttyACM0),遥控/实验指令让小车动
- [ ] 导出可跑:实验后 **Export analysis** → `master_trials.csv` + `condition_summary.csv`
- [ ] 断流检测:拔设备 → 状态变灰/红;插回 → 桥自动重建、状态自动变绿
- [ ] 局域网可访问:同一局域网另一台机器浏览器开 `http://<Windows-IP>:5173` 能看到 GUI
- [ ] 点 **Stop System** → 进程清干净、状态回 **Stopped**;点 **Exit Launcher** → 控制服务关闭

## 7. 依赖与版本表

| 类别 | 依赖 | 版本 |
|---|---|---|
| Python(仓库 `requirements.txt`) | numpy / scipy / pyedflib / pylsl | numpy>=1.26、scipy>=1.12、pyedflib>=0.1.36、pylsl>=1.16 |
| Web GUI 后端 | fastapi / uvicorn / pydantic / PyYAML / websockets | fastapi==0.115.6、uvicorn[standard]==0.32.1、pydantic==2.10.3、PyYAML==6.0.2、websockets==14.1 |
| 测试 | pytest | >=8.0 |
| ROS2 | Kilted(apt;`/opt/ros/kilted`) | Ubuntu 24.04 |
| 前端(npm) | vite / react / echarts | vite ^5.4.11、react ^18.3.1(Node 18+) |
| g.tec 设备桥 | gpype / UnicornPy / pylsl | 跑桥的 Python 环境 |
| 系统工具 | usbipd / wsl / robocopy / netsh | Windows / WSL 内置 |
