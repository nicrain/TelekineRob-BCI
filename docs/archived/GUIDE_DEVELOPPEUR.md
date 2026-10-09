# GUIDE_DEVELOPPEUR

> 已归档：保留旧指南、设计或验证历史，不作为当前操作、开发或需求依据。现行说明见[中文 README](../../README_cn.md)、[技术档案](../DOSSIER_TECHNIQUE_cn.md)与[开发手册](../GUIDE_DEVELOPPEUR_cn.md)。

> 旧开发者指南（中文版，保留作参考）。完整安装、调试、修改与测试、更新和恢复说明已整合到[中文版开发手册](../GUIDE_DEVELOPPEUR_cn.md)，后续以该手册为准。本文件不代表已完成 Windows + WSL 真机验收。

相关文档：[安装部署](GUIDE_INSTALLATION.md) · [技术架构](ARCHITECTURE_TECHNIQUE.md) · [用户操作手册（中文）](../MANUEL_OPERATEUR_cn.md) · [用户排障手册（中文）](../GUIDE_DEBUG_cn.md)。

## 1. 包结构

以下目录相对于仓库内的 `thymio_control/` 包，不是整个仓库根目录。

```
launch/               experiment_core.launch.py(统一入口)
scripts/              eeg_control_node.py(EEG 主节点)、cmd_vel_fuser.py(双设备融合)
thymio_control/
  adapters/           数据输入:lsl_raw(RawLslAdapter)
  processors/         信号处理:band_power(Welch PSD)、enrich(特征)、blink_metric(眨眼)
  policies/           控制策略:Ei、Tbr、Alpha
  contracts.py        EegFrame
  calibration.py      校准阈值 + 写回
  device_profiles.py  设备注册表(hybrid-black、bci-core-4)
  pipeline.py         模块化入口(adapter + processor + policy)
  watchdog.py         断流看门狗
```

## 2. 核心类与数据流

```
LSL 流 (Windows bridge)
  → RawLslAdapter (pull_chunk → Welch PSD → band powers)
  → enrich_features (theta_beta 等)
  → Policy.compute_intents (speed_intent, steer_intent)
  → _intents_to_twist (按 role 映射) → Twist → /cmd_vel
  → 眨眼检测(metric-only)→ 切换转向方向
```

