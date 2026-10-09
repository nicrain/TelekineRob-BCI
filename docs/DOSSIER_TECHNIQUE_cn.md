# TelekineRob-BCI 技术档案（中文版）

[返回中文项目总览](../README_cn.md) · [法语版](DOSSIER_TECHNIQUE.md)

产品说明 · 技术需求 · 系统设计

| 文档信息 | 内容 |
|---|---|
| 版本 / 日期 | v0.4 / 2026-10-09 |
| 实现核对基线 | `main` 的 `ce1ed66`；当前实现与下一阶段需求分开说明 |
| 读者 | 项目负责人、接手开发者、需要了解系统边界的使用者 |
| 适用环境 | 项目目标环境为 Windows + WSL2，Ubuntu 24.04、ROS2 Kilted；不是对所有系统版本的兼容性保证 |
| 验证状态 | 代码核对及已执行测试的范围见[验证口径](#41-验证口径)；完整仿真与目标电脑真机验收尚无完整验证记录 |

本文件汇编当前产品定义、实现需求和设计，不是安装命令手册或逐步点击教程。日常使用见[中文操作手册](MANUEL_OPERATEUR_cn.md)，问题恢复见[中文排障手册](GUIDE_DEBUG_cn.md)，安装、调试、更新与恢复见[中文开发手册](GUIDE_DEVELOPPEUR_cn.md)。

## 阅读导航

- 项目负责人：[产品说明](#1-产品说明) → [技术需求](#2-技术需求) → [验收与验证状态](#4-验收与验证状态)。
- 新开发者：[系统总体设计](#31-系统总体设计) → [数据处理](#35-eeg信号处理设计) → [配置与接口](#39-配置与持久化设计) → [限制和待确认信息](#5-当前限制与待确认信息)。
- 快速查找：[启动与状态](#33-启动与状态设计) · [设备连接](#34-设备连接设计) · [自动校准](#37-校准设计) / [手动调整校准值](#手动调整校准值) · [断流与恢复](#38-断流与恢复设计) · [接口](#310-接口与数据契约) · [测试口径](#41-验证口径)。
- 下一阶段开发重点：[同型号双 g.tec 需求](#25-下一阶段主要需求同型号双-gtec) → [开发者实施路线](GUIDE_DEVELOPPEUR_cn.md#75-首要开发任务同型号双-gtec-集成)。

## 0. 事实、需求与证据的区分

本文使用三种证据口径：

1. **代码确认**：能在当前源码或仓库配置找到实现依据，不等于在目标电脑执行成功。
2. **用户确认**：来自项目实际使用信息，例如使用集成蓝牙、指定USB口、Headband手动运行；不推广成所有电脑或厂商设备的通用结论。
3. **测试确认**：仅指有明确运行环境和结果的测试记录；测试文件存在或代码审阅通过，不等于运行测试通过。

需求编号用于对应实现与验收，不代表已经全部验收。标为“待确认”的性能指标、机器实值和授权信息必须补证据，不能填成产品保证。

## 1. 产品说明

### 1.1 项目目的

TelekineRob-BCI将g.tec设备采集的EEG数据转换成Thymio机器人的运动命令，并提供连接、参数选择、校准、信号观察和停止控制的网页界面。

核心场景是单人单设备控制，以及两人各使用一台设备、分别负责速度和转向的协同控制。系统同时保留仿真和手动遥控路径，便于开发与链路检查；完整ROS / Gazebo / 网页仿真流程尚无完整验证记录。

这里的“注意力控制”指按选定EEG指标和校准参数进行策略映射，不是直接读取用户意图，也不是已验证的注意力诊断或干预效果。本文不定义临床研究方案，不承诺疗效或跨被试一致的控制准确率。

### 1.2 参与者与职责

| 参与者 | 职责 |
|---|---|
| 非计算机专业操作者 | 按手册启动、连接、校准、控制、停止及恢复常见小问题 |
| EEG佩戴者 | 按当前任务承担Speed或Steering角色 |
| 开发人员 | 部署、调试、修改代码、验证、备份恢复和维护 |
| 项目负责人 | 确定运行配置、使用范围、验收标准与数据访问权限 |

### 1.3 硬件与软件组成

| 组成 | 当前用途 |
|---|---|
| Windows电脑及集成蓝牙 | 运行System Control、连接EEG、运行桥脚本 |
| g.tec BCI Core-4 Headband | 4通道EEG，经gpype桥发布LSL |
| Unicorn Hybrid Black | 8通道EEG，经UnicornPy桥发布LSL |
| Thymio及其USB Dongle | 无线机器人控制；Dongle从Windows attach到WSL |
| WSL2 / Ubuntu | 运行ROS2、信号处理和web服务 |
| 浏览器 | 显示总控和EEG控制页面 |

两个EEG在原项目电脑默认使用集成蓝牙，该选择基于现场连接稳定性，不是厂商通用要求；依据和迁移限制见[设备连接设计](#34-设备连接设计)。Thymio Dongle仍然需要插入，它与EEG蓝牙适配器不是同一种设备。

部署所需的版本与本地配置见[开发手册环境检查](GUIDE_DEVELOPPEUR_cn.md#21-环境基线与检查)；蓝牙、电源和电量检查见[排障手册使用前检查](GUIDE_DEBUG_cn.md#1-每次实验前检查)。

### 1.4 两个页面与正常使用流程

| 页面 / 入口 | 职责 | 状态的含义 |
|---|---|---|
| `launcher.bat`打开的System Control | 起停WSL与网页服务、连接设备、显示连接状态、日志与网页恢复 | Running主要表示网页服务准备好，不表示EEG正在控制机器人 |
| 主区域的Thymio EEG Control | 选择输入、角色、指标、输出，校准、观察指标，Start / Stop控制 | 顶部Running是前端本地运行标记，不持续探测ROS进程健康，也不替代设备 / 数据链路检查 |

前端顶部状态与后端 `running` 标记都不是ROS子进程的持续健康监测；Start / Stop请求失败或子进程退出时，不能只凭按钮状态判断控制已启动或停止。实际运行需结合节点、话题数据和机器人响应确认，诊断方法见[开发手册的ROS检查](GUIDE_DEVELOPPEUR_cn.md#63-wsl网页与-ros-检查)。

正常流程为：

```text
设备及电脑检查
  → 打开System Control → Start System
  → 连接所需EEG和真实Thymio（仿真无需真实机器人）
  → 选择Role / Device / Brand / Metric / Output Target
  → 按设备逐个校准
  → 确认校准结果；建议校准与正式控制之间先Stop，再Start
  → 暂停或结束时Stop
  → Headband脚本Ctrl+C → Stop System → Exit Launcher
```

图中的Stop / Start指EEG控制页面的按钮，不是System Control的Stop System / Start System。单设备校准可能继续运行，双设备校准结束后界面自动请求Stop；建议分开校准与正式控制阶段，不是说所有新校准值必须重启才生效，详见[校准结束后的控制状态](#校准结束后的控制状态)。Headband还需要额外的VS Code手动运行步骤，详见[设备连接设计](#34-设备连接设计)。本产品当前不是完全“零终端”的工作流。

### 1.5 使用模式与运动语义

| 模式 | 配置 | 运动 / 用途 |
|---|---|---|
| 单EEG速度 | 第一行Role=Speed，Device=EEG；第二行None | 根据指标输出前进速度，不承担转向 |
| 单EEG转向 | 第一行Role=Steering，Device=EEG；第二行None | 根据指标原地旋转，眨眼切换左右方向 |
| 双EEG协同 | 两路EEG，分别Speed与Steering | 融合前进与旋转命令；两路均须保持有效 |
| 手动检查 | 一路，Device=Keyboard；第二行None | 鼠标 / 触摸方向按钮，用于单独检查机器人链路 |
| 仿真输出（开发路径） | Output Target=Thymio Simu | 代码配置为向Gazebo中的Thymio输出；完整流程待验证，且不能证明USB或真实电机链路可用 |

双设备的当前设备组合是Headband和Hybrid Black。当前桥使用每种型号固定的source_id，没有实现多台同型号设备的唯一身份管理；不能把“双EEG”理解为任意两台EEG均可直接使用。

支持同型号双设备是已确认的下一阶段主要需求，不是当前已交付功能；范围与验收见[第 2.5 节](#25-下一阶段主要需求同型号双-gtec)。

EEG中的Steering单独控制时是原地转向。双设备融合时可以同时前进和转向，实际为两路命令共同作用。Keyboard的左右按钮另外使用手动控制参数，不能直接套用EEG的原地转向语义。

### 1.6 显示内容与可观察结果

网页图表展示频带功率、派生指标、控制意图及校准参考的时间序列；不是原始电极电压的逐样本示波器。实时显示意味着持续更新，不意味着零延迟、250Hz网页刷新或精确同步的原始数据记录。

设备状态绿色、图表有数据、管线Running、机器人运动是不同证据：

- EEG绿色：Windows的LSL探针读到有效样本。
- Thymio绿色：配置的WSL设备检查通过，当前检查为 `/dev/ttyACM0`存在。
- 图表更新：分析消息已经经过ROS和后端到达浏览器。
- 机器人运动：还需要输出配置、有效速度命令、驱动和机器人本身正常。

因此Thymio不动时保留Keyboard单独测试，见[用户排障步骤](GUIDE_DEBUG_cn.md#b-thymio-没有动作)。

### 1.7 产品边界

- 当前 EEG 控制管线只支持 LSL 输入。
- SDK安装、首次Windows蓝牙配对、Dongle共享、ROS构建和机器配置不是Start System自动完成的任务。
- 无完整的多用户登录、权限角色体系、互联网部署方案或自动升级系统。
- 没有证据保证连续使用时长、无线断连率、完整控制延迟或每位用户的分类性能。
- 当前项目未实现原始 EEG 数据的保存功能。网页第 4 部分仅供开发人员收集处理后的指标与控制信息，用于验证系统，不是日常控制的必要步骤；该功能目前仍保留，后续可考虑屏蔽或删除。
- 源码保留循线、RViz等路径，但不属于本文标准EEG控制流程的已验证功能；如需启用，应单独验证。

## 2. 技术需求

### 2.1 需求范围与验收规则

第 2.2～2.4 节定义当前系统的需求与限制；[第 2.5 节](#25-下一阶段主要需求同型号双-gtec)单独列出已确认、尚未实现的下一阶段需求。需求的代码实现、自动测试和目标环境验收分别记录，不能互相替代。

统一要求：测试前明确使用真机还是仿真。真机放在平坦、安全且有活动空间的位置，周围无障碍物，远离桌边和台阶，避免校准结束或数据恢复时的动作造成碰撞、跌落；重连、重新配置或重启前先停止控制并确认停车。验收记录应包含commit、实际配置、运行环境、步骤、预期与观察结果，失败和skip不能写成通过。

### 2.2 功能需求

| 编号 | 需求与通过条件 | 设计依据 | 验证方式 / 当前状态 |
|---|---|---|---|
| RF-01 | System Control能启动网页服务并显示结果；失败时不伪装成Running | [启动设计](#33-启动与状态设计) | 代码已实现；目标电脑起停及失败场景待验收 |
| RF-02 | Headband Connect打开脚本，手动运行后按数据活性显示连接；手动中断后可结束连接 | [设备连接](#34-设备连接设计) | 用户确认当前流程；需复验解释器、API与状态变化 |
| RF-03 | Hybrid Black Connect / Disconnect能够启动 / 停止托管桥，连接确认基于LSL样本 | [设备连接](#34-设备连接设计) | 代码已实现；目标电脑SDK与设备待验收 |
| RF-04 | 已共享的1-1 Dongle可attach到配置的WSL并通过设备检查；新Dongle的共享步骤可查 | [Thymio连接](#34-设备连接设计) | 配置与流程已核对；USB / 配对 / 电机链路待验收 |
| RF-05 | 单EEG可选Speed或Steering；双EEG两路角色不同，按实际source_id读取对应数据 | [路由设计](#36-策略与运动映射设计) | 模型与代码已实现；设备 / 角色交换待验收 |
| RF-06 | 可选择Alpha、TBR、EI策略；策略采用本路校准参数和EMA | [信号处理](#35-eeg信号处理设计)、[策略设计](#36-策略与运动映射设计) | 策略已实现；正式使用的指标与控制效果待确认 |
| RF-07 | 节点从首个有效指标帧开始采集30s；至少50个指标样本才保存新校准参考值；不足时清除校准状态 | [校准设计](#37-校准设计) | 校准判断 / 写回相关测试通过；完整链路待验收 |
| RF-08 | 两路校准分别保存，不能覆盖另一路配置；校准后的启动读取保存结果 | [配置设计](#39-配置与持久化设计) | 代码已实现；双设备独立校准待真机确认 |
| RF-09 | 双设备融合取Speed的linear.x、Steering的angular.z，其余Twist分量为零 | [运动映射](#36-策略与运动映射设计) | 融合纯函数测试通过；ROS路由 / 电机待验收 |
| RF-10 | 眨眼确认切换Steering方向；确认与冷却期间转向意图钳到中性 | [眨眼设计](#36-策略与运动映射设计) | 检测器相关测试通过；真实主动 / 自然眨眼表现待测 |
| RF-11 | 单路数据陈旧发送零命令；双路缺失 / 陈旧时融合器输出整车零命令 | [断流设计](#38-断流与恢复设计) | 看门狗 / 融合函数测试通过；全链路停车及恢复待测 |
| RF-12 | 图表按role显示各路新鲜分析数据，不把连接状态当成EEG曲线更新 | [显示接口](#310-接口与数据契约) | 代码已实现；角色交换、断流和刷新待验收 |
| RF-13 | Keyboard按钮能发送方向和停止；用于区分EEG问题与机器人链路问题 | [手动路径](#36-策略与运动映射设计) | 鼠标 / 触摸流程已核对；实际动作和停止待验收 |
| RF-14 | 网页Stop、Headband手动停止、Stop System、Exit Launcher职责不同且文档明确 | [生命周期](#33-启动与状态设计) | 代码与手册已核对；残留进程及机器人停住待验收 |
| RF-15 | 参数修改可保存并重新加载；停止时可逐路手动调整Min / Max，下一次Start读取；返回实际源码配置路径以支持定位错误仓库 | [手动校准值](#手动调整校准值)、[配置设计](#39-配置与持久化设计) | config_store与界面已实现；手动调整、源码 / install一致性待验收 |
| RF-16 | 日志与网页恢复入口可用；重启或诊断前能保存所需信息 | [观测设计](#311-错误处理与可观测性) | 日志路径已核对；真实错误消息与恢复待验收 |

### 2.3 非功能需求与限制

| 编号 | 技术要求 | 当前实现 / 限制 | 通过条件 |
|---|---|---|---|
| RN-01 安全停止 | 必须明确数据新鲜度、零命令和恢复行为 | 单节点 / 融合器watchdog为软件保护，不是硬件急停 | 测实际停车与恢复；操作者知道恢复可能自动续动 |
| RN-02 实时性 | 不积压处理完的旧窗口；说明各层更新节奏 | 适配器只取最新PSD结果；不同层频率不同，无硬实时保证 | 记录卡顿 / 延迟现象；需要数值门槛时由负责人确定并测量 |
| RN-03 可用性 | 常规流程可按非技术用户手册执行 | Headband仍需VS Code，异常情况下需PowerShell共享检查 | 用户按手册独立完成一轮，按钮 / 截图与实际一致 |
| RN-04 可维护性 | 参数位置、模块职责与测试入口可追踪 | YAML、JSON配置与模块化策略 / 适配器已存在；并非所有算法常量均已配置化 | 新开发者能定位一个问题并完成小修改及对应验证 |
| RN-05 可重建性 | 新电脑能获取依赖与授权并恢复部署 | requirements与npm lock不包含完整ROS / Windows SDK环境 | 补版本和安装来源，在目标环境复现并记录 |
| RN-06 状态准确性 | 状态显示与其实际探测对象对应 | 绿色 / Running各有边界，健康检查不是完整控制验收 | 分别测试服务、LSL、ROS和机器人链路 |
| RN-07 网络边界 | 真实机器人控制只在明确授权的使用范围开放 | loopback、origin及可选token不是完整用户认证；代理路径需核验 | 确认实际监听、转发和客户端来源，不向不可信网络直接暴露 |
| RN-08 数据与备份 | 可识别配置、分析文件、日志和原始数据的区别，并有恢复方法 | Windows本地config被同步排除；默认 `experiment_data/` 整目录已Git忽略，历史未清除；自定义输出路径须另行检查 | 明确保存数据的范围、权限、备份和恢复验证 |

### 2.4 尚未确定的量化指标

当前只记录代码设置，不制定未经确认的产品性能门槛：

| 项目 | 已知 | 待确认 |
|---|---|---|
| 采样 / 显示 | 设备档案名义采样率250Hz；实际从StreamInfo读取；PSD默认1s窗、0.5s步长 | 目标电脑有效数据率、抖动、显示延迟 |
| 控制刷新 | EEG节点及融合器默认20Hz；网页流循环约0.2s一次 | 实际调度、端到端响应、设备与电机延迟 |
| 停车 | 软件有数据新鲜度和零命令逻辑 | 从数据中断到实际停车的时限、浏览器 / 网络失效场景 |
| 控制质量 | 指标、校准、眨眼确认及EMA已实现 | 命中、误动作、自然眨眼误触、跨人 / 跨次稳定性 |
| 连续运行 | 桥有重连 / 重建逻辑 | 连续运行时长、断连频率、重连成功率 |
| 部署兼容性 | 项目目标栈已明确 | 实际OS、SDK、Python、ROS / Gazebo和工具版本组合 |

### 2.5 下一阶段主要需求：同型号双 g.tec

**状态：需求已确认，尚未实现；当前安装 SDK 的双设备并发能力及真机表现待现场验证。**

目标是在同一 Windows + WSL2 系统中同时采集两台同型号 g.tec EEG，分别绑定 Speed 和 Steering，控制同一台 Thymio。目标组合为两台 Hybrid Black、两台 Headband；先验证哪一组合，由现场可用设备及 SDK 验证结果确定。保留现有单设备和 Headband + Hybrid Black 混合模式。

本需求不扩展到任意数量 EEG、多机器人控制或跨设备原始信号严格同步。不能仅解除前端品牌禁选就宣称完成：现有两个 ROS 节点与融合器可以复用，但设备发现、唯一身份、桥生命周期、配置和状态探针均需核对。

| 编号 | 新需求与通过条件 | 当前缺口 / 验收依据 |
|---|---|---|
| RF-NEXT-01 并发采集 | 两台同型号真实设备可同时产生可区分、持续更新的 EEG 流；记录 SDK 版本、运行方式及测试时长 / 异常 | 当前未做目标电脑验证；授权条件向 Lucas 核实，SDK 限制向厂商资料 / 支持确认；模拟流不能替代 |
| RF-NEXT-02 设备身份 | 型号、物理序列号、唯一且稳定的 LSL source_id、角色分别表达；两路不允许选同一物理设备 | 当前 source_id 按型号固定；唯一身份必须覆盖桥、探针、配置和 ROS，冲突的有效流不得任意选第一条 |
| RF-NEXT-03 独立生命周期 | 每台设备有独立连接状态和日志；断开 / 重连 A 不改 B 的设备绑定，A 只重连原序列号 | Hybrid 当前连接和重连均取第一台；Headband桥内看门狗按流名扫描，总控探针按source_id选第一条，两者均须区分物理设备，不能用 B 的样本证明 A 正常；保留 IDE 手动工作流 |
| RF-NEXT-04 配置与校准 | 页面可选相同型号的不同设备；保存、刷新和重启后身份 / 角色一致；分别校准且不串用 | 当前页面禁同型号，按品牌重建 source_id；校准按两条配置保存，不是按物理设备管理；更换设备或校准条件后须重新校准 / 验证 |
| RF-NEXT-05 信号与控制正确 | 设备身份变化不关闭型号所需滤波；确认采样率、通道与单位；角色互换后仍只由对应设备驱动速度 / 转向 | Hybrid 当前额外滤波按流名称判断；身份与型号不可混为一谈；保留部分命令话题及现有融合语义 |
| RF-NEXT-06 安全与兼容 | 任一路断流保留融合器零速度保护；单设备、混合型号、校准和停止流程回归通过 | 0.5s 软件阈值不是整机停车保证；仍 Running 时恢复可能续动，须实测并记录，不得关闭保护来通过验收 |

两份 Hybrid Black API licence 的存在不能证明同机双设备并发已获许可或已可运行；需核对实际 SDK 能力与适用授权条件。授权状态、资料联系人及迁移方式见[开发手册授权说明](GUIDE_DEVELOPPEUR_cn.md#hybrid-black-api-授权)。

接手开发人员的阶段任务、代码入口、最小验证和回归清单集中在[开发者第 7.5 节](GUIDE_DEVELOPPEUR_cn.md#75-首要开发任务同型号双-gtec-集成)，不在本档案重复维护实现步骤。RF-NEXT 验收结果与当前 RF 基线分开登记；没有通过真实双设备测试时，只能报告软件验证进展。

## 3. 系统设计

### 3.1 系统总体设计

```text
Windows
  集成Bluetooth ← Headband / Hybrid Black
  gpype_lsl_bridge.py / unicornpy_lsl_bridge.py → LSL
  launcher.bat → launcher_server.py（8020）→ System Control
       ├─ WSL启动检查、文件同步、网页服务管理、LSL活性探针
       └─ usbipd attach（1-1）→ WSL内USB串行设备

WSL / Ubuntu
  EEG节点内：LSL → RawLslAdapter（预滤波 / PSD）
                  → enrich_features → Policy → 角色速度映射
       ├─ 单路：最终速度topic
       └─ 双路：/eeg_cmd_vel/<role> → cmd_vel_fuser → 最终速度topic
  最终速度topic → Thymio驱动 → 真机
                 或 Gazebo桥 → 仿真
  分析topics → RosBridge → FastAPI（8010）→ WebSocket
  React / Vite（5173）← 分析显示 / 参数 / 控制操作

浏览器
  System Control（本机总控）嵌入Thymio EEG Control
  前端通过Vite代理访问/api与/ws，不需直接暴露后端8010
```

图中的端口、发行版、路径和BUSID是仓库配置基线，可由机器本地配置改变。当前配置详见 [windows_launcher/config.json](../windows_launcher/config.json)。

单一WSL仓库作为launcher与桥代码的同步来源，是为了避免维护两套代码；不是自动获取远程更新。Windows机器配置保留在本地，配置边界见[开发手册](GUIDE_DEVELOPPEUR_cn.md#22-路径与配置模板)。

### 3.2 模块职责与关键设计选择

| 模块 | 职责与入口 | 设计理由 / 边界 |
|---|---|---|
| Windows总控 | [launcher_server.py](../windows_launcher/launcher_server.py) | 浏览器不能直接执行wsl、usbipd、Python；本地控制服务负责执行与状态管理 |
| Headband桥 | [gpype_lsl_bridge.py](../gtec_bridge/gpype_lsl_bridge.py) | SDK运行在Windows；当前由IDE启动，重建数据管线以恢复部分断流 |
| Hybrid桥 | [unicornpy_lsl_bridge.py](../gtec_bridge/unicornpy_lsl_bridge.py) | 用UnicornPy采集并发布LSL；launcher托管进程，采集异常后重连 |
| 数据适配器 | [lsl_raw.py](../thymio_control/thymio_control/adapters/lsl_raw.py) | 统一read_frame接口，读取StreamInfo；不能据此宣称支持所有LSL设备 |
| 信号处理 | [band_power.py](../thymio_control/thymio_control/processors/band_power.py)、[enrich.py](../thymio_control/thymio_control/processors/enrich.py) | 流式PSD、单位转换和特征计算与ROS解耦，便于测试 |
| 控制策略 | [pipeline.py](../thymio_control/thymio_control/pipeline.py)、policies | 用注册表选择Alpha / TBR / EI，保留各路校准及平滑状态 |
| EEG节点 | [eeg_control_node.py](../thymio_control/scripts/eeg_control_node.py) | 组合数据、校准、策略、眨眼、速度映射、分析发布和看门狗 |
| 双路融合 | [cmd_vel_fuser.py](../thymio_control/scripts/cmd_vel_fuser.py) | 避免两节点争写最终速度；按角色融合，任一路陈旧则零命令 |
| ROS编排 | [experiment_core.launch.py](../thymio_control/launch/experiment_core.launch.py) | 统一真机 / 仿真拓扑，第二节点重命名，使用角色后缀topics |
| 后端 | [main.py](../web_gui/backend/app/main.py)、[config_store.py](../web_gui/backend/app/config_store.py)、[command_runner.py](../web_gui/backend/app/command_runner.py) | 分离API、配置和进程操作；实际命令不由前端直接执行 |
| ROS网页桥 | [signal_subscriber.py](../web_gui/backend/app/signal_subscriber.py) | 在一个rclpy线程内订阅分析、处理遥控队列，避免多执行器争用 |
| 前端 | [App.jsx](../web_gui/frontend/src/App.jsx)、[api.js](../web_gui/frontend/src/api.js) | 展示按角色分路数据、逐路校准和控制；不是信号计算核心 |

策略和适配器分离便于单测与扩展；策略注册表、配置模型和界面选项共同约束可用策略，扩展入口见[开发手册](GUIDE_DEVELOPPEUR_cn.md#73-扩展时不能漏掉的层)。

第三方 ROS-Aseba / ROS-Thymio 使用本项目跟踪版本，其中包含兼容性及仿真相关修改，不能直接视为上游原版。固定来源、逐文件差异及 `use_sim_time` 传递限制见[开发手册第 5.5 节](GUIDE_DEVELOPPEUR_cn.md#55-第三方源码与本项目修改)。

### 3.3 启动与状态设计

System Control的主要状态为Stopped、Starting、Running、Stopping、Error；设备独立为Disconnected、Connecting、Connected、Disconnecting、Error。状态规则见 [state.py](../windows_launcher/state.py)。

Start System主链路：

```text
检查WSL / 共享目录可用
  → robocopy同步launcher与桥（排除Windows config.json）
  → 清理旧网页进程 → 启动后端与前端
  → 检查网页就绪 → 尝试刷新LAN转发并探测结果
  → Running或Error
```

LAN转发失败与网页服务失败是不同问题：前者不必阻塞本机Start System。运行期间另有服务健康检查。Running时按钮显示Restart System；Stopped / Error时为Start System。

网页顶部Start先请求停止旧控制管线，再保存 / 重读配置，并经后端启动ROS launch。后端显式设置 `use_teleop:=false`，网页Keyboard不使用launch里的 `teleop_twist_keyboard` 节点。因此不能用保存的 `launch_args.yaml` 中某次 `use_teleop` 值推断网页启动命令。

生命周期归属：

| 对象 | 启动者 | 停止 / 更新边界 |
|---|---|---|
| Windows总控服务 | launcher.bat | Exit Launcher退出；已运行代码要退出重开才更新 |
| Headband桥 | VS Code里的人工运行 | Ctrl+C人工中断；Disconnect / Stop System不负责杀IDE脚本 |
| Hybrid桥 | launcher | Disconnect / Stop System结束托管进程；新进程读取同步后的脚本 |
| 网页前后端 | launcher经WSL | Restart Web / Stop System管理；重启前先停控制 |
| ROS控制管线 | 后端command_runner | 网页Stop清理；默认按进程名的清理也可能影响同机其他匹配任务 |
| WSL发行版 | WSL命令启动 | 默认Stop System执行终止发行版，不只停止本项目 |

Start / Stop请求携带 `dry_run`；其模型默认true，但当前前端正常控制请求使用false。环境变量 `WEB_GUI_ALLOW_REAL_COMMANDS` 默认true，设false可阻止该启动路径执行真实ROS命令，但不阻断直接遥控发布，不是全系统禁止运动的开关；测试仍须隔离真机输出，详见[命令与网络边界](#312-网络命令与数据边界)。

### 3.4 设备连接设计

**Headband。** 仓库设置 `connect_mode=open_in_ide`：总控打开同步后的脚本并等待LSL样本，但不托管桥进程；桥由操作者在Windows VS Code中手动运行和中断。当前等待超时为120s，不表示120s内一定连上。IDE工作流与g.Pype适用许可相关，不意味着API技术上不能代码连接或VS Code是唯一允许的IDE；许可与安装边界见[开发手册SDK说明](GUIDE_DEVELOPPEUR_cn.md#38-sdk-使用边界与连接方式)，具体点击步骤见[操作手册](MANUEL_OPERATEUR_cn.md#headband-连接与断开)。

Headband脚本建立 `BCICore8(channel_count=4)` → 0.5–45Hz带通 → 48–52Hz带阻 → LSLSender。使用BCICore8类名不代表采集8个通道。桥的看门狗针对数据停滞执行管线重建与重试，与机器人停车watchdog不是同一个计时器。

**Hybrid Black。** `connect_mode=spawn`运行UnicornPy桥，只发送8个EEG通道，source_id固定为 `gtec_hybrid_black`。初次采集失败会退出；采集过程中某些设备异常会触发退避重连。不能把局部异常恢复逻辑理解为任何蓝牙 / SDK故障均可自动恢复。

UnicornPy [官方 API](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api-reference.md)可按序列号连接、开始 / 停止采集及释放连接，不要求IDE人工执行，因此项目由总控托管桥。Windows SDK安装与授权独立于Linux环境，部署与迁移见[开发手册SDK说明](GUIDE_DEVELOPPEUR_cn.md#38-sdk-使用边界与连接方式)。

原电脑使用Hybrid Black附带的USB蓝牙适配器时曾频繁断连，改用集成蓝牙后更稳定，因此两台EEG均默认使用集成蓝牙。这是现场经验，与厂商Suite手册推荐附带适配器不同；换电脑或增加设备时须重新验证，参考资料见[开发手册蓝牙选择](GUIDE_DEVELOPPEUR_cn.md#蓝牙选择)。

**EEG状态探测。** launcher用该设备的 `python_cmd` 运行LSL探针；因此VS Code脚本运行成功但探针解释器缺pylsl时，仍可能不显示Connected。桥进程存在 / 流存在而没有样本不作为绿色依据。

**Thymio。** 当前命令为 `usbipd attach --wsl=Ubuntu --busid=1-1`；Disconnect执行detach。Shared表示Windows设备已允许共享给Linux，Attached表示已经接入WSL。bind不是常规Connect的自动步骤，新Dongle共享见[排障第4节](GUIDE_DEBUG_cn.md#4-第-7-项怎么做检查并共享新的-thymio-dongle)。

标准Thymio / Dongle对由用户确认通常已配好，无需常规重新配对。当前设备检测不是驱动握手或运动确认；程序不自动选择任意BUSID，设备编号与WSL发行版等本地配置的调整见[开发手册硬件部署约定](GUIDE_DEVELOPPEUR_cn.md#23-硬件部署约定)。

### 3.5 EEG信号处理设计

**设备身份。** 当前标准LSL标识：

| source_id | 设备档案通道 | 档案名义采样率 |
|---|---|---|
| `gtec_bci_core4` | F8、Fp2、Fp1、F7 | 250Hz |
| `gtec_hybrid_black` | Fz、C3、Cz、C4、Pz、PO7、Oz、PO8 | 250Hz |

运行时通道数与采样率来自StreamInfo，不以档案数值代替实际检查。source_id为空时适配器退回按type=EEG发现；无论按source_id还是type查找，当前均取匹配结果第一条。标准组合须确保标识唯一，双设备不能依赖空标识或重复标识保证正确绑定。

**预处理。** Headband在Windows桥直接调用 gpype 的带通（0.5–45Hz）与带阻（48–52Hz）节点，接口见[g.Pype SDK 参考](https://gpype.gtec.at/content/7_sdk_reference/index.html)。Hybrid 的 Windows 桥不调用这套滤波；核对的[UnicornPy 公开参考](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api-reference.md)未提供相应接口，因此WSL适配器使用流式 `StreamingPreFilter` 补相同截止频率的滤波，默认 4 阶 Butterworth 设计与 SOS 实现。这不说明硬件完全无处理，也不证明两种实现的响应 / 延迟完全相同。当前补滤波判断依赖流名 `gtec_hybrid_black`，不只是source_id；改流名或接入新桥时须重新检查处理链，避免漏滤波或重复滤波。具体代码及验证入口见[开发者第 5.4 节](GUIDE_DEVELOPPEUR_cn.md#54-两类-eeg-的预滤波实现)。

**PSD与单位。** 默认滑动窗口1s、步长0.5s，使用Welch PSD计算各通道频带功率：delta 1–4、theta 4–8、alpha 8–13、beta 13–30、gamma 30–100Hz。频段定义不说明预处理后仍保留全部高频信息；带通上限45Hz已限制高频内容。

适配器对通道功率求平均，转换成µV²，并补充可用的按通道指标。单位优先从流描述 `source_unit` 读取；缺失时使用DSP默认µV并警告，不等于成功自动推断厂商真实单位。SDK输出单位与LSL元数据须一致，图表数值“看起来正常”不能证明单位正确。

若一次有多个窗口完成，控制路径只返回最新结果，优先实时性，不构成所有窗口完整留存。

**特征** `enrich_features()`计算：

```text
TBR = theta / (beta + 1e-9)
EI  = beta / (alpha + theta + 1e-9)
Alpha使用平均alpha频带功率
```

适配器先返回含频带功率的 `EegFrame(ts, source, metrics)`，EEG节点再调用 `enrich_features()`得到上述派生特征。`source="lsl_raw"`表示适配器类型，不是设备source_id或物理序列号；不能靠该字段区分两台设备。当前适配器的ts是产生分析帧时的墙上时钟，不保留采集端每个原始LSL样本的时间戳，不能据此承诺原始采集到电机的精确端到端延迟。

开发合成流也不是两种真实处理链的等价替代：[dummy_dual_streams.py](../thymio_control/lsl_test/dummy_dual_streams.py)中的Hybrid流名为 `hybrid_black_EEG`，不会触发上面按名称启用的Hybrid补滤波。相关数值测试与完整仿真的边界见[验证口径](#41-验证口径)。

### 3.6 策略与运动映射设计

三个策略先对各自指标做EMA，再按本路offset / scale归一化并截断到0–1。EMA默认系数0.35，第一帧直接取当前值；该系数在策略类中，不是当前界面可调的YAML参数。

令归一化值为n：

| 策略 | n的来源 | speed_intent | steer_intent |
|---|---|---|---|
| Alpha | alpha平滑值 | 1−n | max(0.5, 0.75−0.5n) |
| TBR | theta_beta平滑值 | 1−n | max(0.5, 0.75−0.5n) |
| EI | beta_alpha_theta平滑值 | n | max(0.5, 0.25+0.5n) |

公式是当前软件的控制映射，不是独立证实的生理状态测量结论。归一化scale应有效；自动校准会设置下限0.001，不应把直接改文件为0视为受支持的配置。

在标准 `line_mode=''` 路径中：

```text
Speed:
  linear.x = max_forward_speed × speed_intent
  angular.z = 0

Steering:
  linear.x = 0
  magnitude = abs(steer_intent − 0.5)
  magnitude < steer_deadzone时 angular.z = 0
  否则 angular.z = −steer_direction × turn_angular_speed × magnitude
```

速度命令单位为m/s，角速度为rad/s；参数值是命令尺度，不是电机实测速度。现行策略转向意图范围0.5–0.75，因此实际角速度也不是恒等于 `turn_angular_speed`。节点默认值、后端默认值、当前YAML保存值可能不同，正式运行的参数以确认后的实际配置为准。

单EEG直接发最终速度topic；双EEG各发角色partial，融合器按Speed.linear.x和Steering.angular.z合成。第一路 / 第二路和品牌不永久对应角色。

**眨眼换向。** `MetricBlinkDetector`相对30帧滚动中位数检测上冲 / 下降，默认至少15帧建立基线、连续2帧确认、4帧冷却。Alpha / TBR上冲阈值为基线×2；EI下降阈值为基线×0.5。上冲模式在参考值为正时，额外以节点创建时读取的 `calib_offset + calib_scale` 为基线下限。自动校准且未触发最小scale修正时，该值近似对应p50；手动调整后则是设定的Max，不能统一称为p50。该规则并不消除所有自然眨眼或肌电误触发。

确认事件使 `steer_direction` 乘−1；1表示右、−1表示左。在确认 / 冷却期间转向意图置0.5，不冻结旧的非零转向命令。确认帧和冷却帧按指标帧计数，不是原始250Hz样本数。

**手动路径。** Keyboard按钮发送forward、backward、left、right、stop，经 `/ws/teleop`入RosBridge队列，再由ROS线程发布Twist。松开 / 离开按钮发送stop，前端200ms后补发stop；这不是服务器端网络失联急停保证。当前WebSocket断开处理没有显式发送零命令，相关风险须在[停止验收](#42-目标电脑验收场景)中核验。

### 3.7 校准设计

#### 自动校准与保存

```text
Calibrate选中一路
  → 保存该路calibrate=true并启动ROS管线
  → 界面Preparing，等待该路分析数据
  → 节点首个有效指标帧后采集30s；界面从该路首个分析帧开始倒计时
  → 样本达到50：计算p5、p50；不足：中止，不生成新参考值
  → 写对应参数文件并清除calibrate
  → 更新当前policy的offset / scale，保留EMA
  → 前端轮询配置回读结果
```

```text
calib_offset = round(p5, 4)
calib_scale  = round(max(p50 − p5, 0.001), 4)
```

至少50个样本指本路策略指标样本，不是50个原始电压采样点。30s也是数据开始后采集时长，不是从按按钮到完成的总耗时。

节点尝试写源码与colcon安装目录。写文件失败会记录错误；清除calibrate或倒计时结束本身不保证保存成功。前端新旧参数未变化时会提示没有新值，这也可能是重复采集得到相同四舍五入结果，并不能单凭相同值认定故障。保存问题的定位见[开发手册配置检查](GUIDE_DEVELOPPEUR_cn.md#63-wsl网页与-ros-检查)。

两路文件独立，校准值按当前两条配置保存，并非按物理设备建立个人档案；换设备、指标、佩戴条件或角色配置后，不应直接沿用旧值而不验证。Preparing表示等待该路分析数据，不等于已经开始采集；等待异常的恢复见[排障手册](GUIDE_DEBUG_cn.md#a-校准卡在-preparing--启动后没有波形)。

#### 校准结束后的控制状态

Calibrate在点击时就启动控制管线。校准中的节点不发布运动命令；结束并清除校准标记后，节点可恢复发布，随后前端才通过轮询获知结果：

- 单设备：前端不自动请求Stop，可能继续Running。成功校准会立即原位更新policy的offset / scale并保留EMA，不必为了让这些值生效而重启。
- 双设备：每一路校准结束后，前端自动请求Stop，而不是等结束时才首次启动管线。节点恢复发布到Stop完成之间仍可能有短暂命令，不能把它当成同步停止保证。

Steering使用Alpha / TBR时，眨眼检测器的上冲基线下限来自节点创建时的 `calib_offset + calib_scale`；自动校准只更新policy，不刷新这个旧参考。Stop / Start会让新节点读取新参考，不能把这个原因推广成所有指标的校准值都必须重启才生效。

真机在校准前就应放到[安全测试位置](#21-需求范围与验收规则)，不是到倒计时结束才处理可能的动作。用户点击步骤见[操作手册校准说明](MANUEL_OPERATEUR_cn.md#校准)。

#### 手动调整校准值

网页支持在停止状态下分别编辑每一路的Min / Max；运行时输入框禁用。这里是选定指标的归一化参考范围，不是原始EEG电压的最小 / 最大值：

```text
Min = calib_offset
Max = calib_offset + calib_scale
```

修改Min只写offset，保留scale，因此显示的Max也会跟着移动；修改Max则写 `scale=max(0.001, Max−Min)`。两端值按编辑顺序分别保存，不是原子更新；同时调整两端时应先设Min，再设Max，否则后改Min会移动已设定的Max。Max不大于Min时会被最小scale规则修正，不是形成反向区间。

修改经配置API保存到该路参数文件，下一次Start读取，并非对运行中ROS节点的实时调参。手动调整改变归一化范围，不修复断流、单位或佩戴问题；写回路径见[配置与持久化设计](#39-配置与持久化设计)。

### 3.8 断流与恢复设计

EEG节点以20Hz调度，但PSD指标约2Hz产生。正常两帧之间没有新指标不等于断流；在新鲜度宽限内，节点回放最近意图以维持partial消息流。

| 情况 | 单路节点 | 双路节点 / 融合器 |
|---|---|---|
| 最近数据仍新鲜 | 持续发布最近命令 | 持续发布partial，融合器按两路新鲜消息输出 |
| 数据超出节点阈值 | 发一次零Twist，之后静默 | 节点停止partial，融合器在接收消息超时后持续发零Twist |
| 仍Running且数据恢复 | 节点恢复计算和发布 | 两路均恢复新鲜时融合器恢复输出 |
| 人工按网页Stop | 管线停止 | 管线 / 融合器停止；仅恢复数据不应代替人工重新Start |

节点的EEG数据阈值和融合器的partial阈值是两级检查，不能将后者0.5s直接表述为整套系统停车上限。设备桥重连、launcher颜色轮询、ROS数据新鲜度、浏览器显示也各有不同节奏。

这些机制针对数据丢失，不证明ROS线程挂死、机器断电、USB失效或遥控网络断开时均能安全停住；驾驶环境及实际驱动停止行为必须验收。需明确暂停时点Stop，而非等待自动恢复逻辑。

### 3.9 配置与持久化设计

| 来源 | 内容 | 读取 / 修改者 | 更新与备份规则 |
|---|---|---|---|
| Windows本地 `windows_launcher/config.json` | WSL、同步目录、解释器、USB命令、服务与侧边栏 | launcher | 被同步排除；必须单独备份实际文件，仓库版只是基线 |
| 源码 `thymio_control/config/launch_args.yaml` | launch保存设置 | 后端config_store；安装版由ROS launch读取 | 确认源码与安装目录关系 |
| `eeg_control_node.params.yaml` | 第一路策略、source_id、校准、运动等 | 后端 / EEG节点 | 用户配置和校准会改写，不是永久默认样例 |
| `eeg_control_node.eeg2.params.yaml` | 第二路配置 | 后端 / 第二节点 | 独立写回；停用第二路时后端仍可写安全默认文件 |
| 环境变量 | 真执行门禁、绑定地址、origin、token、数据目录 | 后端启动时读取 | 环境改变需按正确流程重启；token不写公开文档 |
| DSP / 策略类常量 | 窗长、步长、频段、EMA等 | 代码 | 并非都已通过界面或YAML暴露 |

`GET /api/config`的 `source_files`只报告后端源码文件路径，不报告所有ROS安装配置或Windows本地配置。`reload=true`重新从文件读入配置；更新为 `PUT /api/config` 的patch形式。

`brand`在前端根据source_id映射，后端不把该额外字段作为设备身份持久化。`eeg2=null`表示不开启第二路，`run_eeg2`由保存逻辑推导。双路同角色配置被模型拒绝。

后端修改的源码配置与ROS实际读取的安装配置需保持一致；校准值变化本身不要求重新编译。两套路径的检查和更新边界见[开发手册配置说明](GUIDE_DEVELOPPEUR_cn.md#53-三套配置边界)。

### 3.10 接口与数据契约

**ROS topics。**

| 场景 / topic | 载荷 | 方向 |
|---|---|---|
| 单路 `/eeg_analysis` | std_msgs/String中的分析JSON，含role | EEG节点 → RosBridge |
| 双路 `/eeg_analysis/speed`、`/eeg_analysis/steering` | 分路分析JSON | 两个EEG节点 → RosBridge |
| `/eeg_cmd_vel/speed`、`/eeg_cmd_vel/steering` | geometry_msgs/Twist的角色partial | EEG节点 → fuser |
| 真机 `/cmd_vel` | geometry_msgs/Twist | 单节点 / fuser / 手动RosBridge → 驱动 |
| 仿真 `/model/thymio/cmd_vel` | geometry_msgs/Twist | 单节点 / fuser / 手动RosBridge → 仿真桥 |
| `/led` | Thymio LED消息（驱动消息可用时） | Steering显示方向用途，不是电机指令反馈 |

角色后缀是 `steering`，不是 `steer`。第二节点名为 `eeg_control_node_eeg2`，避免与第一节点重名。标准流程不同时开启EEG和手动遥控争写最终topic；拓扑中没有通用多控制源仲裁器。

**分析JSON。** 节点发布 `ts`、`cmd_vel_ts`、`source`、`role`、`metrics`、`features`、`intents`、`control_mode`、`command_linear_x`、`command_angular_z`、`steer_direction`。command字段是本节点计算的命令，`cmd_vel_ts`是计算时的墙上时钟；它们不是命令发布确认或电机反馈。校准期间分析消息仍可包含非零计算值，但校准中的节点不发布该运动命令；双设备时这些字段也不等于最终融合命令或真实轮速。

**网页消息。** RosBridge订阅三个分析topic，按消息role / topic分路；旧帧超过其0.5s新鲜度阈值后不再返回。WebSocket `/ws/stream`主要结构为：

```json
{
  "status": { "running": true },
  "devices": {
    "speed": {
      "channels": { "alpha": 0.0, "beta": 0.0, "theta": 0.0 },
      "features": { "theta_beta_ratio": 0.0, "focus_index": 0.0 },
      "control": { "speed_intent": 0.0, "steer_intent": 0.5 },
      "timestamp": 0.0
    }
  },
  "timestamp": 0.0
}
```

此为字段示意，省略其他字段，数值不作为测试数据或有效测量。第二路按 `steering`键显示；无新鲜帧时实际接口可返回 `devices=null`。网页循环约每0.2s发送最新快照，不表示每次都是一个新PSD结果。

**核心HTTP / WebSocket入口。**

| 服务 | 入口 | 职责 / 载荷 |
|---|---|---|
| Windows总控 | GET `/status`、`/config`、`/log` | 总控状态、侧边栏配置、日志尾部 |
| Windows总控 | POST `/start-system`、`/stop-system`、`/restart-system`、`/restart-web` | 系统 / 网页生命周期 |
| Windows总控 | POST `/connect-device`、`/disconnect-device` | `{"device":"headband"}`等；Hybrid内部key为hybrid |
| Windows总控 | POST `/shutdown`、`/lan-forward/fix` | 退出总控 / 请求LAN转发修复 |
| WSL后端 | GET `/api/health`、`/api/status` | ROS桥初始化 / 错误信息、后端探测状态 |
| WSL后端 | GET / PUT `/api/config` | ConfigEnvelope；PUT为 `{"patch":{...}}` |
| WSL后端 | POST `/api/system/start`、`/api/system/stop` | `{"dry_run":false}`表示请求真实控制，另受环境门禁 |
| WSL后端 | WS `/ws/stream` | status、按role的devices、时间戳 |
| WSL后端 | WS `/ws/teleop` | `{"direction":"forward"}`等，返回config / ack / error |
| WSL后端 | WS `/ws/gazebo_frame` | 仿真摄像头代理；上游camera bridge默认8011 |
| WSL后端 | GET `/api/logs` | 后端记录及WSL launcher日志尾部 |

API名称中的system并不意味着它与Windows的start-system是一套作用范围。仿真摄像头不可用与EEG控制不可用也不是同一个故障。

### 3.11 错误处理与可观测性

| 位置 | 可观察证据 | 不应误解为 |
|---|---|---|
| System Control状态及View Log | 服务管理结果、设备探针、Windows日志 | 当前EEG算法 / 电机全链路通过 |
| Headband的VS Code终端 | SDK、桥创建 / 重建、样本停滞 | 必然存在 `bridge_headband.log` 文件 |
| `bridge_hybrid.log` | 托管Hybrid进程的输出 | 所有Headband或ROS节点日志 |
| WSL `/tmp/launcher_backend.log`、`launcher_frontend.log` | launcher启动网页服务时的重定向输出 | ROS节点所有stdout已包含其中 |
| ROS节点日志 | 校准样本、CALIB写回、眨眼 / 断流、启动异常 | 仅凭CALIB标志清除就认为阈值成功保存 |
| `/api/health` | subscriber_ready、subscriber_error、消息计数 | ready=true必然表示成功；初始化失败也会结束等待并设置ready |
| `/api/status` | ROS / 串行设备 / 后端运行标记 | eeg_stream_alive是独立原始EEG活性证明；当前实现与后端running标记关联 |

后端启动ROS子进程时stdout / stderr导向DEVNULL，因此View Log不包含全部节点输出；日志定位与保存方法见[开发手册](GUIDE_DEVELOPPEUR_cn.md#64-日志位置与故障记录)。Preparing、颜色、服务Running和数据时间序列各反映不同层的状态，不能互相替代。

### 3.12 网络、命令与数据边界

总控服务默认绑定127.0.0.1:8020，并检查POST来源。后端默认127.0.0.1:8010；Vite监听0.0.0.0:5173，通过代理访问API / WebSocket。launcher按当前WSL IP尝试刷新Windows前端端口转发。

当前仓库launcher配置把 `WEB_GUI_FRONTEND_ORIGIN` 设置为 `*`，默认控制token为空，真实命令默认开启。不能因此认为局域网访问只有观看权限。Origin检查不是用户认证，token也不等于完整权限体系。

`/api/config/control_token`允许后端看到的loopback客户端读取token，前端会自动获取。Vite代理连接本身来自loopback，所以不能仅凭该检查宣称LAN访问前端的客户端无法获得token；实际代理 / 网络路径必须核验。不可信网络不能仅通过设置token就认定部署安全。

前端按钮禁用不是安全权限检查。`/api/config`等接口也没有统一的用户授权模型；当前遥控发布路径不通过 `WEB_GUI_ALLOW_REAL_COMMANDS` 的ROS launch门禁，因此不能将mock门禁说成全API总安全开关。

数据类型与保存边界：

- 源码与依赖声明：Git仓库；`src/ros-aseba`、`src/ros-thymio`为第三方代码，许可证和来源需保留。
- 实际机器配置与校准：Windows本地config、WSL配置，修改后需备份，不以出厂参数代替。
- 日志：Windows日志、VS Code终端、WSL临时日志；留存周期并未由系统统一管理。
- 研究分析数据：历史 `experiment_data/` 已从当前工作区移除，整个目录已加入 `.gitignore`，已有Git历史未清除；仍保留的数据收集功能及用途见[产品边界](#17-产品边界)。
- 原始EEG：当前未实现原始EEG保存，分析CSV中的处理后指标与控制信息不能代替原始信号记录。

敏感数据范围、去标识化和访问权限由负责人确认。密码、token和完整授权凭据不放入公开文档或Git；配置、日志和数据的备份恢复方法见[开发手册](GUIDE_DEVELOPPEUR_cn.md#9-备份与恢复)。

## 4. 验收与验证状态

### 4.1 验证口径

以下为2026-10-09的验证记录，运行环境为macOS、Python 3.14，不代表目标Windows + WSL2环境的复现。测试执行方法与依赖见[开发手册测试入口](GUIDE_DEVELOPPEUR_cn.md#71-现有测试入口)。

| 测试文件（仓库相对路径） | 记录结果 |
|---|---|
| `thymio_control/test/` 下的 `test_watchdog.py`、`test_cmd_vel_fuser.py`、`test_calibration.py`、`test_blink_metric.py`、`test_pre_filter.py`，以及 `thymio_control/lsl_test/test_dummy_dual_streams.py` | 合计38 passed |
| `thymio_control/test/test_verify_blink_clamp.py` | 2 skipped：依赖的历史 `experiment_data/archive/` 已移除 |

通过的测试不需要真实ROS / EEG / Thymio，也未验证Windows SDK。合成流相关2项只验证生成信号及指标行为，没有运行真实LSL网络传输或Gazebo端到端流程。跳过的回放测试是验证缺口，不能算通过；该记录不包含完整后端测试、前端构建或目标电脑真机验收。

| 验证层 | 能证明什么 | 当前状态 |
|---|---|---|
| 代码与配置核对 | 逻辑、路径、参数、接口存在及其边界 | 已核对本文主要实现依据 |
| 纯逻辑 / 数值 / 文件测试 | 看门狗判断、融合、校准判断 / 写回、检测器、预滤波及合成信号规则 | 上述测试已通过，不证明SDK、无线连接或完整ROS链路 |
| 历史数据回放测试 | 在既有采集数据上验证眨眼参考下限的影响 | 数据已移除，测试跳过，不算验证通过 |
| ROS / 后端集成 | 启动、消息路由、配置回读、WebSocket与清理 | 有测试 / 实现基础，目标环境待执行 |
| 仿真 | 非硬件端到端控制路径 | 尚无完整验证记录，不作为真机替代 |
| Windows真机 | SDK、蓝牙、USB、WSL网络和电机 | 用户提供过使用信息，尚无完整验收记录 |
| 可用性 / 可维护性验证 | 用户独立操作、开发人员独立部署 / 修改 | 尚无对应验证记录 |

### 4.2 目标电脑验收场景

每项记录“未执行 / 通过 / 失败”，不能仅保留勾选框；条件不满足时说明缺什么。

| 场景 | 关联需求 | 必须观察 |
|---|---|---|
| 正常起停总控 | RF-01、RF-14 | 两类Start区别、服务状态、退出及残留进程 |
| Headband连接 / 手动停止 | RF-02、RF-14 | 正确venv、数据活性、Ctrl+C停止、再连不重复旧脚本 |
| Hybrid连接 / 断开 | RF-03 | SDK可导入、LSL有样本、托管进程正确结束 |
| Dongle共享 / attach | RF-04 | 指定USB口、1-1、Shared / Attached、WSL设备和机器人响应 |
| 单EEG两种角色 | RF-05、RF-06 | 选正确品牌；分别验证前进与原地转向，不同时混入遥控 |
| 双EEG角色交换 | RF-05、RF-09、RF-12 | 换品牌 / 角色仍正确分路；图表 / 命令无交叉覆盖 |
| 逐路校准与不足样本 | RF-07、RF-08、RF-15 | 采集、成功 / 中止提示、各自文件、policy原位更新及下一次Start读取；眨眼旧参考的更新边界另行核对 |
| 校准结束与手动调整 | RF-07、RF-15、RN-01 | 单路可能继续运行、双路自动Stop请求的实际时序；停止后逐路调整Min / Max，重读、刷新和下一次Start读取一致 |
| 眨眼切换 | RF-10 | 主动切换、自然眨眼误触、冷却期间无旧转向保持 |
| 断流与恢复 | RF-11、RN-01 | 单 / 双路零命令、实际停车、颜色与数据变化、恢复是否自动续动 |
| Keyboard机器人检查 | RF-13、RN-01 | 按下 / 松开方向按钮、stop、切换输出正确 |
| 遥控异常停止 | RN-01、RN-07 | 关闭页面、WebSocket / 网络断开、后端异常时真实驱动是否停住；不得预设通过 |
| 网页故障与日志 | RF-16 | 前 / 后端分别失败的反馈、Restart Web、需要的诊断信息可保存 |
| 更新、备份、恢复 | RN-05、RN-08 | 同步不改本地config；新代码生效边界；恢复后能重复运行 |
| 非技术用户演练 | RN-03 | 只靠用户两份手册完成一次使用及一种常见问题恢复 |
| 开发维护验证 | RN-04、RN-05 | 阅读技术 / 开发手册后定位问题、小修改、运行相应验证 |

### 4.3 需求到代码与测试的追踪

| 需求组 | 实现依据 | 验证入口 |
|---|---|---|
| RF-01～04、RF-14、RF-16 | windows_launcher的config、server、state、commands、lsl_probe | windows_launcher/tests；目标Windows验收 |
| RF-05、RF-08、RF-15 | models、config_store、App、ROS launch | 后端models / config_store测试；双路真机 |
| RF-06、RF-10 | policies、enrich、blink_metric、EEG节点 | test_policy、test_blink_metric、test_eeg_control_node；真实EEG验证 |
| RF-07 | calibration、EEG节点、前端useCalibration | [test_calibration.py](../thymio_control/test/test_calibration.py)；网页 / 节点校准完整流程 |
| RF-09、RF-11、RN-01 | fuser、watchdog、launch | [test_cmd_vel_fuser.py](../thymio_control/test/test_cmd_vel_fuser.py)、[test_watchdog.py](../thymio_control/test/test_watchdog.py)；停车及故障恢复实测 |
| 信号处理与开发合成流 | RawLslAdapter、StreamingPreFilter、dummy_dual_streams | [预滤波测试](../thymio_control/test/test_pre_filter.py)、[合成信号测试](../thymio_control/lsl_test/test_dummy_dual_streams.py)；LSL传输 / ROS / 仿真另行集成验证 |
| RF-12、RF-13 | signal_subscriber、main、App | 后端subscriber测试、launcher的UI相关测试；网页和机器人验证 |
| RN-05、RN-07、RN-08 | 依赖声明、Vite代理、后端授权、同步与实际部署 | 目标环境重建、网络权限与恢复演练 |

表中已执行测试及结果以[第4.1节](#41-验证口径)的记录为准，其他文件仅列作后续验证入口。实际命令、默认测试范围与依赖见[开发手册测试入口](GUIDE_DEVELOPPEUR_cn.md#71-现有测试入口)。

## 5. 当前限制与待确认信息

### 5.1 当前限制及优先验证事项

| 项目 | 影响 | 应对与验证要求 |
|---|---|---|
| Headband手动脚本生命周期 | 总控停止不等于脚本停止 | 保留用户手册的Ctrl+C步骤；验证无重复桥 |
| 同型号source_id固定、空source_id或多个匹配结果选第一流 | 不具备同型号双设备可靠身份管理 | 当前沿用标准组合；下一阶段按[RF-NEXT需求](#25-下一阶段主要需求同型号双-gtec)开发并验收，不承诺现状直接可用 |
| 新校准不刷新旧检测器参考 | Steering的Alpha / TBR上冲参考可能仍旧，policy的新校准值则已原位生效 | 需要刷新检测参考时Stop / Start；详见[校准状态](#校准结束后的控制状态) |
| 两级watchdog、数据恢复自动续动 | 0.5s不能作整机保证；恢复可能重新动作 | 重点验收停车、恢复，使用者主动Stop暂停 |
| 手动WS断开未显式发零 | 浏览器 / 网络故障的停止行为无已验证保证 | 必须测真实驱动，不把前端200ms补发当网络急停 |
| 网页服务健康不等于ROS / EEG有效 | 某些状态可能误导定位 | 对照数据、ROS错误和实际运动，不只看颜色 |
| 真实命令默认开、网络访问缺完整权限体系 | 非可信客户端可能控制或修改配置 | 核对监听 / 代理路径和访问范围，未审查前不对互联网开放 |
| 保存的配置可能是某次运行残留 | 当前角色、指标和速度不一定适合下一次使用 | 确认正式运行配置，备份实际参数 |
| SDK与环境不在pip声明中完整覆盖 | clone仓库或导入WSL不能直接恢复Windows设备桥 | 优先评估[WSL整体迁移](GUIDE_DEVELOPPEUR_cn.md#93-推荐迁移方式导出与导入整套-wsl)，Windows SDK、授权、解释器、蓝牙及USB仍单独配置 |
| 完整仿真尚无验证记录 | 有合成流和Gazebo代码，不等于完整流程已通过验证 | 按[开发仿真路径](GUIDE_DEVELOPPEUR_cn.md#43-无设备离线验证)单独验证，不代替真机验收 |
| 数据及日志缺统一生命周期管理 | 信息泄露、误删或恢复缺资料 | 确定权限、保存范围和备份方案 |

量化指标的未知项见[第2.4节](#24-尚未确定的量化指标)，目标环境验收场景见[第4.2节](#42-目标电脑验收场景)；部署、授权与迁移的具体步骤由[开发手册](GUIDE_DEVELOPPEUR_cn.md)维护。
