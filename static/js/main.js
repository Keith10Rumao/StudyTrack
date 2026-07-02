// StudyTrack — small client-side helpers

function confirmDelete(message) {
  return confirm(message || "Are you sure you want to delete this? This cannot be undone.");
}

// Renders the daily study time trend bar chart on the Progress page
function renderTrendChart(canvasId, labels, values) {
  const el = document.getElementById(canvasId);
  if (!el || typeof Chart === 'undefined') return;
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const gridColor = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)';
  const textColor = isDark ? '#ffffff' : '#111111';

  new Chart(el, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Hours studied',
        data: values,
        backgroundColor: '#B084F5',
        borderColor: '#000000',
        borderWidth: 2,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: textColor, font: { weight: 700 } }, grid: { color: gridColor } },
        y: { beginAtZero: true, ticks: { color: textColor, font: { weight: 700 } }, grid: { color: gridColor } }
      }
    }
  });
}

// Generic horizontal bar chart with a distinct color per bar — used for
// "Subject Time Allocation" (hours) and "Subject Progress" (completion %)
function renderColoredBarChart(canvasId, labels, values, colors, opts) {
  const el = document.getElementById(canvasId);
  if (!el || typeof Chart === 'undefined') return;
  opts = opts || {};
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const gridColor = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)';
  const textColor = isDark ? '#ffffff' : '#111111';

  new Chart(el, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: opts.label || '',
        data: values,
        backgroundColor: colors,
        borderColor: '#000000',
        borderWidth: 2,
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.parsed.x}${opts.suffix || ''}`
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          max: opts.max,
          ticks: { color: textColor, font: { weight: 700 } },
          grid: { color: gridColor }
        },
        y: { ticks: { color: textColor, font: { weight: 700 } }, grid: { color: gridColor } }
      }
    }
  });
}

// Live stopwatch — used on the "Start Session" timer page.
// startedAtIso must be an ISO 8601 UTC timestamp (with trailing 'Z').
function startLiveClock(displayId, startedAtIso) {
  const el = document.getElementById(displayId);
  if (!el || !startedAtIso) return;
  const start = new Date(startedAtIso).getTime();

  function tick() {
    const diffMs = Math.max(0, Date.now() - start);
    const totalSeconds = Math.floor(diffMs / 1000);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    el.textContent = [h, m, s].map((v) => String(v).padStart(2, '0')).join(':');
  }
  tick();
  setInterval(tick, 1000);
}

