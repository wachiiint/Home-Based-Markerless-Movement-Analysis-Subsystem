# RTMPose Movement Analysis — Pipeline Overview

เอกสารนี้อธิบาย **pipeline การประมวลผล** และ **data pipeline** ของ service นี้
สำหรับให้เพื่อนในทีมเข้าใจภาพรวมได้เร็ว ๆ ก่อนลงไปอ่านโค้ดจริง

> TL;DR: ผู้ป่วยอัดวิดีโอท่าขยับขา → service รับวิดีโอ → รัน 2D pose ทีละเฟรม →
> คำนวณมุมข้อต่อ + range of motion (ROM) → คัดกรองความเสี่ยง → (ถ้ามี calibration board)
> ยกเป็น 3D → ส่งผลกลับเป็น JSON contract คงที่ ให้แพทย์รีวิว

---

## 1. ภาพรวมระบบ (System Context)

service นี้เป็น **หนึ่ง microservice** ในระบบใหญ่ ไม่ได้คุยกับผู้ป่วยตรง ๆ

```
Patient (frontend) ──upload video──▶ Backend หลัก
                                        │  (เก็บ session, เรียก service นี้ผ่าน MEDIAPIPE_SERVICE_URL)
                                        ▼
                          RTMPose Movement Analysis Service  ◀── (เอกสารนี้)
                                        │  (คืน assessment JSON)
                                        ▼
                                     Backend เก็บผล
                                        ▼
                                 Doctor dashboard (อ่าน risk_level, ROM, quality)
```

- **Entry point:** `POST /api/movement/assess` (ต้องมี header `X-Internal-Service-Key`)
- **Contract:** ดู [API_CONTRACT.md](API_CONTRACT.md) — response มี 5 top-level keys เสมอ
- **Demo UI:** `GET /` + `POST /api/demo/assess` (สำหรับทดสอบเอง ดูวิดีโอ annotated ได้)

ไฟล์: [app/main.py](app/main.py)

---

## 2. Pipeline ระดับสูง (End-to-End)

```
[1] Request รับเข้า        main.py: assess_movement()
       │  validate service key, validate video, normalize view
       ▼
[2] เซฟไฟล์ชั่วคราว         video_io.save_upload()
       ▼
[3] วิเคราะห์วิดีโอ         video_analysis.analyze_video()   ◀── หัวใจของ pipeline
       │
       ├─ Pass 1: 2D pose ทุกเฟรม + เขียนวิดีโอ annotated
       ├─ คำนวณมุม 2D + ROM + คัดกรองความเสี่ยง
       └─ Pass 2 (optional): ยก 3D ถ้ามี calibration
       ▼
[4] ประกอบ response        response_mapper.build_assessment_response()
       ▼
[5] คืน JSON + ลบไฟล์ชั่วคราว
```

โหมดการทำงานถูกเลือกตอน **startup** (`main.py: lifespan`):
- `FAKE_MODE=true` → คืนผลปลอม ไม่โหลดโมเดล (ใช้ทดสอบ integration)
- ปกติ → โหลด RTMPose (2D) เสมอ; โหลด 3D lifter **เฉพาะเมื่อ** `ENABLE_3D=true` และไฟล์ weights ผ่าน guard
- ถ้า 3D ใช้ไม่ได้ → ระบบ **degrade เป็น 2D อย่างสะอาด** ไม่ crash

---

## 3. Data Pipeline — ข้อมูลแปลงร่างอย่างไร

นี่คือส่วนสำคัญที่สุด: ข้อมูลเดินทางจาก **พิกเซล → มุมข้อต่อ → ระดับความเสี่ยง**

