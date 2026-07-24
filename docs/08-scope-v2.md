# 08 — Scope v2: Toward the End-Goal Architecture

> Defined 2026-07-24, after the professor's *Production & Peer-Review Ready Document* (2026)
> and a re-scoping of the feature set. Supersedes the informal roadmap in `AGENTS.md`.

---

## 1. Why this pivot

Two inputs forced a re-scope:

1. **The professor's spec** defines a **3-tier system** (Screening / Assessment / Monitoring).
   Everything built so far is **Tier 2 only**. See §7 for the gap list.
2. **Calibration is too heavy.** Getting metric scale currently requires a printed ChArUco
   board, a *separate* same-resolution calibration clip, a device match, and successful board
   detection in the patient clip. That chain is the single biggest source of 3D→2D fallback,
   and it asks too much of a home user.

The fix is a change of scale source, and it cascades through the whole design.

---

## 2. The core architectural change: bone length replaces the board

Metric scale currently comes from the board (back-project ankles onto the floor plane) with a
patient-height fallback. Instead, the patient enters **hospital-measured bone lengths once**:

```
known femur (mm)  ÷  lifted femur (units)  =  mm per unit
```

**Why this is better:**

- No printing, no calibration clip, no resolution matching, no device store.
- More accurate than feet-on-floor, which inherits camera-calibration error.
- **Removes ~4 of the 8 conditions that force a 3D→2D fallback** (see `03-pipeline.md` §4.6).
- The same known lengths then *constrain* the lifted pose, reducing monocular jitter.

### End-goal pipeline

```
Patient enters bone lengths (once, from hospital)
   → records clip starting with a neutral standing pose (2–3 s)
   → 2D pose  →  3D lift
   → bone-length constrained refinement + metric scale   ◀── replaces board calibration
   → continuous angle trajectories (not just max/min/ROM)
   → metrics + graphs
   → compare against baseline  →  MCID verdict
```

### Decisions recorded

| Decision | Choice | Consequence |
|---|---|---|
| **ChArUco board** | **Demoted to optional** | Bone length is the primary scale source. The board is kept only for the floor plane / `transformation_matrix_6dof`. The BH board-highlight task drops to the backlog. |
| **Before/after history** | **Stateless** | The main backend already stores sessions. It passes the prior session's metrics in the request; this service computes the comparison. No database here, no new PDPA obligation. |
| **Calibration pose** | **Neutral standing, side-on, 2–3 s** | Not a full T-pose. The legs are what we measure, and this works in the lateral view the tasks already use — feasible for elderly/impaired patients. |
| **Professor's Tier 1** | **Out of scope for now** | 5-STS / gait speed / TUG are a separate build (timing logic, walking tasks). Finish Tier 2 properly first. |

---

## 3. Work items

Each has benefit / risk / time / constraint. Times are rough working estimates.

### A — Bone length input + metric scale · **2–3 d** · high priority

- **Benefit:** kills most 3D→2D rollbacks; better accuracy than the board; removes the printing
  and calibration-clip burden from the user entirely.
- **Risk:** hospital measurements use *anatomical landmarks* (greater trochanter → lateral
  femoral epicondyle); the model uses *joint centres*. Expect a systematic offset of a few
  percent.
- **Constraint:** lengths must be entered **per side** (left/right femur, left/right tibia). A
  single shared value would erase leg-length discrepancy, which is a real clinical finding.
- **Mitigation for the offset:** use bone length for **scale** (a self-consistent ratio) and do
  not report absolute segment lengths back to the clinician as measurements.

### B — Bone-length constrained pose refinement · **3–5 d** · high priority

- **Benefit:** enforcing known, constant bone lengths across frames is an established fix for
  monocular depth ambiguity and jitter. Directly improves every downstream metric.
- **Risk:** over-constraining can hide genuine asymmetry — hence the per-side requirement in A.
- **Constraint:** must degrade gracefully when lengths are absent (fall back to today's
  behaviour, never reject the request).
- **v1 approach:** hierarchical bone-length normalisation outward from the root — cheap, no
  optimizer. Upgrade to a reprojection-aware optimisation later only if v1 proves insufficient.

### C — Neutral standing calibration pose · **3–5 d**

- **Benefit:** gives a **per-patient 0° reference**. This is the direct fix for the systematic
  7–15° joint-angle bias flagged in the literature review (`05-evaluation-plan.md`). Also a
  free tracking sanity check and a cross-check on the entered bone lengths.
- **Risk:** patients will get the instruction wrong, or be unable to stand still.
- **Constraint:** must be **optional** — if no neutral segment is detected, skip the offset
  correction and warn, never fail.
- **Detection:** find the longest low-motion window in the first N seconds; require the leg to
  be near-straight and confidence high.

### D — Continuous angle trajectories + graphs · **3–4 d** · highest value per day

- **Benefit:** max/min/ROM discards ~95% of the signal. Trajectories also **unblock** Phase E
  motion export, per-trajectory LDLJ, and the MCID comparison in F.
- **Risk:** response payload grows — manageable (~150 frames × a few series).
- **Constraint:** additive only. The existing five top-level contract keys must not change.
- **Note:** `angle_series_3d` already returns per-frame values; they are currently reduced to
  max/min/ROM and discarded. This is largely a matter of *not throwing them away*.

### E — Professor's spec quick wins · **2–3 d**

Cheap alignment with the advisor's document:

