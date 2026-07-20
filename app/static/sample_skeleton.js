// DEV/PREVIEW ONLY — synthetic H36M17 walking skeleton for the "04 / 3D" panel.
// Lets you see the real viewer3d.js render before the MotionBERT weights exist.
// Safe to delete once real 3D works: remove this file, the #preview-3d button in
// index.html, and the preview wiring in app.js.
//
// Skeleton layout must match app/services/lifting/skeleton_convert.py (H36M17).

const JOINT_NAMES = [
  'pelvis', 'r_hip', 'r_knee', 'r_ankle', 'l_hip', 'l_knee', 'l_ankle',
  'spine', 'thorax', 'neck_nose', 'head',
  'l_shoulder', 'l_elbow', 'l_wrist', 'r_shoulder', 'r_elbow', 'r_wrist',
];
const EDGES = [
  [0, 1], [1, 2], [2, 3], [0, 4], [4, 5], [5, 6],
  [0, 7], [7, 8], [8, 9], [9, 10], [8, 11], [11, 12], [12, 13], [8, 14], [14, 15], [15, 16],
];

// Forward-kinematics rig. Every limb swing is a rotation about X (the left-right
// axis = the sagittal plane), so a joint's world rotation is just the sum of its
// ancestors' angles — rotations about one axis commute and add.
const PARENT = { 0: -1, 7: 0, 8: 7, 9: 8, 10: 9, 1: 0, 2: 1, 3: 2, 4: 0, 5: 4, 6: 5, 11: 8, 12: 11, 13: 12, 14: 8, 15: 14, 16: 15 };
const OFFSET = {
  0: [0, 0, 0], 7: [0, 0.20, 0], 8: [0, 0.20, 0], 9: [0, 0.10, 0.03], 10: [0, 0.10, -0.02],
  1: [-0.09, 0, 0], 2: [0, -0.42, 0], 3: [0, -0.42, 0],
  4: [0.09, 0, 0], 5: [0, -0.42, 0], 6: [0, -0.42, 0],
  11: [0.17, -0.02, 0], 12: [0.02, -0.26, 0], 13: [0.01, -0.24, 0],
  14: [-0.17, -0.02, 0], 15: [-0.02, -0.26, 0], 16: [-0.01, -0.24, 0],
};
const ORDER = [0, 7, 8, 9, 10, 1, 2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16]; // parents before children

const rotX = (v, a) => {
  const c = Math.cos(a), s = Math.sin(a);
  return [v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c];
};

function buildFrame(cycleFraction) {
  const p = 2 * Math.PI * cycleFraction;
  const HIP = 0.5, KNEE = 0.9, SHOULDER = 0.35, ELBOW = 0.35;
  const angle = {
    1: HIP * Math.sin(p),                 // right hip swings forward/back
    4: -HIP * Math.sin(p),                // left hip opposite
    2: KNEE * Math.max(0, Math.sin(p)),   // right knee bends on back-swing
    5: KNEE * Math.max(0, -Math.sin(p)),  // left knee opposite
    14: -SHOULDER * Math.sin(p),          // arms swing opposite to legs
    11: SHOULDER * Math.sin(p),
    15: ELBOW, 12: ELBOW,                 // slight constant elbow bend
  };
  const bob = 0.02 * Math.cos(2 * p);     // vertical bob, twice per stride
  const world = {}, cum = {};
  for (const j of ORDER) {
    const par = PARENT[j];
    if (par < 0) { world[j] = [0, bob, 0]; cum[j] = angle[j] || 0; continue; }
    const off = rotX(OFFSET[j], cum[par]);
    world[j] = [world[par][0] + off[0], world[par][1] + off[1], world[par][2] + off[2]];
    cum[j] = cum[par] + (angle[j] || 0);
  }
  const arr = [];
  for (let j = 0; j < 17; j += 1) arr.push(world[j]);
  return arr;
}

// Returns a payload shaped exactly like the backend's build_pose3d_payload output.
export function buildSamplePose3dPayload({ frames = 60, cycles = 2, fps = 20 } = {}) {
  const seq = Array.from({ length: frames }, (_, i) => buildFrame((cycles * i) / frames));
  return {
    num_frames: frames,
    fps,
    joint_names: JOINT_NAMES,
    edges: EDGES,
    frames: seq,
    valid_mask: Array(frames).fill(true),
    analyzed_side: 'right',
    analysis_mode: '3d',
    lift_reliable: true,
    lift_warnings: [],
  };
}
