# 01 — Project Specification

> **Status:** current source of truth for *what this project is and why*.
> **Audience:** the project team, the advisor, and anyone joining the work.
> **Companion documents:** [00-glossary.md](00-glossary.md) defines every technical and clinical term
> used here. [02-pipeline.md](02-pipeline.md) explains how the system works step by step.
> [04-planning.md](04-planning.md) tracks what is built and what comes next.

---

## 1. Introduction

### 1.1 The problem

**Sarcopenia** is the age-related loss of muscle mass and strength. It progresses quietly: an older
adult becomes weaker, then slower, then unsteady, and eventually falls. Falls in the elderly are a
leading cause of fracture, hospitalisation, loss of independence, and death. Thailand is an ageing
society, so the number of people at risk is growing faster than the clinical capacity to assess them.

Sarcopenia is treatable when caught early — resistance exercise and nutrition genuinely reverse it.
The difficulty is **detection**. The standard assessment requires the patient to travel to a clinic
and be measured by trained staff. For the people who most need screening — elderly, frail, rural, or
mobility-limited — that trip is the barrier. Patients are therefore assessed rarely, or only after a
fall has already happened.

### 1.2 The opportunity

Modern **markerless pose estimation** can locate a person's joints in ordinary video from a single
consumer camera, with no markers, no suits, and no specialised hardware. A patient who owns a
smartphone already owns the sensor. If joint motion can be measured reliably from a home recording,
assessment stops being an event that requires travel and becomes something that can happen
repeatedly, cheaply, and early.

### 1.3 What this project contributes

This project builds the **measurement layer** of that idea: a local service that takes a short video
of a patient performing a prescribed leg movement and returns objective, quantified motion metrics —
joint angles, range of motion, movement speed, and movement smoothness — together with an honest
statement of how much the recording can be trusted.

It is deliberately **not** a diagnosis system. It produces the numbers a clinician uses to decide.

### 1.4 Who the system is for

The measurement itself is not specific to any disease or age group. A joint angle, a range of
motion, or a smoothness score means the same thing for a young adult recovering from knee surgery as
for an eighty-year-old at risk of sarcopenia.

**Sarcopenia screening in the elderly is the first use case and shaped the current design. The final
goal is a movement-analysis tool usable with anyone.** What is tuned to the elderly today is the
*interpretation* layer: the per-task ROM thresholds behind each risk level were confirmed by the
supervising clinician for elderly patients, and have not been reviewed for other populations.
Widening them is tracked in the backlog in [04-planning.md](04-planning.md).

### 1.5 Project phase: proof of concept

An application grows through three engineering phases: **proof of concept**, then **prototype**, then
**deployment**. This round of the project is the proof of concept, and it is concluding. What it set
out to demonstrate, it has: **a camera alone can record and analyse a patient's movement for
tele-rehabilitation** — no markers, no wearables, no special hardware.

The next round is the prototype: rebuilt deliberately, with human-reviewed engineering rather than
exploratory code. Its plan will be a new proposal that combines this proof of concept's summary with
the professor's proposal of 2026-08-07 — ground-truth data gathering with IMU sensors, possible
model training for better keypoint extraction from video, and a more solid application.

---

## 2. Overview

In plain terms, the system does this:

1. A patient records a short clip (a few seconds) performing one prescribed movement, such as bending
   one knee, filmed from the side.
2. The service detects the person in every sampled frame and locates their body joints.
3. It converts those joint positions into an angle at the joint of interest, for every frame of the
   recording, producing a continuous picture of the movement rather than a single snapshot.
4. From that angle series it derives clinical measures: the largest and smallest angle, the range of
   motion between them, how fast the joint moved (**velocity** and **acceleration**), and how smooth
   the motion was.
5. It grades the *quality* of the recording itself, and reports the metrics alongside that grade.
6. It returns four things: the numeric results, an analysis graph of the angle through the
   movement, an annotated video showing the detected skeleton, and a motion simulation — a 3D
   replay of the movement with a muscle overlay.

A few measures cannot come from one recording alone. Comparing the left leg against the right, or
comparing today against an earlier visit, needs two recordings. These are handled as a separate
question asked after the recordings exist, rather than as part of analysing any single one —
described in Section 7.5.

The guiding stance is **decision support, not diagnosis**. Every number carries an explicit
uncertainty, and any quantity the camera infers rather than measures is labelled as *estimated*.

