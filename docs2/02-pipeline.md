# 02 — Pipeline

> How the system works, from two angles: what a **person** does in the real world, and what the
> **software** does with the resulting video.
> Terms are defined in [00-glossary.md](00-glossary.md). The reasoning behind these choices is in
> [01-specification.md](01-specification.md).

**Status markers.** Not every stage described here is built yet. Built stages are marked ✅ and
planned stages ⚠️, with delivery scheduled in [04-planning.md](04-planning.md).

---

# Part A — The real-world workflow

## A1. One-time setup, per patient

Done once when a patient joins the programme, not before every recording.

| Step | What happens | Why |
|------|--------------|-----|
| Record patient ID | The clinician assigns an identifier such as `PT-001` | Links recordings to the same person over time. No name or address is needed |
| Measure bone lengths ⚠️ | Femur and tibia are measured at the hospital, **for each leg separately** | Converts the 3D reconstruction to real millimetres. Per side, because leg length can genuinely differ |

## A2. Preparing to record

| Step | Guidance |
|------|----------|
| Choose the task | One of the six movements, and **which leg** performs it |
| Camera position | Roughly hip height, level, filming the patient **from the side** |
| Distance | The whole body stays inside the frame for the entire movement |
| Background | Plain and uncluttered, so no bystander is mistaken for the patient |
| Lighting | Even and bright. Avoid a bright window behind the patient |
| Clothing | The knee and ankle should be visible. Long loose trousers hide the joints being measured |
| Stability | The phone rests on something solid. Handheld footage shakes the whole reconstruction |

## A3. Recording one task

1. Start recording.
2. The patient stands still in a **neutral position for 2 to 3 seconds** ⚠️ — this gives a personal
   zero-degree reference, and is far easier for an elderly patient than a full calibration pose.
3. The patient performs the movement **slowly**, three to five times.
4. Stop recording. A few seconds is enough; longer clips do not improve the result.

## A4. Submitting

The clinician/patient's caretaker submits the video together with the patient ID, the task, **which leg** was moved, and
the camera view. The system analyses it and returns the result for that one recording.

## A5. Reading the result

Read it in this order — the first item can invalidate everything after it.

1. **Quality grade.** If the recording was rejected, nothing else matters. Re-record following A2.
2. **The annotated video.** Confirm the skeleton actually follows the patient. If it jumps to another
   person or drifts off the body, the numbers describe the wrong thing.
3. **Analysis mode.** Whether the result came from the 3D or the 2D path.
4. **The numbers.** ROM, speed, smoothness.
5. **The graph.** The angle through time shows *how* the movement happened — hesitation, tremor, or
   an early stop that a single ROM number hides.
6. **The motion simulation.** An optional 3D replay with the muscle overlay, for visual inspection.

## A6. Getting symmetry and progress

These need two recordings, so they are requested separately.

**For left-versus-right symmetry:** record the same task on the other leg, then ask for symmetry.

**For progress over time:** record the same task and side at the next visit, then ask for progress.

Both default to the most recent recordings. A clinician can instead choose two specific sessions.

---

# Part B — The data pipeline

What the software does with one submitted video.

```
video in
   │
   ├─ 1. validate + decode
   ├─ 2. sample frames
   ├─ 3. detect 2D pose per frame
   ├─ 4. select the patient
   ├─ 5. assemble the pose sequence
   │
   ├─ 6. lift to 3D                ◀── the main path
   ├─ 7. apply metric scale
   │
   ├─ 8. compute joint angles (both legs)
   ├─ 9. smooth the angle series
   ├─ 10. derive metrics
   ├─ 11. grade quality  ──▶ reject if too poor
   ├─ 12. screen against task thresholds
   ├─ 13. build outputs
   └─ 14. store the result
                                          result out
```

## Stage 1 — Validate and decode ✅

The request is checked for a known task, a valid view, a declared side, and a readable video. The
video is decoded and its duration, resolution, and frame rate are read. An unreadable file is
rejected here, before any analysis begins.

