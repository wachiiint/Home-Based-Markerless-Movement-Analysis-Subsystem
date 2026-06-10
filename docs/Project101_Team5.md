# **Project Proposal: Home-Based Markerless Movement Analysis Subsystem (Team 5\)**

**ทีมที่รับผิดชอบ:** Team 5 (Movement Analysis & Tele-Rehabilitation Subsystem)

**อาจารย์ที่ปรึกษาโครงการ:** รศ.ดร.พิษณุ คนองชัยยศ

**ปีการศึกษา:** ภาคฤดูร้อน ปีการศึกษา 2568 (Academic Year 2025-2026)

## **1\. บทนำและวัตถุประสงค์ (Introduction & Executive Summary)**

•          พัฒนาเว็บแอปพลิเคชันให้ผู้ป่วยสามารถทำ Movement Assessment จากที่บ้านผ่านกล้อง Smartphone/Webcam โดยเน้นการถ่ายหรืออัปโหลดวิดีโอที่บันทึกเสร็จแล้ว พร้อม tutorial step-by-step, camera setup checklist และคำเตือนด้านความปลอดภัยระหว่างทำท่า ทั้งนี้ real-time skeleton preview ถือเป็นส่วนเสริมในระยะถัดไป ไม่ใช่ core requirement ของ prototype แรก 

•          สร้าง pipeline ที่รับ raw video และ metadata จากฝั่งผู้ป่วย แล้วประมวลผลด้วย Pose Estimation บน Cloud/Backend เพื่อแปลงเป็น keypoint sequence และ clinical/technical movement features เช่น joint angle, ROM, velocity, smoothness, symmetry, pelvic instability และ gait parameters

•          พัฒนา screening module แบบ rule-based หรือ lightweight ML เพื่อช่วย flag movement limitation, compensation pattern หรือ risk level เบื้องต้น พร้อม confidence/flag explanation สำหรับแพทย์ใช้ประกอบการพิจารณา โดยไม่ทำหน้าที่วินิจฉัยโรคแทนแพทย์

•          พัฒนา Admin Application สำหรับแพทย์/นักกายภาพให้ดู video playback, skeleton/keypoint overlay หรือ keypoint timeline, ตรวจ feature ราย frame, ดูกราฟเปรียบเทียบ before-after และส่ง feedback/notification กลับไปหาผู้ป่วย

•          ออกแบบระบบให้รองรับ tele-rehabilitation workflow: ผู้ป่วยทำท่าที่บ้าน แพทย์ให้ feedback หลังประมวลผลหรือระหว่าง session ตามความเหมาะสม และติดตามความก้าวหน้ารายคนไข้ในระยะยาว

##  

## **2\. สถาปัตยกรรมระบบแบ่งชั้น (System Layered Architecture)**

โครงสร้างระบบถูกออกแบบและสกัดตามหลักสถาปัตยกรรมแบบ 5 ชั้น (Five-Layer Architecture) เพื่อรักษาสมดุลระหว่างประสิทธิภาพการประมวลผล ความเป็นไปได้ของ prototype และการกระจายภาระงานบนเซิร์ฟเวอร์คลาวด์อย่างมีเสถียรภาพ ดังนี้

