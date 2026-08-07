# 04 — Planning

> What is built, what is next, and what it costs.
> Everything marked ⚠️ in [02-pipeline.md](02-pipeline.md) and every change listed in
> [03-api-contract.md](03-api-contract.md) part 9 appears here as a task.

**How to read the annotations.** Each task carries `effort · risk · benefit`. Effort is working days
for one person. Risk is the chance it takes longer than estimated or breaks something else.

---

## 1. Where the project stands

| Capability | Status |
|------------|--------|
| 2D pose estimation, joint angles, ROM | ✅ Built |
| Both-legs analysis | ✅ Built |
| Smoothness (LDLJ, SPARC, movement units) | ✅ Built |
| Screening against task thresholds | ✅ Built |
| Annotated skeleton video | ✅ Built |
| 3D lifting and motion simulation with muscle overlay | ✅ Built, unreliable — see P3 |
| Symmetry across two recordings, one clip per leg | ✅ Built — `/compare` page and `GET /api/demo/compare`, no threshold yet |
| Symmetry inside a single clip (`symmetry_index_score`) | ⚠️ Still in the response and still wrongly scoped — superseded, remove in P4 |
| ChArUco board calibration | ✅ Built, being demoted to optional |
| Quality **rejection** | ❌ Flags only, does not reject |
| Angle trajectory in the response, and the graph in the interface | ✅ Built |
| Storing results and reopening a past session | ✅ Built — file store, ahead of the SQLite layer |
| Bone-length scale, velocity, comparisons between sessions | ❌ Not built |

**The honest summary:** the measurement core works, and results are now kept rather than discarded.
What is missing is the safety guard, the patient-specific scaling that makes 3D trustworthy, and the
layer that *compares* two stored recordings — storing them was the prerequisite, not the answer.

---

## 2. Phase plan

Five phases, roughly seven to eight weeks of one person's work. Each phase leaves the system working.

| Phase | Theme | Effort |
|-------|-------|--------|
| **P0** | Contract, naming, and the safety guard | ~1 week |
| **P1** | Trajectories, velocity, and graphs | ~1 week |
| **P2** | Storage and bone-length scale | ~2 weeks |
| **P3** | 3D reliability | ~2 weeks |
| **P4** | Comparison and monitoring | ~1.5 weeks |

---

## P0 — Contract, naming, and the safety guard

The response shape changes here, so this comes first — later work builds on it. Also contains the one
genuine safety gap.

- [ ] **Restructure the response to the new contract** — 3 d · medium · everything downstream assumes it
- [x] **Add `side` to the analysis request** — 0.5 d · low · unblocks all pairing and symmetry work
      *Done ahead of the restructure: `side` is mandatory on `/api/movement/assess` and `/api/demo/assess`,
      and only the declared leg is screened. Previously the resting contralateral leg was screened too, so
      its near-zero ROM drove the headline risk to `high` on every unilateral clip.*
