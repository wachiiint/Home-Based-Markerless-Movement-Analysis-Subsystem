# 07 — Evaluation and Limitations

> How accurate this system is, how we know, and where it is wrong even when working perfectly.
> This is the document to read before claiming anything about the numbers the system produces.

Related but different: [01-specification.md](01-specification.md) says what we chose **not to build**;
[02-pipeline.md](02-pipeline.md) says what happens when a stage **fails**; this document is about
**error in the things we do measure**, when nothing has failed at all.

---

## 1. The distinction that matters most

A joint angle of 92.7 degrees can be **correctly computed** and still be **wrong by 10 degrees**.

- **Code correctness** — does the software compute what we told it to? *Yes, and it is tested.*
- **Measurement validity** — does the number match the patient's real joint angle? *Unknown. Never
  measured.*

These are separate claims, and only the first is currently supported by evidence. Everything in this
document follows from that gap.

---

## 2. What we can and cannot claim today

### Defensible

- The joint-angle formula is the standard vector method and is implemented correctly.
- ROM is computed as maximum minus minimum over the movement, matching the accepted definition.
- The smoothness measure follows a published method with a citable reference.
- The system reports its own data quality and refuses recordings below a defined floor.
- Results are reproducible: the same video produces the same numbers every time.
- The approach — single camera, pose model, joint angles, screening — is supported by published work
  showing home-usable video assessment reaching moderate-to-strong agreement with clinical tests.

### Not defensible

- ❌ "Accurate to within N degrees." **We have never measured our error against any reference.**
- ❌ "Validated." No validation study has been run.
- ❌ "Clinical grade." No regulatory or clinical evaluation has taken place.
- ❌ "Detects sarcopenia." The system measures movement; it does not diagnose.
- ❌ "The 3D output is metrically accurate." Monocular depth is an estimate, currently unverified.
- ❌ "Our thresholds identify abnormal movement." They are conventions, not derived from patient data.

> **Rule of thumb for writing and presenting:** every claim about *what the software does* is safe.
> Every claim about *how close to the truth the numbers are* is not, until a validation study exists.

---

## 3. What the test suite actually proves

The project has a passing automated test suite. It is worth being precise about its scope, because it
is easy to overstate.

| The tests prove | The tests do **not** prove |
|-----------------|----------------------------|
| Known geometric inputs produce the expected angles | That detected keypoints sit on the real joints |
| ROM equals maximum minus minimum | That the detected maximum is the true maximum |
| The API returns the documented structure | That the returned values are clinically meaningful |
| Failures degrade rather than crash | That degraded results are still useful |
| Smoothness behaves correctly on synthetic signals | That it distinguishes healthy from impaired patients |
| Calibration maths inverts synthetic projections | That it works on real phone footage in a real room |

Every test uses synthetic or fixed input. **No test compares a system output against a physical
measurement of a real person.** That is the missing piece, and section 8 describes what filling it
would take.

---

## 4. Evidence from the literature

> **Verify every citation before it enters a thesis or paper.** Entries marked ✔ are confirmed from
> the advisor's reference list. Entries marked ~ are described from prior project notes or are
> well-known works whose exact details should be checked at the source.

### 4.1 Markerless pose estimation carries systematic, joint-specific error

The most important finding for this project. Studies comparing markerless joint angles against
laboratory motion capture report root-mean-square errors in the region of **7 to 15 degrees**,
varying by joint and by camera view. Error fell below the commonly cited **6-degree clinical
acceptability threshold** only after fitting a **per-joint, per-movement correction**.

**This system applies no such correction.** Angles go directly from detected keypoints into threshold
comparison. If the published error range holds here, a patient measured at 62 degrees might truly be
anywhere from roughly 50 to 75 degrees — a span that crosses the borderline threshold for several
tasks. ~

### 4.2 ROM is least reliable exactly where it matters

Reliability of video-based ROM against motion capture has been reported as low as **ICC 0.18 to 0.64**
for joints where the estimated angle trajectory *flattens* near maximal flexion, because of
self-occlusion and limb overlap, even while the true angle keeps changing.

This is precisely the failure mode this system is most exposed to. ROM is `max − min`, so it depends
entirely on the extremes of the trajectory — the least reliable part — and that is also where
screening draws its risk boundary. ~

### 4.3 The reference standard is not perfect either