| 文件 | 职责 |
|---|---|
| `launch/experiment_core.launch.py` | 统一 launch 入口;`use_sim`(仿真/实机)、`run_eeg`(是否起 EEG 节点)、`use_teleop`(true 时 EEG 节点被条件抑制) |
| `scripts/eeg_control_node.py` | EEG 主节点:`_tick` = read_frame → enrich → 眨眼检测 → compute_intents → `_intents_to_twist` → `/cmd_vel`;发 `/eeg_analysis`;LED;看门狗;校准模式 |
| `scripts/cmd_vel_fuser.py` | 双设备融合:订阅 `/eeg_cmd_vel/speed` + `/eeg_cmd_vel/steering`,watchdog=0.5s 缺失/陈旧 → 整车零速,发 `/cmd_vel` |
| `thymio_control/pipeline.py` | `POLICIES` = {ei, tbr, alpha};`build_adapter`(仅 lsl);`build_pipeline` → (adapter, processor, policy) |
| `processors/band_power.py` | `StreamingBandPowerExtractor`,Welch PSD 五个频段 |
| `processors/blink_metric.py` | `MetricBlinkDetector` 瞬态眨眼，见[眨眼转向检测](ARCHITECTURE_TECHNIQUE.md#5-眨眼转向检测) |
| `policies/*` | `EiPolicy`(β/(α+θ))、`TbrPolicy`(θ/β)、`AlphaPolicy`(α 功率);支持 offset/scale 校准参数与 EMA 平滑 |

**输入模式。** eeg 节点仅支持 `lsl`;Web GUI `keyboard` 模式为独立 teleop 路径(经 `/ws/teleop` → RosBridge → `/cmd_vel`)。

## 3. 运行测试

在 WSL 的仓库根目录激活 `.venv`；依赖来自根目录 `requirements.txt`。以下是不同套件的入口，不是测试通过记录。

```bash
source .venv/bin/activate
python -m pytest thymio_control/test windows_launcher/tests -v
python -m pytest thymio_control/lsl_test -v
```

后端测试导入 `app.*`，从后端目录运行，继续使用同一个仓库根 venv：

```bash
cd web_gui/backend
../../.venv/bin/python -m pytest app -v
```

- 仓库根直接执行 `python -m pytest` 只发现 `pytest.ini` 中的三个目录：`thymio_control/test`、`thymio_control/lsl_test`、`windows_launcher/tests`，**不包含后端测试**。
- `lsl_test` 包含 dummy 双流、EDF 回放和流式提取验证；缺少可选依赖或样本文件时，部分测试会 skip。skip 不等于通过。
- launcher 逻辑测试用 fake executor 代替 `wsl` / `usbipd` 等命令；通过这些测试不证明 Windows USB、蓝牙或 WSL 网络可用。
- 前端构建另在 `web_gui/frontend` 执行 `npm ci`、`npm run build`；构建成功不代替真机界面和控制验收。

## 4. 扩展(新增 metric/策略、新增设备)

**新增 metric / 策略。**
1. 在 `thymio_control/policies/` 新增策略类(参照 `TbrPolicy` 模式:实现 `compute_intents`、支持 `offset`/`scale` 校准参数与 EMA 平滑)。
2. 在 `thymio_control/pipeline.py` 的 `POLICIES` 注册:`{..., "新名": NewPolicy}`。
3. 参数文件 `eeg_control_node.params.yaml` 设 `policy: <新名>`。
4. 校准：收到数据后采集 30s → p5/p50 → 写回 `calib_offset`/`calib_scale` → 调用 `policy.set_calibration()` 原位更新参数，保留 EMA 状态，不重建策略实例。

**EMA 平滑参数(`ema_alpha`)。**
- 三个策略 `policies/tbr.py`、`policies/ei.py`、`policies/alpha.py` 都有类属性 `ema_alpha: float = 0.35`。
- 作用:对原始指标(α 功率 / θ/β 比值)先做指数移动平均,再归一化——`smoothed = ema_alpha × 新值 + (1 − ema_alpha) × 上次平滑值`;0.35 = 新数据信 35%、历史信 65%。
- 效果:单帧波动不突跳,控制更稳;代价是反应略慢。第一帧无历史,直接取原始值(`_primed` 标志)。
- 调参:调大 → 更跟手、更抖;调小 → 更平滑、更钝;0.35 为当前中间偏稳取值。
- 代码仍注册 `ei`、`alpha`、`tbr` 三种策略。交付时采用哪些指标需要确认，不能从仓库保存的某次运行参数推断当前研究方案。

**新增设备。**
- 在 `thymio_control/device_profiles.py` 注册表登记设备(如 `hybrid-black` 8 通道、`bci-core-4` 4 通道);`RawLslAdapter` 从 LSL StreamInfo 自动读取通道数与采样率。

## 5. 编码规范

- **代码文件零字面中文**(`.md` 除外),含测试断言——必须出现中文时用 unicode 转义(`\uXXXX`,正则 pattern 里同样生效)。
- 命名与注释沿既有风格:纯函数可测、阈值集中为命名常量、注释写明"分析假设"。

**常见开发问题。**

1. **LSL 连接挂起（无波形 / 校准卡 Preparing）**：先确认 Windows 桥有数据、`lsl_source_id` 对应正确。当前部署曾遇到 WSL 的 IPv6 地址选择问题；按[网络配置](GUIDE_INSTALLATION.md#4-网络配置)检查，不把禁用 IPv6 当成所有连接故障的通用处理。
2. `use_teleop=true` 时 EEG 节点不启动 → 设 `use_teleop:=false`。
3. **校准后值未更新**：先停止控制，检查 ROS 日志中的 `CALIB:`、样本不足 / 写文件失败信息，以及对应设备参数文件的 `calib_offset`、`calib_scale` 和 `calibrate`。当前代码会原位更新策略，并尝试写回源码及安装目录，不需要为校准结果重新编译，更不能删除 `thymio_control/` 源码目录。
4. **网页配置与 YAML 不一致**：查看 `/api/config` 返回的 `source_files`，确认正在运行的后端来自预期仓库，并检查实际配置文件。不要把重新构建前端当成 YAML 更新方法。
5. **启动了错误版本**：Windows 的 launcher 和桥从 WSL 当前检出文件同步，流程不执行 Git fetch / pull。Windows 的本地 `config.json` 不参与覆盖；launcher 自身的已运行进程要在退出并重新打开后才加载同步后的代码。
