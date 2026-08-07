// Left against right, across two stored recordings.
//
// The analysis page answers "how did this leg move". This one answers "how do
// the two legs differ", which is a question about two clips: each recording
// contributes only the leg it was instructed to move, because a leg filmed from
// the far side of the body is occluded and foreshortened and its numbers are not
// on the same footing as the near leg's.
//
// Nothing is computed here. The page picks two sessions and renders what
// /api/demo/compare says about them, including its refusals.

import { mountViewer } from '/static/viewer3d.js';
import { drawAngleChart, SIDE_COLOR, label } from '/static/anglechart.js';

const patientInput = document.querySelector('#patient-input');
const refreshButton = document.querySelector('#picker-refresh');
const pickerState = document.querySelector('#picker-state');
const pickerMessage = document.querySelector('#picker-message');
const lists = { left: document.querySelector('#left-list'), right: document.querySelector('#right-list') };

const comparisonSection = document.querySelector('#comparison-section');
const comparisonState = document.querySelector('#comparison-state');
const blockingNotice = document.querySelector('#blocking-notice');
const metricsHost = document.querySelector('#asymmetry-metrics');
const checksBlock = document.querySelector('#checks-block');
const checksList = document.querySelector('#checks-list');

const trajectoryBlock = document.querySelector('#trajectory-block');
const trajectoryChart = document.querySelector('#trajectory-chart');
const trajectoryLegend = document.querySelector('#trajectory-legend');
const trajectoryReadout = document.querySelector('#trajectory-readout');

const viewerSection = document.querySelector('#viewer-section');
const viewerState = document.querySelector('#viewer-state');
const viewerWarning = document.querySelector('#viewer-warning');
const playButton = document.querySelector('#viewer-play');
const muscleToggle = document.querySelector('#muscle-toggle');
const muscleLegend = document.querySelector('#muscle-legend');
const frameSlider = document.querySelector('#viewer-frame');
const frameLabel = document.querySelector('#viewer-frame-label');
const sideButtons = { left: document.querySelector('#viewer-side-left'), right: document.querySelector('#viewer-side-right') };

const TASK_LABELS = {
  knee_flexion: 'Knee flexion',
  knee_extension: 'Knee extension',
  hip_flexion: 'Hip flexion',
  hip_extension: 'Hip extension',
  ankle_dorsiflexion: 'Ankle dorsiflexion',
  ankle_plantarflexion: 'Ankle plantarflexion',
};

const selected = { left: null, right: null };
let sessions = [];

// ---- Picking --------------------------------------------------------------

function sessionRow(session, side) {
  const when = session.recorded_at ? new Date(session.recorded_at).toLocaleString() : '—';
  const task = TASK_LABELS[session.task_type] || label(session.task_type);
  const rom = session.rom_deg?.[side];
  const chosen = session.session_id === selected[side] ? ' is-open' : '';
  const warnings = (session.guard_warnings || []).length;
  return `
    <button type="button" class="history-item picker-item${chosen}" data-side="${side}" data-session="${session.session_id}">
      <span class="history-when">${when}</span>
      <span class="history-main">
        <strong>${task}</strong>
        <small>${session.patient_id || '—'} · ${label(session.view)} · ${session.analysis_mode === '3d' ? '3D' : '2D'}${warnings ? ` · ${warnings} warning${warnings > 1 ? 's' : ''}` : ''}</small>
      </span>
      <span class="history-rom">${rom == null ? 'ROM —' : `ROM ${Number(rom).toFixed(1)}°`}</span>
    </button>`;
}

function renderLists() {
  for (const side of ['left', 'right']) {
    const rows = sessions.filter((s) => s.side === side);
    lists[side].innerHTML = rows.length
      ? rows.map((s) => sessionRow(s, side)).join('')
      : `<p class="history-empty">No stored ${side}-leg recordings.</p>`;
  }
}

