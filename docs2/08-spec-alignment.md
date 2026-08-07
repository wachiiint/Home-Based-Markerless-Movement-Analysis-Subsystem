# 08 — Alignment with the Advisor's Specification

> A living checklist against the *Architecture Specification: AI-Based Home Remote Assessment System
> (2026)*. It answers one question at a glance: **which parts of the specification are done, which are
> coming, and which we have deliberately declined.**
>
> Update this file whenever a phase in [04-planning.md](04-planning.md) completes.

**Status legend**

| Mark | Meaning |
|------|---------|
| ✅ | Aligned — implemented and matching the specification |
| ⚠️ | Partial — the quantity exists but the scale, name, or structure differs |
| 🔵 | Planned — scheduled in [04-planning.md](04-planning.md), with the phase named |
| ❌ | Missing — not built and not currently scheduled |
| ⛔ | Out of scope — a deliberate decision, with the reason given |

---

## 1. Scoreboard

| Status | Count | Summary |
|--------|-------|---------|
| ✅ Aligned | 4 | The core mathematics: joint angle, ROM, LDLJ smoothness, and the reference list |
| ⚠️ Partial | 5 | Right quantity, wrong scale or name — cheap to fix |
| 🔵 Planned | 7 | Mostly P0 and P4 |
| ❌ Missing | 7 | Metrics needing data or research we do not have |
| ⛔ Out of scope | 9 | The entire screening layer, by agreement |

**The headline:** every formula the specification defines for the assessment layer is either already
correct or a rename away from correct. The real gaps are the data-quality guard, which is a safety
issue, and the entire screening layer, which is a separate project.

---

## 2. Section 1 — Mathematical formulations

| Specification item | Status | Notes |
|--------------------|--------|-------|
| Joint angle: `arccos(v1·v2 / (‖v1‖‖v2‖))` | ✅ | Identical to our implementation, including the clipping guard |
| ROM = `max_angle − min_angle` | ✅ | Identical |
| `estimated_step_length_ratio` = ankle distance ÷ height in pixels | 🔵 **P1** | Scale-invariant, needs no calibration. The cheapest item in the specification |
| Log dimensionless jerk (LDLJ) | ✅ | Implemented from the same cited reference. We also compute SPARC as a cross-check |
| Age-matched smoothness Z-score | ❌ | Requires mean and standard deviation of LDLJ per age group. We have no such reference data — see the advisor question in [07](07-evaluation-and-limitations.md) |
| LSI = `\|L−R\| / (0.5·(L+R)) × 100` | ⚠️ → 🔵 **P4** | Same quantity, expressed as a 0-to-1 ratio instead of a percentage. Ours × 200 gives the specification's value. Being rebuilt as a cross-recording comparison, which is also the clinically correct form |

---

## 3. Section 2.1 — Screening thresholds

The whole of this table is ⛔ **out of scope for this project round**, by agreement. These are
stopwatch tests requiring timing logic and walking tasks, not camera measurement of joint angles.

| Specification item | Status | Notes |
|--------------------|--------|-------|
| 5-STS ≥ 12.0 s | ⛔ | Separate build |
| Gait speed < 0.8 m/s | ⛔ | Separate build. Bone-length scale makes this newly feasible without a board, so it is the natural next project |
| TUG ≥ 12.0 s | ⛔ | Separate build. See the interpretation question in part 8 |
| Calf circumference cut-offs | ⛔ | A tape measurement, not obtainable from video at all |
| Thai cohort adjustment (BMI ≥ 25, +1 cm) | ⛔ | Depends on calf circumference |

---

## 4. Section 2.2 — Assessment biomarkers

This table is the heart of the project.

| Specification item | Status | Notes |
|--------------------|--------|-------|
| `estimated_knee_rom_deg` | ⚠️ → 🔵 **P0** | Computed correctly; needs the `estimated_` prefix |
| `estimated_hip_rom_deg` | ⚠️ → 🔵 **P0** | Same |
| `estimated_pelvis_sway_mm` | ❌ | Not requested by our clinician. Cheap to add once metric scale exists |
| `estimated_step_length_ratio` | 🔵 **P1** | See part 2 |
| `estimated_symmetry_index` (percent) | ⚠️ → 🔵 **P4** | See part 2 |
| `log_dimensionless_jerk` | ✅ | Implemented |
| Age-matched Z-score | ❌ | No reference data |

> **Note:** the specification names only knee and hip ROM. This project also measures **ankle**
> dorsiflexion and plantarflexion, at the clinician's request. See part 7.

---

## 5. Section 3 — Evaluation and quality logic

| Specification item | Status | Notes |
|--------------------|--------|-------|
| **Data quality guard** — reject when `valid_frame_ratio < 0.70` or `mean_conf < 0.60` | 🔵 **P0** | **The most important gap.** We currently flag and still return numbers. This is a genuine safety issue, not a cosmetic one |
| `assessment_status: "rejected"` with `rejection_reason` | 🔵 **P0** | Adopted in the new contract |
| Confidence = `0.40·frames + 0.40·confidence + 0.20·tracking_stability` | 🔵 **P0** | Currently a 0.5 / 0.5 blend |
| `tracking_stability_score` | 🔵 **P0** | Does not exist. Must be defined — intended meaning is frame-to-frame steadiness of the skeleton |
| `valid_frame_ratio`, `mean_keypoint_confidence` | ✅ | Both computed |
| `missing_joint_ratio` | ❌ | Straightforward to add alongside the confidence work |
| `lighting_score` | ❌ | Frame brightness measurement already exists for board diagnostics and could be reused |
| `blur_score` | ❌ | Blur measurement likewise already exists |
| Sarcopenia classification (`low_strength OR low_performance`) | ⛔ | Screening layer |
| `screening_support_flags` | ⛔ | Depends on calf circumference |
| Configurable `tug_threshold`, `cc_mode` | ⛔ | Screening layer |
| `risk_level` low / moderate / high | ⚠️ | We produce this, but from **per-task ROM thresholds**, not from the AWGS criteria. Same field name, different meaning — worth flagging to avoid confusion |

