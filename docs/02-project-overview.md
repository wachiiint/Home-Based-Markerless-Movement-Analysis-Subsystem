# 02 — Project Overview

## What this service is

A local **FastAPI** service for **markerless movement analysis** using **RTMPose**. It takes an
uploaded video of a patient performing a leg movement and returns a JSON assessment (joint angles,
range of motion, smoothness, left/right symmetry, pose quality, and a risk screening result). 2D
analysis always runs; single-camera **3D** lifting is optional and best-effort on top of it.

It is designed as a drop-in replacement for an existing MediaPipe-based analysis service, so it
returns the **same JSON contract** the main backend already expects.

> **This is a local decision-support / demo service. It is not a clinical diagnosis system.**

---

## Vision / north star (beyond v1)

The screening numbers are the foundation, but the intended *differentiators* — what makes this
project valuable to a doctor — are visual and longitudinal:

1. **3D movement viewer (Three.js).** Let a doctor *see* the patient's movement pattern in 3D, not
   just read angle numbers. Built: the demo viewer, display-only.
2. **Muscle overlay.** Show which muscles lengthen and shorten during the movement, connecting *how
   the patient moves* to *the underlying muscle*. Built as a kinematic length proxy (display only);
   see [03-pipeline.md](03-pipeline.md) §4.5 for what it does and does not claim.
3. **Before/after comparison for the same patient.** Compare two sessions to visualise rehabilitation
   progress. **Planned** — stateless (the backend passes the baseline in the request; this service
   stores nothing). See [08-scope-v2.md](08-scope-v2.md) work item F.

Scope note: CT-derived muscle data is **permanently out of scope** for a single-camera setup — see
[08-scope-v2.md](08-scope-v2.md), which is the current roadmap and supersedes older plans.

---

## Where it fits in the bigger system

This service is **one microservice**. It never talks to the patient directly — the main backend
calls it server-to-server.

```
Patient (frontend) ──upload video──▶ Main backend
                                        │  (stores the session, calls this service via MEDIAPIPE_SERVICE_URL)
                                        ▼
                          RTMPose Movement Analysis Service  ◀── (this repo)
                                        │  (returns assessment JSON)
                                        ▼
                                     Backend stores the result
                                        ▼
                                 Doctor dashboard (reads risk_level, ROM, quality)
```

---

## The end-to-end flow

1. A patient uploads a movement video in the frontend.
2. The backend receives the session and calls this service through `MEDIAPIPE_SERVICE_URL`.
3. This service validates the internal API key, reads the multipart video, analyzes the movement,
   and returns the fixed assessment contract.
4. The backend stores the result and moves the session toward doctor review.
5. The doctor dashboard reads `risk_level`, `confidence_score`, pose quality, and the task metrics.

---

## Key terms (glossary)

| Term | Meaning |
|------|---------|
| **Pose estimation** | Finding body-joint (keypoint) locations in an image. Here, RTMPose does this per video frame. |
| **Keypoints** | The detected joint positions (e.g. hip, knee, ankle). This service uses the 26-point "Halpe26" set. |
| **ROM (Range of Motion)** | How far a joint moves — the difference between its maximum and minimum angle across the video. |
| **Screening** | Turning the measured angles + pose quality into a `risk_level` (low / moderate / high) with a confidence score. |
| **3D lifting** | Optionally estimating a 3D pose from the 2D pose (via the MotionBERT model). Off by default, best-effort. |
| **ChArUco board** | A printed calibration pattern. **Optional.** When visible, it gives the floor plane and the camera→floor 6DoF transform (and today, metric scale). It does not feed the 3D lift. |
| **Metric scale** | Converting the lift's arbitrary units to millimetres. Today: back-projected feet on the floor, with entered height as fallback. Planned (see [08-scope-v2.md](08-scope-v2.md) work item A): hospital-measured bone lengths, which removes the board from the scale path. |

---

**Next:** [03-pipeline.md](03-pipeline.md) — a detailed walkthrough of how the
data flows from raw pixels to a risk level.
