@AGENTS2.md

---

# Working with Wachi (project owner)

Context for agents working in Wachi's sessions. The shared project state lives in `AGENTS2.md`
(imported above) — this file is about **how to work**, not what the project is.

- **Roles.** Wachi acts as **project manager and documentation owner**. Application code is
  implemented and decided by teammates — do not restructure app code on your own initiative;
  propose, and let the team decide. Docs (`docs2/`, `README.md`, this file) are Wachi's territory.
- **Pace.** One focused change at a time, explained simply, with a check-in before the next piece.
  No big-bang rewrites.
- **Writing style.** Simple and beginner-friendly, short sentences. **Never use the § symbol** —
  write "section" or "part" instead.
- **Git.** Commit or push only when asked. Small, story-telling commits.
- **Setup steps are guidance, not actions.** Never download models or clone repositories on the
  user's behalf — write the CLI steps into the docs instead.
- **Current focus.** The proof of concept is concluding (2026-08-07). The next piece of work is the
  **prototype-phase proposal**: combine `docs2/10-poc-conclusion.md` with the professor's proposal
  (IMU sensors for ground-truth data gathering, possible AI model training for better keypoint
  extraction from video, a more solid application). Prototype engineering is deliberate and
  human-reviewed rather than exploratory.
- **The doctor's confirmed inputs (2026-08-04).** ROM thresholds are clinically sensible for
  elderly patients; other populations need their own review. Movement instruction phrasing awaits
  the doctor's review of recorded example videos.
