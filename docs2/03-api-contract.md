# 03 — API Contract

> The exact requests and responses of the local service.
> Terms are defined in [00-glossary.md](00-glossary.md). What each stage does is in
> [02-pipeline.md](02-pipeline.md).

> **Status: a design, not yet the running API.** The `/api/v1/` contract in parts 1–7 was designed
> in this round and is ready for the **prototype phase** to implement. What actually runs today is
> `/api/movement/assess` plus the demo endpoints — part 8.1 lists them, and part 9 maps every
> difference between the running API and this design.

---

## 1. Principles

| Principle | Applied as |
|-----------|------------|
| **Versioned** | Every path begins `/api/v1/`. A breaking change becomes `v2`, never a silent edit |
| **Honest naming** | Any quantity the camera infers is prefixed `estimated_`. Measured or computed facts (frame counts, dates) are not |
| **Explicit status** | Every response says whether the assessment completed or was rejected. A caller never infers success from the presence of fields |
| **Measure and compare are separate** | Analysing a recording and comparing recordings are different endpoints |
| **Refuse rather than mislead** | Insufficient or mismatched data returns an explicit reason, never a plausible-looking number |
| **Integration-ready** | Plain HTTP and JSON, so a web backend can call this later without redesign |

**Units are in the field name.** `_deg`, `_mm`, `_sec`, `_percent`, `_deg_s`. No field carries an
ambiguous unit.

---

## 2. Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/assessments` | Analyse one recording |
| `GET` | `/api/v1/assessments/{session_id}` | Retrieve a stored result |
| `GET` | `/api/v1/assessments` | List sessions, filtered |
| `GET` | `/api/v1/comparisons/symmetry` | Left against right for one task |
| `GET` | `/api/v1/comparisons/progress` | Now against an earlier baseline |
| `PUT` | `/api/v1/patients/{patient_id}` | Record bone lengths |
| `GET` | `/api/v1/patients/{patient_id}` | Read patient record |
| `GET` | `/health` | Service and model status |

**Authentication.** All `/api/v1/` paths require the header `X-Service-Key`, matched against the
configured key. On a single local machine this is light protection, but it keeps the interface honest
for the day the service is reachable from elsewhere. `/health` is open.

---

## 3. Analyse a recording

### `POST /api/v1/assessments`

Multipart form upload.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | file | yes | The video |
| `patient_id` | string | yes | e.g. `PT-001` |
| `task_type` | enum | yes | `hip_flexion`, `hip_extension`, `knee_flexion`, `knee_extension`, `ankle_dorsiflexion`, `ankle_plantarflexion` |
| `side` | enum | yes | `left` or `right` — **which leg the patient was told to move** |
| `view` | enum | no | `lateral` (default) or `frontal` |
| `recorded_at` | ISO-8601 | no | When the video was filmed. Defaults to upload time |
| `notes` | string | no | Free text kept with the session |

`side` is mandatory (and already is on the running API). Without it, left and right recordings cannot
be paired for symmetry, and the system cannot check that the instructed leg is the one that moved.

### Response — completed

