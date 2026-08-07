# 04 — Planning

> Where the project stands as its proof-of-concept round closes, what remains to close it, and what
> carries into the prototype proposal. The phase-by-phase history of how it was built lives in git.

---

## 1. The direction — decided 2026-08-07

An application grows through three engineering phases: **proof of concept**, then **prototype**, then
**deployment**. This round concludes as the proof of concept, and its claim is demonstrated:
**a camera alone can record and analyse a patient's movement for tele-rehabilitation.**

The standing decisions for the PoC:

- The **ChArUco board** is the camera-calibration and metric-scale path. Bone-length scaling is
  postponed to the prototype phase — its design is kept in
  [01-specification.md](01-specification.md) section 6.4.
- Storage is **local files, plus export and re-import**. SQLite is cancelled.
- Implementation of the remaining changes is owned by the team; this document tracks what and why.

**What comes after:** a new proposal for the **prototype phase** — engineered deliberately, with
human review — combining this PoC's summary ([10-poc-conclusion.md](10-poc-conclusion.md)) with the
professor's proposal of 2026-08-07: IMU ground-truth data gathering, possible model training for
better keypoint extraction from video, and a more solid application.

---

## 2. Where the project stands

| Capability | Status |
|------------|--------|
| 2D pose estimation, joint angles, ROM | ✅ Built |
| Both-legs analysis, with the instructed side screened | ✅ Built |
| Smoothness (LDLJ, SPARC, movement units) | ✅ Built |
| Screening against task thresholds | ✅ Built |
| Annotated skeleton video | ✅ Built |
| Angle trajectory in the response, and the graph in the interface | ✅ Built |
| Storing results and reopening a past session | ✅ Built — local file store |
| Symmetry across two recordings, one clip per leg | ✅ Built — `/compare` page, no threshold yet |
| ChArUco board calibration | ✅ Built — the PoC's calibration and scale path |
| 3D lifting and motion simulation with muscle overlay | ✅ Built, but frequently falls back to 2D |
| Quality **rejection** | ❌ Flags only, does not reject |
| Bone-length scale, velocity, progress comparison | ❌ Not built — prototype phase |

**The honest summary:** the measurement core works, and results are kept rather than discarded. The
known gaps are the hard-reject safety guard, the patient-specific scaling that would make 3D
trustworthy, and comparing a patient against their own earlier baseline.

---

## 3. Remaining work to close the PoC

- [ ] The interface separates into three clear steps: **camera calibration → video upload → analysis**
- [ ] The analysis view shows metrics, the angle graph, and the 3D model, and can **compare against
      the patient's stored history**
- [ ] **Export and re-import** of results
- [ ] The one-page conclusion a newcomer can read end to end — [10-poc-conclusion.md](10-poc-conclusion.md)

---

## 4. Carried into the prototype proposal

Everything designed or discovered in the PoC that was deliberately not built here. This table plus
the professor's proposal is the raw material for the prototype plan.

| Item | Why it matters |
|------|----------------|
| **Hard-reject quality guard** | The one safety gap: today a poor recording is flagged but still returns plausible numbers. The `v1` contract ([03-api-contract.md](03-api-contract.md)) already defines the rejection shape |
| **Implement the `v1` API contract** | Designed and documented in [03-api-contract.md](03-api-contract.md); the running API differs as its part 9 maps — including the `estimated_` renames and `tracking_stability_score` |
| **Bone-length metric scale** (manual entry, MRI import) | Removes the printed board and its failure modes; per side, ratio only. Design in [01-specification.md](01-specification.md) section 6.4 |
| **3D reliability** — bone-length constrained refinement, neutral-pose zero reference | What makes a 3D-first architecture honest. Both are high-risk: refinement can over-constrain and hide real asymmetry; the neutral pose must be optional |
| **Angular velocity and acceleration** | Shows hesitancy that ROM alone hides; the trajectory it derives from already ships |
| **Progress against the patient's own baseline, with MCID verdict** | The monitoring layer. Also removes the superseded in-response `symmetry_index_score` |
| **Test–retest repeatability study** | The blocker on every threshold: until we know what two recordings of the *same* leg disagree by, no asymmetry percentage can honestly be called abnormal. Needs several people recorded two or three times per leg — data collection, not code |
| **Record the camera setup per session** | The known hole in the comparability guard: nothing stored says where the camera sat. Subject bounding-box size is the cheap proxy, and it must land **before** the repeatability data is collected |
| **ROM thresholds for other populations** | Current values are clinician-confirmed **for elderly patients only** (2026-08-04); the end goal is use with anyone |
| **Screening layer** (5-STS, gait speed, TUG) | A separate build needing stopwatch timing and walking tasks |
| Smaller items | Ankle tasks in 3D (needs a lifter with foot joints); age-matched smoothness Z-score (needs reference data); pelvis sway, lighting and blur scores; OpenSim export (confirm wanted); CT muscle data (Team 6); cloud portal for remote review |

---

## 5. Open questions

| Question | Who decides |
|----------|-------------|
| How many days may separate two sides of one symmetry comparison? Default 30 (`ASYMMETRY_MAX_DAYS_APART`); exceeding it warns rather than refuses | The clinician |
| What asymmetry counts as abnormal? Nothing is claimed today | The repeatability study first, then the clinician |
| Are the movement instruction phrases universal enough? Awaiting the doctor's review of recorded example videos | The clinician |
| Should rejected recordings be visible in patient history, or hidden? | The clinician |
| Is the OpenSim export still wanted? | The advisor |

---

## 6. Risks that carry into the prototype

| Risk | Mitigation |
|------|------------|
| 3D stays unreliable even after refinement | The 2D fallback is clinically valid; report the mode honestly and do not overclaim |
| Bone-length offset (landmarks versus joint centres) | Use as a scaling ratio only; never report absolute segment lengths |
| Patients cannot hold the neutral pose | Optional by design — skip and warn, never fail |
| Rejection guard rejects too many real recordings | Measure the rejection rate on real clips before fixing thresholds |
| Thresholds are convention, not validated | Stated openly in [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md); a validation study is future work |
