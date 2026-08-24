# PROTOCOLE_EXPERIMENTAL

> 实验协议 — 中文源文(将翻译为法语)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。

## 1. 目标与假设

**范围。** 本协议覆盖 **M2 技术验证**:证明系统能控、各通道/指标/模式性能可量化。**明确不含 ADHD 临床设计**——招募、伦理、前后测、纵向设计、参与度/坚持率由合作博士的课题负责;本协议只在 E1 记录字段上与他对齐。

**双人协同控制模型。**

| 操作者 | 注意力 → | 眨眼 → |
|---|---|---|
| A | 前进 / 停止 | — |
| B | 转向(转 / 不转) | **切换方向(左转 ↔ 右转)** |

- 注意力是主控制模态(指标 alpha / tbr,各自设备独立校准);**眨眼切向是 B 独有**。
- 眨眼检测为瞬态判据(MetricBlinkDetector):相对近期基线判尖峰,持续 rest 漂移不触发。

**假设。**
- 各通道 / 指标 / 模式的命中与误报可量化,且显著高于随机水平(chance)。
- 指标对比给出哪个指标控制质量更好(alpha vs tbr)。

## 2. 被试与设备

**两层被试。**
- **预实验 Pilot**:开发者本人——系统全链路可用 + 记录闭环成立(两个通道校准合理、眨眼能稳定切换方向、机器人有响应、数据能落盘)。
- **正式实验**:5–10 对/名被试(两人一组协同);每对被试 1–3 次 session(建议 ≥2,可报跨 session 稳定性,防"单次运气"质疑)。

**记录元数据。** 年龄、性别、利手、BCI 经验、疲劳/状态自评;双人组记录配对与各自角色。

**设备。**
| 设备 | 通道 | 备注 |
|---|---|---|
| Headband(g.tec BCI Core-4) | 4 通道:F8, Fp2, Fp1, F7 | 经 gpype |
| Hybrid Black(g.tec Unicorn) | 8 通道:Fz, C3, Cz, C4, Pz, PO7, Oz, PO8 | 经 gpype / UnicornPy;电极 dry / wet |

**角色固定(真机结论)。** **Headband = 转向(B,含眨眼切向)**;**Hybrid Black = 速度(A)**——Hybrid Black 对眨眼不敏感,配速度角色不受眨眼干扰。

## 3. 实验设计

**因素。**
- 指标:**alpha / tbr**(ei 已弃;对比仅 alpha vs tbr)× 模式:**单设备 / 双设备**。
- 电极(仅 Hybrid Black):干 / 湿作为对照条件,顺序随机平衡。

**范式(四种)。**
- **① 注意力通道验证(A:前进/停止)**:注意(心算等集中)vs 休息(放松)→ 期望前进 / 停住。
- **② 注意力通道验证(B:转向)**:同样注意 vs 休息 → 期望开始转 / 不转(独立验证 B 的注意力通道)。
- **③ 眨眼方向开关验证(B:左/右)**:提示"切换到 左转/右转"→ 期望一次(或几次)眨眼完成切换;记方向切换正确性(dir_hit / dir_fa)与方向控制质量(clean_switch_rate);**rest 自然眨眼 ≠ 误触发**。
- **④ 联合任务(旗舰,双人协同)**:A 控前进/停、B 控转向 + 方向,一起把 Thymio 开到目标点;记完成率、完成时间、路径效率、失误归属。

**试次数。** 每状态约 **10 次**(疲劳限制);trial 时长默认 20 秒,试次之间 "Get ready" 提示倒计时(可配置)。

**随机化。** 目标顺序随机/平衡(防顺序效应);随机种子记录,可复现。

## 4. 单设备与双设备模式

**单设备。** 同一操作者/设备,前进与转向**分块各测**,证明单设备两种控制都可用。

**双设备。** 只测 **alpha-dual + tbr-dual**——同一指标、两台设备各承担一个角色;不混指标、不角色互换、不干湿交叉。**融合与指标无关**(fuser 只按 role 合并指令)。

**角色分工。** Headband = steering(B,含眨眼切向);Hybrid Black = speed(A)。

**融合与 fail-safe。** `cmd_vel_fuser` 融合 `/eeg_cmd_vel/speed` + `/eeg_cmd_vel/steering` 发布最终 `/cmd_vel`;**任一流断流 → 0.5s 内整车零速**(fail-safe)。

**眨眼转向检测。** 瞬态判据(滚动中位基线 + 确认/保持帧;眨眼确认/保持期间转向钳中性 0.5);**P47 上冲基线钳制**——alpha/tbr 专注时滚动基线塌到专注水平,钳制 `baseline = max(滚动中位数, 校准 p50)`,降低小被动眨眼的误触发。

## 5. 数据管道与文件

**E1 落盘**(每 session 目录,见 DONNEES_EXPERIMENTALES):
- `session.json`(元数据 + 实际配置 + 打乱协议)
- `labels.csv`(E4 真值流)
- `trials.csv`(每试次汇总)
- `run_<R>_trial_<NNN>.csv`(每试次样本帧)

**E5 导出**:`master_trials.csv`(主试次长表)+ `condition_summary.csv`(每 session×run×channel 汇总)。

**E6 面板一键导出**:web GUI 实验面板 **Export analysis** 按钮,直接调 E5。

## 6. 统计分析

**速度通道(A,命中/虚警按实际命令 P48)。** 有效前进帧 = `cmd_lin > 0.02 m/s`;trial 成功(`speed_active`)= 该 trial 内 speed-role 帧有效前进占比 ≥ **0.10**(20s trial ≈ 至少 2s);`attention` 且成功 → **hit**、`rest` 且成功 → **false alarm**;**AUC 基于连续 `mean_cmd_lin`**。

**转向通道(B)。** 命中/虚警 = 每 trial 均值 `steer_intent > 0.5`;AUC 基于连续 `steer_intent`;`dir_hit_rate`(目标方向改变时输出匹配新目标的比例)/ `dir_fa_rate`(目标稳定时输出仍改变的比例)。

**方向控制质量(P46)。** `clean_switch_rate`(需换向试次中输出恰好翻转必要次数 toggles == needed 的比例 ≈ 1 − 换向时误触发率)/ `avg_toggles_per_switch`(需换向试次平均翻转次数,理想 1.0)。

**分离度。** `d′ = z(hit) − z(fa)`(反正态近似);AUC 为 rank-based(Mann-Whitney U 统计量)。

**系统延迟。** 管线延迟 `latency_ms`(各环节时间戳相减),按状态取均值;电机响应可选。

**统计。** 被试内配对 t / 被试间均值·SD·CI·ANOVA(条件 × 通道)。
