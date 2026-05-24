'use strict';

// Rolling buffers for sparklines (live + sparklines history mode).
// 90 samples ≈ 3 minutes at the default 2s poll interval. Kept in memory only.
const MAX_POINTS = 90;
const buffers = { cpu: [], ram: [], temp: [] };

let cfg = { host: '—', port: 8080 };

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);

function fmtBytes(n) {
  if (n == null) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  n = Number(n);
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function fmtBps(n) {
  if (n == null) return '—';
  return `${fmtBytes(n)}/s`;
}

function fmtUptime(s) {
  if (s == null) return '—';
  s = Math.floor(s);
  const d = Math.floor(s / 86400); s %= 86400;
  const h = Math.floor(s / 3600); s %= 3600;
  const m = Math.floor(s / 60);
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h || d) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(' ');
}

function levelClass(pct) {
  if (pct >= 90) return 'crit';
  if (pct >= 70) return 'warn';
  return '';
}

function push(buf, v) {
  buf.push(v);
  if (buf.length > MAX_POINTS) buf.shift();
}

// ---------- sparkline ----------
function drawSpark(canvas, data, color, opts = {}) {
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  const dpr = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (data.length < 2) return;

  const min = opts.min != null ? opts.min : Math.min(...data);
  const max = opts.max != null ? opts.max : Math.max(...data);
  const range = (max - min) || 1;
  const stepX = w / (data.length - 1);
  const y = (v) => h - ((v - min) / range) * (h - 3) - 2;

  // line
  ctx.beginPath();
  data.forEach((v, i) => {
    const px = i * stepX;
    const py = y(v);
    i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.lineJoin = 'round';
  ctx.stroke();

  // area fill
  ctx.lineTo((data.length - 1) * stepX, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.globalAlpha = 0.14;
  ctx.fillStyle = color;
  ctx.fill();
  ctx.globalAlpha = 1;
}

const SPARK_COLOR = { cpu: '#2dd4bf', ram: '#a78bfa', temp: '#ffb44c' };

function redrawSparks() {
  drawSpark($('cpu-spark'), buffers.cpu, SPARK_COLOR.cpu, { min: 0, max: 100 });
  drawSpark($('ram-spark'), buffers.ram, SPARK_COLOR.ram, { min: 0, max: 100 });
  drawSpark($('temp-spark'), buffers.temp, SPARK_COLOR.temp, { min: 30, max: 90 });
}

// ---------- per-core bars ----------
function renderCores(perCore) {
  const host = $('cpu-cores');
  if (!Array.isArray(perCore)) { host.innerHTML = ''; return; }
  if (host.children.length !== perCore.length) {
    host.innerHTML = perCore.map((_, i) =>
      `<div class="core"><div class="core-fill" data-i="${i}"></div><span class="core-num">${i}</span></div>`
    ).join('');
  }
  perCore.forEach((pct, i) => {
    const fill = host.querySelector(`.core-fill[data-i="${i}"]`);
    if (fill) {
      fill.style.height = `${Math.max(2, pct)}%`;
      fill.className = `core-fill ${levelClass(pct)}`;
    }
  });
}

// ---------- disks ----------
function renderDisks(disks) {
  const host = $('disk-list');
  if (!Array.isArray(disks) || !disks.length) {
    host.innerHTML = '<div class="muted" style="font-size:11px">No disks reported</div>';
    $('disk-count').textContent = '';
    return;
  }
  $('disk-count').textContent = `${disks.length} mount${disks.length > 1 ? 's' : ''}`;
  host.innerHTML = disks.map((d) => {
    const pct = d.percent ?? 0;
    return `
      <div class="disk-row">
        <div class="disk-top">
          <span class="disk-mount">${d.mount}</span>
          <span class="disk-used">${fmtBytes(d.used)} / ${fmtBytes(d.total)} · ${pct.toFixed(0)}%</span>
        </div>
        <div class="bar"><div class="bar-fill ${levelClass(pct)}" style="width:${pct}%"></div></div>
      </div>`;
  }).join('');
}

// ---------- throttle ----------
function renderThrottle(t) {
  const chip = $('throttle-chip');
  if (!t) { chip.classList.add('hidden'); return; }
  if (t.under_voltage_now || t.throttled_now || t.freq_capped_now) {
    chip.textContent = t.under_voltage_now ? '⚠ UNDER-VOLTAGE' : '⚠ THROTTLING NOW';
    chip.className = 'chip';
    chip.classList.remove('hidden');
  } else if (t.under_voltage_occurred || t.throttled_occurred) {
    chip.textContent = '⚠ throttled earlier';
    chip.className = 'chip warn-amber';
    chip.classList.remove('hidden');
  } else {
    chip.classList.add('hidden');
  }
}

// ---------- main render ----------
function setStatus(state) {
  const dot = $('status-dot');
  dot.className = `dot dot-${state}`;
}

function renderOk(d) {
  setStatus('ok');
  // identity
  $('hostname').textContent = d.host?.hostname || 'Pi';
  $('ipaddr').textContent = `${cfg.host}:${cfg.port}`;
  $('uptime').textContent = `uptime ${fmtUptime(d.host?.uptime_seconds)}`;
  $('platform').textContent = d.host?.machine || '';

  // CPU
  if (d.cpu) {
    const pct = d.cpu.percent ?? 0;
    $('cpu-pct').textContent = `${pct.toFixed(0)}%`;
    const bar = $('cpu-bar');
    bar.style.width = `${pct}%`;
    bar.className = `bar-fill ${levelClass(pct)}`;
    const freq = d.cpu.freq_mhz ? `${(d.cpu.freq_mhz / 1000).toFixed(2)} GHz` : '— MHz';
    $('cpu-freq').textContent = `${freq} · ${d.cpu.cores_logical || '?'} cores`;
    const la = d.cpu.load_avg || [];
    $('cpu-load').textContent = la[0] != null
      ? `load ${la[0].toFixed(2)} / ${la[1].toFixed(2)} / ${la[2].toFixed(2)}`
      : 'load —';
    renderCores(d.cpu.per_core);
    push(buffers.cpu, pct);
  }

  // Memory
  if (d.memory) {
    const pct = d.memory.percent ?? 0;
    $('ram-pct').textContent = `${pct.toFixed(0)}%`;
    const bar = $('ram-bar');
    bar.style.width = `${pct}%`;
    bar.className = `bar-fill ${levelClass(pct)}`;
    $('ram-detail').textContent = `${fmtBytes(d.memory.used)} / ${fmtBytes(d.memory.total)}`;
    push(buffers.ram, pct);
  }
  if (d.swap && d.swap.total > 0) {
    $('swap-detail').textContent = `swap ${d.swap.percent.toFixed(0)}%`;
  } else {
    $('swap-detail').textContent = '';
  }

  // Temp
  if (d.temp_c != null) {
    $('temp-val').textContent = `${d.temp_c.toFixed(1)} °C`;
    push(buffers.temp, d.temp_c);
  } else {
    $('temp-val').textContent = 'n/a';
  }
  renderThrottle(d.throttle);

  // Storage + network
  renderDisks(d.disks);
  $('net-down').textContent = fmtBps(d.network?.recv_bps);
  $('net-up').textContent = fmtBps(d.network?.sent_bps);
  $('proc-count').textContent = d.processes ?? '—';

  redrawSparks();
  $('updated').textContent = `updated ${new Date().toLocaleTimeString()}`;
}

function renderError(payload) {
  setStatus('err');
  $('ipaddr').textContent = `${payload.host || cfg.host}:${payload.port || cfg.port}`;
  $('updated').textContent = `disconnected (${payload.error}) — ${new Date().toLocaleTimeString()}`;
}

// ---------- settings panel ----------
function openSettings() {
  $('cfg-host').value = cfg.host;
  $('cfg-port').value = cfg.port;
  $('cfg-interval').value = cfg.intervalMs;
  $('cfg-token').value = cfg.token || '';
  $('cfg-aot').checked = !!cfg.alwaysOnTop;
  $('cfg-login').checked = !!cfg.openAtLogin;
  $('settings-panel').classList.remove('hidden');
}
function closeSettings() { $('settings-panel').classList.add('hidden'); }

async function saveSettings() {
  cfg = await window.api.setConfig({
    host: $('cfg-host').value.trim() || cfg.host,
    port: Number($('cfg-port').value) || cfg.port,
    intervalMs: Number($('cfg-interval').value) || cfg.intervalMs,
    token: $('cfg-token').value.trim(),
    alwaysOnTop: $('cfg-aot').checked,
    openAtLogin: $('cfg-login').checked,
  });
  closeSettings();
}

// ---------- wire up ----------
window.api.onConfig((c) => { cfg = c; });
window.api.onMetrics((payload) => {
  if (payload.ok && payload.data?.ok) {
    renderOk(payload.data);
  } else if (payload.ok && payload.data) {
    // reachable but agent reported an error (e.g. psutil missing)
    renderError({ error: payload.data.error || 'agent error', host: cfg.host, port: cfg.port });
  } else {
    renderError(payload);
  }
});

$('gear-btn').addEventListener('click', openSettings);
$('cfg-cancel').addEventListener('click', closeSettings);
$('cfg-save').addEventListener('click', saveSettings);

window.addEventListener('resize', redrawSparks);

// pull initial config in case the push hasn't arrived yet
window.api.getConfig().then((c) => { if (c) cfg = c; });