| Layer | Component / Layer Name | Input / Technology | Main Processing | Output / Clinical Value |
| :---- | :---- | :---- | :---- | :---- |
| **L1** | **Sensing / Capture Layer** (Edge Hardware) | กล้อง RGB จาก smartphone / webcam ของผู้ป่วยเป็นหลัก \[Optional\] RGB-D camera, IMU sensor, camera setup checklist | บันทึกวิดีโอการเคลื่อนไหวในบ้านของผู้ป่วย โดยไม่ต้องใช้ marker, motion capture lab หรืออุปกรณ์เฉพาะทาง มีขั้นตอนช่วยจัดตำแหน่งกล้อง แสง ระยะ และมุมมองให้เหมาะสม | ได้วิดีโอ movement task ที่ใช้วิเคราะห์ต่อได้ ผู้ป่วยสามารถใช้งานที่บ้านได้ง่าย ลด barrier ของ tele-rehabilitation |
| **L2** | **Pose Estimation & Quality Control Layer** (Cloud / Backend Engine) | Raw video จาก L1, MediaPipe Pose / Hands บน backend หรือ cloud processing \[Optional future work\] real-time preview บน browser | ประมวลผลหลังอัปโหลดวิดีโอเพื่อสกัด 2D/3D skeleton keypoints ทำ temporal smoothing, keypoint confidence scoring, occlusion detection และ data quality check | ได้ skeleton/keypoints ที่พร้อมนำไปคำนวณต่อ ระบบสามารถแจ้งเตือนได้เมื่อข้อมูลคุณภาพต่ำ เช่น กล้องบัง มุมไม่เหมาะ แสงไม่พอ หรือ keypoint confidence ต่ำ |
| **L3** | **Feature Extraction Layer** (Cloud / Hybrid Kinematic Engine) | Input: Raw keypoints จาก L2, Python-based clinical feature extraction library | แปลง keypoints เป็น **Clinical Kinematic Features** เช่น joint angle, ROM, velocity, movement smoothness, gait metrics, symmetry, compensation pattern, pelvic drop angle, single/double support phase และ task-specific metrics | ได้ clinical features ที่ interpret ได้โดยแพทย์/นักกายภาพ ใช้เปรียบเทียบก่อน-หลังการรักษา หรือติดตาม progress ของผู้ป่วยรายบุคคล |
| **L4** | **Analysis & Screening Layer** (Rule-based / Lightweight ML Decision Support) | Input: Clinical features จาก L3 Baseline models: **rule-based screening, Random Forest, XGBoost** | วิเคราะห์รูปแบบการเคลื่อนไหวเพื่อทำ **movement impairment screening, compensation pattern flagging, preliminary risk level** และ progress tracking เบื้องต้น โดยไม่ใช้ deep learning เป็น core requirement ใน prototype แรก | ส่งผลลัพธ์เป็น prediction/flag, confidence score และ explanation ให้แพทย์ใช้ประกอบการตัดสินใจ เน้นเป็น **clinical decision-support system** ไม่ใช่ระบบวินิจฉัยแทนแพทย์ |
| **L5** | **Application / Presentation Layer** (Patient & Doctor Interface) | **Patient** web app **Doctor** admin portal Example tech stack: **React \+ Next.js \+ TypeScript \+ Tailwind CSS** \[Optional\] Three.js สำหรับ integration ระยะถัดไป | **ฝั่งผู้ป่วย:** tutorial การทำท่า, camera setup guide, video capture/upload, รับ feedback จากแพทย์ **ฝั่งแพทย์:** dashboard, video playback, skeleton/keypoint overlay หรือ timeline, frame-level graphs, clinical metrics, report/feedback function | เชื่อมผลวิเคราะห์เข้ากับ workflow ของ **tele-rehabilitation** แพทย์สามารถดู movement replay, ตรวจ frame ที่ผิดปกติ, ติดตาม progress และให้คำแนะนำกลับไปยังผู้ป่วยได้ |

##  

## **3\. คุณลักษณะทางเทคนิคเชิงลึกเพื่อการวินิจฉัย (Clinical Technical Features & Methodologies)**

เพื่อให้แพทย์วินิจฉัยและติดตามการฟื้นฟูได้อย่างแม่นยำ ระบบจะไม่ประมวลผลพิกัดคีย์พอยต์แบบดิบ (Raw Keypoints) เพียงอย่างเดียว แต่จะสกัดคุณลักษณะทางกลศาสตร์ที่ตรงตามเกณฑ์ชี้วัดทางการแพทย์ (Explainable Biometrics) โดยเพิ่มตัวชี้วัดที่จำเพาะต่อโรคกล้ามเนื้ออ่อนแรงและ gait abnormality ดังตารางด้านล่าง:

