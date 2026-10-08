# ARCHITECTURE_TECHNIQUE

> 技术架构（中文版）。2026-10-08 对照 launch、融合器、EEG 节点和校准代码核对。本文描述实现，不作为真机验收记录；后续将并入 `DOSSIER_TECHNIQUE_cn.md`。

## 1. 全栈数据流

```
Windows 主机:
  gtec_bridge/ (gpype_lsl_bridge.py / unicornpy_lsl_bridge.py) → LSL
        ↓ LSL (raw EEG)
WSL2:
  RawLslAdapter → Welch PSD → enrich_features → Policy.compute_intents
      → _intents_to_twist (按 role 映射) → Twist → /cmd_vel
  RosBridge (rclpy 线程) 订阅 /eeg_analysis → WebSocket /ws/stream → 前端图表
```

- **eeg 输入模式仅 `lsl`**(实时 LSL raw EEG);Web GUI 的 `keyboard` 模式是独立 teleop 路径(经 `/ws/teleop` → RosBridge → `/cmd_vel`),与 EEG 节点无关。
- 双设备:两个 eeg 节点各发 partial Twist 到 `cmd_vel_fuser`,fuser 融合后发布最终 `/cmd_vel`。
- 分析数据:每个 eeg 节点把每帧分析 JSON(含指标与 `steer_direction`)发到 `/eeg_analysis` 系列主题,RosBridge 订阅后经 WebSocket 推给前端。

## 2. EEG 处理管线

```
LSL 流 → RawLslAdapter (pull_chunk → Welch PSD → 五个频段 band powers)
      → enrich_features (theta_beta 等特征)
      → Policy.compute_intents (speed_intent, steer_intent)
      → _intents_to_twist (按 role 映射) → Twist → /cmd_vel
      → 眨眼检测(metric-only)→ 切换 steer_direction
```

`eeg_control_node.py` 的 `_tick` 流程:
1. `adapter.read_frame()` → `EegFrame`(含频段特征)
2. 若含频段特征 → `enrich_features` → 检测眨眼(metric-only,见 §5)
3. `policy.compute_intents` → `_intents_to_twist`(按 role 映射)→ 发布 `/cmd_vel`
4. 发布分析 JSON 到 `/eeg_analysis`(含 `steer_direction`)
5. 每 tick 更新圆弧 LED(显示转向方向)
6. 看门狗:超时发布零速 Twist

**设备。**

| key | 设备 | 通道 |
|---|---|---|
| `hybrid-black` | Unicorn Hybrid Black | 8(Fz, C3, Cz, C4, Pz, PO7, Oz, PO8) |
| `bci-core-4` | BCI Core-4 Headband | 4(F8, Fp2, Fp1, F7) |

通道数与采样率由 `RawLslAdapter` 从 LSL StreamInfo 自动读取;设备配置在 `device_profiles.py`。

## 3. 双设备融合(fuser、role 主题、fail-safe)

**主题。** `cmd_vel_fuser` 订阅 `/eeg_cmd_vel/speed`(role=speed 节点)+ `/eeg_cmd_vel/steering`(role=steering 节点),融合后发布 `/cmd_vel`(仿真下 `/model/thymio/cmd_vel`)。

**融合语义。** `merge_twists`:输出 `linear.x` 取自 speed、`angular.z` 取自 steer,其余分量零;`build_command`:任何一路缺失/陈旧 → 整车零速。

**fail-safe。** 融合器的 `watchdog_sec = 0.5` 针对接收的 partial Twist：任一路超过阈值没有新消息，就发布整车零速度命令。EEG 节点另有自己的数据新鲜度检查，双设备断流后停止发布 partial，随后由融合器判超时。两路消息恢复且仍处于运行状态时，融合器会自动恢复输出。发布频率 `publish_hz = 20`；这不是“从 EEG 断连到电机完全停住只需 0.5 秒”的实测保证。

**数据流动 vs 真断流(D4)。** 分析帧按 hop 节奏(~2Hz)到达,`_tick` 以 20Hz 运行——帧间空隙**不是断流**,节点持续回放保持 partial 20Hz 让 fuser 输入新鲜;只有**真断流**(超 watchdog 无新帧)才触发零速静默。

