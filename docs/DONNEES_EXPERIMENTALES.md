# DONNEES_EXPERIMENTALES

> 实验数据 — 中文源文(将翻译为法语)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。
> 列名一律以 `web_gui/backend/app/experiment.py`(E1)与 `experiment_export.py`(E5)的列常量为准。

## 1. 目录约定

- 根目录 `experiment_data/`(默认;`EXPERIMENT_DATA_DIR` 可覆盖)。
- 每个 session 一个目录 `experiment_data/<session_id>/`。
- **session_id 编码**:`{subject}[_{subject_b}]_s{session_no}_{metric}_{device_mode}_[{electrode}_]{date}_{epoch}`——双人模式含两人(`subject_subject_b`);电极段仅含 Hybrid Black 时出现(`dry` / `wet`),纯头戴单设备不出现。
- **每次 Start = 新 run**(P44 运行隔离):试次文件带 `run_<R>` 前缀,同 session 多次 Start 不混数据;旧数据无 run 前缀时回退 `trial_<NNN>.csv`。
- `experiment_data/` 下非 session 目录:`archive/`(归档)与 `analysis/`(E5 导出输出,gitignored)。

## 2. session.json

- `meta`(手填):subject / subject_b / session_no / electrode / date 等。
- `system`(实际配置,P20 后端从 AppConfig 推导,不手填):metric / device_mode / roles / devices。
- 打乱协议:`trials` 列表 + shuffle 模式 + 随机种子——记录完整,可复现。

## 3. labels.csv · trials.csv

**labels.csv(E4 真值流)**——每试次在 prompt 入口写一行,`wall_ts` 与样本的 `row_ts` 同一墙上时钟(EEG 对齐):

| 列 | 含义 |
|---|---|
| run, trial_idx | 运行号 / 试次号 |
| phase | 写入时相位(prompt) |
| wall_ts | 墙钟时间戳 |
| a_state, b_state, b_direction | 目标三路真值(attention/rest、left/right) |

**trials.csv(每试次汇总)**——列:`run, trial_idx, a_state, b_state, b_direction, prompt_ts, start_ts, end_ts, duration_sec, n_samples, mean_alpha, mean_tbr, mean_ei, blink_count`。

## 4. run_<R>trial<NNN>.csv(每试次样本帧)

列与 `experiment.py` 的 `TRIAL_CSV_COLUMNS` 一致:

| 分组 | 列 |
|---|---|
| 目标与起止 | `trial_idx, a_state, b_state, b_direction, trial_start_ts, trial_end_ts` |
| 时序与来源 | `row_ts, frame_ts, cmd_vel_ts, source, role` |
| 指标 | `alpha, theta, beta, tbr, ei` |
| 意图与输出 | `speed_intent, steer_intent, steer_direction, cmd_lin, cmd_ang, is_blink, latency_ms` |

`is_blink` 记录转向翻转事件;`latency_ms` = 管线延迟(时间戳相减)。

## 5. master_trials.csv · condition_summary.csv

**master_trials.csv(主试次长表,每 trial 一行)**——`MASTER_COLUMNS`:

| 分组 | 列 |
|---|---|
| session 字段 | `session_id, date, subject, subject_b, device_mode, metric, electrode, roles` |
| 目标三路 | `run, trial_idx, a_state, b_state, b_direction` |
| 输出 | `speed_intent, steer_intent, steer_direction, clean_switch, is_blink, latency_ms` |
| 速度(P48) | `mean_cmd_lin, moving_time_ratio, speed_active` |
| 指标均值 | `mean_alpha, mean_tbr, mean_ei, blink_count` |

**condition_summary.csv(每 session×run×channel 一行)**——`SUMMARY_COLUMNS`:

`session_id, run, channel, n_attention, n_rest, hit_rate, fa_rate, d_prime, auc, mean_score_attention, mean_score_rest, mean_latency_attention, mean_latency_rest, dir_hit_rate, dir_fa_rate, clean_switch_rate, avg_toggles_per_switch`

**指标算法(与 `experiment_export.py` 一致):**
- **speed 通道**:hit / FA 用 `speed_active`(`moving_time_ratio >= 0.10` 且 speed-role 帧 `cmd_lin > 0.02`),不来自 `speed_intent` 分类;AUC 与均值基于连续 `mean_cmd_lin`;无 speed-role 帧的试次不判(数据缺口,非失败)。
- **steering 通道**:hit / FA 用每 trial 均值 `steer_intent > 0.5`;AUC 基于连续 `steer_intent`;`dir_hit_rate` / `dir_fa_rate`(目标方向改变 / 稳定时输出是否匹配/改变);`clean_switch_rate` / `avg_toggles_per_switch`(P46 方向控制质量)。

## 6. 分析与可复现

- **E5 确定性**:纯 stdlib、同输入同输出,`python -m app.experiment_export --out <dir>` 或面板 **Export analysis** 均可重跑。
- **可重跑脚本**:`thymio_control/scripts/verify_blink_clamp.py`(回放 P47 上冲基线钳制验证)等,配合 `experiment_data/archive/` 使用。
- **latency**:每帧 `latency_ms` 已记;汇总取各状态均值(`mean_latency_attention` / `mean_latency_rest`)。
- **分析注意**:按 `run` 隔离,不跨 run 混算;无输出帧的试次跳过而非判失败;rest 自然眨眼不当作误触发。