- [ ] **Hard-reject guard on poor recordings** — 1 d · medium · **the safety fix**; stops plausible numbers coming from unusable video
- [ ] **Add `tracking_stability_score`** — 2 d · medium · new metric; catches jumpy tracking that per-frame confidence misses
- [ ] **Reweight confidence to 0.40 / 0.40 / 0.20** — 0.5 d · low · matches the advisor's specification
- [ ] **Rename inferred quantities to `estimated_`** — 1 d · low · honesty, enforced in the field names
- [x] **Flag when the declared side is not the leg that moved** — 0.5 d · low · catches mislabelled recordings for free
      *Emitted as `declared_side_did_not_move_most` (only when the other leg out-moves the declared one by
      15°+, so a lateral view's occluded far leg does not trip it) and `declared_side_barely_moved`.*
- [ ] **Update tests and the demo page to the new shape** — 1.5 d · low · keeps the suite green
- [ ] **Trim the test suite while updating it** — 0.5 d · low · 105 tests is heavy for a project this size

**On trimming tests.** The response restructure invalidates a chunk of the suite anyway, so P0 is the
right moment to cut rather than doing it as separate work. Two cautions when choosing what goes.
Keep the **known-answer kinematics tests** — they check that a known geometric input produces the
expected angle, which is the only real evidence the measurement maths is right. And remember that the
suite already proves less than it appears to: it demonstrates code correctness, not measurement
accuracy (see [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) part 3). Cutting
tests reduces the first without improving the second, so trim duplicates and scaffolding, not the
maths.

**Note on `tracking_stability_score`.** It does not exist yet and must be defined. The intended
meaning is how steadily the skeleton was tracked between frames — large frame-to-frame jumps in joint
position lower it, even when each individual frame looks confident.

---

## P1 — Trajectories, velocity, and graphs

The highest value per day in the whole plan. The per-frame angles are already computed and then
thrown away; keeping them unlocks the graph, velocity, and later the progress comparison.

- [x] **Return the angle trajectory in the response** — the movement itself, not just its extremes.
      Top-level `trajectory`, one entry per sampled frame, `null` for frames the tracker could not read.
- [ ] **Compute angular velocity and acceleration** — 1 d · low · shows hesitancy that ROM alone hides
- [x] **Draw the trajectory graph in the interface** — plain SVG in `03 / ANALYSIS`, both legs on one
      time axis with the instructed leg emphasised, plus a per-frame CSV of the plotted series
- [ ] **Add `estimated_step_length_ratio`** — 0.5 d · low · advisor's specification; needs no calibration at all

---

## P2 — Storage and bone-length scale

The architectural centre of the plan. Replaces the printed board with a number typed in once, and
gives the application memory.

- [ ] **SQLite storage layer** — 3 d · medium · foundation for patient records and all history
      *Partly delivered ahead of schedule as a **file-backed store** (`services/session_store.py`), because
      a proof-of-concept demo needed results to survive a restart. Analyses are written to
      `data/sessions/<patient_id>/<timestamp>-<session_id>/` and summarised one row per session in an
      append-only `index.jsonl`; `GET /api/demo/sessions` lists them and `GET /api/demo/sessions/{id}`
      reopens one in the shape a fresh analysis returns. The remaining SQLite work is the index layer over
      these rows, not a rewrite of them. See [03-api-contract.md](03-api-contract.md) part 8.1.*
- [ ] **Patient record endpoints, with bone lengths per side** — 2 d · low · where the scale reference lives
- [ ] **Bone-length metric scale** — 2 d · medium · removes printing, calibration clips, and resolution matching
- [x] **Store every completed session** — 1 d · low · required by every comparison
      *Every completed analysis is stored and kept. Rejected sessions cannot be stored yet because the
      rejection guard itself is P0 work and does not exist.*
- [ ] **Demote the ChArUco board to optional** — 1 d · low · keeps floor and 6DoF; removes it from the scale path
- [ ] **Bone-length entry in the interface** — 1 d · low · one form, filled once per patient

**Watch for:** hospital bone measurements use anatomical landmarks while the model uses joint
centres, so expect a systematic offset of a few percent. Use bone length only as a scaling *ratio*
and never report absolute segment lengths back to a clinician.

---

## P3 — 3D reliability

Today the 3D reconstruction is frequently rejected by its own consistency check. This phase is what
makes a 3D-first architecture honest rather than aspirational.

- [ ] **Bone-length constrained refinement** — 5 d · high · known bone lengths *correct* the reconstruction instead of only judging it
- [ ] **Neutral standing pose as a personal zero reference** — 4 d · high · the direct fix for systematic joint-angle bias
- [ ] **Report 3D reliability honestly in the response** — 1 d · low · a reader always knows which path produced the numbers

**Both carry high risk.** Constrained refinement can over-constrain and hide genuine asymmetry, which
is why bone lengths are per side. The neutral pose depends on patients following an instruction, so
it must be optional — if no still segment is found, skip the correction and warn rather than fail.

---

## P4 — Comparison and monitoring

Delivers the monitoring layer, and puts symmetry back on a correct footing.

- [x] **Session lookup and listing** — find the counterpart to compare against
- [x] **Symmetry comparison endpoint** — `GET /api/demo/compare`, left against right across two recordings
- [x] **Comparability guard on the symmetry pair** — blocking checks refuse a mismatched pair outright
- [x] **Symmetry view in the interface** — the `/compare` page: metric table, two-line angle graph, and the 3D viewer with a left/right selector
- [ ] **Test–retest repeatability study** — 3 d + data collection · **high** · the blocker on every threshold below
- [ ] **A defensible asymmetry threshold** — 1 d · low · trivial once the study reports, impossible before it
- [ ] **Progress endpoint with MCID verdict** — 3 d · medium · answers whether a change is real or noise
- [ ] **Comparability guard on progress** — 1 d · medium · the same refusals, over two recordings of one leg
- [ ] **Progress views in the interface** — 2 d · medium
- [ ] **Record the camera setup per session** — 1 d · medium · subject bbox size, resolution, orientation in the index row
- [ ] **Remove `symmetry_index_score` from the analysis response** — 0.5 d · low · superseded by the endpoint above

**The repeatability study is the critical path, and it is the one item that cannot be shortened by
working harder.** Until we know what two recordings of the *same* leg disagree by, no number of
percent can be called abnormal — a 12 percent threshold over 15 percent recording noise flags
everybody. Collecting it needs several people recorded two or three times per leg, so it should start
in parallel with the code work rather than after it.

**Camera setup is the known hole in the comparability guard.** Nothing stored today says where the
camera sat, so the guard cannot check that two clips were filmed the same way; it says so in a
standing warning instead of implying a check it did not make. Recording the subject's bounding-box
size per session is the cheap proxy — it moves with camera distance — and it must land before the
repeatability data is collected, or that data inherits the same blind spot.

---

## 3. Dependencies

```
P0 (contract + side field)
      │
      ├──▶ P1 (trajectories) ──────────────┐
      │                                     │
      └──▶ P2 (storage + bone length) ──┬──▶ P4 (comparisons)
                                         │
                                         └──▶ P3 (3D reliability)
```

P0 comes first because everything assumes the response shape. P1 and P2 are independent and can run
in either order. P3 needs bone lengths from P2. P4 needs storage from P2 and trajectories from P1.

---

## 4. Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| 3D stays unreliable even after P3 | Medium | High — undermines the 3D-first claim | 2D fallback already works and is clinically valid. Report the mode honestly and do not overclaim |
| Bone-length offset from landmark-versus-joint-centre difference | High | Low | Use as a ratio only; never report absolute segment lengths |
| Patients cannot hold the neutral pose | Medium | Medium | Optional by design — skip and warn, never fail |
| Rejection guard rejects too many real recordings | Medium | Medium | Measure the rejection rate on real clips before fixing thresholds. Return the annotated video so users can see why |
| Interface work exceeds the team's comfort | Medium | Medium | Plain HTML and JavaScript, no framework or build step. Graphs are the only new component |
| Ankle tasks can never be 3D | Certain | Low | Documented and accepted. 2D sagittal is the clinical standard for ankle ROM anyway |
| Thresholds are convention, not validated | High | Medium | Stated openly in [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md); a validation study is future work |

---

## 5. Backlog — deliberately not scheduled

| Item | Why deferred |
|------|--------------|
| **Screening layer** (5-STS, gait speed, TUG) | A separate build needing stopwatch timing and walking tasks. Bone-length scale makes gait speed newly feasible, so this is the natural next project |
| **Ankle tasks in 3D** | Needs a lifting model with foot joints. Real work, low return — 2D ankle measurement is the clinical standard |
| **Age-matched smoothness Z-score** | Needs reference data from many patients per age group, which the project does not have |
| **Pelvis sway, lighting score, blur score** | In the advisor's specification but not requested by the clinician. Cheap to add later |
| **OpenSim kinematics export** | Scientifically interesting, one to three weeks, and absent from the advisor's specification. Confirm it is wanted before starting |
| **CT muscle data (Team 6)** | Another team's work. Integration is possible later; nothing here depends on it |
| **Cloud portal for remote review** | Would let a doctor read results without sitting at the machine, but brings real privacy obligations. The contract stays integration-ready so this remains possible |
| **ROM thresholds for non-elderly patients** | The current per-task thresholds were confirmed by the clinician for **elderly** patients (2026-08-04). The end goal is use with anyone, so other populations need their own reviewed values before the risk levels can be trusted for them |
| **MRI import of bone lengths** | Raised by the advisor (2026-08-04). Manual entry in P2 comes first; where a patient already has a scan, importing the lengths from it would remove the typing step |

---

## 6. Definition of done

A phase is complete when all of the following hold.

- [ ] Every task in the phase is ticked
- [ ] The full test suite passes
- [ ] New behaviour has tests covering both the working path and the failure path
- [ ] The affected documents in `docs2/` are updated in the same change
- [ ] The application starts and runs one real recording end to end
- [ ] Any new limitation is recorded in [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md)

---

## 7. Open questions

| Question | Who decides | Blocks |
|----------|-------------|--------|
| How many days may separate two sides of one symmetry comparison? Default is 30 (`ASYMMETRY_MAX_DAYS_APART`), and exceeding it warns rather than refuses, precisely because nobody has decided | The clinician | Nothing — the comparison ships without the answer |
| What asymmetry counts as abnormal? Nothing is claimed today | The repeatability study first, then the clinician | The asymmetry threshold |
| ~~Are the per-task expected and borderline ROM values clinically right?~~ **Answered 2026-08-04: yes, for elderly patients.** Values for other populations are a backlog item | — | Resolved |
| Are the movement instruction phrases universal enough? Awaiting the doctor's review of recorded example videos | The clinician | Nothing now — reword in [05-user-manual.md](05-user-manual.md) once reviewed |
| Is the OpenSim export still wanted? | The advisor | Backlog |
| Should rejected recordings be visible in patient history, or hidden? | The clinician | P2 |

---

## Related documents

| Document | Purpose |
|----------|---------|
| [00-glossary.md](00-glossary.md) | Definitions of every term used |
| [01-specification.md](01-specification.md) | What the project is and why |
| [02-pipeline.md](02-pipeline.md) | Patient workflow and the technical data pipeline |
| [03-api-contract.md](03-api-contract.md) | Request and response formats |
| **04-planning.md** | *This document* |
| [05-user-manual.md](05-user-manual.md) | How to perform, record, and interpret each task |
| [06-setup.md](06-setup.md) | Installation and running the application |
| [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) | Accuracy, validation, and honest limits |
| [08-spec-alignment.md](08-spec-alignment.md) | Status against the advisor's specification |
