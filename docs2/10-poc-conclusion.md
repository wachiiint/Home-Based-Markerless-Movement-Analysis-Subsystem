# 10 — Proof-of-Concept Conclusion

> The result of this round in one read. New to the project? Start here, then follow the links.

---

## 1. What was demonstrated

**A camera alone can record and analyse a patient's movement for tele-rehabilitation.** A patient
films a short clip of one prescribed leg movement on an ordinary phone — no markers, no wearables,
no special hardware — and the local application returns, in about a minute:

- **Joint angles and range of motion** for hip, knee, and ankle tasks, for **both legs**, with the
  instructed leg screened against clinical thresholds
- **Movement smoothness** (LDLJ, SPARC, movement-unit count) per side
- The **angle-through-time graph** of the whole movement, not just its extremes
- An **annotated skeleton video**, so a human can verify the right person was tracked
- A best-effort **3D motion simulation** with a muscle-length overlay
- **Left-right comparison** across two recordings, one clip per leg, with mismatched pairs refused
- A **stored history** — every result is kept on disk and can be reopened later

Everything runs locally. The uploaded video is never stored. All of it is
**decision support, not diagnosis**.

## 2. What the numbers can and cannot claim

Honesty is the project's core convention, so the limits are stated as plainly as the abilities:

- Every camera-derived quantity is an **estimate**. Published markerless systems show joint-angle
  errors of roughly 7 to 15 degrees against laboratory reference; **this system's own accuracy has
  not been measured** — no goniometer or motion-capture comparison was run. That validation is the
  first scientific task of the next phase.
- The screening thresholds are clinician-confirmed **for elderly patients only** (2026-08-04).
- Poor recordings are **flagged but not refused** — the hard-reject guard is designed but not built.
- The 3D reconstruction **frequently falls back to 2D**, which is reported, and 2D sagittal
  measurement is itself the established clinical method.

The full account is [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md).

## 3. Decisions the PoC settled

| Decision | Outcome |
|----------|---------|
| Target population | Elderly sarcopenia screening first; the end goal is use with anyone |
| Metric scale | ChArUco board for the PoC; bone-length scaling designed and postponed to the prototype |
| Storage | Local human-readable files plus export and re-import; no database |
| Measure versus compare | Analysis measures one recording; comparisons are separate queries over stored results |
| Symmetry basis | Across two recordings (one per leg), never within one clip — the far leg in a side view is unreliable |
| Screening layer (timed tests) | Out of scope — a separate build |

## 4. What the prototype phase starts from

Three inputs, to be combined into one new proposal:

1. **This conclusion** — what works, what is designed but unbuilt
   ([04-planning.md](04-planning.md) part 4 is the itemised carry-over list)
2. **The professor's proposal (2026-08-07)** — IMU sensors for ground-truth data gathering, possible
   AI model training for better keypoint extraction from video, and a more solid application
3. **The engineering reset** — the prototype is rebuilt deliberately, with human-reviewed code,
   rather than grown from the PoC's exploratory codebase

## 5. Where to read more

| Question | Document |
|----------|----------|
| What is this project and why? | [01-specification.md](01-specification.md) |
| How does it work, stage by stage? | [02-pipeline.md](02-pipeline.md) |
| What remains, and what carries forward? | [04-planning.md](04-planning.md) |
| How do I install and run it? | [06-setup.md](06-setup.md) |
| How accurate is it, honestly? | [07-evaluation-and-limitations.md](07-evaluation-and-limitations.md) |
