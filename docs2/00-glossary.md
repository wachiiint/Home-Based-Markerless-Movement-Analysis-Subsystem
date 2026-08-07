# 00 — Glossary

> Every clinical, technical, and project-specific term used across this documentation set.
> Entries are short on purpose. If a term appears anywhere in `docs2/` and is not here, that is a gap
> worth fixing.

Terms are grouped by the world they come from:
[Clinical](#1-clinical-terms) · [Movement](#2-movement-and-measurement) ·
[Pose estimation](#3-cameras-ai-and-pose-estimation) · [Software](#4-software-and-system) ·
[This project](#5-project-specific-terms)

---

## 1. Clinical terms

| Term | Meaning |
|------|---------|
| **Sarcopenia** | Age-related loss of muscle mass and strength. It makes an older adult weaker, then slower, then unsteady, and eventually leads to falls. Treatable when caught early, which is why screening matters. |
| **AWGS 2019** | Asian Working Group for Sarcopenia, 2019 consensus. The agreed clinical rulebook for diagnosing sarcopenia in Asian populations, including the threshold numbers. Western standards use different cut-offs because body types differ. |
| **Possible sarcopenia** | The AWGS classification meaning *low muscle strength OR low physical performance*. Only one of the two is needed to raise the flag. |
| **Fall risk** | The likelihood that a patient will fall. Related to sarcopenia but a separate clinical question — a patient can be unsteady without being sarcopenic. |
| **5-STS** | Five-Times Sit-to-Stand. Stand up and sit down five times as fast as possible. Taking 12 seconds or more indicates low muscle strength. |
| **Gait speed** | How fast a patient walks at a comfortable pace. Below 0.8 metres per second indicates low physical performance. |
| **TUG** | Timed Up and Go. Stand from a chair, walk 3 metres, turn, walk back, sit down. 12 seconds or more indicates high fall risk. Note that TUG is a **fall-risk** indicator, not a sarcopenia criterion. |
| **Calf circumference** | Tape measurement around the calf. Below roughly 34 cm (men) or 33 cm (women) is suspicious. Used only as screening support, never as a diagnosis on its own. |
| **MCID** | Minimal Clinically Important Difference. The smallest change that actually matters to a patient. A 2-degree ROM gain is noise; +5 degrees is a real improvement. MCID is what stops a system from reporting noise as progress. |
| **Baseline** | An earlier recording of the same patient and task, used as the reference point for measuring change. |
| **Longitudinal** | Tracking the same patient across multiple visits over time, rather than assessing them once. |
| **Decision support** | A system that supplies numbers a clinician uses to decide. It does not diagnose. This project is decision support. |
| **ADL** | Activities of Daily Living — ordinary tasks like standing, walking, climbing stairs. Some ROM thresholds are set by what an ADL requires. |
| **Goniometer** | The handheld protractor a clinician uses to measure a joint angle by hand. The traditional gold standard, and a two-dimensional instrument. |
| **Contralateral** | On the opposite side of the body. Comparing an injured leg against the patient's own healthy leg is a contralateral comparison. |
| **Unilateral / bilateral** | Involving one side / both sides. All six tasks in this project are unilateral: the patient moves one leg at a time. |
| **Anatomical landmark** | A bony point on the body a clinician can feel and measure from, such as the greater trochanter at the hip. Hospital bone-length measurements use landmarks. |
| **Leg length discrepancy** | A genuine difference in length between a patient's two legs. A real clinical finding, which is why bone lengths are recorded per side rather than shared. |

---

## 2. Movement and measurement

| Term | Meaning |
|------|---------|
| **Kinematics** | The study of movement itself — positions, angles, speeds — without considering the forces that caused it. This project is purely kinematic. |
| **Joint angle** | The angle formed at a joint by the two body segments meeting there. Measured from three points: the joint itself plus one point on each segment. |
| **ROM** | Range of Motion. How far a joint travelled during a movement, calculated as the largest angle minus the smallest angle. The headline clinical number. |
| **Flexion** | Bending a joint so the angle between the bones decreases — bending the knee. |
| **Extension** | Straightening a joint so the angle increases — straightening the knee. |
| **Dorsiflexion** | Lifting the foot upward at the ankle, toes toward the shin. |
| **Plantarflexion** | Pointing the foot downward at the ankle, as when standing on tiptoes. |
| **Sagittal plane** | The plane dividing the body into left and right halves. Bending a knee happens in this plane, which is why these tasks are filmed from the side. |
| **Jerk** | The rate of change of acceleration. Sudden, abrupt motion has high jerk; controlled motion has low jerk. |
| **Smoothness** | How controlled and continuous a movement is. Healthy motor control produces smooth motion; impairment produces hesitant, jerky motion. |
| **LDLJ** | Log Dimensionless Jerk. The standard smoothness measure, derived from jerk but adjusted so that movement duration and size do not distort it. Higher values mean smoother. |
| **SPARC** | Spectral Arc Length. A second smoothness measure computed from the frequency content of the movement. Used alongside LDLJ as a cross-check. |
| **Movement units** | The number of separate speed peaks in one movement. A single smooth motion has one; a hesitant, corrected motion has several. |
| **LSI** | Limb Symmetry Index. How different the left and right legs are, as a percentage: the difference divided by the average, times 100. Above roughly 10 percent is worth a clinician's attention. |
| **Ground reaction force** | The force between the foot and the floor, measured by a force plate. Required to calculate muscle force — and impossible to obtain from a camera. |
| **Force plate** | Laboratory equipment that measures ground reaction force. Not used in this project, which is why muscle *force* is out of scope. |
| **Muscle length** | How stretched or shortened a muscle is, which can be estimated from joint geometry alone. Distinct from muscle *force* or *activation*, which cannot. |

---

## 3. Cameras, AI, and pose estimation

| Term | Meaning |
|------|---------|
| **Pose estimation** | Automatically finding a person's joint positions in an image or video. |
| **Markerless** | Requiring no markers, suits, or sensors on the patient — just ordinary video. What makes home assessment possible. |
| **Keypoint** | One detected body point, such as the left knee. A pose is a set of keypoints. |
| **Skeleton** | The defined set of keypoints a model uses, plus how they connect. Different models use different skeletons. |
| **Halpe26** | A 26-keypoint skeleton that includes six foot points (big toe, small toe, and heel on each side). Used in this project because ankle tasks need a toe. |
| **COCO-17** | The common 17-keypoint skeleton, which stops at the ankles and has no foot points. This is why people often believe pose models cannot see toes. |
| **H36M-17** | The 17-joint skeleton from the Human3.6M dataset, required by the 3D lifting model. It ends at the ankle and has **no toe joint**, which is why ankle tasks cannot be computed in 3D. |
| **RTMPose** | The pose estimation model used in this project. Detects 2D keypoints in each video frame. |
| **rtmlib** | The Python library that runs RTMPose. |
| **MotionBERT** | The model used to convert a sequence of 2D poses into 3D joint positions. |
| **2D pose** | Joint positions in image coordinates — where each joint appears on the flat picture. |
| **3D lifting** | Estimating 3D joint positions from 2D ones. Called *lifting* because it raises flat image data into three dimensions. |
| **Monocular** | Using a single camera. A monocular view cannot directly observe depth, which is the core difficulty of 3D lifting. |
| **Depth ambiguity** | The fundamental problem that one camera cannot tell a small object nearby from a large object far away. It is why monocular 3D is an estimate rather than a measurement. |
| **Keypoint confidence** | A score from 0 to 1 saying how certain the model is about one detected joint. Low confidence means the joint was probably occluded or unclear. |
| **Occlusion** | A body part being hidden — by clothing, furniture, another limb, or the frame edge. A main cause of unreliable results. |
| **Frame sampling** | Analysing a fixed number of frames per second rather than every frame, to keep processing time reasonable. |
| **Subject selection** | Choosing which detected person is the patient when several people appear in the video. |
| **Temporal smoothing** | Averaging each frame's value with the preceding ones to reduce frame-to-frame jitter. This project uses an exponential moving average. |
| **ONNX** | A portable file format for trained AI models, letting a model run without its original training framework. |
| **Inference** | Running a trained model on new data to get a prediction — as opposed to training it. |
| **Metric scale** | The conversion factor from the reconstruction's arbitrary units to real millimetres. Without it, a 3D pose has correct shape but unknown size. |
| **Bone-length scaling** | Obtaining metric scale by dividing a known real bone length in millimetres by the same bone's reconstructed length in arbitrary units. The approach chosen by this project. |
| **Camera intrinsics** | A camera's internal properties, chiefly focal length and lens distortion. Needed for geometric measurement in the image. |
| **Camera extrinsics** | Where the camera sits and how it is oriented relative to the scene. |
| **ChArUco board** | A printed pattern combining a chessboard with ArUco markers, used for camera calibration. Optional in this project since bone-length scaling replaced it as the scale source. |
| **Floor plane** | The mathematical description of where the floor is in the camera's view. |
| **6DoF** | Six Degrees of Freedom — three of position and three of rotation. The full description of one coordinate frame relative to another. |

---

## 4. Software and system

| Term | Meaning |
|------|---------|
| **API** | Application Programming Interface. The defined set of requests one program can make to another. |
| **Endpoint** | One specific address in an API that performs one job, such as analysing a video or querying symmetry. |
| **Request / response** | The message sent to an endpoint, and the message sent back. |
| **JSON** | The text format used for responses. Readable by both people and programs. |
| **Contract** | The agreed structure of requests and responses. Changing it without coordination breaks whatever depends on it. |
| **FastAPI** | The Python web framework used to build the local service. |
| **Localhost** | The local machine itself. A localhost application is reachable only from the computer it runs on. |
| **SQLite** | A small database that lives in a single local file and needs no server. Was considered for session history, but the project settled on plain local files instead (2026-08-07). |
| **Stateless / stateful** | Whether a system remembers anything between requests. Analysis is stateless with respect to comparison; storage makes history possible. |
| **Session** | One completed assessment: one patient, one task, one side, one recording, and the metrics derived from it. |
| **Fallback** | Producing a simpler but still valid result when the preferred path fails — here, returning the 2D result when 3D cannot be trusted. |
| **Graceful degradation** | The general principle behind fallback: reduce capability rather than fail entirely. |
| **Guard** | A check that stops bad data from proceeding. Some guards reject a result; some reject the whole recording. |
| **Regression test** | An automatic test that proves previously working behaviour still works after a change. |
| **pytest** | The testing tool used in this project. |
| **Three.js** | The JavaScript library that renders the 3D motion simulation in the browser. |

---

## 5. Project-specific terms

| Term | Meaning |
|------|---------|
| **Task (task type)** | Which of the six prescribed movements the patient performed, such as knee flexion. Determines which joint is measured and which thresholds apply. |
| **View** | Which direction the camera filmed from — lateral or frontal. |
| **Side** | Which leg the patient was instructed to move. Required so that left and right recordings can be paired for symmetry. |
| **Tier1: Screening layer** | The clinical layer using timed tests to decide whether a patient is at risk at all. Not built in this project. |
| **Tier2: Assessment layer** | The layer measuring *how* the patient moves. The core of this project. |
| **Tier3: Monitoring layer** | The layer tracking improvement over time against the patient's own baseline. Planned, and part of the end goal. |
| **Quality guard** | The check that rejects a recording outright when it is too poor to measure — too few usable frames, or confidence too low. Returns a rejection with a reason instead of numbers. |
| **Valid frame ratio** | The fraction of sampled frames in which the patient was detected well enough to use. |
| **Confidence score** | An overall 0-to-1 grade for how much the result can be trusted, combining valid frame ratio, keypoint confidence, and tracking stability. |
| **Tracking stability** | How steadily the skeleton was tracked from frame to frame. Jumpy tracking lowers confidence even when individual frames look acceptable. |
| **`estimated_` prefix** | A naming convention marking any quantity the camera inferred rather than measured. Honesty enforced in the field names themselves. |
| **Risk level** | The screening output for one recording: low, moderate, or high, based on ROM against task thresholds and on recording quality. |
| **Flags** | Short machine-readable reasons attached to a result, such as a ROM below the borderline threshold. |
| **Expected / borderline ROM** | Per-task reference values. Below *expected* is moderate concern; below *borderline* is high concern. |
| **Annotated video** | The output video with the detected skeleton drawn on it, so a clinician can verify what the system actually tracked. |
| **Motion simulation** | The interactive 3D replay of the movement, including the muscle overlay. |
| **Muscle overlay** | A visualisation of how muscles stretch and shorten during the movement, derived from joint geometry. Display only — not force, not activation. |
| **Comparability guard** | The check that two recordings may legitimately be compared: same task, same view, both of adequate quality. Prevents reporting a symmetry or progress figure built from mismatched recordings. |
| **Analysis mode** | Which path produced the result, 2D or 3D. Always reported, so a reader knows which applies. |

---

## Related documents

| Document | Purpose |
|----------|---------|
| **00-glossary.md** | *This document* |
| [01-specification.md](01-specification.md) | What the project is and why |
| [02-pipeline.md](02-pipeline.md) | Patient workflow and the technical data pipeline |
| [03-api-contract.md](03-api-contract.md) | Request and response formats |
| [04-planning.md](04-planning.md) | Phases, tasks, risk, effort, benefit |
| [05-user-manual.md](05-user-manual.md) | How to perform, record, and interpret each task |
| [06-setup.md](06-setup.md) | Installation and running the application |
| [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) | Accuracy, validation, and honest limits |
| [08-spec-alignment.md](08-spec-alignment.md) | Status against the advisor's specification |
