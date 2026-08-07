# Task List — TelekineRob-BCI (feature/double-gtec)

## ✅ Completed

| # | Task | Date |
|---|---|---|
| 1 | P1: BCI Core-4 LSL bridge (gpype → LSL → RawLslAdapter) | 2026-07-02 |
| 2 | Calibration Phase B: auto-save p5/p95 + UX | 2026-07-06 |
| 3 | Policy rename: Ei/Tbr/Alpha | 2026-07-03 |
| 4 | Remove legacy: Enobio/Tobii/TCP/EDF/gaze/mock from production path (lsl_test retained for offline validation) | 2026-07-10 |
| 5 | One-click stop-before-start | 2026-07-05 |
| 6 | Device persistence in YAML | 2026-07-14 |
| 7 | Default input=lsl everywhere | 2026-07-14 |
| 8 | WSL2 IPv6 fix: disable eth0 IPv6 — liblsl picks unreachable fe80:: LSL address, hanging the eeg node | 2026-08-03 |

---

## 🔴 Phase 1 — Validation (4 combos device × metric → forward)

| # | Task | Status |
|---|---|---|
| P1.1 | headband + tbr → forward | ✅ 2026-07-17 |
| P1.2 | hybrid black + tbr → forward | ✅ 2026-07-18 |
| P1.3 | headband + alpha → forward | ✅ 2026-07-20 |
| P1.4 | hybrid black + alpha → forward | ✅ 2026-07-20 |

---

## 🟡 Phase 2 — Steering

| # | Task | Depends on | Status |
|---|---|---|---|
| P2.1 | UI improvements for steering | — | ✅ 2026-07-21 |
| P2.2 | Blink detection: active vs passive | — | ✅ 2026-07-21 |
| P2.3a | Restore steer_intent in TbrPolicy + AlphaPolicy | P1.1–4 | ✅ 2026-07-20 |
| P2.3b | Blink steer: turn direction state machine + circle LED | P2.3a | ✅ 2026-07-24 |
| P2.4 | Metric-only blink detection (p95×2 threshold + confirm counter) | P2.3b | ✅ 2026-07-24 |
| P2.5 | Steering: half-range mapping + reduced speed (max_forward=0.05, turn_angular=0.8) | P2.4 | ✅ 2026-07-24 |
| P2.6 | Calibration p95→p50 (median as upper reference) | P2.5 | ✅ 2026-07-24 |

---

## 🟢 Phase 3 — Dual-device

> 实现完成（M1–M4，2026-08-04）。已验证通过(2026-08-07)：双设备真机跑通、校准出真值、断流安全停车、O4 Unicorn 桥自愈。EegConfig2 缺口（P3.1 原注）已在 M1 补齐校准字段。

| # | Task | Depends on | Status |
|---|---|---|---|
| P3.1 | UI + backend for dual-device setup（EegConfig2 校准字段 M1 补齐；每设备独立参数文件；双设备每列独立校准） | — | ✅ 2026-08-04 |
| P3.2 | Dual-device routing（`cmd_vel_fuser` 融合；`/eeg_cmd_vel/<role>` 角色后缀主题；任一流断流 0.5s 整车零速） | P2.3a, P2.3b, P3.1 | ✅ 2026-08-04 |

里程碑：M1 数据建模（含 review O1/O2/O3/O25/N1/N4）→ M2 ROS 融合（fuser/launch/参数文件/CMake，O7/O8/O9）→ M3 后端接入（三主题 RosBridge/devices 负载，O18/O20/O21/O24）→ M4 前端（双系列/每列校准/useChartOptions，O19/O22/O17）。

---

## ⚪ Other (lower priority)

| # | Task | Status |
|---|---|---|
| O1 | Calib UX: rename p5/p95 + manual edit input | ✅ 2026-07-20 |
| O2 | Device connect integration + Log panel | TODO |
| O3 | 17-channel support: send all Unicorn Hybrid Black channels (8 EEG + 3 accel + 3 gyro + battery + counter + validation) via LSL for motion/artifact detection | TODO |
| O4 | Docs: keep all .md files in sync with code | ✅ 2026-08-03 |
| O5 | App.jsx 1157→~300 lines: extract components/hooks incrementally alongside UI feature work | TODO |