Which of these capabilities are already built and which are planned is tracked in
[04-planning.md](04-planning.md).

---

## 3. Objectives

### 3.1 Primary objective

Produce clinically meaningful, reproducible lower-limb movement metrics from a single-camera home
video recording, with sufficient transparency about accuracy that a clinician can judge how far to
trust each result.

### 3.2 Specific objectives

| # | Objective | Success looks like |
|---|-----------|--------------------|
| O1 | Measure joint angles and ROM for hip, knee, and ankle tasks | Angles computed for every frame; ROM derived from the angle series |
| O2 | Quantify movement quality beyond ROM | Angular velocity, acceleration, and smoothness reported per session |
| O3 | Grade recording quality and refuse bad data | A quality guard that rejects unusable clips rather than returning misleading numbers |
| O4 | Remove calibration burden from the patient *(prototype phase)* | Metric scale obtained without printed markers or a separate calibration recording. The PoC uses the ChArUco board |
| O5 | Present results visually, not only numerically | Time-series graph, annotated skeleton video, and 3D motion simulation with muscle overlay |
| O6 | Compare across recordings | Left leg against right leg for limb symmetry, and today against an earlier baseline for clinically meaningful change |

### 3.3 End goal

A clinician hands a patient a simple instruction sheet. The patient records the prescribed movements
at home on their own phone. The results arrive as objective numbers with an explicit confidence
grade, alongside a visual replay the clinician can inspect. Repeat sessions show whether the patient
is genuinely improving — judged against published thresholds for meaningful change rather than
against noise.

The end goal therefore covers **both the assessment layer and the monitoring layer** described in
Section 4: measuring how the patient moves today, and tracking whether that is improving over time.

### 3.4 Explicit non-goals

Stating these protects the project from scope drift and from overclaiming.

**Not a diagnosis.** The system flags and quantifies; a clinician diagnoses.

**No muscle force or activation.** Calculating the force a muscle produces requires knowing the force
between the foot and the ground, which is measured by a force plate. A camera cannot recover it. The
muscle overlay in the motion simulation shows muscle *length change* derived from joint geometry — it
is a visualisation of how muscles stretch and shorten as the limb moves, not a measurement of effort.

**No medical imaging integration for now.** CT-derived muscle data is **Team 6's work**. Integrating
it later is a genuine possibility and the architecture should not block it, but it is **out of scope
for this project round** and nothing here depends on it.

**No replacement for the clinical stopwatch tests.** The timed screening tests (5-STS, gait speed,
TUG) ask *how long did the patient take*; this system asks *how did the body move* while doing it.
The two are complementary — a stopwatch says a patient is slow, this system can show the slowness
comes from a restricted right knee — but this project does not compute the timed tests, and a result
from it must never be presented as if it were one.

**Not a general-purpose motion capture system.** Scope is lower-limb assessment tasks.

---

## 4. Clinical framework

Assessment of an at-risk patient happens in three layers. Separating them clarifies exactly what this
project delivers and what it deliberately leaves to others. The framework below is written for the
sarcopenia use case; the assessment layer itself applies to any patient (Section 1.4).

| Layer | Purpose | Typical output | In this project |
|-------|---------|----------------|-----------------|
| **Screening** | Decide quickly whether a patient is at risk at all | Timed tests (5-STS, gait speed, TUG) compared against clinical thresholds | ❌ Not built |
| **Assessment** | Measure objectively *how* the patient moves | Joint angles, ROM, velocity, smoothness, plus a data-quality grade | ✅ **The core of this project** |
| **Monitoring** | Track whether the patient is improving | Comparison against the patient's own earlier baseline, judged by meaningful-change thresholds | ⚠️ Planned — part of the end goal |

**This project delivers the assessment layer, and extends into the monitoring layer as its end goal.**
The screening layer is a separate build requiring stopwatch timing logic and walking tasks, and is
deliberately deferred.

The distinction that matters: **screening asks how long a movement took; assessment asks how the body
moved while doing it.** A stopwatch says a patient needed 14 seconds to stand five times. This system
says their knee moved through 62 degrees, slowly and unevenly, and the recording was good enough to
believe.

### 4.1 Clinical reference standards

The thresholds and metrics used in this project are taken from published clinical literature rather
than chosen by the team.