async function loadSessions() {
  const patientId = patientInput.value.trim();
  const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : '';
  pickerMessage.textContent = '';
  try {
    const response = await fetch('/api/demo/sessions' + query);
    if (!response.ok) throw new Error('could not read stored sessions');
    sessions = (await response.json()).sessions;
    // A session whose selection has scrolled out of the filtered list would
    // otherwise stay silently selected and be compared against.
    for (const side of ['left', 'right']) {
      if (selected[side] && !sessions.some((s) => s.session_id === selected[side])) selected[side] = null;
    }
    renderLists();
    const counts = ['left', 'right'].map((side) => sessions.filter((s) => s.side === side).length);
    pickerState.textContent = `${counts[0]} left · ${counts[1]} right`;
  } catch (error) {
    console.error(error);
    for (const side of ['left', 'right']) lists[side].innerHTML = '<p class="history-empty">Stored sessions could not be read.</p>';
    pickerState.textContent = 'unavailable';
  }
}

for (const side of ['left', 'right']) {
  lists[side].addEventListener('click', (event) => {
    const item = event.target.closest('.picker-item');
    if (!item) return;
    // Clicking the chosen row again clears it, so a mistaken pick is undoable
    // without reloading.
    selected[side] = selected[side] === item.dataset.session ? null : item.dataset.session;
    renderLists();
    runComparison();
  });
}

refreshButton.addEventListener('click', loadSessions);
patientInput.addEventListener('change', loadSessions);

// ---- Comparison -----------------------------------------------------------

// Counts (movement units) are whole things and reading "3.00" of them invites the
// thought that the .00 means something.
const decimals = (value, unit) => (unit === '°' ? 1 : Number.isInteger(value) ? 0 : 2);
const fmt = (value, unit) => (value == null ? '—' : `${Number(value).toFixed(decimals(value, unit))}${unit}`);

// A signed difference reads better with its direction spelled out than with a
// minus sign the reader has to decode. "Higher", not "more": SPARC and LDLJ are
// negative, so the larger value is the less negative one, and "more smoothness"
// would be an interpretation this table is not making.
function differenceText(row) {
  if (row.difference == null) return '—';
  if (row.larger_side === null || row.difference === 0) return `0${row.unit}`;
  const magnitude = Math.abs(row.difference).toFixed(decimals(row.difference, row.unit));
  return `${magnitude}${row.unit} higher on ${row.larger_side}`;
}

// A bar per side, scaled against the larger of the two, so the size of a
// difference is visible before the numbers are read. Only drawn for metrics
// where a magnitude comparison is meaningful -- the ones that carry an index.
function bars(row) {
  if (row.symmetry_angle_pct == null || row.left == null || row.right == null) return '';
  const peak = Math.max(row.left, row.right, 1e-9);
  const width = (value) => `${Math.max(0, (value / peak) * 100)}%`;
  return `
    <span class="sym-bars" aria-hidden="true">
      <span class="sym-bar"><i class="is-left" style="width:${width(row.left)}"></i></span>
      <span class="sym-bar"><i class="is-right" style="width:${width(row.right)}"></i></span>
    </span>`;
}

function renderMetrics(metrics) {
  if (!metrics.length) {
    metricsHost.innerHTML = '<p class="history-empty">No shared metrics between these two recordings.</p>';
    return;
  }
  const body = metrics
    .map((row) => `
      <tr>
        <th>${row.label}</th>
        <td>${fmt(row.left, row.unit)}</td>
        <td>${fmt(row.right, row.unit)}</td>
        <td>${differenceText(row)}</td>
        <td>${row.symmetry_angle_pct == null ? '<span class="not-applicable" title="A ratio index needs a positive magnitude with a meaningful zero; this metric has neither.">n/a</span>' : `${Math.abs(row.symmetry_angle_pct).toFixed(1)}%`}</td>
        <td class="bar-cell">${bars(row)}</td>
      </tr>`)
    .join('');
  metricsHost.innerHTML = `
    <table class="compare-table asymmetry-table">
      <thead><tr><th>Metric</th><th>Left</th><th>Right</th><th>Difference</th><th>Symmetry angle</th><th></th></tr></thead>
      <tbody>${body}</tbody>
    </table>`;
}

