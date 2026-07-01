// ---------------------------------------------------------------------------
// helios/charts.js — Monkey-themed Chart.js dashboard, 30 s refresh.
// ---------------------------------------------------------------------------

const C = {
  acc:    '#00d4ff',   // cyan
  acc2:   '#ff6b35',   // orange
  acc3:   '#00ff88',   // green
  acc3b:  '#00cc66',   // muted green (float state)
  danger: '#ff3366',   // red
  txt:    '#e8e8f0',
  txt2:   '#8888aa',
  txt3:   '#4444aa',
  border: 'rgba(0, 212, 255, 0.12)',
};

// Charge state → { color, label } for the state timeline
const STATE_STYLE = {
  0: { color: C.txt3,   label: 'deactivated'   },
  1: { color: C.acc2,   label: 'activated'     },
  2: { color: C.acc3,   label: 'mppt'          },
  3: { color: C.acc,    label: 'equalizing'    },
  4: { color: C.acc,    label: 'boost'         },
  5: { color: C.acc3b,  label: 'floating'      },
  6: { color: C.danger, label: 'current_limit' },
};

Chart.defaults.color = C.txt2;
Chart.defaults.borderColor = C.border;
Chart.defaults.font.family = "'IBM Plex Mono', monospace";
Chart.defaults.font.size = 10;

// Time-axis label formats. Chart.js auto-selects a unit (second, minute,
// hour, day, ...) based on data density; if we don't define the format
// for the chosen unit, it falls back to a locale-default like "3:35:00 p.m."
// which breaks the monospaced look. Cover every unit Chart.js might pick.
const TIME_FORMATS = {
  millisecond: 'HH:mm:ss',
  second:      'HH:mm:ss',
  minute:      'HH:mm',
  hour:        'HH:mm',
  day:         'MMM d',
  week:        'MMM d',
  month:       'MMM',
  quarter:     'QQQ',
  year:        'yyyy',
};

let powerChart, batteryChart, socChart, chargeIChart, tempChart, stateChart, energyChart, faultChart;

// ---------------------------------------------------------------------------
// Chart initialization
// ---------------------------------------------------------------------------

function baseTimeOpts() {
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: { type: 'time', time: { displayFormats: TIME_FORMATS }, grid: { color: C.border }, ticks: { color: C.txt3, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
      y: { grid: { color: C.border }, ticks: { color: C.txt3 }, beginAtZero: true },
    },
    plugins: {
      legend: { labels: { color: C.txt2, font: { size: 10 } } },
      tooltip: { backgroundColor: '#0f0f1a', borderColor: C.border, borderWidth: 1, titleColor: C.txt, bodyColor: C.txt },
    },
  };
}

function line(id, color, label) {
  return new Chart(document.getElementById(id), {
    type: 'line',
    data: { datasets: [{ label, data: [], borderColor: color, backgroundColor: color + '22', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 }] },
    options: baseTimeOpts(),
  });
}

