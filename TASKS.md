# Task List — TelekineRob-BCI (feature/gtec-only)

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

| # | Task | Depends on | Status |
|---|---|---|---|
| P3.1 | UI + backend for dual-device setup (note: EegConfig2 lacks calibrate/calib_offset/calib_scale — needs modelling before dual calibration works) | — | TODO |
| P3.2 | Dual-device routing (headband→steer, hybrid→speed) | P2.3a, P2.3b, P3.1 | TODO |

---

## ⚪ Other (lower priority)

| # | Task | Status |
|---|---|---|
| O1 | Calib UX: rename p5/p95 + manual edit input | ✅ 2026-07-20 |
| O2 | Device connect integration + Log panel | TODO |
| O3 | 17-channel support: full Unicorn data + selective DSP | TODO |
| O4 | Docs: keep all .md files in sync with code | ONGOING |
| O5 | App.jsx 1157→~300 lines: extract components/hooks incrementally alongside UI feature work | TODO |