function renderChecks(checks) {
  const warnings = checks.filter((c) => c.severity === 'warning');
  checksBlock.hidden = warnings.length === 0;
  checksList.innerHTML = warnings.map((c) => `<li>${c.message}</li>`).join('');
}

function renderComparison(payload) {
  comparisonSection.hidden = false;
  const blocking = payload.checks.filter((c) => c.severity === 'blocking');

  document.querySelector('#task-value').textContent = TASK_LABELS[payload.left.task_type] || label(payload.left.task_type);
  document.querySelector('#patient-value').textContent = payload.left.patient_id || '—';
  document.querySelector('#apart-value').textContent = payload.days_apart == null ? '—' : `${payload.days_apart} d`;
  document.querySelector('#mode-value').textContent =
    payload.left.analysis_mode === payload.right.analysis_mode
      ? payload.left.analysis_mode.toUpperCase()
      : `${payload.left.analysis_mode.toUpperCase()} / ${payload.right.analysis_mode.toUpperCase()}`;

  if (blocking.length) {
    // Refused on purpose: a number from a mismatched pair would be worse than
    // no number, because it would look like an answer.
    comparisonState.textContent = 'Not comparable';
    blockingNotice.hidden = false;
    blockingNotice.textContent = `No comparison was made. ${blocking.map((c) => c.message).join(' ')}`;
    metricsHost.innerHTML = '';
    renderChecks(payload.checks);
    return;
  }
  comparisonState.textContent = 'Compared';
  blockingNotice.hidden = true;
  renderMetrics(payload.metrics);
  renderChecks(payload.checks);
}

// ---- The graph ------------------------------------------------------------
// One line per leg, each read from its own recording -- the same series the ROM
// numbers above were read from, so the picture and the figures cannot disagree.
//
// The two clips do not share a clock. They are drawn on one axis because that is
// the only way to compare the shapes, and the caveat under the chart says plainly
// that the alignment means nothing. Interpolating them onto a common normalised
// time would look tidier and would invent a correspondence between frames that
// were never simultaneous.
function renderTrajectories(assessments) {
  try {
    const series = ['left', 'right']
      .map((side) => {
        const assessment = assessments[side];
        const trajectory = assessment?.trajectory;
        return {
          key: side,
          label: `${label(side)} leg`,
          color: SIDE_COLOR[side],
          emphasis: 'primary', // both are instructed legs here; neither is a reference
          time: trajectory?.time_sec || [],
          values: trajectory?.[`${side}_angle_deg`],
          joint: trajectory?.joint,
        };
      })
      .filter((s) => Array.isArray(s.values));

    const joint = series.find((s) => s.joint)?.joint || '';
    const drawn = drawAngleChart({
      chartEl: trajectoryChart,
      legendEl: trajectoryLegend,
      readoutEl: trajectoryReadout,
      series,
      jointLabel: label(joint.replace(/_deg$/, '')),
    });
    trajectoryBlock.hidden = !drawn;
  } catch (error) {
    // The graph is a second reading of numbers the table already shows, so it
    // never gets to take the table down with it.
    console.error('angle graph failed to draw', error);
    trajectoryBlock.hidden = true;
  }
}

// ---- The 3D viewer --------------------------------------------------------
// One recording at a time. The two clips have their own cameras, their own scale
// and their own timelines, so overlaying the skeletons would render a difference
// between two setups and invite it to be read as a difference between two legs.
// The side buttons switch which recording is on screen; the comparison itself
// stays in the table above, where it is measured rather than eyeballed.
let viewer = null;
let playTimer = null;
let viewerSide = null;
const pose3dUrls = { left: null, right: null };

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

function setupMuscleToggle() {
  musclesOn = false;
  muscleLegend.hidden = true;
  const available = Boolean(viewer && viewer.hasMuscles);
  muscleToggle.hidden = !available;
  muscleToggle.textContent = 'Muscles: off';
  if (available) viewer.setMusclesVisible(false);
}

