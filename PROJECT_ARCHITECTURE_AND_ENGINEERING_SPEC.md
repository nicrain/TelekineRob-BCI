# TelekineRob-BCI 项目架构说明书

## 1. 文档信息
- 项目: g.tec EEG 驱动的 Thymio 机器人控制平台
- 版本: v3.0
- 日期: 2026-07-10
- 状态: gtec-only 精简架构，BCI Core-4 + Hybrid Black 双设备支持
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
| 特征 | `processors/enrich.py` | theta_beta, alpha_asym 等 |
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
    source: str            # “lsl_raw”, “keyboard”
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

- `calibrate=true` → 30 秒采集 → p5/p95 → 写入 YAML → 重建 policy
- 支持三个 policy (ei/tbr/alpha) 各自的 metric 校准
- Web GUI 图表显示校准上下限虚线

---

## 7. 测试

```bash
pytest thymio_control/test/ -v   # 23 tests
```

---

## 8. 设计原则

1. **设备无关**：`RawLslAdapter` 从 LSL StreamInfo 自动读取通道数和采样率
2. **Config-driven**：YAML 配置驱动所有参数，不硬编码
3. **策略模式**：`POLICIES` dict + `build_adapter()` factory
4. **只前进**：`_intents_to_twist` 仅映射到正向速度，无后退逻辑

