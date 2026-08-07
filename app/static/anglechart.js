// The angle-through-time graph, shared by the analysis page and the comparison
// page.
//
// It was written for the analysis page, where both lines come from one clip and
// therefore share a time axis. The comparison page broke that assumption: its two
// lines come from two separate recordings of different lengths. So every series
// carries its own time array here, and the axis is the longest of them. Two clips
// of different lengths ending at different points on the axis is the honest
// picture -- they *were* different lengths.
//
// Plain SVG on purpose: one chart is not worth a plotting library, and the pages
// have no build step.

// Viewbox units, not pixels: the SVG is scaled to the panel width. The wide
// aspect keeps the graph from towering over the table it sits under, and keeps
// the axis text near its nominal size once scaled.
const CHART = { w: 1000, h: 280, left: 56, right: 18, top: 18, bottom: 36 };

export const SIDE_COLOR = { left: '#16764f', right: '#2f6fb9' };

export const label = (key) => String(key || '').replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());

// Round the angle axis outwards to a readable step, so the gridline labels are
// whole numbers rather than whatever the extremes happened to be.
function niceAxis(min, max) {
  const span = Math.max(max - min, 5);
  const step = [1, 2, 5, 10, 20, 25, 50].find((s) => span / s <= 6) || 100;
  return { lo: Math.floor(min / step) * step, hi: Math.ceil(max / step) * step, step };
}

// A null means the leg was not confidently visible in that frame. The line breaks
// there instead of bridging the gap, which would draw movement that was never
// measured.
function segments(series, toX, toY) {
  const paths = [];
  let current = [];
  series.values.forEach((value, index) => {
    if (value == null) {
      if (current.length > 1) paths.push(current);
      current = [];
      return;
    }
    current.push(`${toX(series.time[index]).toFixed(1)},${toY(value).toFixed(1)}`);
  });
  if (current.length > 1) paths.push(current);
  return paths;
}

const IDLE_READOUT = 'Hover the graph to read the angle at a moment.';

/**
 * Draw the chart, or report that there was nothing to draw.
 *
 * `series` entries: { key, label, color, emphasis: 'primary' | 'reference',
 * time: number[], values: (number | null)[] }. `time` and `values` are parallel;
 * each series may have its own length.
 *
 * Returns false when no series carried plottable data, so the caller can hide the
 * block rather than leave an empty frame.
 */
