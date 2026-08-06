// 00 / CALIBRATION -- its own page (/calibrate). Kept off the analysis page
// because it is a once-per-device chore, not part of the per-clip flow.
const calibrateForm = document.querySelector('#calibrate-form');
const calibFileInput = document.querySelector('#calib-file');
const calibFileName = document.querySelector('#calib-file-name');
const calibrateButton = document.querySelector('#calibrate-button');
const calibrateMessage = document.querySelector('#calibrate-message');
const calibrateResult = document.querySelector('#calibrate-result');
const deviceList = document.querySelector('#device-list');
const deviceCount = document.querySelector('#device-count');

// Mirror of the 01/INPUT picker, as a read-only list: this page is where you
// come to find out what is already calibrated.
async function loadDevices() {
  try {
    const response = await fetch('/api/demo/devices');
    if (!response.ok) throw new Error('could not load devices');
    const { devices } = await response.json();
    deviceCount.textContent = `${devices.length} saved`;
    if (!devices.length) {
      deviceList.innerHTML = '<p class="empty-line">No calibrated devices yet. Upload a board video to add one.</p>';
      return;
    }
    deviceList.innerHTML = devices
      .map((d) => {
        const name = [d.make, d.model].filter(Boolean).join(' ') || 'Unnamed device';
        const size = d.image_size ? `${d.image_size[0]}×${d.image_size[1]}` : 'unknown resolution';
        const ok = d.status === 'valid';
        return `<div class="device-row"><div><strong>${name}</strong><small>${size} · ${d.device_id}</small></div>` +
          `<span class="device-status ${ok ? 'ok' : 'warn'}">${d.status}</span></div>`;
      })
      .join('');
  } catch (error) {
    console.error(error);
    deviceCount.textContent = 'unavailable';
  }
}

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
    if (payload.ok) await loadDevices();
  } catch (error) {
    calibrateMessage.textContent = error.message;
  } finally {
    calibrateButton.disabled = false;
    calibrateButton.querySelector('span').textContent = 'Calibrate device';
  }
});

loadDevices();
