// 3D skeleton viewer for the lifted MotionBERT output (demo UI only).
//
// The payload is root-relative and unitless, and MotionBERT's axis convention
// is not something we want to hard-code. So orientation is derived from the
// skeleton itself: the mean pelvis->head vector is the body's "up", and the
// same vector sets the scale (1 unit = pelvis-to-head). That keeps the viewer
// correct even if the lifter or its export convention changes.

import * as THREE from 'three';
import { OrbitControls } from '/static/vendor/OrbitControls.js';

const PELVIS = 0;
const HEAD = 10;
const RIGHT_LEG = new Set([1, 2, 3]);
const LEFT_LEG = new Set([4, 5, 6]);
const UP = new THREE.Vector3(0, 1, 0);

// Tuned for the light panel background of styles.css (brand green #16764f).
const COLOR_ANALYZED = 0x16764f; // the leg the metrics were measured from
const COLOR_OTHER = 0xc3cfc9; // de-emphasised opposite leg
const COLOR_BODY = 0x8a9993; // spine and arms
const COLOR_JOINT = 0x12201b;
const COLOR_GRID = 0xd1ddd7;
const COLOR_GRID_SUB = 0xe6f3ec;

// Muscle overlay (M-A): length proxy coloured contracted (warm) -> stretched (cool).
const COLOR_MUSCLE_SHORT = new THREE.Color(0xd9534f); // most shortened (length 0)
const COLOR_MUSCLE_LONG = new THREE.Color(0x3b7fd0); // most stretched (length 1)
const MUSCLE_OFFSET = 0.05; // lateral offset (units of pelvis-head) to fan tubes off the bone
const MUSCLE_RADIUS = 0.03;

// Rotate so the body stands upright and rescale to pelvis-head = 1 unit.
function normalizeFrames(frames) {
  const up = new THREE.Vector3();
  let heightSum = 0;
  let counted = 0;
  for (const joints of frames) {
    const pelvis = new THREE.Vector3(...joints[PELVIS]);
    const head = new THREE.Vector3(...joints[HEAD]);
    const spine = new THREE.Vector3().subVectors(head, pelvis);
    const length = spine.length();
    if (length < 1e-6) continue;
    up.add(spine.clone().divideScalar(length));
    heightSum += length;
    counted += 1;
  }
  if (!counted) return frames.map((joints) => joints.map((p) => new THREE.Vector3(...p)));

  const height = heightSum / counted;
  const quaternion = new THREE.Quaternion().setFromUnitVectors(up.normalize(), UP);
  return frames.map((joints) =>
    joints.map((p) =>
      new THREE.Vector3(...p).applyQuaternion(quaternion).divideScalar(height),
    ),
  );
}

function boneColor(edge, analyzedSide) {
  const [, child] = edge;
  const isLeg = LEFT_LEG.has(child) || RIGHT_LEG.has(child);
  if (!isLeg) return COLOR_BODY;
  if (!analyzedSide) return COLOR_BODY;
  const side = LEFT_LEG.has(child) ? 'left' : 'right';
  return side === analyzedSide ? COLOR_ANALYZED : COLOR_OTHER;
}

