# 09 — Calibration Board Protocol (optional, legacy)

> ⚠️ **Optional and being superseded.** This describes the ChArUco board path, which is how metric
> scale works *today*. Per [01-specification.md](01-specification.md) section 6.4, hospital-measured
> **bone lengths** replace the board as the scale source in P2 of
> [04-planning.md](04-planning.md), after which the board is needed only for the floor plane and the
> camera-to-floor transform. Most users will never need this document.
>
> Joint angles, ROM, smoothness, and screening are **scale-invariant** and never require the board.
> Follow this only when you specifically need distances in millimetres before P2 lands.

How to take a device from "uncalibrated" to producing metric 3D output, and how
to record a patient clip so the metric-3D path actually engages. This is the
operator-facing companion to the code in `app/services/calibration/` and the
CLIs in `app/tools/`.

> Metric 3D (`joint_angles_3d`, `scale_mm_per_unit`, `transformation_matrix_6dof`)
> only appears when **(a)** the recording device has a `valid` intrinsics record
> **and (b)** a calibrated ChArUco board is visible in the clip **and (c)** the
> task has a 3D-defined angle (hip/knee; ankle stays 2D). Miss any one and the
> service degrades to the 2D result — check `analysis_mode` and `guard_warnings`
> in the response to see which.

## 1. Print the board

```powershell
uv run python -m app.tools.generate_board --out board_a4.svg --pdf board_a4.pdf --png board_preview.png
```

- **Preferred: print `board_a4.pdf`.** Open it in any PDF viewer and print on
  **A4 with "Actual size" / 100%** (not "Fit to page"). The PDF is an A4 page
  sized in points with the board embedded at true physical size, so it reproduces
  correctly across viewers/printers with the least guesswork. `--pdf` is
  optional — omit it if you only want the SVG.
- Alternatively, open `board_a4.svg` in a browser and print it on **A4 at 100%
  scale** — turn off "fit to page" / "shrink to fit". The SVG is sized in
  millimetres, so 100% reproduces true size.
- The default board is **175 × 250 mm** (7 × 10 squares, 25 mm each,
  `DICT_5X5_100`). It fits A4 with room below for the reference bar.
- **Mount it flat and rigid** — glue or tape to stiff card. Any curl or wrinkle
  biases the recovered plane. Matte paper; avoid glossy stock (glare hides
  markers).

## 2. Print-verify (correct for printer scaling)

Even at "100%", printers drift. After printing, measure the drawn **100 mm
reference bar** with a ruler and note the value (e.g. `99` mm). You pass it to
the next step; `app/services/calibration/print_verify.py` turns it into a
`print_scale_factor` that corrects every downstream length. A deviation over
10% is rejected as a fit-to-page mistake rather than tolerance — reprint.

## 3. Calibrate the device (once per phone + resolution)

Record a short clip of the printed board held at **several angles and
distances** — tilt it left/right/up/down, fill different parts of the frame,
keep it in focus. 10–20 varied views is plenty.

**Use the exact camera mode you will record patients with** (same resolution and
orientation). Intrinsics are tied to resolution, and the device id is keyed on
it — a different mode is treated as a different, uncalibrated device.

```powershell
uv run python -m app.tools.calibrate_device `
  --video calib.mp4 --make Apple --model "iPhone 13" --measured-bar-mm 99
```

- Passing `--make`/`--model` makes the device id stable. Without them the id
  falls back to resolution only and two phones at the same resolution collide
  (the tool warns).
- Success prints the reproj RMS (aim for **< 1 px**) and writes the record to
  `CALIBRATION_DATA_DIR` (default `data/calibration/`, gitignored).
- `--images "shots/*.jpg"` works instead of `--video` if you shot stills.

> **Disable EIS / optical stabilisation and any digital zoom** before both
> calibration and patient recording. They silently change the effective focal
> length; the per-session guard flags this as `high session reproj … (EIS/zoom?)`
> but it is better avoided than detected.

## 4. Record the patient clip

- Place the board **flat on the floor, coplanar with the patient**, fully in
  frame, not occluded during the movement.
- Camera on a tripod, **lateral (sagittal) view** for hip/knee flexion, patient
  filling the frame, even lighting, contrasting clothing.
- Same device/resolution/orientation as calibration, EIS/zoom off.
- Keep the board still — it defines the floor frame for the whole clip.

## 5. Run and confirm 3D engaged

Set `ENABLE_3D=true` and `MOTIONBERT_MODEL_PATH` (see the README "3D lifting"
section), start the service, and submit the clip through the demo UI. Confirm:

- `analysis_mode == "3d"` in the response (not `"2d"`).
- `board_diagnostics.recommendation == "ok"` and no blocking `guard_warnings`.
- `joint_angles_3d` populated and `scale_source` set.

If it stayed 2D, `guard_warnings` and `board_diagnostics.likely_causes` say why
(board not detected, device not calibrated, high reproj, guard-rejected lift).

## Validating accuracy (needs ground truth — not yet available)

The steps above prove the pipeline *engages* on a real board. Proving it is
*accurate* additionally needs a reference: measure hip/knee ROM with a
goniometer during the same clip and compare against `joint_angles_3d`, and check
`scale_mm_per_unit` against a known length. Target the ~6° clinical-acceptability
band from `docs2/07-evaluation-and-limitations.md`. Record the first real board clip + its
reference as the first non-synthetic fixture when hardware is available.
