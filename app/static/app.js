import { mountViewer } from '/static/viewer3d.js';
import { buildSamplePose3dPayload } from '/static/sample_skeleton.js';

const form = document.querySelector('#analysis-form');
const fileInput = document.querySelector('#file');
const fileName = document.querySelector('#file-name');
const sourceVideo = document.querySelector('#source-video');
const resultVideo = document.querySelector('#result-video');
const emptyState = document.querySelector('#empty-state');
const metricsSection = document.querySelector('#metrics-section');
const submitButton = document.querySelector('#submit-button');
const message = document.querySelector('#form-message');
const resultState = document.querySelector('#result-state');

fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (!file) return;
  fileName.textContent = file.name;
  sourceVideo.src = URL.createObjectURL(file);
  sourceVideo.hidden = false;
});

// ---- Calibrated-device picker (01 / INPUT) --------------------------------
const deviceSelect = document.querySelector('#device-select');
const deviceMake = document.querySelector('#device-make');
const deviceModel = document.querySelector('#device-model');

async function loadDevices() {
  // Keep the first "Auto" option, replace the rest on every refresh.
  while (deviceSelect.options.length > 1) deviceSelect.remove(1);
  try {
    const response = await fetch('/api/demo/devices');
    if (!response.ok) return;
    const { devices } = await response.json();
    for (const d of devices) {
      const make = d.make || '';
      const model = d.model || '';
      // Only make/model-bearing devices are addressable from the patient clip;
      // resolution-only calibrations are reached via the "Auto" option.
      if (!make && !model) continue;
      const size = d.image_size ? `${d.image_size[0]}×${d.image_size[1]}` : '';
      const option = document.createElement('option');
      option.value = d.device_id;
      option.dataset.make = make;
      option.dataset.model = model;
      if (d.image_size) {
        option.dataset.w = d.image_size[0];
        option.dataset.h = d.image_size[1];
      }
      option.textContent = `${[make, model].filter(Boolean).join(' ')} · ${size}${d.status !== 'valid' ? ` (${d.status})` : ''}`;
      deviceSelect.appendChild(option);
    }
  } catch (error) {
    console.error(error);
  }
}

// Proactively warn when the chosen calibrated device's resolution won't match the
// uploaded clip: metric 3D is keyed on resolution, so a mismatch silently drops to
// 2D. This is a best-effort heads-up (browser videoWidth can differ from the
// backend for rotated clips); the authoritative reason still comes back post-run.
let clipDims = null;

function checkResolutionMatch() {
  const warn = document.querySelector('#device-warning');
  const option = deviceSelect.selectedOptions[0];
  const dw = Number(option?.dataset.w || 0);
  const dh = Number(option?.dataset.h || 0);
  if (!dw || !clipDims) {
    warn.hidden = true;
    return;
  }
  if (dw === clipDims.w && dh === clipDims.h) {
    warn.hidden = true;
    return;
  }
  warn.hidden = false;
  warn.textContent = `Selected device was calibrated at ${dw}×${dh}, but this clip is ${clipDims.w}×${clipDims.h}. Metric 3D needs a matching resolution — it will fall back to 2D. Recalibrate at ${clipDims.w}×${clipDims.h}, or use a clip recorded at ${dw}×${dh}.`;
}

deviceSelect.addEventListener('change', () => {
  const option = deviceSelect.selectedOptions[0];
  deviceMake.value = option?.dataset.make || '';
  deviceModel.value = option?.dataset.model || '';
  checkResolutionMatch();
});

sourceVideo.addEventListener('loadedmetadata', () => {
  clipDims = { w: sourceVideo.videoWidth, h: sourceVideo.videoHeight };
  checkResolutionMatch();
});

loadDevices();

// Calibration lives on its own page (/calibrate, calibrate.js). New devices show
// up in the picker above on the next load of this page.

const percent = (value) => `${(Number(value) * 100).toFixed(0)}%`;
const label = (key) => key.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