```json
{
  "session_id": "sess-20260724-a1b2c3",
  "assessment_status": "completed",
  "recorded_at": "2026-07-24T09:15:00+07:00",
  "patient_id": "PT-001",

  "recording": {
    "task_type": "knee_flexion",
    "side": "left",
    "view": "lateral",
    "duration_sec": 6.2,
    "source_fps": 30.0,
    "sampled_fps": 10,
    "processed_frames": 62
  },

  "analysis": {
    "mode": "3d",
    "fallback_reason": null,
    "scale_mm_per_unit": 2.41,
    "scale_source": "bone_length"
  },

  "metrics": {
    "left": {
      "estimated_knee_angle_max_deg": 177.4,
      "estimated_knee_angle_min_deg": 84.7,
      "estimated_knee_rom_deg": 92.7,
      "estimated_peak_angular_velocity_deg_s": 118.3,
      "estimated_peak_angular_acceleration_deg_s2": 402.1,
      "movement_smoothness": {
        "log_dimensionless_jerk": -10.12,
        "sparc": -1.63,
        "n_movement_units": 3
      }
    },
    "right": {
      "estimated_knee_angle_max_deg": 179.1,
      "estimated_knee_angle_min_deg": 171.2,
      "estimated_knee_rom_deg": 7.9,
      "estimated_peak_angular_velocity_deg_s": 9.4,
      "estimated_peak_angular_acceleration_deg_s2": 31.0,
      "movement_smoothness": null
    }
  },

  "trajectory": {
    "time_sec": [0.0, 0.1, 0.2],
    "left_angle_deg": [176.9, 174.2, 168.8],
    "right_angle_deg": [178.9, 179.0, 178.7]
  },

  "quality": {
    "confidence_score": 0.89,
    "breakdown": {
      "valid_frame_ratio": 1.0,
      "mean_keypoint_confidence": 0.78,
      "tracking_stability_score": 0.91
    },
    "occlusion_warning": false
  },

  "screening": {
    "risk_level": "low",
    "flags": []
  },

  "artifacts": {
    "annotated_video_url": "/api/v1/artifacts/sess-20260724-a1b2c3/video",
    "motion_simulation_url": "/api/v1/artifacts/sess-20260724-a1b2c3/motion",
    "expires_at": "2026-07-24T10:15:00+07:00"
  },

  "warnings": []
}
```

**Notes on the shape.**

- `metrics` is keyed by **side**, not by prefixed field names. `recording.side` says which leg was
  instructed; the other is the contralateral reference.
- `movement_smoothness` is `null` for a leg that did not move — smoothness of a stationary limb is
  meaningless, and reporting a number would invite misreading.
- `trajectory` carries the full per-frame series for the graph. Roughly 60 to 150 values per side.
  **Shipped today** on the current response, at the top level and in this shape:
  `{ "joint": "knee_flexion_deg", "time_sec": [...], "left_angle_deg": [...], "right_angle_deg": [...] }`.
  One entry per *sampled* frame, `null` where the leg was not confidently visible — the graph breaks
  there rather than bridging a gap that was never measured — and a whole side is `null` when that leg
  was never usable. The values are the smoothed ones that min/max/ROM were read from, so the graph
  and the summary numbers cannot disagree.
- `scale_source` is `bone_length`, `charuco_board`, or `null` when no scale was available. Angles
  remain valid with no scale.
- `warnings` holds non-fatal notes, such as `declared_side_did_not_move_most`.

### Response — rejected

Returned with HTTP `200`. The request was valid; the *recording* was not usable.

```json
{
  "session_id": "sess-20260724-d4e5f6",
  "assessment_status": "rejected",
  "rejection_reason": "valid_frame_ratio 0.41 below floor 0.70",
  "recorded_at": "2026-07-24T09:22:00+07:00",
  "patient_id": "PT-001",
  "recording": { "task_type": "knee_flexion", "side": "left", "view": "lateral" },
  "quality": {
    "confidence_score": 0.38,
    "breakdown": {
      "valid_frame_ratio": 0.41,
      "mean_keypoint_confidence": 0.52,
      "tracking_stability_score": 0.44
    }
  },
  "artifacts": {
    "annotated_video_url": "/api/v1/artifacts/sess-20260724-d4e5f6/video",
    "expires_at": "2026-07-24T10:22:00+07:00"
  }
}
```

No `metrics` block is present — deliberately, so a caller cannot read numbers from a rejected
recording. The **annotated video is still returned**, because seeing where tracking failed is how
someone fixes the next recording.

**Rejection thresholds:** `valid_frame_ratio < 0.70` or `mean_keypoint_confidence < 0.60`.

**Rejected sessions are stored** but never used as a comparison counterpart.

---

## 4. Retrieve and list

### `GET /api/v1/assessments/{session_id}`

Returns the stored session in the same shape as above. Artifacts may have expired; the metrics have
not.

### `GET /api/v1/assessments`

| Query | Notes |
|-------|-------|
| `patient_id` | Required |
| `task_type`, `side` | Optional filters |
| `from`, `to` | Optional ISO-8601 date range |
| `status` | `completed` (default) or `all` |

```json
{
  "patient_id": "PT-001",
  "count": 2,
  "sessions": [
    { "session_id": "sess-...c3", "recorded_at": "2026-07-24T09:15:00+07:00",
      "task_type": "knee_flexion", "side": "left",
      "assessment_status": "completed", "estimated_rom_deg": 92.7, "confidence_score": 0.89 }
  ]
}
```