Worth stating because it sets a realistic target. Manual goniometry, the clinical gold standard, has
its own measurement error: inter-rater differences of around **5 degrees** are commonly reported for
lower-limb joints, and larger for the ankle.

So the goal is not to match a perfect reference. It is to be **no worse than the human measurement it
would replace**, which is a meaningfully lower bar and an achievable one. ~

### 4.4 Monocular 3D lifting has an unmeasured domain gap

The 3D model was trained on **Human3.6M**, a dataset of healthy adults performing everyday actions in
a laboratory. The target population here is elderly patients with restricted or pathological movement,
filmed in homes.

Two consequences. Benchmark accuracy figures for such models do not transfer to this population.
And the model has a learned prior about how human bodies move, which may **normalise** exactly the
abnormality being measured — pulling an impaired movement toward the healthy pattern it was trained
on. This risk is unquantified and is a strong argument for reporting the 2D result whenever the 3D
reconstruction is not clearly trustworthy. ~

### 4.5 Smoothness metrics are well grounded

The smoothness measure used here (log dimensionless jerk) comes from a published, peer-reviewed
method designed specifically to be robust to movement duration and amplitude, which naive jerk
measures are not. ✔ (DOI: 10.1186/s12984-015-0090-9)

The caveat is interpretive rather than mathematical: the metric is validated for characterising
movement, but there is **no reference range for what value indicates impairment** in this population.
The advisor's specification anticipates this by asking for an age-matched Z-score, which needs
reference data the project does not have.

### 4.6 Clinical thresholds are borrowed, and their populations matter

| Threshold | Source | Question to ask |
|-----------|--------|-----------------|
| Sarcopenia criteria, 5-STS ≥ 12 s, gait speed < 0.8 m/s | AWGS 2019 ✔ (DOI: 10.1016/j.jamda.2019.12.012) | Derived for Asian populations, which suits this project |
| Gait speed MCID +0.10 m/s | Bohannon & Glenney ✔ (DOI: 10.1111/jep.12158) | Derived across mixed pathology — does it apply to sarcopenia specifically? |
| Knee ROM MCID +5 degrees | Advisor's specification ✔ | From which population and which measurement method? |
| TUG ≥ 12 s | Shumway-Cook et al. ✔ (DOI: 10.1093/ptj/80.9.896) | A **fall-risk** measure, not a sarcopenia criterion — see section 10 |
| Limb symmetry > 10 % | Advisor's specification, described as a research biomarker ✔ | Largely derived from sports and ACL rehabilitation. Is it right for elderly patients? |
| Per-task expected and borderline ROM | **This project's own convention** | No published source. See section 6 |

### 4.7 Muscle modelling was correctly excluded

Reviews of Hill-type muscle models document unresolved numerical instability problems that remain
open research rather than solved engineering. Combined with the impossibility of obtaining ground
reaction force from a camera, this supports the decision to present muscle *length* only, and never
force or activation. ~

---

## 5. Known systematic errors in this implementation

These are specific, identified weaknesses in the current code — not general limitations of the
approach. Each is fixable.

| # | Issue | Effect | Status |
|---|-------|--------|--------|
| 1 | **No angle-bias correction.** Raw keypoint angles feed straight into screening | Systematic per-joint error carried into every result and every risk level | Open, no fix scheduled |
| 2 | **ROM uses raw extremes.** A single spurious frame sets the maximum or minimum | One bad frame inflates ROM. No percentile or robust bounds | Open |
| 3 | **Smoothing is causal.** The filter uses only past frames | Magnitudes are fine, but peak *timing* is shifted later. Affects velocity and trajectory timing, not ROM | Open, by design |
| 4 | **Confidence averages all 26 keypoints**, including face and arms | Under-reports confidence in the leg joints actually being measured. A clear face can mask an unclear knee | Open |
| 5 | **Occlusion warning is a proxy**, computed as valid-frame-ratio below 0.8 | Unrelated to real occlusion detection, and its 0.8 disagrees with the 0.6 used for the quality flag — two thresholds on one ratio | Open |
| 6 | **Subject selection is per frame**, choosing the most confident person independently each time | The tracked person can switch mid-recording without any warning | Open |
| 7 | **Side is chosen from limited evidence** | A noisy early frame can bias which leg is treated as primary | Partly mitigated by analysing both legs |
| 8 | **Ankle tasks depend on toe keypoints**, the least reliable in the set | Ankle results are systematically less trustworthy than hip and knee | Documented, inherent |