| Standard | Role in this project | Reference |
|----------|---------------------|-----------|
| AWGS 2019 Consensus | Definition of sarcopenia and the screening thresholds this system's results support | DOI: 10.1016/j.jamda.2019.12.012 |
| MCID — gait speed | Meaningful-change threshold (+0.10 m/s) for the monitoring layer | DOI: 10.1111/jep.12158 |
| MCID — knee ROM | Meaningful-change threshold (+5 degrees) for the monitoring layer | Applied in longitudinal comparison |
| LDLJ smoothness | The movement-smoothness metric implemented here | DOI: 10.1186/s12984-015-0090-9 |
| TUG fall risk | Fall-risk indicator — note that it is **not** a sarcopenia criterion | DOI: 10.1093/ptj/80.9.896 |

---

## 5. Scope

### 5.1 Movement tasks

Six lower-limb tasks are supported. All six are **mandatory** — they are the set requested by the
supervising clinician. Each is measured as the angle at a vertex joint formed by two neighbouring
body segments. Recording instructions and the clinical purpose of each task are in
[05-user-manual.md](05-user-manual.md).

| Task | Vertex joint | Angle formed by | Measured quantity | 3D capable |
|------|--------------|-----------------|-------------------|------------|
| Hip flexion | Hip | Shoulder – hip – knee | Hip ROM | Yes |
| Hip extension | Hip | Shoulder – hip – knee | Hip ROM | Yes |
| Knee flexion | Knee | Hip – knee – ankle | Knee ROM | Yes |
| Knee extension | Knee | Hip – knee – ankle | Knee ROM | Yes |
| Ankle dorsiflexion | Ankle | Knee – ankle – big toe | Ankle ROM | **No — 2D only** |
| Ankle plantarflexion | Ankle | Knee – ankle – big toe | Ankle ROM | **No — 2D only** |

### 5.2 Foot and toe keypoints

Ankle tasks need a toe position, and the pose model does provide one — the standard 17-point body
skeleton stops at the ankles, but this project uses the **Halpe26** variant, which adds big toe,
small toe, and heel on each side. The limitation lies in the 3D stage: the lifting model uses a
17-joint layout with no toe joint at all, so an ankle angle cannot be computed in 3D, and both ankle
tasks are 2D by design rather than by oversight (options for lifting this restriction are recorded in
[04-planning.md](04-planning.md)). Toes are also the least reliable keypoints in practice — small in
the frame and often hidden by shoes or trouser hems — so ankle results warrant more caution than hip
and knee results.

### 5.3 In scope

- Single-camera RGB video of one patient performing one prescribed task
- Per-frame joint angles and the metrics derived from them
- Angular velocity, acceleration, and movement smoothness
- Recording-quality assessment with the authority to reject a clip
- Metric scale from ChArUco board calibration (bone-length scale is prototype-phase work)
- Limb symmetry, computed by comparing left and right recordings of the same task
- Comparison against a prior baseline with a meaningful-change verdict
- Visual output: time-series graph, annotated skeleton video, and 3D motion simulation with muscle
  overlay

### 5.4 Out of scope

- Multi-person analysis, multi-camera capture, real-time streaming
- The timed screening tests and walking tasks
- Muscle force and activation
- Upper-limb and spinal assessment
- Any autonomous clinical decision

---

## 6. Methodology

### 6.1 Approach

The system follows a fixed chain: video in, sampled frames, 2D joint detection per frame, subject
selection, 3D lifting, scaling to real-world units, angle computation, metric derivation, quality
grading, and result assembly. [02-pipeline.md](02-pipeline.md) documents each stage in detail.

Four methodological choices define the project and are justified below.

### 6.2 Markerless pose estimation

Joints are located using **RTMPose** with the **Halpe26** keypoint set, which includes the foot points
needed for ankle tasks. Markerless estimation is what makes home assessment possible at all — the
alternative, marker-based motion capture, requires a laboratory.

The cost is accuracy. Published validation of markerless systems reports joint-angle errors in the
range of roughly 7 to 15 degrees against laboratory reference, varying by joint and camera view. This
is the single most important limitation of the entire project and is treated in detail in
[07-evaluation-and-limitations.md](07-evaluation-and-limitations.md). It is the reason for the
`estimated_` naming convention and for the quality guard.