function markSideButtons() {
  for (const side of ['left', 'right']) {
    const available = Boolean(pose3dUrls[side]);
    sideButtons[side].disabled = !available;
    sideButtons[side].classList.toggle('is-active', available && viewerSide === side);
    sideButtons[side].title = available ? '' : `No 3D lift was produced for the ${side} recording.`;
  }
}

async function showSide(side) {
  const url = pose3dUrls[side];
  if (!url) return;
  stopPlayback();
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('could not load 3D pose data');
    const payload = await response.json();
    // Unhide before mounting: a display:none container measures 0x0, which would
    // leave the renderer stuck at its default canvas size.
    viewerSection.hidden = false;
    if (!viewer) viewer = mountViewer(document.querySelector('#viewer-canvas'));
    const count = viewer.load(payload);
    viewer.fps = payload.fps;
    frameSlider.max = Math.max(0, count - 1);
    frameSlider.value = 0;
    updateFrameLabel();
    setupMuscleToggle();
    viewerSide = side;
    markSideButtons();
    viewerState.textContent = `${label(side)} recording · ${payload.analysis_mode === '3d' ? 'calibrated 3D' : 'uncalibrated lift'}`;
    if (payload.lift_reliable) {
      viewerWarning.hidden = true;
    } else {
      viewerWarning.hidden = false;
      viewerWarning.textContent = `Lift flagged as unreliable — view for illustration only. ${(payload.lift_warnings || []).join(' ')}`;
    }
  } catch (error) {
    console.error(error);
    viewerSection.hidden = true;
  }
}

for (const side of ['left', 'right']) {
  sideButtons[side].addEventListener('click', () => showSide(side));
}

function setupViewer(payloads) {
  stopPlayback();
  pose3dUrls.left = payloads.left?.pose_3d_url || null;
  pose3dUrls.right = payloads.right?.pose_3d_url || null;
  viewerSide = null;
  if (!pose3dUrls.left && !pose3dUrls.right) {
    // Neither run produced a lift -- 3D is best-effort and often falls back.
    // Everything above still stands, so the section simply goes away.
    viewerSection.hidden = true;
    return;
  }
  viewerSection.hidden = false;
  markSideButtons();
  showSide(pose3dUrls.left ? 'left' : 'right');
}

// ---- Driving it -----------------------------------------------------------

async function fetchSession(sessionId) {
  const response = await fetch(`/api/demo/sessions/${encodeURIComponent(sessionId)}`);
  if (!response.ok) throw new Error('could not reopen one of the selected sessions');
  return response.json();
}

async function runComparison() {
  if (!selected.left || !selected.right) {
    comparisonSection.hidden = true;
    trajectoryBlock.hidden = true;
    viewerSection.hidden = true;
    stopPlayback();
    return;
  }
  pickerMessage.textContent = '';
  comparisonState.textContent = 'Comparing…';
  try {
    const query = `?left=${encodeURIComponent(selected.left)}&right=${encodeURIComponent(selected.right)}`;
    const response = await fetch('/api/demo/compare' + query);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Comparison failed');
    renderComparison(payload);

    if (!payload.comparable) {
      // A refused pair gets no graph and no skeleton either: two pictures side by
      // side are exactly the invitation to compare them by eye that the refusal
      // exists to withhold.
      trajectoryBlock.hidden = true;
      viewerSection.hidden = true;
      stopPlayback();
      return;
    }

    // The comparison response deliberately carries only metrics. The series and
    // the lifted skeleton live in the stored sessions, so they are read from the
    // same endpoint the analysis page reopens a session with -- one shape of a
    // stored result, not two.
    const [left, right] = await Promise.all([
      fetchSession(payload.left.session_id),
      fetchSession(payload.right.session_id),
    ]);
    renderTrajectories({ left: left.assessment, right: right.assessment });
    setupViewer({ left, right });
  } catch (error) {
    comparisonSection.hidden = true;
    trajectoryBlock.hidden = true;
    viewerSection.hidden = true;
    stopPlayback();
    pickerMessage.textContent = error.message;
  }
}

loadSessions();