Items 4, 5, and 6 are cheap to improve and would raise confidence in the quality grade itself.

---

## 6. The threshold problem

Every `risk_level` the system produces comes from comparing measured ROM against two numbers per
task: `expected_rom_deg` and `borderline_rom_deg`.

**These numbers were chosen by convention. They are not derived from patient data, not taken from a
published source, and have never been checked against clinical judgement.**

| Task | Expected | Borderline |
|------|----------|-----------|
| Hip flexion | 40° | 25° |
| Hip extension | 20° | 10° |
| Knee flexion | 60° | 40° |
| Knee extension | 20° | 10° |
| Ankle dorsiflexion | 15° | 8° |
| Ankle plantarflexion | 25° | 15° |

Two things follow. The screening output is only as good as these numbers, so it should be presented
as a **relative indicator**, not an absolute classification. And validating them is arguably higher
value than improving measurement accuracy — a perfectly accurate angle compared against a wrong
threshold still yields a wrong risk level.

---

## 7. Limitations that remain even when everything works

These do not disappear with better code. They are properties of the approach.

**Single camera, no force.** Muscle force and activation require ground reaction force. No camera can
provide it. Muscle output is geometric length only, permanently.

**Depth is inferred, not observed.** One viewpoint cannot see depth directly. Monocular 3D is always
an estimate, however good the model becomes.

**Camera placement affects 2D results.** A 2D angle is only correct when the movement plane faces the
camera squarely. Foreshortening from a poorly aimed phone silently reduces the measured angle, and
nothing in the result reveals it.

**Clothing, lighting, and footwear change accuracy.** Loose trousers hide the knee; bulky shoes hide
the toes; backlighting flattens the body into a silhouette. These are patient-side variables the
system cannot control and only partly detects.

**A single session is a snapshot.** Performance varies with time of day, fatigue, pain, medication,
and motivation. One recording is one moment, not a stable trait.

**Effort is not measured.** The system cannot distinguish "cannot move further" from "chose not to."
Two clinically opposite situations produce an identical ROM.

**Ankle tasks cannot use 3D.** The lifting skeleton has no toe joint. Inherent to the model.

---

## 8. What a validation study would require

The single most valuable thing this project could do next. A realistic minimum:

**Design.** Concurrent measurement — the same patient, same movement, measured simultaneously by this
system and by a reference method (manual goniometry at minimum; laboratory motion capture ideally).

**Population.** Participants matching the intended users: older adults, including some with restricted
movement. Healthy young volunteers would produce flattering and misleading results, because they are
exactly the population the underlying models were trained on.

**Sample size.** A statistician should set this, but reliability studies of this kind typically need
**30 or more participants**, with each measurement repeated.

**What to report.**

| Analysis | Question it answers |
|----------|--------------------|
| Bland–Altman agreement | How far do our numbers sit from the reference, and is the error constant or proportional? |
| ICC against reference | How well do we agree with the accepted method? |
| Test-retest ICC | If the same patient is recorded twice, do we get the same answer? |
| Minimal detectable change | What size of change exceeds our own measurement noise? |
| Per-task breakdown | Which of the six movements are trustworthy and which are not? |

**Why test-retest matters most.** Even with a systematic offset, a system that reports the *same*
patient consistently is still useful for tracking change over time — which is the monitoring goal.
Poor repeatability would undermine that entirely, so it is the first thing worth measuring.

**Ethics.** Any study involving patients needs institutional approval. This should be started early,
as approval takes longer than the analysis.

---

## 9. Questions for the clinician

Questions the team cannot answer alone. Grouped by what they would change.

### Thresholds and interpretation

1. Are the expected and borderline ROM values in section 6 clinically sensible for elderly patients?
   If not, what values would you use?
2. Should thresholds vary by age, sex, or body size, or is one value per task acceptable?
3. For a seated knee-flexion test specifically, what ROM would you expect from a healthy 75-year-old,
   and what would concern you?
4. Is `max − min` the right summary, or do you care whether the patient reaches a **specific**
   position — for example, "can they achieve 90 degrees of knee flexion"?
5. What measurement error would still be clinically useful? Published work uses 6 degrees as an
   acceptability bar — do you agree for this purpose?
6. Is a **seated** test adequate, or does weight-bearing movement tell you something a seated test
   cannot?

### Symmetry and monitoring

7. What left-right difference is actionable in an elderly patient? The 10 percent figure comes largely
   from sports rehabilitation.