| Item | Change |
|---|---|
| Naming | prefix estimated quantities with `estimated_` (e.g. `estimated_knee_rom_deg`) to signal *markerless estimation, not measurement* |
| Symmetry | rescale to LSI **percentage**: `\|L−R\| / (0.5·(L+R)) × 100`, research threshold >10% (currently a 0–1 ratio; the spec value is ours × 200) |
| Quality guard | **hard reject** when `valid_frame_ratio < 0.70` or `mean_confidence < 0.60` → `assessment_status: "rejected"`. Today the service only flags and still returns numbers — a genuine safety gap |
| Confidence | `0.40·valid_frames + 0.40·confidence + 0.20·tracking_stability` (currently 0.5/0.5, and `tracking_stability_score` does not exist yet) |
| New metric | `estimated_step_length_ratio` = ankle distance ÷ height in pixels — scale-invariant, so it needs **no calibration at all** |

- **Risk:** the reject guard changes API behaviour for poor-quality clips. Coordinate with the
  backend before shipping.

### F — Before/after comparison + MCID · **4–6 d**

- **Benefit:** implements the professor's **Tier 3**. MCID thresholds are already defined:
  knee ROM **+5°**, gait speed +0.10 m/s, 5-STS −2.0 s.
- **Risk:** ⚠️ two sessions are only comparable if task, view, and capture conditions match.
  Reporting improvement across mismatched recordings is **worse than not having the feature**.
- **Constraint:** requires a **comparability guard** — same `task_type`, same `view`, both above
  a confidence floor. If the guard fails, report "not comparable" rather than a number.
- **Shape:** stateless. The request carries an optional `baseline` block; the response gains an
  optional `longitudinal` block.

### Backlog (deliberately not scheduled)

| Item | Why deferred |
|---|---|
| **BH** — board highlight in video / Three.js | The board is now optional; highlighting an optional accessory is low value. ~1–2 d whenever wanted. |
| **Tier 1** — 5-STS, gait speed, TUG | Separate build. Note: bone-length scale makes **gait speed** newly feasible without a board, so this is the natural next phase. |
| **M-B** — OpenSim gait2392 kinematics export | Still valid, but absent from the professor's spec. Confirm it is still wanted before spending 1.5–3 weeks. |
| **CT muscle force** | Impossible without a force plate. Permanently out of scope for single-camera. |

---

## 4. Dependencies and order

```
A (bone length) ──▶ B (constrained refinement)
                └──▶ makes the board optional  ──▶ BH deprioritised

C (neutral pose) ──▶ improves A, B, and angle accuracy

D (trajectories) ──▶ F (before/after)
                 └──▶ Phase E motion export
```

**A and D are independent and both high-value — start there.** F must come after D.

## 5. Phased plan (~5–6 weeks)

| Phase | Contents | Time |
|---|---|---|
| **P0 — Spec alignment** | E (quick wins) | 2–3 d |
| **P1 — Foundation** | A (bone length + scale), D (trajectories in response) | 1.5–2 wk |
| **P2 — Pose quality** | C (neutral pose), B (constrained refinement), graphs in the demo UI | 1.5–2 wk |
| **P3 — Longitudinal** | F (before/after + MCID) | 1–1.5 wk |

## 6. Principles carried forward

These do not change:

1. **Additive only.** The five top-level contract keys stay stable.
2. **Best-effort, never raises.** Every new path degrades to the previous behaviour rather than
   failing the request. The one deliberate exception is the P0 reject guard, which is a
   *safety* rejection and must be coordinated with the backend.
3. **Decision support, not diagnosis.** Every estimated quantity is labelled as estimated.

---

## 7. Gap against the professor's spec

Tracked here so the alignment status is visible at a glance.

| Spec item | Status |
|---|---|
| Joint angle via `arccos(v1·v2 / ‖v1‖‖v2‖)` | ✅ identical to `three_point_angle` |
| ROM = max − min | ✅ identical |
| LDLJ smoothness (Balasubramanian 2015) | ✅ implemented (SPARC also, as a bonus) |
| Pose-quality gate | ⚠️ exists, but flags instead of rejecting → **P0** |
| Confidence weights 0.40/0.40/0.20 + `tracking_stability_score` | ❌ → **P0** |
| LSI as a percentage, >10% research threshold | ⚠️ same quantity, wrong scale → **P0** |
| `estimated_` naming convention | ❌ → **P0** |
| `estimated_step_length_ratio` | ❌ → **P0** |
| LDLJ age-matched **Z-score** | ❌ needs age-group reference data — unscheduled |
| `estimated_pelvis_sway_mm` | ❌ unscheduled |
| `missing_joint_ratio`, `lighting_score`, `blur_score` | ❌ unscheduled |
| Tier 3 longitudinal + MCID | ❌ → **P3** |
| Tier 1 (AWGS 2019: 5-STS, gait speed, TUG, calf circumference) | ❌ out of scope this round |
| `tier_1 / tier_2 / tier_3` JSON structure | ❌ **incompatible with the current 5-key contract — needs an advisor decision** |
| Configurable thresholds (`tug_threshold`, `cc_mode`) | ❌ currently hard-coded in `task_config.py` |

### Open question for the advisor

The spec's docstring defines *Possible Sarcopenia = low strength **OR** low performance*, and
Table 2.1 lists TUG as a **fall-risk** indicator — but the reference code folds
`tug >= threshold` into `low_performance`, so **TUG ends up driving a sarcopenia
classification**. Under AWGS 2019, TUG is not a sarcopenia criterion. Confirm whether this is
intended before implementing Tier 1.
