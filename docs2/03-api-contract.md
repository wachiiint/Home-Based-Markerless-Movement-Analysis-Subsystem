# 03 — API Contract

> The exact requests and responses of the local service.
> Terms are defined in [00-glossary.md](00-glossary.md). What each stage does is in
> [02-pipeline.md](02-pipeline.md).

**This is a redesign.** The previous contract was shaped to drop into an existing MediaPipe-based
backend. With the application now running standalone, it has been rebuilt around what the system
actually produces. Differences from the old shape are listed in Part 9.

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

`side` is new and mandatory. Without it, left and right recordings cannot be paired for symmetry, and
the system cannot check that the instructed leg is the one that actually moved.

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

**SQLite**, one local file. It ships with Python, needs no server, and the whole history is one file
to back up or delete.

| Table | Holds |
|-------|-------|
| `patients` | `patient_id`, bone lengths, measurement date |
| `sessions` | `session_id`, `patient_id`, task, side, view, date, status, quality, metrics JSON, trajectory JSON |

**Only derived numbers are stored — never video, never images.** Videos live in a temporary folder
during analysis and are deleted when the request finishes.

**Every attempt is stored, including rejected ones.** Rejected sessions are excluded from comparison
but kept, so a clinician can see that three attempts were made. Choosing between several good takes
is done by naming sessions explicitly in a comparison, rather than by the system guessing which take
counts.

---

## 9. What changes from the current implementation

| Area | Before | Now |
|------|--------|-----|
| Path | `/api/movement/assess` | `/api/v1/assessments` |
| Top-level shape | Five fixed keys | Status-led, with `recording`, `analysis`, `metrics`, `quality`, `screening`, `artifacts` |
| `side` on request | Absent | **Required** |
| Both-legs metrics | Side-prefixed keys (`left_knee_rom_deg`) | Nested under `metrics.left` / `metrics.right` |
| Bad recordings | Flagged, metrics still returned | **Rejected**, no metrics returned |
| Confidence | `0.5 × frames + 0.5 × confidence` | `0.40 × frames + 0.40 × confidence + 0.20 × tracking stability` |
| Symmetry | Ratio 0 to 1, inside the analysis response | Percentage, from its own comparison endpoint |
| Naming | `knee_rom_deg` | `estimated_knee_rom_deg` |
| Trajectories | Computed then discarded | Returned in `trajectory` — *already shipped on the current response* |
| Velocity, acceleration | Absent | In `metrics` |
| History | None | SQLite, enabling symmetry and progress |
| Calibration board | Primary scale source | Optional; bone length is primary |

**The rejection guard is the one behaviour change a caller must handle.** Everything else is additive
or a rename; a caller that previously received numbers for a poor recording will now receive a
rejection instead. That is the intended safety improvement, and any consumer must branch on
`assessment_status` before reading `metrics`.

---

## Related documents

| Document | Purpose |
|----------|---------|
| [00-glossary.md](00-glossary.md) | Definitions of every term used |
| [01-specification.md](01-specification.md) | What the project is and why |
| [02-pipeline.md](02-pipeline.md) | Patient workflow and the technical data pipeline |
| **03-api-contract.md** | *This document* |
| [04-planning.md](04-planning.md) | Phases, tasks, risk, effort, benefit |
| [05-user-manual.md](05-user-manual.md) | How to perform, record, and interpret each task |
| [06-setup.md](06-setup.md) | Installation and running the application |
| [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) | Accuracy, validation, and honest limits |
| [08-spec-alignment.md](08-spec-alignment.md) | Status against the advisor's specification |