export function drawAngleChart({ chartEl, legendEl, readoutEl, series, jointLabel }) {
  const usable = (series || []).filter((s) => Array.isArray(s.values) && Array.isArray(s.time) && s.time.length);
  const finite = usable.flatMap((s) => s.values.filter((v) => v != null));
  if (!usable.length || !finite.length) return false;

  const axis = niceAxis(Math.min(...finite), Math.max(...finite));
  const { w, h, left, right, top, bottom } = CHART;
  const plotW = w - left - right;
  const plotH = h - top - bottom;
  const lastTime = Math.max(...usable.map((s) => s.time[s.time.length - 1] || 0), 1e-6);
  const toX = (t) => left + (t / lastTime) * plotW;
  const toY = (angle) => top + (1 - (angle - axis.lo) / (axis.hi - axis.lo)) * plotH;

  let grid = '';
  for (let angle = axis.lo; angle <= axis.hi + 1e-9; angle += axis.step) {
    const y = toY(angle).toFixed(1);
    grid += `<line class="grid-line" x1="${left}" x2="${w - right}" y1="${y}" y2="${y}"></line>`;
    grid += `<text class="axis-text" x="${left - 8}" y="${y}" text-anchor="end" dominant-baseline="middle">${angle}°</text>`;
  }
  // ~8 time labels regardless of clip length. Driven by the time axis rather than
  // by frame indices, because the series no longer necessarily share one.
  let ticks = '';
  for (let step = 0; step <= 8; step += 1) {
    const t = (lastTime / 8) * step;
    ticks += `<text class="axis-text" x="${toX(t).toFixed(1)}" y="${h - bottom + 18}" text-anchor="middle">${t.toFixed(1)}s</text>`;
  }

  const lines = usable
    .map((s) => {
      const emphasis = s.emphasis === 'reference' ? 'is-reference' : 'is-instructed';
      return segments(s, toX, toY)
        .map((points) => `<polyline class="angle-line ${emphasis}" stroke="${s.color}" points="${points.join(' ')}"></polyline>`)
        .join('');
    })
    .join('');

  const cursors = usable
    .map((s) => `<circle class="cursor-dot" data-key="${s.key}" r="4" fill="${s.color}" cx="-99" cy="-99"></circle>`)
    .join('');

  chartEl.innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" class="trajectory-svg" role="img" aria-label="Joint angle through time">
      ${grid}${ticks}
      <line class="axis-line" x1="${left}" x2="${left}" y1="${top}" y2="${h - bottom}"></line>
      <line class="axis-line" x1="${left}" x2="${w - right}" y1="${h - bottom}" y2="${h - bottom}"></line>
      ${lines}
      <line class="cursor-line" x1="-99" x2="-99" y1="${top}" y2="${h - bottom}"></line>
      ${cursors}
      <rect class="hover-area" x="${left}" y="${top}" width="${plotW}" height="${plotH}" fill="transparent"></rect>
    </svg>`;

  if (legendEl) {
    legendEl.innerHTML = usable
      .map((s) => `<span class="legend-item"><i style="background:${s.color}"></i>${s.label}</span>`)
      .join('');
  }

  attachHover({ chartEl, readoutEl, series: usable, toX, toY, lastTime, jointLabel });
  return true;
}

// Reading a single moment off the graph is what turns a shape into a number, so
// the hover reports the angle of every plotted line at the moment under the
// cursor. Each series is searched in its own time array: on the comparison page
// the two recordings do not share frames, so "the same index" would be the wrong
// question -- "the nearest moment" is the right one.
function attachHover({ chartEl, readoutEl, series, toX, toY, lastTime, jointLabel }) {
  const svg = chartEl.querySelector('svg');
  const cursorLine = svg.querySelector('.cursor-line');
  const dots = [...svg.querySelectorAll('.cursor-dot')];

  const clear = () => {
    cursorLine.setAttribute('x1', -99);
    cursorLine.setAttribute('x2', -99);
    for (const dot of dots) dot.setAttribute('cx', -99);
    if (readoutEl) readoutEl.textContent = IDLE_READOUT;
  };

  svg.addEventListener('pointerleave', clear);
  svg.addEventListener('pointermove', (event) => {
    // Map the pointer through the viewBox: the SVG is scaled to the panel width,
    // so client pixels are not chart units.
    const box = svg.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width) * CHART.w;
    const t = Math.min(Math.max(((x - CHART.left) / (CHART.w - CHART.left - CHART.right)) * lastTime, 0), lastTime);
    const cx = toX(t).toFixed(1);
    cursorLine.setAttribute('x1', cx);
    cursorLine.setAttribute('x2', cx);

    const parts = [];
    for (const dot of dots) {
      const s = series.find((entry) => entry.key === dot.dataset.key);
      let index = 0;
      for (let i = 1; i < s.time.length; i += 1) {
        if (Math.abs(s.time[i] - t) < Math.abs(s.time[index] - t)) index = i;
      }
      const value = s.values[index];
      // Past the end of a shorter clip there is no frame to report, and the
      // nearest one is its last -- which would draw a line that stopped moving
      // rather than a recording that ended.
      const beyondClip = t > (s.time[s.time.length - 1] || 0) + 1e-9;
      if (value == null || beyondClip) {
        dot.setAttribute('cx', -99);
        parts.push(`${s.label} — ${beyondClip ? 'clip ended' : 'not tracked'}`);
        continue;
      }
      dot.setAttribute('cx', toX(s.time[index]).toFixed(1));
      dot.setAttribute('cy', toY(value).toFixed(1));
      parts.push(`${s.label} ${value.toFixed(1)}°`);
    }
    if (readoutEl) readoutEl.textContent = `${t.toFixed(1)}s · ${jointLabel} · ${parts.join(' · ')}`;
  });
}