// Both legs are reported: joint_angles keys are side-prefixed (left_/right_) and
// smoothness is nested per side. Render one Left|Right row per metric so the
// clinician compares sides at a glance.
function renderComparison(metrics) {
  const rows = new Map(); // label -> {left, right}
  const cell = (name, side, text) => {
    if (!rows.has(name)) rows.set(name, { left: '—', right: '—' });
    rows.get(name)[side] = text;
  };
  for (const [key, value] of Object.entries(metrics.joint_angles || {})) {
    const side = key.startsWith('left_') ? 'left' : key.startsWith('right_') ? 'right' : null;
    if (!side) continue;
    const name = label(key.replace(/^(left|right)_/, '').replace(/_deg$/, ''));
    cell(name, side, `${Number(value).toFixed(1)}°`);
  }
  for (const [key, value] of Object.entries(metrics.joint_angles_3d || {})) {
    const side = key.startsWith('left_') ? 'left' : key.startsWith('right_') ? 'right' : null;
    if (!side) continue;
    const name = `${label(key.replace(/^(left|right)_/, '').replace(/_3d$/, '').replace(/_deg$/, ''))} (3D)`;
    cell(name, side, `${Number(value).toFixed(1)}°`);
  }
  const smooth = metrics.smoothness || {};
  const smoothMetric = (name, prop, fmt) => {
    for (const side of ['left', 'right']) {
      if (smooth[side] && prop in smooth[side]) cell(name, side, fmt(smooth[side][prop]));
    }
  };
  smoothMetric('Smoothness (SPARC)', 'sparc', (v) => v.toFixed(2));
  smoothMetric('Smoothness (LDLJ)', 'log_dimensionless_jerk', (v) => v.toFixed(2));
  smoothMetric('Movement units', 'n_movement_units', (v) => String(v));

  const body = [...rows.entries()]
    .map(([name, v]) => `<tr><th>${name}</th><td>${v.left}</td><td>${v.right}</td></tr>`)
    .join('');
  const symmetry = metrics.symmetry_index_score;
  const symmetryRow = symmetry != null
    ? `<tr class="span-row"><th>Asymmetry (L/R)</th><td colspan="2">${(symmetry * 100).toFixed(1)}%</td></tr>`
    : '';
  return `<table class="compare-table"><thead><tr><th>Metric</th><th>Left</th><th>Right</th></tr></thead><tbody>${body}${symmetryRow}</tbody></table>`;
}

// Warnings about the declared side are a data-entry / recording problem, not a
// 3D-pipeline problem, so they get their own notice above the analysis one.
const SIDE_WARNINGS = {
  declared_side_did_not_move_most: 'The other leg moved more than the one you selected — check that the correct side was recorded and selected.',
  declared_side_barely_moved: 'The selected leg barely moved in this clip. The range of motion below may not reflect a real attempt.',
};

// Prefixed warnings carry a computed detail after the colon, so they are matched
// by prefix rather than looked up whole.
const PREFIXED_WARNINGS = {
  heavy_tracking_noise: (detail) => `Tracking was unstable —${detail}. Angles were repaired where possible, but re-record with the whole leg clearly in frame.`,
};

const prefixOf = (warning) => warning.split(':')[0];

function renderSideNotice(assessment) {
  const notice = document.querySelector('#side-notice');
  const messages = (assessment.guard_warnings || [])
    .map((w) => {
      if (w in SIDE_WARNINGS) return SIDE_WARNINGS[w];
      const build = PREFIXED_WARNINGS[prefixOf(w)];
      return build ? build(w.slice(w.indexOf(':') + 1)) : null;
    })
    .filter(Boolean);
  notice.hidden = messages.length === 0;
  notice.textContent = messages.join(' ');
}

// Explain the analysis mode instead of silently returning a 2D result: when 3D
// was expected but did not happen, say why (calibration/board guard warnings).
function renderAnalysisNotice(assessment) {
  const notice = document.querySelector('#analysis-notice');
  const warnings = (assessment.guard_warnings || [])
    .filter((w) => !(w in SIDE_WARNINGS) && !(prefixOf(w) in PREFIXED_WARNINGS));
  const board = assessment.board_diagnostics;
  if (assessment.analysis_mode === '3d') {
    notice.className = 'inline-notice ok';
    notice.hidden = false;
    notice.textContent = `Metric 3D active (calibrated).${warnings.length ? ` Notes: ${warnings.join('; ')}` : ''}`;
    return;
  }
  const reasons = [...warnings];
  if (board && board.recommendation && board.recommendation !== 'ok') {
    reasons.push(board.message || `board ${board.recommendation}`);
  }
  if (reasons.length) {
    notice.className = 'inline-notice warn';
    notice.hidden = false;
    notice.textContent = `2D analysis — metric 3D unavailable: ${reasons.join('; ')}`;
  } else {
    notice.hidden = true;
  }
}

