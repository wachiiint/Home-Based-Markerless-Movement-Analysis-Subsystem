# 02 — Project Overview

## What this service is

A local **FastAPI** service for **2D markerless movement analysis** using **RTMPose**. It takes an
uploaded video of a patient performing a leg movement and returns a JSON assessment (joint angles,
range of motion, pose quality, and a risk screening result).

It is designed as a drop-in replacement for an existing MediaPipe-based analysis service, so it
returns the **same JSON contract** the main backend already expects.

> **Version 1 is a local decision-support / demo service. It is not a clinical diagnosis system.**

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
| **ChArUco board** | A printed calibration pattern. When visible in the video, it lets the service recover real-world scale for 3D. |

---

**Next:** [03-pipeline.md](03-pipeline.md) — a detailed walkthrough of how the
data flows from raw pixels to a risk level.