### 6.3 3D-first, with 2D as the validated path today

**Target architecture: 3D.** A 2D angle is only correct when the movement plane is perpendicular to
the camera. A patient at home will not aim their phone perfectly, and a 2D system silently reports a
foreshortened angle as if it were real. Reconstructing 3D joint positions removes that dependency on
camera placement, which is the single biggest source of uncontrolled error in home recording. It is
also what makes the 3D motion simulation possible.

**Reality today: 2D sagittal is the path that runs.** Honesty requires stating four things:

1. Two-dimensional measurement of planar movement is the *established clinical method*, not a
   degraded approximation. A goniometer is a 2D instrument, and validation studies of video-based ROM
   measure sagittal angles from side-on recordings.
2. Monocular 3D lifting infers depth from a single viewpoint, which is mathematically ambiguous. The
   model used was trained on healthy adults performing everyday actions, not on elderly patients with
   pathological movement, so its accuracy on the target population is unverified.
3. In current testing the 3D reconstruction is frequently rejected by its own consistency check, and
   the system falls back to the 2D result.
4. Ankle tasks are 2D permanently with the current lifter, for the skeleton reason given in Section
   5.2.

The system therefore attempts 3D, falls back to 2D whenever 3D cannot be trusted, and always reports
which path produced the result. Bone-length scaling and constrained refinement — now prototype-phase
work (Section 1.5) — exist specifically to make the 3D path dependable enough to lead
with. Until it is, **the 3D output is the least-validated component of the system** and is documented
as such.

### 6.4 Patient-specific bone lengths for metric scale — postponed to the prototype phase

> **Status (2026-08-07):** postponed. For the proof of concept, the **ChArUco board** remains the
> camera-calibration and metric-scale source — it is built and working. Bone-length scaling below is
> the **prototype-phase design**, kept here with its reasoning for the next proposal.

A 3D reconstruction from a single camera has no inherent size — a small person close to the lens and
a large person far away produce identical images. Converting to millimetres requires an external
reference.

The chosen reference is a **hospital-measured bone length** (femur and tibia, per side), entered once
by the patient. Dividing the known length in millimetres by the reconstructed length in arbitrary
units yields the scale factor. Manual entry is the primary route; importing the lengths from medical
imaging such as MRI, where a scan already exists, was raised by the advisor and sits in the backlog
in [04-planning.md](04-planning.md).

In the prototype phase this will replace the printed calibration board. The reasons:

- **No burden on the patient.** No printing, no separate calibration recording, no resolution
  matching, no device registry.
- **Fewer failure modes.** The board approach required a long chain of conditions to all hold, and
  its failure was the dominant cause of falling back to a non-metric result.
- **A useful side effect.** Known, constant bone lengths also *constrain* the 3D reconstruction across
  frames, directly reducing the depth ambiguity described in Section 6.3.

Lengths are recorded **per side**, because a single shared value would erase leg-length discrepancy —
itself a genuine clinical finding. A known caveat: hospital measurements use anatomical landmarks
while the model uses joint centres, so a systematic offset of a few percent is expected. The
mitigation is to use bone length only as a *ratio* for scaling, and never to report absolute segment
lengths back to a clinician as measurements.

### 6.5 Quality guard before results

A markerless system fails in ways that produce confident-looking but wrong numbers: the patient walks
out of frame, a limb is occluded, lighting is poor, or a bystander is tracked instead of the patient.

The system therefore grades every recording and **refuses to report metrics** when quality falls below
a defined floor, returning an explicit rejection with a reason instead. A clinician reading a result
must be able to assume that a returned number was measurable. This is the one place where the system
deliberately fails a request rather than degrading gracefully.

---

## 7. Application architecture

### 7.1 Deployment posture

The application runs **on a local machine**. The current target is a **standalone localhost
application**: a local service with a browser interface served from the same computer, with no cloud
dependency and no patient video leaving the device.

The response format is nevertheless kept **integration-ready**, so that a web backend or a clinician
portal can be added later without redesigning the analysis core. This matters because remote access
is a plausible future requirement — a doctor may want to review results without sitting at the
machine that produced them — and that would introduce storage and privacy obligations that the local
version avoids. The architecture keeps that door open without walking through it now.

### 7.2 Layered structure

