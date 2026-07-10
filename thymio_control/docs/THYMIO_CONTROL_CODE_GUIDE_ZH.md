# Thymio Control 代码导读

本文覆盖 `thymio_control/` 包的架构和数据流，帮助你理解系统如何运作。

---

## 1. 架构分层

```
Launcher:   launch/experiment_core.launch.py
Node:       scripts/eeg_control_node.py
Pipeline:   thymio_control/pipeline.py (adapter + processor + policy)
Modules:    adapters/        (数据输入：lsl_raw, mock, keyboard)
            processors/      (信号处理：Welch PSD, enrich)
            policies/        (控制策略：Ei, Tbr, Alpha)
Contracts:  contracts.py     (EegFrame)
Config:     device_profiles.py (设备注册表：hybrid-black, bci-core-4)
```

---

## 2. 数据流

```
LSL 流 (Windows bridge)
  → RawLslAdapter (pull_chunk → Welch PSD → band powers)
  → enrich_features (theta_beta, beta_alpha_theta, alpha_asym)
  → Policy.compute_intents (speed_intent, steer_intent)
  → _intents_to_twist → Twist → /cmd_vel
```

输入模式：`mock`（模拟数据）、`keyboard`（键盘）、`lsl`（实时 LSL raw EEG）。

---

## 3. 设备

| key | 设备 | 通道 |
|---|---|---|
| `hybrid-black` | Unicorn Hybrid Black | 8 (Fz, C3, Cz, C4, Pz, PO7, Oz, PO8) |
| `bci-core-4` | BCI Core-4 Headband | 4 (F8, Fp2, Fp1, F7) |

设备配置在 `device_profiles.py` 中管理，`RawLslAdapter` 从 LSL StreamInfo 自动读取通道数和采样率。

---

## 4. 核心文件

### 4.1 `launch/experiment_core.launch.py`

统一 launch 入口。关键参数：
- `use_sim` — 仿真/实机
- `run_eeg` — 是否启动 EEG 节点
- `use_teleop` — teleop 为 true 时 EEG 节点被条件抑制

仿真启动示例：
```bash
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true use_teleop:=false input:=mock
```

实机（g.tec）启动示例：
```bash
ros2 launch thymio_control experiment_core.launch.py use_sim:=false run_eeg:=true use_teleop:=false input:=lsl
```

### 4.2 `scripts/eeg_control_node.py`

EEG 主控制节点。`_tick` 流程：
1. `adapter.read_frame()` → `EegFrame`
2. 若含频段特征 → `enrich_features` → `policy.compute_intents`
3. `_intents_to_twist` → 发布 `/cmd_vel`
4. 发布分析 JSON 到 `/eeg_analysis`
5. 看门狗：超时发布零速 Twist

支持校准模式（`calibrate=true`）：30 秒收集指标 → 计算 p5/p95 → 写入 YAML → 重建 policy。

### 4.3 `thymio_control/pipeline.py`

模块化入口。核心 exports：
- `POLICIES` — `{“ei”: EiPolicy, “tbr”: TbrPolicy, “alpha”: AlphaPolicy}`
- `build_adapter(args)` — 支持 `mock`、`keyboard`、`lsl`
- `build_pipeline(args)` → `(adapter, processor, policy)`

### 4.4 子包

**adapters/**：`RawLslAdapter`（LSL raw EEG + Welch PSD）、`MockAdapter`、`KeyboardAdapter`

**processors/**：`band_power.py`（`StreamingBandPowerExtractor`，Welch PSD 五个频段）、`enrich.py`（特征工程）

**policies/**：`EiPolicy`（β/(α+θ)）、`TbrPolicy`（θ/β）、`AlphaPolicy`（α 功率）。支持 `offset/scale` 校准参数和 EMA 平滑。

---

## 5. 配置文件

### `eeg_control_node.params.yaml`
```yaml
input: mock
policy: tbr
calibrate: false
calib_offset: 0.0
calib_scale: 1.0
lsl_stream_type: EEG
lsl_timeout: 8.0
lsl_source_id: “”
```

### `launch_args.yaml`
```yaml
use_sim: true
run_eeg: false
use_teleop: true
```

调试时先设置 `input: mock`，Web GUI 通过 `/api/config` 管理配置。

---

## 6. 测试

```bash
pytest thymio_control/test/test_*.py -v
```

---

## 7. 易踩坑

1. `use_teleop=true` 时 EEG 节点不启动 → 设 `use_teleop:=false`
2. 校准后值没更新 → 需 clean rebuild（`rm -rf install/build thymio_control`）
3. 前端 YAML 读不到最新值 → 确保 `npm run dev` 重建前端，backend 重启