---

## 5. Comparisons

Both endpoints answer a question about **stored** results. Neither accepts a video.

**Session selection.** By default the most recent qualifying session on each side or date is used.
A caller may name sessions explicitly with `session_a` and `session_b`, which is how a clinician
chooses between several attempts or compares against a particular visit.

**Comparability rules**, applied by both: same `task_type`, same `view`, both `completed`, both above
the confidence floor. Symmetry additionally requires the two recordings to fall within
`max_gap_days` (default 30) — two sides of the same assessment, not a left leg from today against a
right leg from six months ago.

### `GET /api/v1/comparisons/symmetry`

Query: `patient_id`, `task_type`, optional `session_a` / `session_b`, optional `max_gap_days`.

```json
{
  "status": "available",
  "task_type": "knee_flexion",
  "sessions": { "left": "sess-...c3", "right": "sess-...g7" },
  "estimated_symmetry_index_percent": 16.8,
  "threshold_percent": 10.0,
  "exceeds_threshold": true,
  "inputs": { "left_rom_deg": 92.7, "right_rom_deg": 78.4 }
}
```

Computed as `|left − right| / (0.5 × (left + right)) × 100`, using the ROM of the **instructed** leg
in each recording. Above 10 percent is a research-grade signal worth a clinician's attention, not a
diagnostic cut-off.

When it cannot be answered:

```json
{
  "status": "unavailable",
  "reason": "no completed right-side recording of knee_flexion for PT-001",
  "task_type": "knee_flexion",
  "sessions": { "left": "sess-...c3", "right": null }
}
```

`status` is `available`, `unavailable` (a side is missing), or `not_comparable` (both exist but fail
a comparability rule, with `reason` naming which).

### `GET /api/v1/comparisons/progress`

Query: `patient_id`, `task_type`, `side`, optional `session_a` / `session_b`.

```json
{
  "status": "available",
  "task_type": "knee_flexion",
  "side": "left",
  "sessions": { "baseline": "sess-...x1", "current": "sess-...c3" },
  "baseline_date": "2026-04-24",
  "current_date": "2026-07-24",
  "changes": {
    "estimated_knee_rom_deg": {
      "baseline": 78.0,
      "current": 92.7,
      "change": 14.7,
      "mcid_threshold": 5.0,
      "mcid_met": true
    }
  },
  "verdict": "meaningful_improvement"
}
```

`verdict` is `meaningful_improvement`, `meaningful_decline`, or `no_meaningful_change` — decided by
the MCID threshold, so ordinary measurement noise is never reported as progress.

---

### 5.1 What is built today — `GET /api/demo/compare`

The symmetry half of section 5 has shipped, browser-facing, ahead of the `/api/v1` contract. It reads
two stored sessions and reports the difference between the legs. Its page is `/compare`.

```
GET /api/demo/compare?left=<session_id>&right=<session_id>
```

Both ids are required, must differ, and must resolve to sessions whose response named an
`analyzed_side`. A missing session is `404`; a stored pair that is **not comparable** is `200` with
`comparable: false` and the blocking checks that say why — "these two cannot be compared, and here is
the reason" is the useful answer, and the page renders it.

```json
{
  "comparable": true,
  "left":  { "session_id": "rtmpose-…c3", "side": "left",  "task_type": "knee_flexion", "…": "…" },
  "right": { "session_id": "rtmpose-…g7", "side": "right", "task_type": "knee_flexion", "…": "…" },
  "days_apart": 2.0,
  "checks": [ { "code": "camera_setup_unverified", "severity": "warning", "message": "…" } ],
  "metrics": [
    { "key": "rom_deg", "label": "Knee ROM", "unit": "°",
      "left": 88.4, "right": 61.7, "difference": 26.7,
      "symmetry_angle_pct": 11.2, "larger_side": "left" }
  ]
}
```

**Each recording contributes only the leg it was instructed to move.** The contralateral numbers
inside a clip stay what they always were — a within-clip reference and a recording check — and never
become half of an asymmetry index. In a lateral view the far leg is occluded and foreshortened, so
pairing it against the near leg measures distance from the camera as much as it measures the patient.

