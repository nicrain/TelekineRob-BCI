# Thymio Control 代码导读

本文覆盖 `thymio_control/` 包的架构和数据流，帮助你理解系统如何运作。

---

## 1. 架构分层

```
Launcher:   launch/experiment_core.launch.py
Node:       scripts/eeg_control_node.py
Pipeline:   thymio_control/pipeline.py (adapter + processor + policy)
Modules:    adapters/        (数据输入：lsl_raw)
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
  → enrich_features (theta_beta, beta_alpha_theta)
  → Policy.compute_intents (speed_intent, steer_intent)
  → _intents_to_twist (按 role 映射) → Twist → /cmd_vel
  → blink 检测（metric-only）→ 切换转向方向
```

输入模式：`eeg` 节点仅支持 `lsl`（实时 LSL raw EEG）。Web GUI 的 `keyboard` 模式为独立 teleop 路径（经 `/ws/teleop` → RosBridge → `/cmd_vel`），与 EEG 节点无关。

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
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true use_teleop:=false input:=lsl
```

实机（g.tec）启动示例：
```bash
ros2 launch thymio_control experiment_core.launch.py use_sim:=false run_eeg:=true use_teleop:=false input:=lsl
```

### 4.2 `scripts/eeg_control_node.py`

EEG 主控制节点。`_tick` 流程：
1. `adapter.read_frame()` → `EegFrame`
2. 若含频段特征 → `enrich_features` → 检测 blink（metric-only）
3. `policy.compute_intents` → `_intents_to_twist`（按 `role` 映射）→ 发布 `/cmd_vel`
4. 发布分析 JSON 到 `/eeg_analysis`（含 `steer_direction`）
5. 每 tick 更新圆圈 LED（显示转向方向）
6. 看门狗：超时发布零速 Twist

**Blink 检测（metric-only）**：策略指标连续 `blink_confirm_frames` 帧超出校准正常范围（TBR/Alpha `> p95×2`；EI `< p5/2`）即判定眨眼 → 切换 `steer_direction`，进入 `blink_holdoff_frames` 冷却。

**Role 映射**：`speed` → `linear.x = max_forward_speed × speed_intent`、`angular.z = 0`；`steering` → `linear.x = 0`、`angular.z = -steer_direction × turn_angular_speed × |steer_intent-0.5|`。

支持校准模式（`calibrate=true`）：30 秒收集指标 → 计算 p5/p50 → 写入 YAML → 重建 policy → 将 `calibrate` 置回 `false`。

### 4.3 `thymio_control/pipeline.py`

模块化入口。核心 exports：
- `POLICIES` — `{“ei”: EiPolicy, “tbr”: TbrPolicy, “alpha”: AlphaPolicy}`
- `build_adapter(args)` — 仅支持 `lsl`
- `build_pipeline(args)` → `(adapter, processor, policy)`

### 4.4 子包

**adapters/**：`RawLslAdapter`（LSL raw EEG + Welch PSD）

**processors/**：`band_power.py`（`StreamingBandPowerExtractor`，Welch PSD 五个频段）、`enrich.py`（特征工程）

**policies/**：`EiPolicy`（β/(α+θ)）、`TbrPolicy`（θ/β）、`AlphaPolicy`（α 功率）。支持 `offset/scale` 校准参数和 EMA 平滑。

---

## 5. 配置文件

### `eeg_control_node.params.yaml`
```yaml
input: lsl
policy: tbr
eeg_device: bci-core-4
lsl_stream_type: EEG
lsl_timeout: 8.0
lsl_source_id: ""
calibrate: false
calib_offset: 0.0
calib_scale: 1.0
role: speed            # speed | steering
max_forward_speed: 0.05
turn_angular_speed: 0.8
blink_holdoff_frames: 4
blink_confirm_frames: 2
line_mode: ""          # '' | blackline | whiteline
```

### `launch_args.yaml`
```yaml
use_sim: true
run_eeg: false
use_teleop: true
```

调试时先设置 `input: lsl`，Web GUI 通过 `/api/config` 管理配置。

---

## 6. 测试

```bash
pytest thymio_control/test/test_*.py -v
```

---

## 7. 易踩坑

1. **LSL 连接挂起（无波形/校准卡 preparing）**：WSL2 未禁用 eth0 的 IPv6 → liblsl 选中不可达的 IPv6 link-local 地址。需执行 `sysctl net.ipv6.conf.eth0.disable_ipv6=1`（持久化见 README「WSL2 网络配置」）
2. `use_teleop=true` 时 EEG 节点不启动 → 设 `use_teleop:=false`
3. 校准后值没更新 → 需 clean rebuild（`rm -rf install/build thymio_control`）
4. 前端 YAML 读不到最新值 → 确保 `npm run dev` 重建前端，backend 重启