function initCharts() {
  // Power flows — 2 series, cyan + orange
  powerChart = new Chart(document.getElementById('chart-power'), {
    type: 'line',
    data: { datasets: [
      { label: 'PV (W)',   data: [], borderColor: C.acc,  backgroundColor: C.acc + '22',  fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 },
      { label: 'Load (W)', data: [], borderColor: C.acc2, backgroundColor: C.acc2 + '22', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 },
    ]},
    options: baseTimeOpts(),
  });

  batteryChart = new Chart(document.getElementById('chart-battery'), {
    type: 'line',
    data: { datasets: [{ label: 'Battery (V)', data: [], borderColor: C.acc3, backgroundColor: C.acc3 + '22', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 }] },
    options: { ...baseTimeOpts(), scales: { ...baseTimeOpts().scales, y: { ...baseTimeOpts().scales.y, beginAtZero: false } } },
  });

  socChart      = line('chart-soc',       C.acc3, 'SOC (%)');
  socChart.options.scales.y.max = 100;

  chargeIChart  = line('chart-charge-i',  C.acc,  'Charge current (A)');

  // Temps — 2 series
  tempChart = new Chart(document.getElementById('chart-temp'), {
    type: 'line',
    data: { datasets: [
      { label: 'Controller (°C)', data: [], borderColor: C.acc,  backgroundColor: C.acc  + '22', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 },
      { label: 'Battery (°C)',    data: [], borderColor: C.acc3, backgroundColor: C.acc3 + '22', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 },
    ]},
    options: { ...baseTimeOpts(), scales: { ...baseTimeOpts().scales, y: { ...baseTimeOpts().scales.y, beginAtZero: false } } },
  });

  // Charge state — bar per bucket, colored by state, constant height
  stateChart = new Chart(document.getElementById('chart-state'), {
    type: 'bar',
    data: { datasets: [{ label: 'state', data: [], backgroundColor: [], borderWidth: 0, barPercentage: 1.02, categoryPercentage: 1.0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { type: 'time', time: { displayFormats: TIME_FORMATS }, grid: { color: C.border }, ticks: { color: C.txt3, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
        y: { display: false, min: 0, max: 1 },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f0f1a', borderColor: C.border, borderWidth: 1, titleColor: C.txt, bodyColor: C.txt,
          callbacks: {
            label: (ctx) => {
              const state = ctx.dataset._states?.[ctx.dataIndex];
              return STATE_STYLE[state]?.label?.toUpperCase() || 'unknown';
            },
          },
        },
      },
    },
  });

  // 7-day energy — grouped bar, gen + used
  energyChart = new Chart(document.getElementById('chart-energy'), {
    type: 'bar',
    data: { labels: [], datasets: [
      { label: 'Generated (Wh)', data: [], backgroundColor: C.acc,  borderWidth: 0 },
      { label: 'Consumed (Wh)',  data: [], backgroundColor: C.acc2, borderWidth: 0 },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { grid: { color: C.border }, ticks: { color: C.txt3 } },
        y: { grid: { color: C.border }, ticks: { color: C.txt3 }, beginAtZero: true, title: { display: true, text: 'Wh', color: C.txt2 } },
      },
      plugins: {
        legend: { labels: { color: C.txt2, font: { size: 10 } } },
        tooltip: { backgroundColor: '#0f0f1a', borderColor: C.border, borderWidth: 1, titleColor: C.txt, bodyColor: C.txt },
      },
    },
  });

  // Fault timeline — sparse scatter over 30 days
  faultChart = new Chart(document.getElementById('chart-faults'), {
    type: 'scatter',
    data: { datasets: [{ label: 'Faults', data: [], backgroundColor: C.danger, borderColor: C.danger, pointRadius: 5, pointHoverRadius: 7 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { type: 'time', time: { unit: 'day', displayFormats: TIME_FORMATS }, grid: { color: C.border }, ticks: { color: C.txt3, maxRotation: 0 } },
        y: { display: false, min: 0, max: 1 },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f0f1a', borderColor: C.border, borderWidth: 1, titleColor: C.txt, bodyColor: C.txt,
          callbacks: {
            label: (ctx) => ctx.raw.description || 'fault',
          },
        },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function tickClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}

function setStatus(ok, txt) {
  const dot = document.getElementById('status-dot');
  const t   = document.getElementById('status-txt');
  if (ok) { dot.classList.remove('err'); t.classList.remove('err'); t.textContent = txt || 'NOMINAL'; }
  else    { dot.classList.add('err');    t.classList.add('err');    t.textContent = txt || 'ERROR'; }
}

// ---------------------------------------------------------------------------
// Data fetch + populate
// ---------------------------------------------------------------------------

async function refresh() {
  try {
    const [rt, ts, daily, lt, ev] = await Promise.all([
      fetch('/api/realtime').then(r => r.json()),
      fetch('/api/timeseries?hours=24').then(r => r.json()),
      fetch('/api/daily?days=7').then(r => r.json()),
      fetch('/api/lifetime').then(r => r.json()),
      fetch('/api/events?limit=100').then(r => r.json()),
    ]);

    // --- Realtime tiles ---
    if (rt) {
      document.getElementById('soc').textContent           = rt.battery_soc ?? '--';
      document.getElementById('batt-v').textContent        = rt.battery_v?.toFixed(1) ?? '--';
      document.getElementById('batt-temp').textContent     = rt.battery_temp_c ?? '--';
      document.getElementById('charge-i').textContent      = rt.charge_i?.toFixed(2) ?? '--';
      document.getElementById('pv-w').textContent          = rt.pv_w ?? '--';
      document.getElementById('pv-v').textContent          = rt.pv_v?.toFixed(1) ?? '--';
      document.getElementById('pv-i').textContent          = rt.pv_i?.toFixed(2) ?? '--';
      document.getElementById('load-w').textContent        = rt.load_w ?? '--';
      document.getElementById('load-state').textContent    = 'load ' + (rt.load_on ? 'ON' : 'OFF');
      document.getElementById('charge-state').textContent  = (rt.charge_state_label ?? '--').toUpperCase();
      document.getElementById('last-update').textContent   = new Date(rt.ts).toLocaleTimeString('en-US', { hour12: false });
      setStatus(true);
    }

    // --- Timeseries — 8 datasets across 6 charts ---
    if (ts && ts.length) {
      const pts = ts.map(r => r.bucket);

      powerChart.data.datasets[0].data   = ts.map(r => ({ x: r.bucket, y: r.pv_w }));
      powerChart.data.datasets[1].data   = ts.map(r => ({ x: r.bucket, y: r.load_w }));
      powerChart.update('none');

      batteryChart.data.datasets[0].data = ts.map(r => ({ x: r.bucket, y: r.battery_v }));
      batteryChart.update('none');

      socChart.data.datasets[0].data     = ts.map(r => ({ x: r.bucket, y: r.battery_soc }));
      socChart.update('none');

      chargeIChart.data.datasets[0].data = ts.map(r => ({ x: r.bucket, y: r.charge_i }));
      chargeIChart.update('none');

      tempChart.data.datasets[0].data    = ts.map(r => ({ x: r.bucket, y: r.controller_temp_c }));
      tempChart.data.datasets[1].data    = ts.map(r => ({ x: r.bucket, y: r.battery_temp_c }));
      tempChart.update('none');

      // Charge state — constant-height bar per bucket, colored per state
      stateChart.data.datasets[0].data   = ts.map(r => ({ x: r.bucket, y: 1 }));
      stateChart.data.datasets[0].backgroundColor = ts.map(r => STATE_STYLE[r.charge_state]?.color || C.txt3);
      stateChart.data.datasets[0]._states = ts.map(r => r.charge_state);
      stateChart.update('none');
    }

    // --- 7-day energy bar ---
    if (daily && daily.length) {
      const ordered = [...daily].reverse();  // API returns DESC; chart wants ASC
      const labels = ordered.map(d => {
        const dt = new Date(d.date);
        return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      });
      energyChart.data.labels = labels;
      energyChart.data.datasets[0].data = ordered.map(d => d.generated_wh ?? 0);
      energyChart.data.datasets[1].data = ordered.map(d => d.consumed_wh  ?? 0);
      energyChart.update('none');

      // Today's numbers in the aggregate strip
      const today = daily.find(d => d.date === new Date().toISOString().slice(0, 10)) || daily[0];
      document.getElementById('today-gen').textContent  = today.generated_wh ?? '--';
      document.getElementById('today-used').textContent = today.consumed_wh  ?? '--';
    }

    // --- Lifetime counters ---
    if (lt) {
      document.getElementById('lifetime-gen').textContent = (lt.cumulative_gen_wh / 1000).toFixed(2);
      document.getElementById('ops-days').textContent     = lt.operating_days ?? '--';
    }

    // --- Fault timeline + list ---
    if (ev) {
      // Filter to actual faults (non-zero fault_word); skip the "cleared" rows
      const cutoffMs = Date.now() - 30 * 24 * 3600 * 1000;
      const faults = ev.filter(e => e.fault_word && e.fault_word !== 0 && new Date(e.ts).getTime() >= cutoffMs);

      faultChart.data.datasets[0].data = faults.map(e => ({
        x: e.ts, y: 0.5, description: e.description || `fault 0x${(e.fault_word).toString(16).padStart(8, '0')}`,
      }));
      faultChart.update('none');

      const badge = document.getElementById('fault-badge');
      const list  = document.getElementById('fault-list');
      if (faults.length === 0) {
        badge.textContent = 'CLEAR';
        badge.className = 'panel-badge live';
        list.innerHTML = '<span style="color: var(--txt3);">No faults recorded in the last 30 days.</span>';
      } else {
        badge.textContent = `${faults.length} EVENT${faults.length > 1 ? 'S' : ''}`;
        badge.className = 'panel-badge warn';
        // Latest 5 faults in the list
        const rows = faults.slice(0, 5).map(e => {
          const dt = new Date(e.ts).toLocaleString('en-US', { hour12: false });
          const desc = e.description || `0x${(e.fault_word).toString(16).padStart(8, '0')}`;
          return `<div><span style="color: var(--danger);">${dt}</span> · ${desc}</div>`;
        });
        list.innerHTML = rows.join('');
      }
    }

  } catch (e) {
    console.error('refresh failed', e);
    setStatus(false, 'CONNECTION ERROR');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  tickClock();
  refresh();
  setInterval(tickClock, 1000);
  setInterval(refresh, 30000);
});
