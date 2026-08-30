# GUIDE_DEVELOPPEUR

> 开发者指南 — 中文源文(将翻译为法语)。规矩:中文叙述只翻技术标识符之外的部分;内部三方注解(CTO/programmer/reviewer)禁止入正文。术语与 docs/GLOSSAIRE.md 保持一致。改编自 `thymio_control/docs/THYMIO_CONTROL_CODE_GUIDE_ZH.md`(底稿不动,等收尾单归档)。

## 1. 包结构

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
| `processors/blink_metric.py` | `MetricBlinkDetector` 瞬态眨眼(见 ARCHITECTURE_TECHNIQUE §5) |
| `policies/*` | `EiPolicy`(β/(α+θ))、`TbrPolicy`(θ/β)、`AlphaPolicy`(α 功率);支持 offset/scale 校准参数与 EMA 平滑 |

**输入模式。** eeg 节点仅支持 `lsl`;Web GUI `keyboard` 模式为独立 teleop 路径(经 `/ws/teleop` → RosBridge → `/cmd_vel`)。

## 3. 运行测试

- **全量**:`pytest`——`pytest.ini` `testpaths = thymio_control/test thymio_control/lsl_test windows_launcher/tests`。
- **thymio_control 单测**:`pytest thymio_control/test/test_*.py -v`。
- **lsl_test 离线验证**:`thymio_control/lsl_test/`(dummy 双流、EDF 回放、流式提取)。依赖 `pylsl` / `pyedflib` 未安装时相关测试自动 skip。
- 控制服务逻辑不依赖 Windows:`pytest windows_launcher/tests`(wsl/usbipd 走 fake executor)。

## 4. 扩展(新增 metric/策略、新增设备)

**新增 metric / 策略。**
1. 在 `thymio_control/policies/` 新增策略类(参照 `TbrPolicy` 模式:实现 `compute_intents`、支持 `offset`/`scale` 校准参数与 EMA 平滑)。
2. 在 `thymio_control/pipeline.py` 的 `POLICIES` 注册:`{..., "新名": NewPolicy}`。
3. 参数文件 `eeg_control_node.params.yaml` 设 `policy: <新名>`。
4. 校准:30s 采集 → p5/p50 → 写回 `calib_offset`/`calib_scale` → 重建 policy。

**EMA 平滑参数(`ema_alpha`)。**
- 三个策略 `policies/tbr.py`、`policies/ei.py`、`policies/alpha.py` 都有类属性 `ema_alpha: float = 0.35`。
- 作用:对原始指标(α 功率 / θ/β 比值)先做指数移动平均,再归一化——`smoothed = ema_alpha × 新值 + (1 − ema_alpha) × 上次平滑值`;0.35 = 新数据信 35%、历史信 65%。
- 效果:单帧波动不突跳,控制更稳;代价是反应略慢。第一帧无历史,直接取原始值(`_primed` 标志)。
- 调参:调大 → 更跟手、更抖;调小 → 更平滑、更钝;0.35 为当前中间偏稳取值。
- 注明:`ei` 已不用于实验,`alpha` / `tbr` 在用。

**新增设备。**
- 在 `thymio_control/device_profiles.py` 注册表登记设备(如 `hybrid-black` 8 通道、`bci-core-4` 4 通道);`RawLslAdapter` 从 LSL StreamInfo 自动读取通道数与采样率。

## 5. 编码规范

- **代码文件零字面中文**(`.md` 除外),含测试断言——必须出现中文时用 unicode 转义(`\uXXXX`,正则 pattern 里同样生效)。
- 命名与注释沿既有风格:纯函数可测、阈值集中为命名常量、注释写明"分析假设"。

**易踩坑(照搬改编自底稿 §7)。**
1. **LSL 连接挂起(无波形/校准卡 preparing)**:WSL2 未禁用 eth0 的 IPv6 → liblsl 选中不可达的 IPv6 link-local 地址。需执行 `sysctl net.ipv6.conf.eth0.disable_ipv6=1`(持久化见根 README「WSL2 网络配置」)。
2. `use_teleop=true` 时 EEG 节点不启动 → 设 `use_teleop:=false`。
3. 校准后值没更新 → 需 clean rebuild(`rm -rf install/build thymio_control`)。
4. 前端 YAML 读不到最新值 → 确保 `npm run dev` 重建前端、backend 重启。