```
┌─────────────────────────────────────────────────────────┐
│  Presentation — local browser interface                 │
│  upload, progress, results, graph, video, 3D simulation │
├─────────────────────────────────────────────────────────┤
│  Service — local HTTP API                               │
│  request validation, orchestration, error mapping       │
├─────────────────────────────────────────────────────────┤
│  Analysis — the measurement core                        │
│  pose estimation · 3D lifting · scaling · kinematics    │
│  velocity · smoothness · screening · quality grading    │
├─────────────────────────────────────────────────────────┤
│  Foundation                                             │
│  video decoding · model loading · configuration         │
└─────────────────────────────────────────────────────────┘
```

Two rules govern the layering. Analysis code never imports service or presentation code, so the
measurement core stays independently testable. Optional capabilities — 3D lifting, scaling, the
muscle overlay — are isolated behind guards, so that any failure degrades the result rather than
failing the whole request.

### 7.3 Technology

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | Python 3.11 or newer (3.13 in use) | Ecosystem for vision and numerical work |
| API framework | FastAPI | Typed request and response models, automatic validation |
| Pose estimation | RTMPose (Halpe26) via rtmlib | Accuracy and speed balance; includes foot keypoints |
| 3D lifting | MotionBERT (ONNX) | Sequence-aware monocular lifting |
| Inference runtime | ONNX Runtime | Runs on CPU; uses GPU when available |
| Video and geometry | OpenCV, NumPy, SciPy | Decoding, camera geometry, numerical routines |
| Interface | Static HTML, CSS, JavaScript with Three.js | No build toolchain; keeps the local application simple |
| Testing | pytest | Full-suite regression on the analysis core |

The interface deliberately avoids a JavaScript framework and build step. The team's strength is the
analysis, and a plain static page keeps the local application maintainable.

### 7.4 Data handling

**During a single assessment.** The uploaded video is written to a temporary folder, analysed, and
deleted as soon as the request finishes. Nothing is transmitted off the machine.

**For monitoring over time**, the session's *metrics* must be kept — never the video.
**Decision (2026-08-07): local files, plus export and re-import.** Each session is a small folder of
human-readable JSON on the local disk, trivial to back up, copy, or delete; export and re-import let
a result move between machines as a file. A database (SQLite) was considered and **cancelled**: it
earns its keep at hundreds of sessions, and a proof of concept never gets there. A cloud portal for
remote review stays deliberately possible for later.

**Patient identity.** Sessions are keyed by a patient identifier supplied by the clinician. The
application does not need names, addresses, or any other identifying detail, and should not collect
them.

### 7.5 Comparing across recordings

Limb symmetry (left leg against right) and progress over time (today against an earlier visit) each
need two recordings, so neither can come from analysing a single one. They are asked for separately:

1. Submit the **left** knee flexion recording. It is analysed, returned, and stored. No symmetry.
2. Submit the **right** knee flexion recording. Analysed, returned, and stored. Still no symmetry.
3. Ask the comparison endpoint — *symmetry for knee flexion, patient PT-001* — and it returns the
   index, or states what is missing.

By default the comparison uses the most recent recording of each side. A clinician may instead name
two specific sessions, which covers comparing against a chosen earlier visit and choosing between
several attempts at the same task.

Analysis therefore stays a pure measurement step, and comparison is an ordinary lookup over stored
results. The same mechanism answers progress over time, using an earlier session as the counterpart
instead of the opposite leg.

**Comparability guard.** Two recordings are compared only when the task and camera view match and
both pass the quality floor. Otherwise the endpoint reports *not comparable* with the reason rather
than a number, because a figure from mismatched recordings looks just as authoritative as a valid one.

The analysis request states which leg the patient was told to move (`side`, mandatory), which is what
makes pairing possible — and lets the system flag a recording where the declared leg is not the one
that actually moved.

---

## 8. Design principles

1. **Honest labelling.** Any quantity the camera infers is named as an estimate. The system never
   presents an estimate with the authority of a measurement.
2. **Best-effort, never break.** Optional capabilities degrade to the simpler result rather than
   failing the request. The sole exception is the quality guard, which rejects deliberately.
3. **Additive evolution.** New output fields are added; the established structure is not reshaped
   without coordination.
4. **Testable core.** Measurement logic is verified against known-answer cases independently of
   video, models, or the network.
5. **Decision support, not diagnosis.** Stated in the specification, enforced in the output.