## Stage 2 — Sample frames ✅

Frames are taken at a fixed rate rather than every frame. A typical phone records 30 or 60 frames per
second, far more than joint movement requires. Sampling keeps processing time reasonable without
losing the movement.

## Stage 3 — Detect the 2D pose ✅

Each sampled frame goes through RTMPose, which returns the Halpe26 keypoints and a confidence score
for each one. Frames where nobody is detected are recorded as gaps.

## Stage 4 — Select the patient ✅

If several people appear, one must be chosen. The most confidently detected person is treated as the
patient. This is why A2 asks for a clear background — a well-lit bystander can be picked instead.

## Stage 5 — Assemble the pose sequence ✅

The per-frame poses are collected into one whole-clip sequence. This matters because the later stages
need to see the *movement*, not isolated pictures: 3D lifting reads a window of frames at once, and
smoothness cannot be computed from a single frame.

## Stage 6 — Lift to 3D ✅ (main path)

The 2D sequence is converted to the H36M-17 skeleton and passed to MotionBERT, which returns 3D joint
positions for every frame.

A **consistency check** then examines the result. Bones cannot change length during a movement, so if
the reconstructed femur or tibia varies significantly from frame to frame, the reconstruction is
wrong and is discarded. This check is what currently rejects many real recordings, sending them to
the 2D path described in Part C.

**Bone-length constrained refinement** ⚠️ will use the patient's known bone lengths to correct the
reconstruction rather than only judge it, which is expected to make this stage far more reliable.

## Stage 7 — Apply metric scale ⚠️

The 3D reconstruction has correct shape but arbitrary size. Dividing the patient's known bone length
in millimetres by the same bone's reconstructed length gives the conversion factor to real units.

Joint **angles do not need this** — an angle is the same whatever the scale. Scale matters for
distances, so a recording without bone lengths still produces valid angles and ROM.

## Stage 8 — Compute joint angles, both legs ✅

For every frame, the angle at the measured joint is computed from three points: the joint itself and
one point on each adjoining segment. Knee flexion, for example, uses hip, knee, and ankle.

**Both legs are always analysed, even though only one was instructed to move.** Two reasons:

- Comparing an affected leg against the patient's *own* healthy leg is standard clinical practice,
  and a patient's own opposite limb is a better reference than any population average.
- It provides a free validity check. The declared side should be the leg that actually moved. If it
  is not, the recording is probably mislabelled or the patient moved the wrong leg, and it is flagged.

Ankle tasks are computed in 2D, because the 3D skeleton has no toe joint. See
[01-specification.md](01-specification.md) section 5.2.

## Stage 9 — Smooth the angle series ✅

Small frame-to-frame detection errors make the raw angle series jitter. A smoothing filter reduces
this. The filter looks only at past frames, so it introduces a slight lag — acceptable for measuring
how far a joint moved, but worth knowing when reading exactly *when* a peak occurred.

## Stage 10 — Derive metrics ✅ / ⚠️

From the smoothed angle series:

| Metric | How it is obtained | Status |
|--------|--------------------|--------|
| Maximum and minimum angle | The largest and smallest values in the series | ✅ |
| ROM | Maximum minus minimum | ✅ |
| Angular velocity and acceleration | Rate of change of the angle, and of that rate | ⚠️ |
| Smoothness (LDLJ, SPARC, movement units) | Computed from the velocity and jerk of the series | ✅ |
| Angle trajectory | The full per-frame series, kept for the graph rather than discarded | ⚠️ |

## Stage 11 — Grade quality, and reject if too poor ✅ / ⚠️

Recording quality is scored from the proportion of usable frames, the average keypoint confidence,
and how steadily the skeleton was tracked ⚠️.

If quality falls below the floor, the system **rejects the recording** and returns the reason instead
of metrics ⚠️. This is the one place the system deliberately refuses rather than degrading, because a
plausible-looking number from an unusable video is more dangerous than no number.

## Stage 12 — Screen against task thresholds ✅

