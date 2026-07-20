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