// ---- Export (03 / ANALYSIS) ----------------------------------------------
// The panel offers the CSV view of each artifact, because that is the one a
// person opens and reads. The complete JSON record is still served -- its URL
// travels in the response -- but it is for programs, so it gets no button.
// The files live in the session's temp folder and are deleted on TTL expiry,
// so the whole point of these buttons is to save a copy first. Same-origin
// <a download> is all it takes -- no fetch, no blobs.
const exportNote = document.querySelector('#export-note');

// [anchor id, response field, download suffix]
const EXPORT_TARGETS = [
  ['export-assessment-csv', 'assessment_csv_url', 'metrics.csv'],
  ['export-pose2d-csv', 'pose_2d_csv_url', 'pose2d.csv'],
  ['export-pose3d-csv', 'pose_3d_csv_url', 'pose3d.csv'],
];

function renderExports(payload) {
  const sessionId = payload.assessment.session_id;
  for (const [id, field, suffix] of EXPORT_TARGETS) {
    const anchor = document.querySelector('#' + id);
    const href = payload[field];
    anchor.hidden = !href;
    if (!href) {
      anchor.removeAttribute('href');
      continue;
    }
    anchor.href = href;
    anchor.download = `${sessionId}-${suffix}`;
  }

  const notes = [];
  if (!payload.pose_3d_csv_url) notes.push('3D skeleton unavailable — the lifter is off or the lift failed.');
  if (!payload.pose_2d_csv_url) notes.push('2D keypoints unavailable for this run.');
  notes.push('CSV is one row per frame, for reading — it drops the skeleton bone list and the settings needed to reproduce the run, which only the JSON response carries.');
  notes.push(`Files expire at ${new Date(payload.expires_at).toLocaleTimeString()}.`);
  exportNote.textContent = notes.join(' ');
}

const viewerSection = document.querySelector('#viewer-section');
const viewerState = document.querySelector('#viewer-state');
const viewerWarning = document.querySelector('#viewer-warning');
const playButton = document.querySelector('#viewer-play');
const muscleToggle = document.querySelector('#muscle-toggle');
const muscleLegend = document.querySelector('#muscle-legend');
const frameSlider = document.querySelector('#viewer-frame');
const frameLabel = document.querySelector('#viewer-frame-label');

let viewer = null;
let playTimer = null;

const updateFrameLabel = () => {
  frameLabel.textContent = `${Number(frameSlider.value) + 1} / ${viewer.frameCount}`;
};

const stopPlayback = () => {
  clearInterval(playTimer);
  playTimer = null;
  playButton.textContent = 'Play';
};

playButton.addEventListener('click', () => {
  if (!viewer || !viewer.frameCount) return;
  if (playTimer) {
    stopPlayback();
    return;
  }
  playButton.textContent = 'Pause';
  playTimer = setInterval(() => {
    const next = (Number(frameSlider.value) + 1) % viewer.frameCount;
    frameSlider.value = next;
    viewer.setFrame(next);
    updateFrameLabel();
  }, 1000 / (viewer.fps || 10));
});

frameSlider.addEventListener('input', () => {
  if (!viewer) return;
  stopPlayback();
  viewer.setFrame(Number(frameSlider.value));
  updateFrameLabel();
});

let musclesOn = false;
muscleToggle.addEventListener('click', () => {
  if (!viewer || !viewer.hasMuscles) return;
  musclesOn = !musclesOn;
  viewer.setMusclesVisible(musclesOn);
  muscleToggle.textContent = `Muscles: ${musclesOn ? 'on' : 'off'}`;
  muscleLegend.hidden = !musclesOn;
});