export function mountViewer(container) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
  camera.position.set(2.2, 0.6, 2.2);

  // preserveDrawingBuffer keeps the canvas readable via toDataURL (snapshots);
  // negligible cost for a scene this small.
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.1, 0);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xd1ddd7, 2.2));
  const key = new THREE.DirectionalLight(0xffffff, 1.2);
  key.position.set(3, 5, 4);
  scene.add(key);

  const grid = new THREE.GridHelper(4, 16, COLOR_GRID, COLOR_GRID_SUB);
  scene.add(grid);

  const skeleton = new THREE.Group();
  scene.add(skeleton);

  let frames = [];
  let edges = [];
  let bones = [];
  let joints = [];
  let muscles = [];
  let musclesVisible = false;
  let frameIndex = 0;

  function clearSkeleton() {
    for (const mesh of [...bones, ...joints, ...muscles.map((m) => m.mesh)]) {
      skeleton.remove(mesh);
      mesh.geometry.dispose();
      mesh.material.dispose();
    }
    bones = [];
    joints = [];
    muscles = [];
  }

  function buildMuscles(payload) {
    for (const def of payload.muscles || []) {
      const geometry = new THREE.CylinderGeometry(MUSCLE_RADIUS, MUSCLE_RADIUS, 1, 12);
      const material = new THREE.MeshStandardMaterial({ color: COLOR_MUSCLE_SHORT.clone(), roughness: 0.6 });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.visible = musclesVisible;
      skeleton.add(mesh);
      muscles.push({ mesh, a: def.joints[0], b: def.joints[def.joints.length - 1], offset: def.offset, length: def.length });
    }
  }

  // Lay one muscle tube along its origin->insertion segment, pushed sideways off
  // the bone (so antagonists separate) and coloured by its per-frame length.
  function placeMuscle(muscle, pose) {
    const start = pose[muscle.a];
    const end = pose[muscle.b];
    const direction = new THREE.Vector3().subVectors(end, start);
    const length = direction.length();
    if (length < 1e-6) return;
    direction.normalize();
    let perp = new THREE.Vector3().crossVectors(direction, UP);
    if (perp.lengthSq() < 1e-6) perp = new THREE.Vector3(1, 0, 0);
    const ap = new THREE.Vector3().crossVectors(direction, perp.normalize()).normalize();
    const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5).addScaledVector(ap, muscle.offset * MUSCLE_OFFSET);
    muscle.mesh.position.copy(mid);
    muscle.mesh.scale.set(1, length * 0.92, 1);
    muscle.mesh.quaternion.setFromUnitVectors(UP, direction);
    const value = muscle.length[Math.min(frameIndex, muscle.length.length - 1)];
    muscle.mesh.material.color.copy(COLOR_MUSCLE_SHORT).lerp(COLOR_MUSCLE_LONG, value);
  }

  function buildSkeleton(payload) {
    clearSkeleton();
    edges = payload.edges;
    const jointGeometry = new THREE.SphereGeometry(0.035, 16, 12);
    for (let i = 0; i < payload.joint_names.length; i += 1) {
      const mesh = new THREE.Mesh(jointGeometry.clone(), new THREE.MeshStandardMaterial({ color: COLOR_JOINT }));
      skeleton.add(mesh);
      joints.push(mesh);
    }
    for (const edge of edges) {
      // Unit-height cylinder along +Y; scaled/oriented per frame in setFrame.
      const geometry = new THREE.CylinderGeometry(0.018, 0.018, 1, 10);
      const material = new THREE.MeshStandardMaterial({ color: boneColor(edge, payload.analyzed_side) });
      const mesh = new THREE.Mesh(geometry, material);
      skeleton.add(mesh);
      bones.push(mesh);
    }
    buildMuscles(payload);
  }

  function setFrame(index) {
    if (!frames.length) return;
    frameIndex = Math.max(0, Math.min(index, frames.length - 1));
    const pose = frames[frameIndex];
    joints.forEach((mesh, i) => mesh.position.copy(pose[i]));
    bones.forEach((mesh, i) => {
      const [a, b] = edges[i];
      const start = pose[a];
      const end = pose[b];
      const direction = new THREE.Vector3().subVectors(end, start);
      const length = direction.length();
      mesh.position.copy(start).addScaledVector(direction, 0.5);
      mesh.scale.set(1, length, 1);
      if (length > 1e-6) mesh.quaternion.setFromUnitVectors(UP, direction.normalize());
    });
    if (musclesVisible) muscles.forEach((muscle) => placeMuscle(muscle, pose));
  }

  // Drop the skeleton so the lowest joint of the whole clip rests on the grid.
  function groundSkeleton() {
    let lowest = Infinity;
    for (const pose of frames) for (const p of pose) lowest = Math.min(lowest, p.y);
    if (Number.isFinite(lowest)) skeleton.position.y = -lowest;
  }

  function resize() {
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  // Rendered on demand (camera moves, frame changes, resize) rather than from a
  // permanent animation loop: the scene is static between those events.
  function render() {
    renderer.render(scene, camera);
  }

  controls.addEventListener('change', render);
  const observer = new ResizeObserver(() => {
    resize();
    render();
  });
  observer.observe(container);

  return {
    load(payload) {
      frames = normalizeFrames(payload.frames);
      buildSkeleton(payload);
      setFrame(0);
      groundSkeleton();
      resize();
      render();
      return frames.length;
    },
    setFrame(index) {
      setFrame(index);
      render();
    },
    setMusclesVisible(visible) {
      musclesVisible = visible;
      muscles.forEach((muscle) => { muscle.mesh.visible = visible; });
      if (visible && frames.length) muscles.forEach((muscle) => placeMuscle(muscle, frames[frameIndex]));
      render();
    },
    get hasMuscles() {
      return muscles.length > 0;
    },
    get frameCount() {
      return frames.length;
    },
    get frameIndex() {
      return frameIndex;
    },
  };
}
