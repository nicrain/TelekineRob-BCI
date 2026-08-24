# GLOSSAIRE — 术语表

> 全套正式文档(MANUEL_OPERATEUR / GUIDE_INSTALLATION / PROTOCOLE_EXPERIMENTAL / ARCHITECTURE_TECHNIQUE / GUIDE_DEVELOPPEUR / DONNEES_EXPERIMENTALES)的统一「中文术语 ↔ 技术标识符」映射。正文出现任何术语必须与下表一致;技术标识符一律原样保留(大小写、下划线、路径后缀)。

| 中文术语 | 技术标识符 | 一句话说明 |
|---|---|---|
| 操作者 | operator | 驾驶/被测试的人;双人协同时分 A(前进/停)与 B(转向+方向)两角色 |
| O2 总控台 | windows_launcher | 操作者主控台:启动/停止系统、连接设备、编排 web GUI |
| 会话 | session | 一次实验运行(校准 + 若干试次),落一个 session 目录 |
| 试次 | trial | 单次「提示目标 → 执行」最小单元,记真值标签 |
| 校准 | Calibrate | 30s 自动采集基线,计算 p5/p50 写回参数文件 |
| 校准参考 | p5 / p50 | 指标 min-max 与阈值参考;p50 兼作眨眼基线钳制 ref(P47) |
| 导出 | E5 / E6 | 一键导出脚本:session 数据 → 分析表(面板 Export analysis 按钮) |
| 主试次表 | master_trials.csv | E5 长表,每 trial 一行(目标三路 + 输出 + 指标) |
| 条件汇总表 | condition_summary.csv | E5 汇总,每 (session × run × channel) 一行(hit/FA/d′/AUC) |
| 速度命令 | cmd_lin | 线速度指令(m/s),speed 通道实际输出(P48 判定依据) |
| speed 主题 | /eeg_cmd_vel/speed | speed 设备发布的指令主题(role 字面量后缀) |
| 转向命令 | steer_intent | 转向意图(0–1),steering 通道输出 |
| steering 主题 | /eeg_cmd_vel/steering | steering 设备发布的指令主题(role 字面量后缀) |
| 眨眼检测 | MetricBlinkDetector | 瞬态指标眨眼检测:滚动中位基线 + 确认/保持帧 |
| 融合器 | cmd_vel_fuser | 融合 speed + steering 指令发布最终 /cmd_vel;断流 0.5s 整车零速 |
| 脑机接口 | BCI | 脑控技术总称(Brain-Computer Interface) |
| 头戴 | headband | g.tec BCI Core-4 Headband(4 通道,经 gpype) |
| Hybrid Black | Hybrid Black | g.tec Unicorn Hybrid Black(8 通道,经 gpype / UnicornPy) |
| 干·湿电极 | dry / wet | Hybrid Black 电极两种配置(实验对比因素) |
| 状态 | attention / rest | 试次目标状态:集中(前进/转)vs 放松(停/不转) |
| 数据管线 | RawLslAdapter → PSD → enrich_features → Policy | EEG 样本 → 频带特征 → 特征富化 → 控制意图 的链路 |
| 主题 | topic | ROS2 消息通道命名(/eeg_analysis/*、/eeg_cmd_vel/*、/cmd_vel) |
| 参数文件 | eeg_control_node.params.yaml | 每设备独立参数(阈值、校准回写、blink 参考) |