Metrics compared: ROM (2D, and 3D when both runs produced it), peak and minimum joint angle, SPARC,
LDLJ, movement units. Every row carries `difference` (left minus right, in the metric's own unit).
`symmetry_angle_pct` is populated only for quantities where a ratio means something — ROM and movement
units. A joint angle is a position on an arbitrary axis and SPARC/LDLJ are negative by construction,
so those rows are `null` and report the plain difference alone.

`checks` are `blocking` or `warning`. Blocking — different patient, different task, different view,
two recordings of the same leg, an unrecognised task — produces **no metrics at all**. Everything
else warns: recorded further apart than `ASYMMETRY_MAX_DAYS_APART` (default 30), differing sample
rate or analysis mode, low tracking coverage, a leg that barely moved, a possible wrong side, heavy
tracking noise. One warning is always present — camera distance, height and angle are not recorded
anywhere, so the service cannot verify two clips were filmed the same way, and a silent pass must not
read as a verified one.

**Three deliberate differences from the `/api/v1` contract above:**

| `/api/v1/comparisons/symmetry` | `GET /api/demo/compare` |
|--------------------------------|--------------------------|
| Robinson index, `\|L−R\| / (0.5(L+R)) × 100` | **Zifchock symmetry angle**, bounded ±50%, signed toward the larger leg |
| `threshold_percent`, `exceeds_threshold` | **No threshold and no verdict** |
| Picks sessions itself from `patient_id` + `task_type` | Both session ids are given explicitly |

The index changed because the limb-symmetry framing assumes a sound reference limb, which unilateral
injury work supplies and a bilaterally declining population does not. The symmetry angle needs no
reference leg.

**What the page adds on top of the endpoint.** The `/compare` page also draws the angle graph — one
line per leg, each from its own recording, on a **shared axis but not a shared clock** (the caveat is
printed under the chart) — and the 3D viewer, which shows **one recording at a time** behind a
left/right selector, because overlaying two skeletons from two cameras would invite reading camera
differences as leg differences.

**No threshold is reported, deliberately.** Calling 10 percent abnormal requires knowing how far
apart two recordings of the *same* leg land; until the test-retest repeatability study reports
([04-planning.md](04-planning.md)), the endpoint states the difference and stops.

---

## 6. Patient record

### `PUT /api/v1/patients/{patient_id}`

```json
{
  "bone_lengths_mm": {
    "left":  { "femur": 421.0, "tibia": 358.0 },
    "right": { "femur": 419.5, "tibia": 357.0 }
  },
  "measured_at": "2026-07-01",
  "measured_by": "hospital"
}
```

Lengths are **per side** — a shared value would erase leg-length discrepancy, itself a clinical
finding. All four values are optional; whatever is present is used for scaling. Absent lengths mean
angles and ROM still work, but distances in millimetres do not.

Nothing identifying is stored. No name, no address, no date of birth.

---

## 7. Health and errors

### `GET /health`

```json
{ "status": "ok", "device": "cpu", "pose_model_loaded": true, "lifter_loaded": true, "version": "2.0.0" }
```

### Errors

Failures of the *request* are HTTP errors. Failures of the *recording* are `200` with
`assessment_status: "rejected"`.

| Code | When | Body |
|------|------|------|
| `400` | Unknown task, invalid side or view, missing required field | `{ "error": "invalid_task_type", "detail": "..." }` |
| `401` | Missing or wrong service key | `{ "error": "unauthorized" }` |
| `404` | Unknown session or patient | `{ "error": "not_found" }` |
| `413` | File above the size limit | `{ "error": "file_too_large" }` |
| `422` | File present but not decodable as video | `{ "error": "unreadable_video" }` |
| `500` | Unexpected failure | `{ "error": "internal_error" }` |

---

## 8. Storage

**Local files, plus export and re-import** (decision of 2026-08-07 — see
[01-specification.md](01-specification.md) section 7.4). Each session is a small folder of
human-readable JSON on the local disk; the whole history is one directory to back up or delete. The
earlier SQLite plan is cancelled — a database earns its keep at hundreds of sessions, and a proof of
concept never gets there.

**The uploaded video is never stored.** It lives in a temporary folder during analysis and is
deleted when the request finishes. The annotated render may be kept (`KEEP_ANNOTATED_VIDEO`).

**Every attempt is stored, including rejected ones.** Rejected sessions are excluded from comparison
but kept, so a clinician can see that three attempts were made. Choosing between several good takes
is done by naming sessions explicitly in a comparison, rather than by the system guessing which take
counts.

### 8.1 What is built today — the file-backed store

The file store already exists and is the permanent storage. Results survive a restart and a past
session can be reopened. What remains is **re-import**: opening a result file that was exported from
another machine.

```
data/sessions/
    index.jsonl                            one summary row per session, append-only
    PT-001/
        20260807-142530-rtmpose-<uuid>/
            assessment.json                the complete response
            annotated.mp4                  optional — see KEEP_ANNOTATED_VIDEO; H.264
            pose2d.json  pose3d.json       when the run produced them
```

The **directory is the record**; `index.jsonl` is a rebuildable summary of it, so listing a patient's
history costs one file read. A session whose index row is lost is still reachable by id, because the
folder is still there.

Two differences from the target contract above, both deliberate and both temporary:

- **The annotated video is kept**, which the target contract does not do. It is the patient's own
  footage with a skeleton drawn over it, so `KEEP_ANNOTATED_VIDEO=false` turns it off and stores only
  metrics and keypoints. Keep it on for our own clips; turn it off before real patient recordings.
- **Nothing expires.** `DEMO_RESULT_TTL_SECONDS=0` — the default — means a stored session is never
  deleted. A positive value restores the old expiring behaviour, which is why `expires_at` is still on
  the response and is simply `null` when nothing expires.

**The uploaded clip is never stored, under any setting.** The working directory is deleted as soon as
the analysis returns, and it takes the original upload with it.

Endpoints, both browser-facing:

| Endpoint | Returns |
|----------|---------|
| `GET /api/demo/sessions?patient_id=&limit=` | Summary rows, newest first. Omit `patient_id` for every patient |
| `GET /api/demo/sessions/{session_id}` | One stored session, in the **same payload shape** a fresh analysis returns |
| `GET /api/demo/compare?left=&right=` | Left against right across two of these sessions — see part 5.1 |

The shared shape is the point: the interface renders a reopened session through the same code path as
a new one, so there is no second view of a result that can quietly drift from the first.

**Still not built:** the progress comparison. Symmetry now has its endpoint (part 5.1); comparing a
session against an earlier baseline of the *same* leg does not — that work, with its MCID verdict,
carries into the prototype phase.

---

## 9. Running API versus this design

What the prototype phase changes when it implements the `v1` contract. Rows marked *shipped* already
happened in the PoC.

| Area | Running today | The `v1` design |
|------|--------|-----|
| Path | `/api/movement/assess` | `/api/v1/assessments` |
| Top-level shape | Five fixed keys | Status-led, with `recording`, `analysis`, `metrics`, `quality`, `screening`, `artifacts` |
| `side` on request | **Mandatory** *(shipped)* | Same |
| Both-legs metrics | Side-prefixed keys (`left_knee_rom_deg`) | Nested under `metrics.left` / `metrics.right` |
| Bad recordings | Flagged, metrics still returned | **Rejected**, no metrics returned |
| Confidence | `0.5 × frames + 0.5 × confidence` | `0.40 × frames + 0.40 × confidence + 0.20 × tracking stability` |
| Symmetry | `/api/demo/compare` *(shipped — part 5.1)*, plus the superseded in-response `symmetry_index_score` | Its own comparison endpoint; the in-response score removed |
| Naming | `knee_rom_deg` | `estimated_knee_rom_deg` |
| Trajectories | Returned in top-level `trajectory` *(shipped)* | Same |
| Velocity, acceleration | Absent | In `metrics` |
| History | Local file store *(shipped — part 8.1)* | Same store, plus re-import |
| Calibration board | Primary scale source | Stays primary; bone length arrives in the prototype phase |

**The rejection guard is the one behaviour change a caller must handle.** Everything else is additive
or a rename; a caller that previously received numbers for a poor recording will now receive a
rejection instead. That is the intended safety improvement, and any consumer must branch on
`assessment_status` before reading `metrics`.