| Technical Feature | เป้าหมาย / สิ่งที่ใช้วัด | วิธีการคำนวณเชิงเทคนิค (How to Measure) |
| :---- | :---- | :---- |
| **Joint Angle & ROM** | มุมข้อต่อและช่วงการเคลื่อนไหวสูงสุด (Range of Motion) ของไหล่ ข้อศอก สะโพก เข่า และข้อต่อที่เกี่ยวข้อง | ใช้คณิตศาสตร์เวกเตอร์ (Dot Product) ระหว่างกระดูกสองท่อนที่เชื่อมกับข้อต่อ เช่น เส้นท่อนแขนบนและท่อนแขนล่างเพื่อหามุมข้อศอก ติดตามค่าสูงสุดและต่ำสุดของมุมรายเฟรม |
| **Movement Smoothness (Jerk & SPARC)** | ความราบรื่นและจังหวะคงที่ของการขยับ เพื่อตรวจจับอาการสั่น (Tremor) หรือการขยับสะดุดแบบกล้ามเนื้อกระตุก | คำนวณจากค่า Jerk (อนุพันธ์อันดับ 3 ของเวกเตอร์ตำแหน่งเทียบกับเวลา) หรือวัดความสม่ำเสมอของสัญญาณความเร็วในโดเมนความถี่ด้วย Spectral Arc Length (SPARC) |
| **Postural Compensation Patterns** | การโกงท่าทางหรือพฤติกรรมชดเชยของร่างกาย เช่น การโก่งตัว เอี้ยวหลัง หรือยักไหล่ช่วยเมื่อยกแขนไม่ขึ้น | วัดมุมความเอียงของแนวกระดูกสันหลัง (Trunk Lean) และแนวเส้นลาดไหล่ (Shoulder Hike) เทียบกับแนวแกนหลักอ้างอิง หากค่าพิกัดมีการขยับเกิน threshold ทางคลินิกในขณะทำท่าทาง จะบันทึกเป็น compensation flag |
| **Symmetry Index (SI)** | ดัชนีความสมมาตรระหว่างร่างกายซีกซ้ายและซีกขวา เพื่อดูระดับความแตกต่างของการอ่อนแรงครึ่งซีก | คำนวณโดยใช้สมการเปรียบเทียบผลต่างของ ROM หรือความเร็วระหว่างฝั่งขวาและซ้าย: SI \= abs(X\_left \- X\_right) / (0.5 \* (X\_left \+ X\_right)) โดยค่า 0% หมายถึงสมมาตรสมบูรณ์ |
| **Spatiotemporal Gait Parameters** | ลักษณะทางกายภาพของการก้าวเดิน จังหวะ ความยาว ความถี่ก้าว (Cadence) และความมั่นคงของการก้าวขา | วิเคราะห์จากพิกัดข้อเท้า (Ankle) และนิ้วเท้า (Toes) บนระนาบเดิน เพื่อสกัดรอบจังหวะเท้าแตะพื้น (Stance Phase), เท้าลอย (Swing Phase), Stride Length และ Cadence หรือจำนวนก้าวต่อนาที |
| **Pelvic Instability (Trendelenburg Sign)** | ประเมินความไม่มั่นคงของกระดูกเชิงกรานและพฤติกรรมการเดินแบบเตาะแตะ (Waddling / Trendelenburg Gait) ซึ่งสัมพันธ์กับความอ่อนแรงของกล้ามเนื้อสะโพก | วัดมุมการเอียงของกระดูกเชิงกรานในระนาบ frontal plane จาก keypoints ฝั่งซ้ายและขวาของสะโพก หากมีค่า pelvic drop / hip drop เกิน threshold ขณะอยู่ในช่วง single support จะบันทึกเป็น possible Trendelenburg sign |
| **Single Support Phase (%SSP)** | สัดส่วนระยะเวลาที่ยืนรับน้ำหนักบนขาข้างเดียว เพื่อประเมินความมั่นคงในการเดินและความเสี่ยงในการหกล้ม | คำนวณจากรอบการเดิน (Gait Cycle) โดยหาช่วงเวลาที่มีเท้าข้างเดียวสัมผัสพื้น แล้วหารด้วยเวลารวมของ 1 gait cycle ผู้ป่วยที่มีความไม่มั่นคงมักมีค่า %SSP ลดลง |
| **Double Support Phase (%DSP)** | สัดส่วนระยะเวลาที่สองเท้าสัมผัสพื้นพร้อมกัน ใช้ดูพฤติกรรมการเดินแบบระมัดระวังหรือไม่มั่นคง | คำนวณจากช่วงเวลาที่เท้าซ้ายและขวาสัมผัสพื้นพร้อมกันเทียบกับเวลารวมของ gait cycle หาก %DSP สูงผิดปกติ อาจสะท้อนว่าผู้ป่วยหลีกเลี่ยงการยืนรับน้ำหนักบนขาข้างเดียว |

