# DONNEES_EXPERIMENTALES

> 实验数据 — 骨架(待后续单填充正文)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。

## 1. 目录约定

> 写什么:experiment_data/ 下 session 目录命名(subject_…_mode_electrode)与 run 分组。

## 2. session.json

> 写什么:meta(手填)+ system(实际配置)+ 打乱协议 + trials 列表。

## 3. labels.csv · trials.csv

> 写什么:真值流(E4 标签,wall_ts 与样本同钟)与每 trial 汇总行。

## 4. run_<R>trial<NNN>.csv

> 写什么:每 trial 样本级帧(真值三路 + 指标 + 意图 + 眨眼事件 + latency);完整名 run_<R>_trial_<NNN>.csv。

## 5. master_trials.csv · condition_summary.csv

> 写什么:E5 导出长表与汇总表各列含义。

## 6. 分析与可复现

> 写什么:纯 stdlib 确定性导出、归档分析输出(gitignored)、随机种子。
