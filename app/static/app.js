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

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.querySelector('span').textContent = 'Analyzing video…';
  message.textContent = '';
  resultState.textContent = 'Processing…';
  metricsSection.hidden = true;
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
  } catch (error) {
    resultState.textContent = 'Unable to analyze';
    message.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector('span').textContent = 'Analyze movement';
  }
});