## 

## **4\. แผนการดำเนินงานรายสัปดาห์ (Detailed Sprint Plan: 8 สัปดาห์)**

เพื่อให้โครงการสอดรับและประกอบเข้ากับแพลตฟอร์มหลักของทีมอื่นๆ ได้ตามกรอบเวลา โครงการย่อย Team 5 มีกำหนดส่งมอบชิ้นงานสำคัญประจำ Sprint ดังรายละเอียดตารางต่อไปนี้:

| สัปดาห์ที่ / Sprint | กิจกรรมหลัก (Key Activities) | สิ่งที่ต้องส่งมอบ (Deliverables) |
| :---- | :---- | :---- |
| สัปดาห์ที่ 1 — Sprint 0: System Design | ศึกษาทฤษฎีด้านชีวกลศาสตร์, Pose Estimation และ Clinical Movement Features พร้อมออกแบบ 5-Layer Architecture, Data Schema, API Contract ภายในระบบ และ UI Wireframe ฝั่งผู้ป่วย/แพทย์ | Architecture Design, Data Schema, API Contract Draft, UI Wireframe |
| สัปดาห์ที่ 2 — Sprint 1: Backend & Storage | พัฒนา Backend API สำหรับจัดการผู้ใช้, ผู้ป่วย, assessment session, การอัปโหลดวิดีโอผ่าน Signed URL, การจัดเก็บ keypoints/features และระบบจัดเก็บไฟล์ | Backend API Prototype, Database Schema, Video Upload API, Storage Structure |
| สัปดาห์ที่ 3 — Sprint 2: Client Web App | พัฒนา Web App สำหรับผู้ป่วยบนสมาร์ทโฟน ให้สามารถดู tutorial/camera setup guide, บันทึกหรือเลือกวิดีโอที่ถ่ายเสร็จแล้ว และอัปโหลดไปยัง backend ได้ โดย real-time skeleton overlay เป็น optional/future work | Client Web App Prototype พร้อมระบบ video upload, session metadata และ upload status |
| สัปดาห์ที่ 4 — Sprint 3: Feature Extraction | พัฒนา Python Feature Extraction Module เพื่อคำนวณ joint angle, ROM, angular velocity, smoothness, compensation indicators, symmetry index, pelvic drop angle, single/double support phase, cadence, task duration และ pose quality score จาก keypoints | Feature Extraction Library, Feature Output Spec, ตัวอย่างผลลัพธ์จากวิดีโอทดสอบ |
| สัปดาห์ที่ 5 — Sprint 4: Rule-based / Lightweight ML Screening | พัฒนา Screening Module เพื่อ flag movement limitation, compensation pattern หรือ risk level เบื้องต้นจาก clinical features โดยเริ่มจาก rule-based threshold และอาจเพิ่ม Random Forest/XGBoost หากมีข้อมูลตารางเพียงพอ | Screening Module เบื้องต้น, Prediction/Flag API, confidence score และผลจำแนกอย่างน้อย 2-3 classes/flags |
| สัปดาห์ที่ 6-7 — Sprint 5: Doctor Dashboard | พัฒนา Admin/Doctor Dashboard สำหรับดูข้อมูลผู้ป่วย วิดีโอ playback, skeleton/keypoint overlay หรือ timeline, ค่า clinical features, กราฟผลลัพธ์ screening และระบบเขียน feedback กลับไปยังผู้ป่วย โดยลด 3D visualization ซับซ้อนออกจาก prototype แรก | Doctor Dashboard Prototype, video playback, feature visualization, screening result display, feedback function |
| สัปดาห์ที่ 8 — Sprint 6: Integration & Final Report | ทดสอบระบบแบบ End-to-End ตั้งแต่ผู้ป่วยอัปโหลดวิดีโอ ส่งข้อมูล ประมวลผล pose/keypoints, feature extraction, screening ไปจนถึงแพทย์ดูผลและส่ง feedback พร้อมตรวจสอบ data flow, privacy และ security เบื้องต้น | End-to-End Prototype, Integration Verification Report, Demo Scenario, User Guide, Final Technical Report |

