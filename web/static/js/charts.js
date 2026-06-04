const C = {
  acc:    '#00d4ff',
  acc2:   '#ff6b35',
  acc3:   '#00ff88',
  danger: '#ff3366',
  txt:    '#e8e8f0',
  txt2:   '#8888aa',
  txt3:   '#4444aa',
  border: 'rgba(0, 212, 255, 0.12)',
};
Chart.defaults.color = C.txt2;
Chart.defaults.borderColor = C.border;
Chart.defaults.font.family = "'IBM Plex Mono', monospace";
Chart.defaults.font.size = 10;

let powerChart, batteryChart;

function initCharts() {
  const base = {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: { type: 'time', time: { displayFormats: { hour: 'HH:mm', minute: 'HH:mm' } }, grid: { color: C.border }, ticks: { color: C.txt3 } },
      y: { grid: { color: C.border }, ticks: { color: C.txt3 }, beginAtZero: true },
    },
    plugins: {
      legend: { labels: { color: C.txt2, font: { size: 10 } } },
      tooltip: { backgroundColor: '#0f0f1a', borderColor: C.border, borderWidth: 1, titleColor: C.txt, bodyColor: C.txt },
    },
  };
  powerChart = new Chart(document.getElementById('chart-power'), {
    type: 'line',
    data: { datasets: [
      { label: 'PV (W)',   data: [], borderColor: C.acc,  backgroundColor: C.acc + '22',  fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 },
      { label: 'Load (W)', data: [], borderColor: C.acc2, backgroundColor: C.acc2 + '22', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 },
    ]},
    options: base,
  });
  batteryChart = new Chart(document.getElementById('chart-battery'), {
    type: 'line',
    data: { datasets: [
      { label: 'Battery (V)', data: [], borderColor: C.acc3, backgroundColor: C.acc3 + '22', fill: true, tension: 0.2, pointRadius: 0, borderWidth: 1.5 },
    ]},
    options: { ...base, scales: { ...base.scales, y: { ...base.scales.y, beginAtZero: false } } },
  });
}

function tickClock() {
  const d = new Date();
  document.getElementById('clock').textContent = d.toLocaleTimeString('en-US', { hour12: false });
}

function setStatus(ok, txt) {
  const dot = document.getElementById('status-dot');
  const t = document.getElementById('status-txt');
  if (ok) { dot.classList.remove('err'); t.classList.remove('err'); t.textContent = txt || 'NOMINAL'; }
  else    { dot.classList.add('err');    t.classList.add('err');    t.textContent = txt || 'ERROR'; }
}

async function refresh() {
  try {
    const [rt, ts, daily, lt] = await Promise.all([
      fetch('/api/realtime').then(r => r.json()),
      fetch('/api/timeseries?hours=24').then(r => r.json()),
      fetch('/api/daily?days=1').then(r => r.json()),
      fetch('/api/lifetime').then(r => r.json()),
    ]);

    if (rt) {
      document.getElementById('soc').textContent       = rt.battery_soc ?? '--';
      document.getElementById('batt-v').textContent    = rt.battery_v?.toFixed(1) ?? '--';
      document.getElementById('batt-temp').textContent = rt.battery_temp_c ?? '--';
      document.getElementById('charge-i').textContent  = rt.charge_i?.toFixed(2) ?? '--';
      document.getElementById('pv-w').textContent      = rt.pv_w ?? '--';
      document.getElementById('pv-v').textContent      = rt.pv_v?.toFixed(1) ?? '--';
      document.getElementById('pv-i').textContent      = rt.pv_i?.toFixed(2) ?? '--';
      document.getElementById('load-w').textContent    = rt.load_w ?? '--';
      document.getElementById('load-state').textContent = 'load ' + (rt.load_on ? 'ON' : 'OFF');
      document.getElementById('charge-state').textContent = (rt.charge_state_label ?? '--').toUpperCase();
      document.getElementById('last-update').textContent = new Date(rt.ts).toLocaleTimeString('en-US', { hour12: false });
      setStatus(true);
    }
    if (ts && ts.length) {
      powerChart.data.datasets[0].data   = ts.map(r => ({ x: r.bucket, y: r.pv_w }));
      powerChart.data.datasets[1].data   = ts.map(r => ({ x: r.bucket, y: r.load_w }));
      powerChart.update('none');
      batteryChart.data.datasets[0].data = ts.map(r => ({ x: r.bucket, y: r.battery_v }));
      batteryChart.update('none');
    }
    if (daily && daily.length) {
      const today = daily.find(d => d.date === new Date().toISOString().slice(0,10)) || daily[0];
      document.getElementById('today-gen').textContent  = today.generated_wh ?? '--';
      document.getElementById('today-used').textContent = today.consumed_wh ?? '--';
    }
    if (lt) {
      document.getElementById('lifetime-gen').textContent = (lt.cumulative_gen_wh / 1000).toFixed(2);
      document.getElementById('ops-days').textContent     = lt.operating_days ?? '--';
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