// A fresh clip resets the muscle overlay; the toggle only appears when the
// payload actually carries muscle data (metric-3D lifts do).
function setupMuscleToggle() {
  musclesOn = false;
  muscleLegend.hidden = true;
  const available = Boolean(viewer && viewer.hasMuscles);
  muscleToggle.hidden = !available;
  muscleToggle.textContent = 'Muscles: off';
  if (available) viewer.setMusclesVisible(false);
}

// DEV/PREVIEW: feed a synthetic walking skeleton into the 04/3D viewer so it can
// be seen before real MotionBERT weights exist. Remove together with
// sample_skeleton.js and the #preview-3d button in index.html.
document.querySelector('#preview-3d').addEventListener('click', () => {
  stopPlayback();
  const payload = buildSamplePose3dPayload();
  viewerSection.hidden = false;
  if (!viewer) viewer = mountViewer(document.querySelector('#viewer-canvas'));
  const count = viewer.load(payload);
  viewer.fps = payload.fps;
  frameSlider.max = Math.max(0, count - 1);
  frameSlider.value = 0;
  updateFrameLabel();
  setupMuscleToggle();
  viewerState.textContent = 'Sample data (synthetic)';
  viewerWarning.hidden = false;
  viewerWarning.textContent = 'Synthetic preview — not a real analysis. Shows how the viewer renders while waiting for the MotionBERT weights.';
  viewerSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  playButton.click(); // autoplay
});

async function showPose3d(url) {
  stopPlayback();
  if (!url) {
    // 3D off or lifter unavailable -- the 2D result above still stands.
    viewerSection.hidden = true;
    return;
  }
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('could not load 3D pose data');
    const payload = await response.json();
    // Unhide before mounting/loading: a display:none container measures 0x0,
    // which would leave the renderer stuck at its default canvas size.
    viewerSection.hidden = false;
    if (!viewer) viewer = mountViewer(document.querySelector('#viewer-canvas'));
    const count = viewer.load(payload);
    viewer.fps = payload.fps;
    frameSlider.max = Math.max(0, count - 1);
    frameSlider.value = 0;
    updateFrameLabel();
    setupMuscleToggle();
    viewerState.textContent = payload.analysis_mode === '3d' ? 'Calibrated 3D' : 'Uncalibrated lift';
    if (payload.lift_reliable) {
      viewerWarning.hidden = true;
    } else {
      viewerWarning.hidden = false;
      viewerWarning.textContent = `Lift flagged as unreliable — view for illustration only. ${payload.lift_warnings.join(' ')}`;
    }
  } catch (error) {
    viewerSection.hidden = true;
    console.error(error);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.querySelector('span').textContent = 'Analyzing video…';
  message.textContent = '';
  resultState.textContent = 'Processing…';
  metricsSection.hidden = true;
  viewerSection.hidden = true;
  stopPlayback();
  const data = new FormData(form);
  try {
    const response = await fetch('/api/demo/assess', { method: 'POST', body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Analysis failed');
    const assessment = payload.assessment;
    resultVideo.src = payload.annotated_video_url;
    resultVideo.load();
    resultVideo.hidden = false;
    emptyState.hidden = true;
    const download = document.querySelector('#download-link');
    download.href = payload.annotated_video_url;
    download.hidden = false;
    resultState.textContent = 'Analysis complete';
    const screening = assessment.screening_result;
    const quality = assessment.clinical_metrics.pose_quality;
    document.querySelector('#risk-value').textContent = screening.risk_level;
    document.querySelector('#risk-flags').textContent = screening.flags.length ? screening.flags.join(', ') : 'No flags';
    document.querySelector('#confidence-value').textContent = percent(screening.confidence_score);
    document.querySelector('#side-value').textContent = assessment.video_metadata.analyzed_side || '—';
    document.querySelector('#valid-value').textContent = percent(quality.valid_frame_ratio);
    document.querySelector('#angle-metrics').innerHTML = renderComparison(assessment.clinical_metrics);
    renderSideNotice(assessment);
    renderAnalysisNotice(assessment);
    renderExports(payload);
    metricsSection.hidden = false;
    await showPose3d(payload.pose_3d_url);
  } catch (error) {
    resultState.textContent = 'Unable to analyze';
    message.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector('span').textContent = 'Analyze movement';
  }
});
