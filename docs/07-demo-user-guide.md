# Demo User Guide

A step-by-step guide to the browser demo. If you only read one thing, read the next section — it
answers "which video do I upload?".

---

| Video | Where you upload it | Required? | What it is |
|-------|--------------------|-----------|------------|
| **Movement video** | Panel **01 / INPUT** ("Choose a video file") | **Always** | The patient performing the exercise (e.g. a knee bend), filmed from the side. |
| **Calibration video** | Panel **00 / CALIBRATION** ("Choose board video") | **Optional** | A short clip of the printed ChArUco **board** — a checkerboard sheet — held at different angles. Contains **no patient**. It only unlocks millimetre-accurate 3D. |

> **If you are not sure: just upload the movement video in Panel 01 and press Analyze.**
> You do **not** need the calibration video to get angles, range-of-motion, screening, smoothness,
> left/right symmetry, the annotated skeleton video, or the 3D skeleton + muscle overlay. Calibration
> only adds real-world **millimetre** measurements, and it is an advanced, one-time-per-camera step.

---

## Quick start (the common case — no calibration)

1. **Start the server** (see [Getting Started](01-getting-started.md)):
   ```powershell
   uv run python -m app
   ```
   Open **http://127.0.0.1:8000/**.

2. Go to **Panel 01 / INPUT** and fill in:
   - **Patient ID** — any label (default `PT-001`).
   - **Movement task** — the exercise in the clip (e.g. *Knee flexion*). This tells the system which
     joint to measure, so pick the one that matches the video.
   - **Camera view** — **Lateral** (filmed from the side) for knee/hip flexion & extension; Frontal
     only if you filmed head-on.
   - **Calibrated device** — leave on **"Auto — 2D / uncalibrated"** unless you have calibrated (see
     below).

3. **Choose a video file** — your movement clip. A preview appears; check it's the right clip.

4. Press **Analyze movement**. First real run may take a little while (it downloads the pose model
   once, then caches it).