```
วิดีโอ (mp4)
   │  read_video_metadata: fps, width, height, duration
   ▼
เฟรมที่ sample แล้ว (ลดเหลือ ~frame_sample_fps เฟรม/วินาที)
   │  RTMPose BodyWithFeet infer ต่อเฟรม
   ▼
Keypoints หลายคน (N คน × 26 จุด Halpe26) + confidence scores
   │  select_main_subject: เลือก "คนหลัก" (subject ที่เด่นสุด)
   ▼
PoseSequence: 2D pose ของคนเดียว ต่อเฟรม (T เฟรม)   ◀── โครงสร้างข้อมูลกลาง
   │
   ├──────────────── เส้นทาง 2D (ทำเสมอ) ────────────────┐
   │                                                      │
   │  _choose_side: เลือกซ้าย/ขวาที่ confident กว่า        │
   │  _angle_for_frame: three_point_angle() ต่อเฟรม        │
   │  exponential_moving_average: smoothing                │
   │  range_of_motion: min/max/ROM                         │
   │  screen_rom: risk_level + confidence + flags          │
   │                                                      ▼
   │                                              clinical_metrics (2D)
   │
   └──────────────── เส้นทาง 3D (optional) ───────────────┐
      (เฉพาะเมื่อมี lifter + calibration ผ่าน)              │
      sequence_to_arrays: เติมช่องว่างเฟรมที่ไม่มีคน        │
      halpe26_to_h36m17: แปลง skeleton 26→17 จุด            │
      normalize_screen_coordinates                          │
      MotionBERT lift: 2D → 3D (T,17,3) root-relative        │
      bone_length_consistency guard: ทิ้งถ้า lift มั่ว        │
      angle_series_3d + smoothing + ROM                     │
      resolve_metric_scale: หา mm/unit จากพื้น หรือ ส่วนสูง  │
                                                            ▼
                                              joint_angles_3d + scale
```

### 3.1 หน่วยข้อมูลหลัก (Key data structures)

| โครงสร้าง | ไฟล์ | ความหมาย |
|-----------|------|----------|
| `FramePose2D` | [pose_sequence.py](app/services/pose_sequence.py) | pose 2D ของคนหลัก 1 เฟรม (keypoints, scores หรือ None ถ้าไม่เจอคน) |
| `PoseSequence` | [pose_sequence.py](app/services/pose_sequence.py) | รวมทุกเฟรม + width/height ของวิดีโอ |
| `Lifted3DSequence` | [lifting/pipeline.py](app/services/lifting/pipeline.py) | 3D keypoints (T,17,3) + mask เฟรมที่เป็นของจริง |
| `CameraCalibration` | [models/calibration.py](app/models/calibration.py) | intrinsics K, distortion, floor plane, board pose |
| `MovementAssessmentResponse` | [schemas/response.py](app/schemas/response.py) | JSON contract ที่คืนกลับ |

### 3.2 รายละเอียด Pass 1 (2D — ทำเสมอ)

ไฟล์: `_collect_pose_sequence()` ใน [video_analysis.py](app/services/video_analysis.py:52)

1. เปิดวิดีโอด้วย OpenCV, สร้าง `VideoWriter` สำหรับวิดีโอ annotated
2. **Sample เฟรม**: ข้ามเฟรมให้เหลือ ~`frame_sample_fps` เฟรม/วินาที (ลดโหลด)
3. แต่ละเฟรมที่ sample:
   - เรียก `frame_observer` (ถ้ามี calibration) เพื่อหา ChArUco board
   - `estimator.infer(frame)` → keypoints + scores ของทุกคน
   - `select_main_subject` → เลือกคนหลัก
   - วาดโครงกระดูก (`draw_skeleton`) ลงเฟรม แล้วเขียนลงวิดีโอ output
   - เก็บ `FramePose2D` เข้า list
4. คืน `PoseSequence`

> **ทำไมต้อง 2 pass?** เพราะ 3D lifter (MotionBERT) ต้องการ **ลำดับเฟรมทั้งหมด** พร้อมกัน
> จึงเก็บ 2D ทั้งซีเควนซ์ก่อน แล้วค่อยยก 3D ทีเดียว

### 3.3 การคำนวณมุม (2D)

- **แต่ละ task** (เช่น `knee_flexion`) กำหนดใน [task_config.py](app/models/task_config.py) ว่าใช้ 3 จุดไหน
  เป็น vertex + ray 2 เส้น เช่น เข่า = มุมระหว่าง hip–knee–ankle
