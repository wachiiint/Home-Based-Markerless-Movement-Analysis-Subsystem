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
const MUSCLE_RADIUS = 0.028; // belly radius (units of pelvis-head); tapers to the tendons
const MUSCLE_TUBE_SEGMENTS = 24;

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
      // Anchors: [jointA, jointB, t] -> a point t of the way along that bone.
      const anchors = (def.anchors || []).map((a) => ({ a: a[0], b: a[1], t: a[2] }));
      if (anchors.length < 2) continue;
      const material = new THREE.MeshStandardMaterial({ color: COLOR_MUSCLE_SHORT.clone(), roughness: 0.55 });
      const mesh = new THREE.Mesh(new THREE.BufferGeometry(), material);
      mesh.visible = musclesVisible;
      skeleton.add(mesh);
      muscles.push({ mesh, anchors, bulge: def.bulge || 0, length: def.length });
    }
  }

  const _v = new THREE.Vector3();

  // Route a muscle as a smooth curve through its anchor points (each a fraction
  // along a bone, so it bends with the limb), bowed sideways into a belly, and
  // coloured by the per-frame length. Geometry is rebuilt per shown frame -- fine
  // for a scene this small and the on-demand (non-continuous) render loop.
  function placeMuscle(muscle, pose) {
    const pts = muscle.anchors.map(({ a, b, t }) => new THREE.Vector3().lerpVectors(pose[a], pose[b], t));
    // Bow the interior points off the origin->insertion axis to form a belly.
    if (muscle.bulge) {
      const axis = _v.subVectors(pts[pts.length - 1], pts[0]);
      if (axis.lengthSq() > 1e-9) {
        axis.normalize();
        let perp = new THREE.Vector3().crossVectors(axis, UP);
        if (perp.lengthSq() < 1e-6) perp = new THREE.Vector3(1, 0, 0);
        const dir = new THREE.Vector3().crossVectors(axis, perp.normalize()).normalize();
        for (let i = 1; i < pts.length - 1; i += 1) {
          const s = Math.sin((i / (pts.length - 1)) * Math.PI); // 0 at ends, 1 mid
          pts[i].addScaledVector(dir, muscle.bulge * s);
        }
      }
    }
    const curve = new THREE.CatmullRomCurve3(pts);
    // Radius tapers from thin tendon ends to a fuller belly.
    const radius = (i, n) => MUSCLE_RADIUS * (0.4 + 0.6 * Math.sin((i / n) * Math.PI));
    muscle.mesh.geometry.dispose();
    muscle.mesh.geometry = tubeGeometry(curve, MUSCLE_TUBE_SEGMENTS, radius);
    const value = muscle.length[Math.min(frameIndex, muscle.length.length - 1)];
    muscle.mesh.material.color.copy(COLOR_MUSCLE_SHORT).lerp(COLOR_MUSCLE_LONG, value);
  }

  // A tube of varying radius along a curve (three's TubeGeometry is constant-radius).
  function tubeGeometry(curve, segments, radiusFn) {
    const radial = 8;
    const positions = [];
    const indices = [];
    const frames = curve.computeFrenetFrames(segments, false);
    for (let i = 0; i <= segments; i += 1) {
      const p = curve.getPointAt(i / segments);
      const N = frames.normals[i];
      const B = frames.binormals[i];
      const r = radiusFn(i, segments);
      for (let j = 0; j <= radial; j += 1) {
        const a = (j / radial) * Math.PI * 2;
        positions.push(
          p.x + r * (Math.cos(a) * N.x + Math.sin(a) * B.x),
          p.y + r * (Math.cos(a) * N.y + Math.sin(a) * B.y),
          p.z + r * (Math.cos(a) * N.z + Math.sin(a) * B.z),
        );
      }
    }
    const cols = radial + 1;
    for (let i = 0; i < segments; i += 1) {
      for (let j = 0; j < radial; j += 1) {
        const p0 = i * cols + j;
        indices.push(p0, p0 + 1, p0 + cols, p0 + 1, p0 + cols + 1, p0 + cols);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    return geometry;
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