8. How many days may separate the left and right recordings before they no longer represent one
   assessment? Our current assumption is 30.
9. Does the +5 degree knee-ROM MCID apply to this population, or is it drawn from post-surgical
   patients?
10. Should a patient's rejected recordings be visible in their history, or hidden?

### Clinical value

11. Do movement **speed** and **smoothness** change how you would manage a patient, or is ROM alone
    what you act on?
12. If only two of the six movements could be kept, which two carry the most information?
13. What would make you distrust a result from this system?
14. Who realistically records the video — the patient alone, a family caretaker, or a nurse? This
    changes how much setup precision we can assume.

### Making validation possible

15. Could we obtain goniometer measurements on the same patients at the same visit, for comparison?
16. Roughly how many patients could realistically participate?
17. Is there an existing patient cohort or routine clinic where recording could be added without
    burdening anyone?
18. What approval would a validation study need, and how long does that usually take?

---

## 10. Questions for the advisor

**1. The tier structure conflicts with our response format.** The specification nests output under
`tier_1_screening`, `tier_2_assessment`, and `tier_3_monitoring`. Our contract is organised by
recording and metric instead. Should we restructure to match, or keep our shape and map to the tier
format only when producing a report?

**2. TUG appears to drive a sarcopenia classification, and we think that may be unintended.** The
reference code computes:

```
low_performance = (gait_speed < 0.8) or (tug_duration >= tug_threshold)
possible_sarcopenia = low_strength or low_performance
```

So a slow TUG alone classifies a patient as possible sarcopenia. But the specification's own docstring
defines possible sarcopenia as low strength **or** low gait speed with no mention of TUG, and Table
2.1 lists TUG as a **fall-risk** indicator. Under AWGS 2019, TUG is not a sarcopenia criterion. Is
this intentional, or should TUG be reported separately as fall risk?

**3. Is the age-matched smoothness Z-score achievable?** It requires mean and standard deviation of
LDLJ per age group. Does reference data exist that we could use, or should this be dropped?

**4. Is validation within the project scope?** Section 8 describes what it would take. Without it, we
can claim the system works but not that it is accurate.

---

## 11. References

**Confirmed** — from the advisor's verified reference list:

| Work | Topic | DOI |
|------|-------|-----|
| Chen LK, Woo J, Assantachai P, et al. AWGS 2019 Consensus Update, *J Am Med Dir Assoc* 2020;21(3):300-307 | Sarcopenia criteria | 10.1016/j.jamda.2019.12.012 |
| Bohannon RW, Glenney SS, *J Eval Clin Pract* 2014;20(4):295-300 | Gait speed MCID | 10.1111/jep.12158 |
| Balasubramanian S, Melendez-Calderon A, Burdet E, et al. | Movement smoothness, LDLJ | 10.1186/s12984-015-0090-9 |
| Shumway-Cook A, Brauer S, Woollacott M, *Phys Ther* 2000;80(9):896-903 | TUG and fall risk | 10.1093/ptj/80.9.896 |

**To locate and verify** — cited in earlier project notes, or standard works worth reading. Confirm
details at source before citing:

| Topic | What to search for |
|-------|--------------------|
| Markerless joint-angle accuracy against motion capture | Studies comparing pose-estimation angles with Vicon, reporting RMSE by joint and view |
| Video ROM reliability | Reliability of smartphone or webcam ROM against motion capture, reporting ICC per joint |
| Goniometry reliability | Norkin & White, *Measurement of Joint Motion: A Guide to Goniometry* — establishes the error of the reference standard |
| Smartphone-based movement assessment at home | OpenCap (Uhlrich et al.) for smartphone-video biomechanics; also consumer-camera assessment validation work |
| Pose estimation models | RTMPose (Jiang et al.) and MotionBERT (Zhu et al.) original papers, for stated accuracy and training data |
| Human3.6M dataset | Ionescu et al., *IEEE TPAMI* — the training population behind the 3D model |
| Agreement analysis method | Bland & Altman, *Lancet* 1986 — the standard method for comparing two measurement techniques |
| Choosing and reporting ICC | Koo & Li, *J Chiropr Med* 2016 — guideline for reliability studies |
| Hill-type muscle model limitations | Reviews of numerical instability in Hill-type models |

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
| **07-evaluation-and-limitations.md** | *This document* |
| [08-spec-alignment.md](08-spec-alignment.md) | Status against the advisor's specification |
