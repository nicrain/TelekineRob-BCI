# TelekineRob-BCI 项目架构说明书

## 1. 文档信息
- 项目: g.tec EEG 驱动的 Thymio 机器人控制平台
- 版本: v3.1
- 日期: 2026-08-03
- 状态: gtec-only 精简架构，含转向（blink 切换方向）+ 双设备支持
- 分支: `feature/gtec-only`

---

## 2. 架构概览

```
Windows 主机:
  gtec_bridge/gpype_lsl_bridge.py        (BCI Core-4, gpype → LSL)
  gtec_bridge/unicornpy_lsl_bridge.py    (Hybrid Black, UnicornPy → LSL)
        ↓ LSL (250Hz, raw EEG)

WSL2/Ubuntu:
  RawLslAdapter → Welch PSD → enrich_features → Policy → /cmd_vel
                                                      ↓
  web_gui (React + FastAPI) ←──WebSocket──→ RosBridge (rclpy)
```

---

## 3. 分层设计

| 层 | 文件 | 职责 |
|---|---|---|
| 数据接入 | `gtec_bridge/*.py` (Windows) | 设备 → LSL |
| 适配器 | `adapters/lsl_raw.py` | LSL → `EegFrame` |
| DSP | `processors/band_power.py` | Welch PSD 频带功率 |
| 特征 | `processors/enrich.py` | theta_beta, beta_alpha_theta |
| 策略 | `policies/ei.py`, `tbr.py`, `alpha.py` | 频带特征 → speed_intent/steer_intent |
| 控制 | `scripts/eeg_control_node.py` | intent → Twist → /cmd_vel |
| 编排 | `launch/experiment_core.launch.py` | ROS2 进程管理 |
| Web | `web_gui/` | FastAPI + React 控制面板 |

---

## 4. 数据契约

### `EegFrame`
```python
@dataclass
class EegFrame:
    ts: float              # Unix 时间戳
    source: str            # “lsl_raw”（当前仅支持 lsl 输入）
    metrics: Dict[str, float]  # alpha, beta, theta, alpha_Fz, ...
```

### `BandPowers`
```python
@dataclass(frozen=True)
class BandPowers:
    delta: float; theta: float; alpha: float; beta: float; gamma: float
```

---

## 5. 设备

| key | 设备 | 通道 | API |
|---|---|---|---|
| `bci-core-4` | BCI Core-4 Headband | 4 (F8, Fp2, Fp1, F7) | gpype |
| `hybrid-black` | Unicorn Hybrid Black | 8 (Fz, C3, Cz, C4, Pz, PO7, Oz, PO8) | gpype / UnicornPy |

---

## 6. 校准系统

- `calibrate=true` → 30 秒采集 → 计算 p5 与 p50（中位数作为上限参考）→ 写入 YAML → 重建 policy
- 支持三个 policy (ei/tbr/alpha) 各自的 metric 校准
- 校准完成后节点将 `calibrate` 置回 `false` 并写入参数文件；前端轮询 `/api/config?reload=true` 检测到 `calibrate=false` 后结束校准
- Web GUI 图表显示校准上下限虚线（min=`calib_offset`，max=`calib_offset+calib_scale`）

---

## 6.1 转向与眨眼控制

- 节点 `role` 参数：`speed`（前进，`angular.z=0`）或 `steering`（原地转向，`linear.x=0`）
- **Blink 切换方向**（metric-only 检测）：策略指标超过校准正常范围连续 N 帧即判定为眨眼
  - TBR / Alpha：`metric > p95×2`；EI（倒相关）：`metric < p5/2`
  - 连续 `blink_confirm_frames` 帧确认后切换 `steer_direction`，随后进入 `blink_holdoff_frames` 冷却
- **半程转向映射**：`steer_intent ∈ [0.5, 0.75]`，`steer_mag = |steer_intent - 0.5|`，最大角速度 = `turn_angular_speed × 0.25`
- **环灯指示**：转向方向通过 Thymio 圆圈灯显示（右转 → LED 1,2,3；左转 → LED 5,6,7），节点每 tick 发布
- 速度参数：`max_forward_speed=0.05`，`turn_angular_speed=0.8`

---

## 7. 测试

```bash
pytest thymio_control/test/ -v   # 50 tests
```

---

## 8. 设计原则

1. **设备无关**：`RawLslAdapter` 从 LSL StreamInfo 自动读取通道数和采样率
2. **Config-driven**：YAML 配置驱动所有参数，不硬编码
3. **策略模式**：`POLICIES` dict + `build_adapter()` factory
4. **角色分离**：`_intents_to_twist` 按 `role` 映射——`speed` 只驱动前进，`steering` 原地转向，无后退逻辑
5. **WSL2 网络前提**：WSL2 需禁用 eth0 的 IPv6（见 README「WSL2 网络配置」），否则 liblsl 会选中不可达的 IPv6 link-local 地址导致 LSL 连接挂起

