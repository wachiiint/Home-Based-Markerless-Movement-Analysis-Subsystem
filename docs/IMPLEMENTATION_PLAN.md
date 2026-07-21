# Implementation Plan

## Phase 1: Scaffold and Docs

Create the repository structure, documentation, environment example, and dependency metadata.

## Phase 2: API-Compatible Skeleton

Implement FastAPI app startup, `/health`, `/api/movement/assess`, API-key auth, multipart parsing, task/view validation, response models, and `FAKE_MODE`.

Stop after this phase for review.

## Phase 3: Video and RTMPose Inference

Add video decode, metadata, frame subsampling, model loading, rtmlib inference, subject selection, and CPU fallback.

## Phase 4: Quality and Biomechanics MVP

Add quality metrics, smoothing, kinematics, ROM aggregation, screening rules, and temp-file cleanup.