**Role 映射**（`_intents_to_twist`；节点声明默认 `max_forward_speed=0.05`、`turn_angular_speed=0.8`，参数文件可覆盖，不能当成交付电脑实值）：
- `speed` → `linear.x = max_forward_speed × speed_intent`、`angular.z = 0`
- `steering` → `linear.x = 0`、`angular.z = -steer_direction × turn_angular_speed × |steer_intent − 0.5|`

## 4. 参数文件与校准回写

**参数文件。** 按节点 / 配置行独立：`eeg_control_node.params.yaml` 对应第一路，`eeg_control_node.eeg2.params.yaml` 对应第二路。它们不固定绑定 speed、steering 或某一物理设备；角色与设备由界面和配置选择。文件包含 `input`、`policy`、`lsl_source_id`、`calibrate`、`calib_offset`、`calib_scale`、`role`、运动参数和眨眼参数等。

**校准流**(`calibrate=true`):
1. 收到第一帧可用于校准的数据后采集 30 秒指标；至少 50 个样本才计算 `p5` / `p50`（`np.percentile` 5 / 50）。不足时中止，仅清除 `calibrate`，不生成新阈值。
2. `calib_offset = p5`、`calib_scale = max(p50 − p5, 0.001)`
3. 写回 YAML:`calib_offset` / `calib_scale` 更新、`calibrate` 置回 `false`
4. 调用 `policy.set_calibration()` 原位更新 offset/scale，保留 EMA 状态，不重建实例。

节点创建时，读取 `calib_offset + calib_scale` 作为眨眼检测器的 p50 参考（§5）。当前 `_finish_calibration()` 更新策略，但不更新已创建检测器的该参考；按用户手册校准后 Stop / Start，新的节点会读取保存的校准结果。

## 5. 眨眼转向检测

**`MetricBlinkDetector`(瞬态判据,替代旧绝对阈值)。** 相对**短期滚动中位基线**判尖峰——真实眨眼不移动中位数;持续 rest 漂移填满窗口后停止触发。

| 参数 | 值 | 含义 |
|---|---|---|
| `window` | 30 | 滚动中位基线窗口(帧) |
| `k_up` / `k_down` | 2.0 / 0.5 | up 触发 `value > baseline × 2`;down 触发 `value < baseline × 0.5` |
| `confirm_frames` | 2 | 连续超范围帧确认一次眨眼(单帧伪迹被拒) |
| `holdoff_frames` | 4 | 确认后冷却帧数 |
| `min_samples` | 15 | 基线就绪所需样本数 |

- `mode "up"` = alpha / tbr(眨眼使频带通胀,上冲);`mode "down"` = ei(眨眼使分母通胀,瞬落)。
- 确认一次眨眼 → 调用方切换 `steer_direction`(`1 = right` / `-1 = left`,`*=-1`)。
- `in_progress`(确认 + 冷却期间)→ 转向钳中性 0.5,**不冻结旧转向值**。
- **P47 上冲基线钳制**:`baseline = max(滚动中位数, 校准 p50)`——仅上冲(alpha/tbr);专注时 alpha/tbr 远低于 rest,滚动基线塌到专注水平,钳制把阈值下限稳住,降低小被动眨眼误触发。

## 6. 主题与命名约定

| 模式 | 主题 | 方向 |
|---|---|---|
| 单设备 | `/eeg_analysis` | eeg 节点 → RosBridge |
| 单设备 | `/cmd_vel`(仿真 `/model/thymio/cmd_vel`) | eeg 节点 → Thymio |
| 双设备 | `/eeg_analysis/speed`、`/eeg_analysis/steering` | 各 eeg 节点 → RosBridge |
| 双设备 | `/eeg_cmd_vel/speed`、`/eeg_cmd_vel/steering` | 各 eeg 节点 → fuser(partial Twist) |
| 双设备 | `/cmd_vel`(仿真同) | fuser → Thymio |

**命名约定(role 字面量后缀)。** 双设备主题按 **role 字面量**命名:`/eeg_cmd_vel/steering`(非 `steer`)、`/eeg_analysis/steering`——与 WebSocket 负载 `devices: {speed, steering}` 键一致,避免 `steering→steer` 隐式映射表。单设备保留无后缀的 `/eeg_analysis`、`/cmd_vel`。
