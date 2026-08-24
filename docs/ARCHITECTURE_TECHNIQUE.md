# ARCHITECTURE_TECHNIQUE

> 技术架构 — 骨架(待后续单填充正文)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。

## 1. 全栈数据流

> 写什么:g.tec bridge → LSL → WSL2 处理 → /cmd_vel → Thymio 的端到端链路。

## 2. EEG 处理管线

> 写什么:RawLslAdapter → Welch PSD → enrich_features → Policy 各环节。

## 3. 双设备融合(fuser、role 主题、fail-safe)

> 写什么:/eeg_cmd_vel/speed + /eeg_cmd_vel/steering 融合、断流 0.5s 整车零速。

## 4. 参数文件与校准回写

> 写什么:eeg_control_node.params.yaml 结构、p5/p50 回写、blink 基线钳制 ref。

## 5. 眨眼转向检测

> 写什么:MetricBlinkDetector 瞬态判据(滚动基线/确认/保持/钳制)。

## 6. 主题与命名约定

> 写什么:role 字面量后缀(/eeg_analysis/steering、/eeg_cmd_vel/steering 等)全表。