The measured ROM is compared against the expected and borderline values for that task, producing a
risk level, a confidence score, and any flags. These thresholds are per-task reference values, not a
diagnosis.

## Stage 13 — Build the outputs ✅ / ⚠️

| Output | Contents | Status |
|--------|----------|--------|
| Result data | Metrics, quality grade, screening outcome, analysis mode | ✅ |
| Annotated video | The original clip with the detected skeleton drawn on it | ✅ |
| Angle graph | The angle trajectory, for plotting | ⚠️ |
| Motion simulation | 3D joint positions plus the muscle overlay | ✅ |

## Stage 14 — Store the result ⚠️

The metrics are saved — patient, task, side, date, ROM, speed, smoothness, quality. **Only numbers
are stored, never the video.** This record is what later makes symmetry and progress possible.

---

# Part C — The 2D fallback path

3D is the target because a 2D angle is only correct when the movement plane faces the camera
squarely, and a patient at home will not aim their phone perfectly. But 3D is not always available.

**The system falls back to 2D when:** the 3D consistency check rejects the reconstruction, the 3D
model is unavailable, or the task is an ankle task, which has no 3D representation.

On the 2D path, angles are computed directly from the image coordinates. Everything downstream —
smoothing, ROM, smoothness, screening — is unchanged. What is lost is view-independence and any
measurement in millimetres.

**The result always reports which path produced it**, so a reader never has to guess. Note that 2D
sagittal measurement is the established clinical method for planar movement, so a 2D result is not
worthless — it is simply more sensitive to camera placement. The honest accuracy comparison is in
[07-evaluation-and-limitations.md](07-evaluation-and-limitations.md).

---

# Part D — What happens when something fails

The system degrades rather than crashing, with one deliberate exception.

| Problem | What the system does |
|---------|---------------------|
| Video unreadable | Rejects the request with an error |
| Unknown task or missing side | Rejects the request with an error |
| Nobody detected in most frames | **Rejects the recording** on quality grounds ⚠️ |
| Confidence too low | **Rejects the recording** on quality grounds ⚠️ |
| Wrong person tracked | Cannot be detected automatically — the annotated video is how a human catches it |
| 3D reconstruction inconsistent | Falls back to 2D, reports the mode and reason |
| 3D model missing | Falls back to 2D |
| Bone lengths not provided | Angles and ROM still valid; distances in millimetres unavailable |
| Ankle task | Uses 2D by design |
| Declared side did not move most | Result returned with a flag |

---

# Part E — The comparison pipeline

Symmetry and progress are separate queries over stored results, not part of analysing a recording.
Analysis is a measurement; comparison is a question.

```
ask: symmetry for knee flexion, PT-001
   │
   ├─ find the stored left and right recordings
   ├─ check comparability
   └─ compute and return   ─or─   report what is missing
```

**Symmetry** takes the ROM of the instructed leg from a left recording and from a right recording,
and reports the difference as a percentage of their average.

**Progress** takes the same task and side from two different dates and reports the change, judged
against the MCID threshold — the smallest difference that is clinically meaningful rather than noise.

**Both refuse to answer when the recordings are not comparable:** different task, different view, or
either recording below the quality floor. A number built from mismatched recordings looks exactly as
authoritative as a valid one, which is what makes it dangerous.

By default the most recent recording of each side or date is used; a clinician may name two specific
sessions instead.

---

## Related documents

| Document | Purpose |
|----------|---------|
| [00-glossary.md](00-glossary.md) | Definitions of every term used |
| [01-specification.md](01-specification.md) | What the project is and why |
| **02-pipeline.md** | *This document* |
| [03-api-contract.md](03-api-contract.md) | Request and response formats |
| [04-planning.md](04-planning.md) | Phases, tasks, risk, effort, benefit |
| [05-user-manual.md](05-user-manual.md) | How to perform, record, and interpret each task |
| [06-setup.md](06-setup.md) | Installation and running the application |
| [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) | Accuracy, validation, and honest limits |
| [08-spec-alignment.md](08-spec-alignment.md) | Status against the advisor's specification |
