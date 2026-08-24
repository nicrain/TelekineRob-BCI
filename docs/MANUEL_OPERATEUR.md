# MANUEL_OPERATEUR

> 操作者手册 — 中文源文(将翻译为法语)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。

## 1. 简介与安全

**O2 是什么。** O2 是 Windows 上的总控台(windows_launcher):你只需双击一个图标,浏览器就会打开控制页,你在里面点按钮就能启动整个系统、连接 EEG 设备、运行实验、导出数据。全程点击按钮,不碰命令行。

**谁用。** 本手册写给不熟悉电脑技术的操作者。实验可由一人或两人完成:
- 一人模式:同一人戴一台设备,前进/停止与转向分块各测。
- 双人模式:一人(A)戴一台设备负责 **Speed**(前进/停止);另一人(B)戴另一台负责 **Steering**(转向)与 **Direction**(用眨眼切换左转/右转)。

**佩戴与安全。**
1. 戴 **headband**(g.tec 头戴设备)或 **Hybrid Black** 前,先清洁接触部位的皮肤,保持干爽。
2. 使用 **wet**(湿电极)时:在电极与皮肤之间涂抹导电凝胶,信号才稳定;实验结束后用纸巾擦净凝胶。
3. 使用 **dry**(干电极)时:不需要凝胶,让电极贴紧皮肤即可。
4. 开始前确认设备电量/供电充足;实验中途不要拔插 USB 或电源线。
5. 实验过程中不要取下或移动设备——信号中断会触发断流判断(见 §7)。

**注意(眨眼)。** 只有负责转向的操作者(B)用眨眼切换方向(左转 ↔ 右转)。B 请自然眨眼,不要刻意频繁、用力眨眼,以免无意中切换方向。

## 2. 启动系统

1. **双击 O2 图标**(`launcher.bat`)。浏览器自动打开总控页 **System Control**。
2. 刚打开时,系统状态显示 **Stopped**(灰点),三个设备按钮为灰色、不可点。
3. 点侧边栏 **Operations** 组的 **Start System**。
   - 系统依次执行:启动 WSL → 同步文件 → 启动后台服务(web 前端 + 后端)。
   - 等待期间:状态显示 **Starting…**(橙色闪烁点),主区显示 "Starting System…"。
   - 完成:状态变 **Running**(绿点),主区显示 web 界面,设备按钮解除置灰。
4. **状态灯含义:**

   | 状态显示 | 颜色 | 含义 |
   |---|---|---|
   | Stopped | 灰 | 系统未启动 |
   | Starting… | 橙(闪烁) | 正在启动 |
   | Running | 绿 | 系统就绪,可用 |
   | Stopping… | 橙(闪烁) | 正在停止 |
   | Error | 红 | 出错(见 §7) |

5. **失败时的表现:** 底部弹出**一句人话提示**(无技术堆栈);系统状态变 **Error**(红点),主区显示 "System Error"。按提示处理(常见原因见 §7),再点 **Start System** 重试。

## 3. 连接设备与校准

1. 系统 **Running** 后,在侧边栏 **Devices** 组点设备的 **Connect** 按钮:
   - **Headband**(g.tec 头戴设备)
   - **HybridBlack**
   - **Thymio**(机器人)
2. 每个设备从 **Not Connected**(灰)→ **Connecting…**(橙)→ **Connected**(绿)。再点一次同一按钮(此时为 **Disconnect**)即断开。
3. 设备连上后,在 web 界面主区:
   - **01 — Input Source** 区:每台设备一列(单设备一列;双设备两列,列标签 **Speed device** / **Steering device**)。
   - 每列设置 **Role**(Speed / Steering)与 **Metric**(Alpha / TBR / EI)。
4. **校准:** 点设备列的 **Calibrate** 按钮。
   - 系统自动采集 30 秒基线,按钮显示 **Calibrating… Ns** 倒计时。
   - 30 秒后自动停止,得到校准参考 **p5/p50**,图中显示参考虚线。
   - **双设备模式:** 两列各有独立的 **Calibrate**,各自校准、互不影响。
5. 校准完自动停止,**不会自动开始实验**——你手动点 **Start** 才开始正式实验。

## 4. 运行实验