เมื่อสิ้นสุดโครงการ ระบบควรสามารถสาธิตการทำงานครบ flow ได้ในระดับ prototype โดยผู้ป่วยสามารถอัปโหลดวิดีโอการเคลื่อนไหวผ่านเว็บ ระบบ backend สามารถประมวลผล pose/keypoints, features และ screening เบื้องต้นได้ และแพทย์สามารถดูผลวิเคราะห์พร้อมให้ feedback ผ่าน dashboard ได้ ทั้งนี้ระบบถูกออกแบบให้เป็น Clinical Decision Support ไม่ใช่ระบบวินิจฉัยโรคแทนแพทย์

## **5\. ตัวชี้วัดความสำเร็จและเกณฑ์การยอมรับ (KPIs & Acceptance Criteria)**

•          **Patient App Upload & Backend Processing:** เว็บแอปพลิเคชันฝั่งผู้ป่วยต้องสามารถบันทึกหรือรับวิดีโอ movement task ความยาวประมาณ 10-15 วินาทีและอัปโหลดเข้าสู่ระบบได้สำเร็จ โดย backend ต้องสามารถประมวลผล pose/keypoints และสร้างผลลัพธ์เบื้องต้นได้ภายในเวลาที่เหมาะสมสำหรับ prototype เช่น 30-60 วินาทีต่อวิดีโอ ทั้งนี้ real-time skeleton preview ไม่ถือเป็น core acceptance criterion ในระยะต้น

•          **Video Upload & Data Reliability:** ระบบ backend ต้องสามารถรับและจัดเก็บวิดีโอหรือ keypoint data จากฝั่งผู้ป่วยได้อย่างถูกต้อง โดยข้อมูล assessment session, video metadata, extracted features, screening result และ doctor feedback ต้องถูกบันทึกลงฐานข้อมูลครบถ้วนอย่างน้อย 95% ของกรณีทดสอบทั้งหมด และสามารถเรียกดูย้อนหลังผ่าน dashboard ได้

•          **Feature Extraction Correctness:** โมดูล Feature Extraction ต้องสามารถคำนวณค่าหลักทางชีวกลศาสตร์ได้อย่างน้อย 6 กลุ่ม เช่น joint angle, ROM, angular velocity, movement smoothness, compensation indicators, symmetry index, pelvic drop angle, single/double support phase, cadence หรือ task duration โดยผลลัพธ์ต้องอยู่ในรูปแบบที่สอดคล้องกับ feature output specification และสามารถตรวจสอบย้อนกลับจากวิดีโอหรือ keypoints ต้นทางได้

•          **Screening Performance:** Screening Module ต้องสามารถ flag movement class, compensation pattern หรือ risk level เบื้องต้นได้อย่างน้อย 2-3 classes/flags พร้อม confidence score หรือ explanation โดยระยะ prototype จะใช้ rule-based threshold และ simulated abnormal gait/test cases เป็น baseline ก่อน หากมี labeled dataset เพิ่มเติมจึงประเมิน accuracy/F1-score แยกในขั้นถัดไป

•          **Doctor Dashboard Usability & Playback:** Doctor Dashboard ต้องสามารถแสดงข้อมูลผู้ป่วย วิดีโอ playback, skeleton/keypoint overlay หรือ timeline, ค่า clinical features, กราฟผลลัพธ์ และผล screening ได้อย่างชัดเจน โดยการเลื่อนดูวิดีโอหรือกราฟต้องทำงานได้ลื่นไหล ไม่มีอาการค้างที่กระทบต่อการใช้งานหลัก และแพทย์สามารถบันทึก feedback กลับไปยังผู้ป่วยได้

•          **End-to-End System Integration:** ระบบต้องสามารถทำงานครบ flow ตั้งแต่ผู้ป่วยเปิดเว็บ อัปโหลดวิดีโอ ส่งข้อมูลไปยัง backend ประมวลผล pose/keypoints, feature extraction และ screening แสดงผลใน dashboard ฝั่งแพทย์ และบันทึก feedback กลับเข้าระบบได้ โดยผ่านการทดสอบ end-to-end scenario อย่างน้อย 3 กรณี ได้แก่ normal movement, compensation detected และ limited/unsafe movement