---

## 6. Sections 4 and 5 — Monitoring, MCID, and the JSON schema

| Specification item | Status | Notes |
|--------------------|--------|-------|
| Knee ROM MCID +5.0 degrees | 🔵 **P4** | In scope. The one MCID that does not depend on the screening layer |
| Gait speed MCID +0.10 m/s | ⛔ | Depends on gait speed |
| 5-STS MCID −2.00 s | ⛔ | Depends on 5-STS |
| TUG MCID −2.08 to −3.40 s | ⛔ | Depends on TUG |
| `baseline_comparison` with dates | 🔵 **P4** | Our progress endpoint |
| `mcid_evaluation` with `clinical_recovery_status` | 🔵 **P4** | Our `verdict` field |
| `recovery_slope_per_month` | ❌ | Needs three or more sessions. Natural extension once history exists |
| `patient_metadata` — gender, age, BMI | ⚠️ | **Deliberate divergence.** We store only a patient identifier. Age would be needed for the Z-score; gender and BMI only matter for calf circumference, which is out of scope |
| `data_governance` block — retention days, compliance statement | ⚠️ | **Different approach, same intent.** We do not describe retention policy in the response; we simply never store video. Only derived numbers persist |
| `tier_1 / tier_2 / tier_3` nested structure | ❌ | **Structurally incompatible with our contract — needs a decision.** See part 8 |

---

## 7. Where this project goes beyond the specification

Worth stating explicitly, because a gap list read alone gives an unfairly negative picture.

| Capability | Why it exists |
|------------|---------------|
| **Ankle tasks** (dorsiflexion, plantarflexion) | Requested by our clinician. Absent from the specification, which names only knee and hip |
| **Both-legs analysis on every recording** | Contralateral comparison is standard clinical practice, and it doubles as a check that the declared leg is the one that moved |
| **SPARC smoothness** | A second, independent smoothness measure alongside LDLJ |
| **Annotated skeleton video** | Lets a human verify the system tracked the right person — the single most useful sanity check available |
| **3D motion simulation with muscle overlay** | Visual inspection and patient explanation |
| **Angle trajectories and graphs** (planned) | The specification reports only summary values; we keep the whole movement |
| **Angular velocity and acceleration** (planned) | Not in the specification, but they distinguish restricted movement from merely cautious movement |
| **Bone-length metric scale** (prototype phase) | Our answer to calibration burden, postponed past the PoC — the ChArUco board provides scale today. The specification does not address how metric scale is obtained |
| **Per-task ROM screening thresholds** | Gives a per-movement risk indicator where the specification only classifies at the screening layer |
| **General-population end goal** | Advisor's direction (2026-08-04): the specification targets elderly sarcopenia screening, but the final goal is a movement-analysis tool usable with anyone. See `01-specification.md` section 1.4 |

---

## 8. Open questions for the advisor

**1. The tier structure is incompatible with our response format.**
The specification nests output under `tier_1_screening`, `tier_2_assessment`, and
`tier_3_monitoring`. Our contract is organised by recording, analysis, metrics, quality, and
screening. Adopting the tier shape would mean two of the three top-level blocks are permanently
empty, since the screening layer is out of scope. Options: restructure to match, keep our shape and
map to the tier format only when producing a report, or agree that the tier model is a conceptual
framework rather than a required payload. **Our recommendation is the second.**

**2. TUG appears to drive a sarcopenia classification, and we believe it may be unintended.**
The reference code computes:

```
low_performance = (gait_speed < 0.8) or (tug_duration >= tug_threshold)
possible_sarcopenia = low_strength or low_performance
```

so a slow TUG alone yields a possible-sarcopenia classification. But the specification's own docstring
defines possible sarcopenia as low strength **or** low gait speed, with no mention of TUG, and Table
2.1 lists TUG as a **fall-risk** indicator. Under AWGS 2019, TUG is not a sarcopenia criterion.
Should TUG instead be reported separately as fall risk?

**3. Is the age-matched Z-score achievable?**
It needs LDLJ reference values per age group. Does suitable data exist, or should this be dropped?

**4. Is `risk_level` acceptable with a different meaning?**
The specification derives it from AWGS criteria; we derive it from per-task ROM thresholds. Same
field name, different basis. Should we rename ours to avoid confusion?

**5. Is validation within scope for this round?**
See [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) part 8. Without it we can
claim the system works, but not that it is accurate.

---

## 9. Keeping this document honest

- Update it at the end of every phase in [04-planning.md](04-planning.md).
- When an item moves to ✅, state where it is implemented.
- When something is declined, record it as ⛔ **with the reason** — never delete the row. A gap list
  that quietly loses entries stops being trustworthy.

---

## Related documents

| Document | Purpose |
|----------|---------|
| [00-glossary.md](00-glossary.md) | Definitions of every term used |
| [01-specification.md](01-specification.md) | What the project is and why |
| [02-pipeline.md](02-pipeline.md) | Patient workflow and the technical data pipeline |
| [03-api-contract.md](03-api-contract.md) | Request and response formats |
| [04-planning.md](04-planning.md) | Phases, tasks, risk, effort, benefit |
| [05-user-manual.md](05-user-manual.md) | How to perform, record, and interpret each task |
| [06-setup.md](06-setup.md) | Installation and running the application |
| [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) | Accuracy, validation, and honest limits |
| **08-spec-alignment.md** | *This document* |
