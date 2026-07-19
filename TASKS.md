# Task List — TelekineRob-BCI (feature/gtec-only)

## ✅ Completed

| # | Task | Date |
|---|---|---|
| 1 | P1: BCI Core-4 LSL bridge (gpype → LSL → RawLslAdapter) | 2026-07-02 |
| 2 | Calibration Phase B: auto-save p5/p95 + UX | 2026-07-06 |
| 3 | Policy rename: Ei/Tbr/Alpha | 2026-07-03 |
| 4 | Remove legacy: Enobio/Tobii/TCP/EDF/gaze/mock | 2026-07-10 |
| 5 | One-click stop-before-start | 2026-07-05 |
| 6 | Device persistence in YAML | 2026-07-14 |
| 7 | Default input=lsl everywhere | 2026-07-14 |

---

## 🔴 Phase 1 — Validation (4 combos device × metric → forward)

| # | Task | Status |
|---|---|---|
| P1.1 | headband + tbr → forward | ✅ 2026-07-17 |
| P1.2 | hybrid black + tbr → forward | ✅ 2026-07-18 |
| P1.3 | headband + alpha → forward | TODO |
| P1.4 | hybrid black + alpha → forward | TODO |

---

## 🟡 Phase 2 — Steering

| # | Task | Depends on | Status |
|---|---|---|---|
| P2.1 | UI improvements for steering | — | TODO |
| P2.2 | Blink detection: active vs passive | — | TODO |
| P2.3a | Restore steer_intent in TbrPolicy + AlphaPolicy | P1.1–4 | TODO |
| P2.3b | Blink steer: turn direction state machine + LED | P2.3a | TODO |

---

## 🟢 Phase 3 — Dual-device

| # | Task | Depends on | Status |
|---|---|---|---|
| P3.1 | UI + backend for dual-device setup | — | TODO |
| P3.2 | Dual-device routing (headband→steer, hybrid→speed) | P2.3a, P2.3b, P3.1 | TODO |

---

## ⚪ Other (lower priority)

| # | Task | Status |
|---|---|---|
| O1 | Calib UX: rename p5/p95 + manual edit input | TODO |
| O2 | Device connect integration + Log panel | TODO |
| O3 | 17-channel support: full Unicorn data + selective DSP | TODO |
| O4 | Docs: keep all .md files in sync with code | ONGOING |
