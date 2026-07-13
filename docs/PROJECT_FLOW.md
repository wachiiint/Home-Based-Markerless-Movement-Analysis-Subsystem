# Project Flow

1. Patient uploads a movement video in the frontend.
2. Backend receives the session and calls this service through `MEDIAPIPE_SERVICE_URL`.
3. This service validates the internal API key, reads the multipart video, analyzes movement, and returns the fixed assessment contract.
4. Backend stores the result and moves the session toward doctor review.
5. Doctor dashboard reads `risk_level`, `confidence_score`, pose quality, and task metrics.