- `three_point_angle` → มุมองศาต่อเฟรม
- เฟรมไหน confidence ต่ำกว่า threshold → ทิ้ง (นับเป็น "invalid frame")
- `exponential_moving_average` ลด noise → `range_of_motion` ได้ min/max/ROM

### 3.4 การคัดกรองความเสี่ยง (Screening)

ไฟล์: [screening.py](app/services/screening.py)

```
ถ้า valid_frame_ratio ต่ำ  → flag "low_valid_frame_ratio"
ถ้า confidence เฉลี่ยต่ำ    → flag "low_keypoint_confidence"

risk = high      ถ้ามี flag หรือ ROM < borderline
     = moderate  ถ้า ROM < expected
     = low        ถ้าไม่เข้าเงื่อนไขข้างบน

confidence_score = 0.5*valid_frame_ratio + 0.5*mean_confidence  (0..1)
```

ค่า `expected_rom_deg` / `borderline_rom_deg` ต่อ task อยู่ใน [task_config.py](app/models/task_config.py)

---

## 4. เส้นทาง 3D (Phase D) — รายละเอียด

ทั้งหมดอยู่ใน `_augment_with_3d()` ที่ [video_analysis.py:120](app/services/video_analysis.py:120)
หลักการออกแบบ: **best-effort, ไม่มีวัน raise** — ถ้าอะไรพังก็ตกกลับไปใช้ผล 2D

### 4.1 Calibration (ต่อ session)

ไฟล์: [calibration/session.py](app/services/calibration/session.py)

- ระหว่าง Pass 1 ทุกเฟรมถูกส่งเข้า `SessionCalibrator.observe()` เพื่อหา **ChArUco board** (กระดาษ A4 พิมพ์)
- เก็บเฟรมที่เจอมุม board มากที่สุด
- `finalize()`:
  - ดึง **intrinsics ของกล้อง** จาก `DeviceStore` (ระบุกล้องจาก metadata / resolution)
  - กู้ pose ของ board → ได้ **floor plane** + reprojection error
  - ถ้า reproj สูง (>3px) หรือกล้องไม่เคย calibrate → warning / ปิด 3D

### 4.2 การยก 2D → 3D (Lifting)

ไฟล์: [lifting/pipeline.py](app/services/lifting/pipeline.py) + [lifting/lifter.py](app/services/lifting/lifter.py)

1. `sequence_to_arrays`: แปลงเป็น array แน่น (T,26,2) + เติมเฟรมว่างด้วยเฟรมใกล้สุด + mask
2. `halpe26_to_h36m17`: แปลง skeleton จาก 26 จุด (RTMPose) → 17 จุด (H36M ที่ MotionBERT ต้องการ)
3. `normalize_screen_coordinates`: normalize พิกัดพิกเซล
4. `MotionBertAdapter.lift`: ONNX inference → 3D (T,17,3) แบบ root-relative (ไร้หน่วยจริง)
5. **Guard** `bone_length_consistency`: ถ้าความยาวกระดูกไม่คงที่ = lift มั่ว → ทิ้ง กลับไป 2D

> `StubLifter` มีไว้เทสต์ pipeline โดยไม่ต้องมี weights เท่านั้น — **ห้ามใช้จริง**
> `validate_lifter_io` smoke-test รูปร่าง I/O ของ ONNX ตอน startup กัน "ผิดแบบเงียบ ๆ"

### 4.3 Metric scale — ทำให้ 3D มีหน่วยจริง (mm)

ไฟล์: [lifting/metric_scale.py](app/services/lifting/metric_scale.py)

3D ที่ได้ไร้หน่วย ต้องหา **mm ต่อ 1 หน่วย**:
- **Primary (`feet_floor`)**: ยิงรังสีจากพิกเซลข้อเท้าซ้าย/ขวาไปชนพื้น (floor plane) → ได้ระยะจริง เทียบกับระยะในสเกเลตัน
- **Fallback (`subject_height`)**: สเกลให้ระยะหัว-ถึง-เท้า = ส่วนสูงที่ผู้ป่วยกรอก (`subject_height_mm`)
- ถ้ามีทั้งคู่แล้วต่างกัน >15% → warning `scale_uncertain`