•          **Privacy & Security Baseline:** ระบบต้องมีมาตรการพื้นฐานด้านความปลอดภัยของข้อมูลผู้ป่วย เช่น การแยกสิทธิ์ผู้ใช้ระหว่างผู้ป่วยและแพทย์ การใช้ Patient ID แทนข้อมูลระบุตัวตนโดยตรง การไม่แสดงข้อมูลผู้ป่วยโดยไม่ได้รับสิทธิ์ การจัดเก็บข้อมูลอย่างเป็นระบบ การเข้ารหัสข้อมูลสำคัญ และการบันทึก metadata/audit log ที่จำเป็นต่อการตรวจสอบย้อนหลัง เพื่อรองรับการพัฒนาต่อด้าน privacy และ PDPA compliance ในระยะถัดไป

##  

## **6\. ข้อกำหนดทางเทคนิคและการรักษาความปลอดภัยข้อมูล (Technical Constraints & Security Governance)**

**กรอบเครื่องมือการพัฒนา:** ฝั่งเว็บแอปพลิเคชันเลือกใช้ React 18 / Next.js, ภาษา TypeScript และ Tailwind CSS สำหรับการจัดการหน้าจอเพื่อรักษาความเป็นอันหนึ่งอันเดียวกันกับระบบของ Team 2 ขณะที่ระบบสกัดคุณสมบัติและสถาปัตยกรรมคลาวด์หลังบ้านจะใช้ FastAPI (Python 3.11+) ร่วมกับ MediaPipe, NumPy/Pandas, SciPy และชุดไลบรารีวิเคราะห์ทางชีวกลศาสตร์ สำหรับ screening ระยะ prototype จะเริ่มจาก rule-based threshold และอาจใช้ Scikit-learn/XGBoost หากมีข้อมูลตารางเพียงพอ ส่วน deep learning ขั้นสูงจะเชื่อมต่อกับ Team 6 ในระยะถัดไป

**การกำกับดูแลความเป็นส่วนตัว (PDPA & Compliance):** เนื่องจากไฟล์ภาพวิดีโอท่าทางการเคลื่อนไหวของคนไข้และประวัติประเมินจัดเป็นข้อมูลส่วนบุคคลทางการแพทย์ที่มีความอ่อนไหวสูง (Sensitive Personal Health Information \- PHI) ระบบจึงมีข้อบังคับห้ามทำการบันทึกหรือเก็บข้อมูลภาพดิบแบบ Plaintext ไว้ที่เครื่องลูกข่าย (Client-side Web Storage) อย่างเด็ดขาด และไฟล์วิดีโอที่ถูกส่งขึ้น Cloud จะถูกจัดเก็บผ่านสิทธิ์การเข้าถึงความปลอดภัยสูงแบบ Signed URL และผ่านโมดูลการเข้าบันทึกประวัติการตรวจสอบ (Audit Log Service) ทุกครั้งที่มีการเรียกใช้งานโดยผู้เชี่ยวชาญหรือแพทย์ตามแนวทางมาตรฐานกลาง ข้อมูลที่จัดเก็บในฐานข้อมูลจะใช้ Patient ID แทนชื่อจริง แยกสิทธิ์การเข้าถึงระหว่างผู้ป่วยและแพทย์ และเข้ารหัสข้อมูลสำคัญทั้งในระดับ storage/database ตามความเหมาะสม

**คำอธิบาย transformation\_matrix\_6dof:** ค่า transformation\_matrix\_6dof คือเมทริกซ์การแปลงพิกัด 4x4 (4x4 Homogeneous Transformation Matrix) ที่ใช้ระบุตำแหน่งและการหมุนของร่างกายหรือข้อต่อในโลกสามมิติ โดย 6DOF หมายถึงการเลื่อนตำแหน่ง 3 แกน (X, Y, Z) และการหมุน 3 แกน (Pitch, Yaw, Roll) เมทริกซ์นี้ช่วยให้ Team 1/Team 2 หรือระบบ Digital Twin สามารถนำข้อมูลไปวางในพิกัดโลกหรือใช้กับ WebGL/Three.js ได้โดยตรง เช่น การนำไปครอบบนโมเดล 3 มิติด้วยเมทริกซ์ 4x4

ด้านล่างนี้คือตัวอย่างรูปแบบโครงสร้าง JSON Payload ที่ออกแบบไว้สำหรับบันทึกและแลกเปลี่ยนข้อมูลคุณลักษณะการขยับและเมทริกซ์ 6DOF ร่วมกับ Team 1:

{  
   "session\_id": "SESS-MOVE-2026-X982",  
   "patient\_id": "PATIENT-7712",  
   "timestamp": "2026-06-03T21:26:53Z",  
   "video\_metadata": {  
 	"duration\_sec": 12.4,  
 	"fps": 30,  
 	"view": "frontal",  
 	"task\_type": "gait\_walk"  
   },  
   "clinical\_metrics": {  
 	"joint\_angles": {  
   	"shoulder\_flexion\_max\_deg": 142.5,  
   	"elbow\_extension\_min\_deg": 35.2,  
   	"hip\_flexion\_max\_deg": 38.6,  
   	"knee\_flexion\_max\_deg": 61.4  
 	},  
 	"smoothness": {  
   	"jerk\_score": 124.8,  
   	"sparc\_index": \-2.31  
 	},  
 	"compensation": {  
   	"trunk\_lean\_detected": true,  
   	"trunk\_lean\_max\_angle\_deg": 18.4,  
   	"trendelenburg\_sign\_detected": true,  
   	"pelvic\_drop\_angle\_deg": 12.1  
 	},  
 	"gait\_parameters": {  
   	"single\_support\_phase\_percent": 34.5,  
   	"double\_support\_phase\_percent": 30.2,  
   	"cadence\_steps\_per\_min": 95.5,  
   	"stride\_length\_cm": 82.3  
 	},  
 	"symmetry\_index\_score": 0.24,  
 	"pose\_quality": {  
   	"mean\_keypoint\_confidence": 0.88,  
   	"occlusion\_warning": false  
 	}  
   },  
   "screening\_result": {  
 	"risk\_level": "moderate",  
 	"flags": \[  
   	"trunk\_compensation",  
   	"possible\_trendelenburg\_sign"  
 	\],  
 	"confidence\_score": 0.76  
   },  
   "transformation\_matrix\_6dof": \[  
 	\[0.984, \-0.173, 0.043, 12.5\],  
 	\[0.171, 0.981, 0.092, \-4.2\],  
 	\[-0.058, \-0.083, 0.994, 150.8\],  
 	\[0.0, 0.0, 0.0, 1.0\]  
   \]  
 }

## **7\. การประสานงานและความเชื่อมโยงระหว่างทีม (Cross-Team Dependencies)**

ความสำเร็จของโครงงานย่อยนี้ขึ้นอยู่กับการเชื่อมต่อ API Contract ร่วมกับระบบหลักอย่างใกล้ชิด:

•          **การประสานงานร่วมกับ Team 1 (Core Platform):** Team 5 จำเป็นต้องใช้ API Ingestion หรือ Signed URL Upload ของทีม 1 ในการอัปโหลดไฟล์วิดีโอหลักขึ้นระบบ และเมื่อประมวลผลวิดีโอเสร็จแล้วจะส่งผลลัพธ์กลับไปยังระบบกลางผ่าน Microservice API ในรูปแบบ JSON Payload เช่น POST /api/team1/movement-data โดยไม่จำเป็นต้องรวม codebase เข้าด้วยกันโดยตรง

•          **การประสานงานร่วมกับ Team 2 (Digital Twin Interface):** หน้าจอบางส่วนของแอปพลิเคชันแพทย์ในโครงงานนี้จะมีการจัดมาตรฐานหน้าต่างประวัติผู้ป่วยให้สอดคล้องกับ Dashboard ของ Team 2 และสามารถส่ง keypoints หรือ transformation\_matrix\_6dof เพื่อรองรับการเชื่อมต่อกับ Digital Twin/Three.js ในระยะถัดไป

•          **การประสานงานร่วมกับ Team 6 (Advanced AI & Disease Progression Analytics):** Team 5 จะรับผิดชอบการสกัด keypoints และ clinical kinematic features ที่ตรวจสอบย้อนกลับได้ ส่วนการวิเคราะห์ deep learning ขั้นสูง เช่น ST-GCN, PINNs หรือ disease progression index จะเป็นขอบเขตหลักของ Team 6 โดย Team 5 จะส่งข้อมูล time-series skeleton และ feature payload ให้ Team 6 ใช้ต่อเมื่อ API contract พร้อม

