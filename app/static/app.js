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
      option.textContent = `${[make, model].filter(Boolean).join(' ')} · ${size}${d.status !== 'valid' ? ` (${d.status})` : ''}`;
      deviceSelect.appendChild(option);
    }
  } catch (error) {
    console.error(error);
  }
}

deviceSelect.addEventListener('change', () => {
  const option = deviceSelect.selectedOptions[0];
  deviceMake.value = option?.dataset.make || '';
  deviceModel.value = option?.dataset.model || '';
});

loadDevices();

// ---- Camera calibration (00 / CALIBRATION) --------------------------------
const calibrateForm = document.querySelector('#calibrate-form');
const calibFileInput = document.querySelector('#calib-file');
const calibFileName = document.querySelector('#calib-file-name');
const calibrateButton = document.querySelector('#calibrate-button');
const calibrateMessage = document.querySelector('#calibrate-message');
const calibrateResult = document.querySelector('#calibrate-result');

calibFileInput.addEventListener('change', () => {
  const file = calibFileInput.files[0];
  if (file) calibFileName.textContent = file.name;
});

calibrateForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  calibrateButton.disabled = true;
  calibrateButton.querySelector('span').textContent = 'Calibrating…';
  calibrateMessage.textContent = '';
  calibrateResult.hidden = true;
  try {
    const response = await fetch('/api/demo/calibrate', { method: 'POST', body: new FormData(calibrateForm) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Calibration failed');
    const warnings = (payload.warnings || []).map((w) => `<li>${w}</li>`).join('');
    const rows = [
      ['Status', payload.ok ? 'Calibrated ✓' : `Failed (${payload.status})`],
      ['Device ID', payload.device_id],
      ['Metadata source', payload.source],
      ['Resolution', payload.image_size ? `${payload.image_size[0]}×${payload.image_size[1]}` : '—'],
      ['Frames sampled', payload.frames_sampled],
    ];
    if (payload.ok) {
      rows.push(['Reprojection error', `${payload.reproj_error_px} px`]);
      rows.push(['Print scale factor', payload.print_scale_factor]);
    }
    calibrateResult.className = `calibrate-result ${payload.ok ? 'ok' : 'fail'}`;
    calibrateResult.innerHTML =
      `<p class="calibrate-result-msg">${payload.message || ''}</p>` +
      '<div class="metric-table">' +
      rows.map(([k, v]) => `<div class="metric-cell"><span class="metric-label">${k}</span><strong>${v}</strong></div>`).join('') +
      '</div>' +
      (warnings ? `<ul class="calibrate-warnings">${warnings}</ul>` : '');
    calibrateResult.hidden = false;
    if (payload.ok) await loadDevices();  // surface the new device in the 01/INPUT picker
  } catch (error) {
    calibrateMessage.textContent = error.message;
  } finally {
    calibrateButton.disabled = false;
    calibrateButton.querySelector('span').textContent = 'Calibrate device';
  }
});

const percent = (value) => `${(Number(value) * 100).toFixed(0)}%`;
const label = (key) => key.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const viewerSection = document.querySelector('#viewer-section');
const viewerState = document.querySelector('#viewer-state');
const viewerWarning = document.querySelector('#viewer-warning');
const playButton = document.querySelector('#viewer-play');
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
    document.querySelector('#angle-metrics').innerHTML = Object.entries(assessment.clinical_metrics.joint_angles).map(([key, value]) => `<div class="metric-cell"><span class="metric-label">${label(key)}</span><strong>${Number(value).toFixed(1)}°</strong></div>`).join('');
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