### 4.4 มุม 3D + 6DoF transform

- `angle_series_3d`: คำนวณมุมข้อต่อจากสเกเลตัน 3D (task ที่รองรับ) → ใส่ใน `joint_angles_3d` (คีย์ลงท้าย `_3d`)
- `camera_to_floor_6dof`: matrix แปลงพิกัดจาก camera frame → floor frame (ใส่ใน `transformation_matrix_6dof`)
- Task ankle ยังใช้มุม 2D แม้ calibrate สำเร็จ (`supports_3d_angle` = false)

---

## 5. โครงสร้าง Response (Output)

ไฟล์: [response_mapper.py](app/services/response_mapper.py), [schemas/response.py](app/schemas/response.py)

```jsonc
{
  "session_id": "rtmpose-<uuid>",
  "video_metadata": {
    "duration_sec", "fps", "view", "task_type",
    "processed_frames", "sampled_fps", "analyzed_side"
  },
  "clinical_metrics": {
    "joint_angles":     { "<task>_max_deg", "<task>_min_deg", "<task>_rom_deg" },  // 2D
    "joint_angles_3d":  { "..._3d": ... },      // ว่างถ้าไม่ได้รัน 3D
    "scale_mm_per_unit", "scale_source",        // null ถ้าไม่มี scale
    "pose_quality": { "mean_keypoint_confidence", "valid_frame_ratio", "occlusion_warning" }
  },
  "screening_result": { "risk_level", "confidence_score", "flags": [] },
  "transformation_matrix_6dof": {...} | null,
  "analysis_mode": "2d" | "3d",         // บอกว่าจบด้วยโหมดไหนจริง
  "board_diagnostics": {...} | null,    // ผลการหา ChArUco board
  "guard_warnings": []                  // เตือนต่าง ๆ (scale, lift, reproj)
}
```

**จุดที่เพื่อนควรจำ:** `analysis_mode` บอก **ผลจริง** ที่ได้ (2d/3d) —
แม้ตั้ง `ENABLE_3D=true` ถ้า board/calibration/guard ไม่ผ่าน ก็จะได้ `"2d"` และ `guard_warnings` จะบอกเหตุผล

---

## 6. Config สำคัญ (env)

ดู [app/core/config.py](app/core/config.py) และ `.env.example`

| ตัวแปร | ผลต่อ pipeline |
|--------|----------------|
| `FAKE_MODE` | ข้ามโมเดลทั้งหมด คืนผลปลอม |
| `ENABLE_3D` | เปิดเส้นทาง 3D (ยังต้องมี weights + calibration) |
| `MOTIONBERT_MODEL_PATH` | ไฟล์ ONNX ของ lifter |
| `DEVICE` | `cpu` / `cuda:0` / `auto` |
| `FRAME_SAMPLE_FPS` | ลดจำนวนเฟรมที่ประมวลผล |
| `MIN_KEYPOINT_CONFIDENCE` | threshold ตัดจุดที่ไม่มั่นใจ |
| `SMOOTHING_ALPHA` | ค่า EMA smoothing |
| `MIN_VALID_FRAME_RATIO` | เกณฑ์ flag คุณภาพ |
| `SERVICE_API_KEY` | key สำหรับ auth internal |

---

## 7. สรุปสั้น ๆ ให้จำ

1. **สอง pass**: pass 1 เก็บ 2D ทั้งวิดีโอ (+วิดีโอ annotated), pass 2 ยก 3D ทีเดียว
2. **2D ทำเสมอ, 3D เป็น bonus** ที่ degrade ได้อย่างสะอาด — ไม่มีวัน crash เพราะ 3D
3. **หัวใจข้อมูล** คือ `PoseSequence` (2D คนเดียวต่อเฟรม) → ทุกอย่างต่อยอดจากนี้
4. **Screening** ให้ risk/confidence/flags จาก ROM + คุณภาพ pose
5. **Contract คงที่ 5 keys** เสมอ — backend/แพทย์พึ่งได้

ไฟล์ที่ควรเปิดอ่านคู่กัน: [video_analysis.py](app/services/video_analysis.py) (orchestrator) และเอกสารนี้