5. Read the results in **Panel 02** (annotated skeleton video), **Panel 03** (metrics), and
   **Panel 04** (3D). See [Reading the results](#reading-the-results).

That's it. Everything except millimetre 3D works from this one upload.

---

## What you get without calibration

- **Panel 02 — Skeleton overlay:** your video with the detected skeleton drawn on it, plus a download link.
- **Panel 03 — Movement summary:**
  - **Screening risk** (low / moderate / high) — driven by the **worse** leg, with side-tagged flags.
  - **Confidence** and **Valid frame ratio** — how trustworthy the tracking was.
  - **Sides analyzed** — usually `both`.
  - A **Left vs Right table** of joint angles and range-of-motion for **both legs**, plus smoothness
    and a left/right asymmetry index (when both legs actually moved).
- **Panel 04 — 3D skeleton:** a reconstructed 3D pose you can rotate (drag) and scrub through. Turn on
  **"Muscles"** to see the kinematic muscle-length overlay (see [Panel 04](#panel-04--3d-skeleton--muscles)).
  Without calibration this 3D view is **shape-only** — correct proportions, but *not* measured in millimetres.

---

## Optional: unlock millimetre 3D (calibration)

Do this only if you need **real-world distances** (millimetres) and metric 3D joint angles. It is a
**one-time setup per camera + video resolution**, done with the calibration video in Panel 00.

### What calibration adds
- Metric scale (`mm per unit`), millimetre-accurate 3D joint angles, and the camera→floor transform.
- Joint *angles* are already trustworthy without it (angles don't depend on scale) — calibration is
  about **distances**, not angles.

> Coming later: a planned **bone-length** input (a hospital-measured femur/tibia length typed into the
> form) will give metric scale with no board and no printing at all — see
> [08-scope-v2.md](08-scope-v2.md) work item A. The board route below is what works today.

### One-time setup

1. **Print the board.** Generate and print the ChArUco A4 sheet — see
   [CALIBRATION_CAPTURE.md](CALIBRATION_CAPTURE.md). **Print at 100% (turn OFF "fit to page").**
2. **Measure the reference bar.** With a ruler, measure the printed 100 mm bar and note the actual
   value (e.g. 100, or 101 if the printer stretched it).
3. **Record the calibration video.** Film the printed board **held at several angles**, at the **same
   resolution as your patient clips** (1080p recommended — the board reads reliably at 1080p). No
   patient in this clip.
4. In **Panel 00 / CALIBRATION**, fill in:
   - **Camera make / model** (e.g. `Apple` / `iPhone 13`) — this lets the demo match your camera to
     the patient clip later. Use the same values every time for the same phone.
   - **Measured 100 mm bar** — the number you measured in step 2.
   - **Square size / ArUco marker size** — leave at the printed defaults (25 mm / 18 mm) unless your
     board differs.
   - **Choose board video** — your calibration clip. Press **Calibrate device**.
5. On success the device appears in the **"Calibrated device"** dropdown in Panel 01.

### Using it
- In **Panel 01**, pick your calibrated device from the **Calibrated device** dropdown.
- Upload a patient clip recorded at the **same resolution** as the calibration clip.
- Press Analyze. Panel 03 will show a green **"Metric 3D active"** notice and millimetre values.

> **Resolution must match.** The calibration is tied to the exact video resolution (e.g. 1080×1920).
> If your patient clip is a different resolution, the demo warns you *before* you analyze and falls
> back to 2D. Record (and calibrate) everything at the same resolution.

---

## Recording tips (for good results)

**Movement video:**
- One person in frame, whole body (or at least the whole exercising leg) visible the entire time.
- Film **side-on (lateral)** for knee/hip flexion & extension.
- Steady camera, good even lighting, plain background helps.
- Have the patient do the full movement slowly through its complete range.

**Calibration video (only if calibrating):**
- Print at 100%, no "fit to page".
- Hold the board flat and tilt it through several angles; keep it in focus.
- Same resolution as your patient clips; 1080p recommended.

---

## Reading the results

### Panel 03 — Movement summary
- **Screening risk** is a **decision-support** signal, not a diagnosis. It reflects the *worse* leg;
  flags are tagged by side (e.g. `right: rom_below_borderline`).
- The **Left / Right table** lets you compare the two legs directly. `ROM` (range of motion) is the
  headline number for each joint. `(3D)` rows appear only when metric 3D is active.
- **Asymmetry (L/R)** appears only when **both** legs actually performed the movement; single-leg
  clips leave it blank on purpose.
- The **notice bar** at the top of the panel tells you the analysis mode:
  - **green "Metric 3D active"** — calibrated 3D worked.
  - **amber "2D analysis — metric 3D unavailable: …"** — it ran in 2D and tells you why (e.g. no
    calibrated device, resolution mismatch, or the board wasn't found).

### Panel 04 — 3D skeleton & muscles
- **Drag** to rotate, **scroll** to zoom, **Play** or the slider to scrub through time.
- **Muscles** toggle: overlays a kinematic **muscle-length** proxy for the major lower-limb muscles
  (quadriceps, hamstrings, gastrocnemius, iliopsoas, gluteals), colored **contracted → stretched**.
  This is **geometry, not force** — a single camera can't measure muscle force. The legend says so.
- **Preview 3D (sample data)** button (top right): loads a synthetic walking skeleton with muscles so
  you can see the viewer and overlay **without uploading anything**. Handy for a first look.

---

## Troubleshooting

| You see… | Meaning / fix |
|----------|---------------|
| Amber warning under the device dropdown before analyzing | The selected calibrated device's resolution ≠ your clip's. Use a matching-resolution clip, or recalibrate at this resolution, or set the device to "Auto" for a 2D run. |
| Panel 03 notice: "metric 3D unavailable" | Analysis ran in 2D. The message says why (no calibrated device selected, resolution mismatch, or board not detected). 2D results are still valid. |
| "no usable pose found in video" | The person wasn't tracked — check framing, lighting, and that the exercising leg is visible. |
| Muscles toggle is missing in Panel 04 | 3D lifting is off or unavailable for this run. The overlay needs the 3D model enabled (`ENABLE_3D=true`); the 2D results are unaffected. |
| Occlusion / low valid-frame warnings | Parts of the body were hidden or blurry for too many frames — re-record with a clearer view. |

> This demo is a **local decision-support / testing tool. It is not a clinical diagnosis system.**