1. 在 web 界面 **04 — Experiment Mode** 面板填字段(按顺序):
   - **Subject**、**Session #**(被试代号与第几次会话)
   - **Electrode**(仅含 Hybrid Black 时显示:干 = dry / 湿 = wet)
   - **Metric**(Alpha / TBR / EI)
   - **Roles**(Speed / Steering)
   - **Mode**(Single / Dual)
2. **协议模板自动跟随**以上配置,不用手选:
   - **A Forward/Stop**(单设备 + Speed):前进/停止
   - **B Steering + Direction**(单设备 + Steering):转向 + 方向
   - **Dual Collaborative**(双设备):两人协同
3. 设置协议参数:**trials**(总试次数)、**duration**(每试次秒数)、**prompt**(试次之间 "Get ready" 倒计时的秒数)、**shuffle**(试次顺序打乱方式)。
4. 点 **Configure new session**(已有会话时是 **Configure session**)确认配置。
5. 回到主界面顶部点 **Start**,实验开始。

## 5. 实验进行中

**看什么。**
- **03 — Real-time Signals** 区:每台设备的实时波形与指标曲线,确认信号持续跳动、没有停顿。
- 实验面板显示当前试次目标表 **Subjects | Actions | Direction**:状态显示 **Focus**(蓝)/ **Relax**(绿),方向显示 **LEFT** / **RIGHT**。
- 试次之间有 **Get ready** 提示倒计时;每个试次显示进度 **Trial x/y**。
- 观察机器人是否按目标动作:Focus 时前进/转向,Relax 时停止/不转;方向提示改变时用眨眼切换。

**不要做。**
- 试次运行中不要点 **Configure**、**Calibrate**、**Start** 或改任何设备设置——会打断当前试次。
- 不要拔设备、不要关设备电源、不要取下头戴/电极。
- 不要长时间切走浏览器标签页——提示按墙上时钟推进,回来可能已错过目标。
- 试次进行中请按提示做:提示 Focus 就集中注意力,提示 Relax 就放松,不要全程一直用力。

## 6. 导出数据

1. 实验结束(或想保存当前结果)后,在 **04 — Experiment Mode** 面板点 **Export analysis**。
2. 导出成功,结果行显示 `Exported → <目录> (N trials, M conditions)`。
3. 生成两个文件:
   - **master_trials.csv**(主试次表:每个试次一行)
   - **condition_summary.csv**(条件汇总表)
4. 文件默认落在 `experiment_data/analysis/` 目录(WSL 侧);如需拿到 Windows,请技术人员协助拷贝。

## 7. 故障排查

| 现象 | 可能原因 | 操作 |
|---|---|---|
| **无波形**(03 — Real-time Signals 空白) | 后端信号处理未正常启动;或设备流未到 | 确认侧边栏该设备为 **Connected**;点 **Restart Web** 重启前后端;仍无 → 断开该设备再 **Connect** |
| **校准卡在 Preparing…**(点 Calibrate 后不进入倒计时) | 校准在等第一帧分析数据,但设备没流 / 桥停 | 确认侧边栏设备为 **Connected**;点 **Restart Web**;检查设备是否还开着 |
| **断流**(设备断电/拔出,状态变灰或红) | 设备断电 / USB 断开 / 桥进程退出 | 重新开设备、插好 USB;系统会自动恢复(桥重建 + 状态变绿);不恢复 → **Disconnect** 再 **Connect**;系统变 **Error** → **Restart System** |
| **Start System 超时**(长时间不 Ready) | WSL 没就绪(60 秒超时);或 web 服务没起来 | 按底部提示判断:WSL 未就绪 → 检查 WSL;web 未就绪 → 点 **View Log** 看日志,点 **Restart Web** 后重试 |

## 8. 停止系统

1. **停止实验:** 实验运行中,主界面顶部按钮显示 **Running…**,点它停止实验(或等它自然结束)。
2. **停止系统:** 点侧边栏 **Operations** 组的 **Stop System**。系统停止后端、前端与桥进程,状态依次 **Stopping…** → **Stopped**,主区回到 "System Offline"。
3. **退出总控:** 点 **Exit Launcher** 关闭总控台服务(无窗口,日志在 `launcher_server.log`)。退出总控**不影响** WSL 侧实验——它只是关闭控制界面。
4. **安全收尾:** 关闭设备电源,拔掉不用的 USB;湿电极擦净凝胶。
