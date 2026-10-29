/**
 * FocusGuard Dashboard Controller — Professional Formal Presentation Edition
 * Bersih, terfokus pada metrik penting, dan bebas dari elemen dekoratif AI slop.
 */

let accChart = null;
let gyroChart = null;
let pollTimer = null;
let currentSessionState = "IDLE";
let currentTab = "events";

document.addEventListener("DOMContentLoaded", () => {
  initTechnicalCharts();
  startPolling();
  refreshHistory();
});

// =============================================================================
// 1. INISIALISASI GRAFIK REAL-TIME TEKNIS (WHITE CANVAS, SOLID LINES)
// =============================================================================
function initTechnicalCharts() {
  const chartConfig = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    scales: {
      x: {
        grid: { color: '#f4f4f5' },
        ticks: { color: '#71717a', font: { size: 10 }, maxTicksLimit: 6 }
      },
      y: {
        grid: { color: '#f4f4f5' },
        ticks: { color: '#71717a', font: { size: 10 } }
      }
    },
    plugins: {
      legend: {
        display: false // Menggunakan legend kustom di atas card
      }
    }
  };

  // 1. Grafik Percepatan
  const accCtx = document.getElementById("accChart").getContext("2d");
  accChart = new Chart(accCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "HP di Meja",
          borderColor: "#18181b", // Solid Charcoal
          borderWidth: 1.5,
          pointRadius: 0,
          data: []
        },
        {
          label: "HP di Saku",
          borderColor: "#059669", // Solid Emerald
          borderWidth: 1.5,
          pointRadius: 0,
          data: []
        }
      ]
    },
    options: chartConfig
  });

  // 2. Grafik Gyroscope
  const gyroCtx = document.getElementById("gyroChart").getContext("2d");
  gyroChart = new Chart(gyroCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Rotasi HP Meja",
          borderColor: "#18181b",
          borderWidth: 1.5,
          pointRadius: 0,
          data: []
        },
        {
          label: "Gerak Pengguna",
          borderColor: "#059669",
          borderWidth: 1.5,
          pointRadius: 0,
          data: []
        }
      ]
    },
    options: chartConfig
  });
}

// =============================================================================
// 2. POLLING REAL-TIME DARI SERVER
// =============================================================================
function startPolling() {
  fetchStatus();
  pollTimer = setInterval(fetchStatus, 700);
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();
    renderDashboard(data);
  } catch (err) {
    console.warn("Gagal terhubung ke server:", err);
  }
}

function renderDashboard(data) {
  currentSessionState = data.state;

  // 1. Render Hero Section (Timer & Tombol Utama)
  renderHeroControls(data);

  // 2. Render Status Fisik Real-time (Solid Pill)
  renderLiveStatusPill(data);

  // 3. Render Metrik Utama
  const m = data.metrics || {};
  const score = m.continuity_ratio !== undefined ? Math.round(m.continuity_ratio) : 100;

  document.getElementById("focusScore").textContent = `${score}%`;
  const qualityTag = document.getElementById("focusQualityTag");
  if (score >= 85) {
    qualityTag.textContent = "Sangat Baik";
    qualityTag.className = "text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800";
  } else if (score >= 60) {
    qualityTag.textContent = "Cukup Baik";
    qualityTag.className = "text-xs font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800";
  } else {
    qualityTag.textContent = "Perlu Evaluasi";
    qualityTag.className = "text-xs font-bold px-2 py-0.5 rounded bg-rose-100 text-rose-800";
  }

  // Waktu Terganggu & Frekuensi
  document.getElementById("interruptionTimeText").textContent = m.formatted_t_i || "00:00:00";
  document.getElementById("interruptionSecValue").textContent = Math.round(m.t_i_sec || 0);
  document.getElementById("interruptionCount").textContent = m.interruption_count || 0;

  // 4. Status Perangkat
  const dev = data.devices || {};
  renderDevicePill("stateHpA", dev.study_phone, "table");
  renderDevicePill("stateHpB", dev.activity_ref, "pocket");

  // 5. Update Grafik Sensor
  if (data.charts) {
    updateCharts(data.charts);
  }

  // 6. Update Tabel Log Gangguan
  renderEventsTable(data.interruptions || []);
}

function renderHeroControls(data) {
  const m = data.metrics || {};
  const timerText = document.getElementById("studyTimerText");
  const heroStateLabel = document.getElementById("heroStateLabel");
  const btnStart = document.getElementById("btnStart");
  const btnPause = document.getElementById("btnPause");
  const btnStop = document.getElementById("btnStop");
  const textPause = document.getElementById("textPause");
  const sessionInput = document.getElementById("sessionTitleInput");

  timerText.textContent = m.formatted_t_s || "00:00:00";

  if (data.state === "RUNNING") {
    heroStateLabel.textContent = `Sesi Aktif: ${data.title || "Belajar Mandiri"}`;
    heroStateLabel.className = "text-xs font-bold text-emerald-700 uppercase tracking-widest";

    btnStart.classList.add("hidden");
    btnPause.classList.remove("hidden");
    btnStop.classList.remove("hidden");
    textPause.textContent = "Jeda";
    sessionInput.disabled = true;
  } else if (data.state === "PAUSED") {
    heroStateLabel.textContent = `Sesi Dijeda: ${data.title || "Belajar Mandiri"}`;
    heroStateLabel.className = "text-xs font-bold text-amber-700 uppercase tracking-widest";

    btnStart.classList.add("hidden");
    btnPause.classList.remove("hidden");
    btnStop.classList.remove("hidden");
    textPause.textContent = "Lanjutkan";
    sessionInput.disabled = true;
  } else {
    // IDLE atau COMPLETED
    heroStateLabel.textContent = "Sesi Belum Dimulai";
    heroStateLabel.className = "text-xs font-semibold text-zinc-400 uppercase tracking-widest";

    btnStart.classList.remove("hidden");
    btnPause.classList.add("hidden");
    btnStop.classList.add("hidden");
    sessionInput.disabled = false;
  }
}

function renderLiveStatusPill(data) {
  const pill = document.getElementById("statusPill");
  const dot = document.getElementById("statusDot");
  const msg = document.getElementById("statusMessage");
  const state = data.current_fused_state || "FOKUS_BELAJAR";

  if (data.state !== "RUNNING" && data.state !== "PAUSED") {
    pill.className = "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-zinc-100 text-zinc-600 border border-zinc-200";
    dot.className = "w-2 h-2 rounded-full bg-zinc-400";
    msg.textContent = "Menunggu dimulainya sesi belajar";
    return;
  }

  if (state === "FOKUS_BELAJAR") {
    pill.className = "inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-900 border border-emerald-300";
    dot.className = "w-2 h-2 rounded-full bg-emerald-600";
    msg.textContent = "Kondisi Belajar Tenang — Kedua ponsel diam di posisi belajar";
  } else if (state === "INTERUPSI_HP_MEJA") {
    pill.className = "inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300";
    dot.className = "w-2 h-2 rounded-full bg-amber-600";
    msg.textContent = "Terdeteksi Gangguan: HP di meja sedang diangkat / disentuh";
  } else if (state === "INTERUPSI_PENGGUNA_AWAY") {
    pill.className = "inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300";
    dot.className = "w-2 h-2 rounded-full bg-amber-600";
    msg.textContent = "Terdeteksi Gangguan: Pengguna sedang beranjak / meninggalkan meja";
  } else if (state === "INTERUPSI_PINDAH_MEMBAWA_HP") {
    pill.className = "inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold bg-rose-100 text-rose-900 border border-rose-300";
    dot.className = "w-2 h-2 rounded-full bg-rose-600";
    msg.textContent = "Terdeteksi Gangguan: Berpindah tempat sambil membawa HP";
  }
}

function renderDevicePill(elementId, info, role) {
  const el = document.getElementById(elementId);
  if (!el || !info) return;

  if (!info.online) {
    el.textContent = "Tidak Terhubung";
    el.className = "font-bold px-2 py-0.5 rounded bg-zinc-100 text-zinc-500 border border-zinc-200";
    return;
  }

  const isMoving = info.latest && info.latest.is_moving;
  if (role === "table") {
    if (isMoving) {
      el.textContent = "Diangkat / Bergerak";
      el.className = "font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-200";
    } else {
      el.textContent = "Diam di Meja";
      el.className = "font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 border border-emerald-200";
    }
  } else {
    if (isMoving) {
      el.textContent = "Sedang Bergerak";
      el.className = "font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-200";
    } else {
      el.textContent = "Duduk Tenang";
      el.className = "font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-900 border border-emerald-200";
    }
  }
}

function updateCharts(charts) {
  const bufA = charts.study_phone || [];
  const bufB = charts.activity_ref || [];
  const maxLen = Math.max(bufA.length, bufB.length);
  if (maxLen === 0) return;

  const labels = [];
  const accA = [];
  const accB = [];
  const gyroA = [];
  const gyroB = [];

  for (let i = 0; i < maxLen; i++) {
    const itemA = bufA[i] || {};
    const itemB = bufB[i] || {};
    labels.push(itemA.time || itemB.time || "");
    accA.push(itemA.acc_mag !== undefined ? itemA.acc_mag : null);
    accB.push(itemB.acc_mag !== undefined ? itemB.acc_mag : null);
    gyroA.push(itemA.gyro_mag !== undefined ? itemA.gyro_mag : null);
    gyroB.push(itemB.gyro_mag !== undefined ? itemB.gyro_mag : null);
  }

  accChart.data.labels = labels;
  accChart.data.datasets[0].data = accA;
  accChart.data.datasets[1].data = accB;
  accChart.update("none");

  gyroChart.data.labels = labels;
  gyroChart.data.datasets[0].data = gyroA;
  gyroChart.data.datasets[1].data = gyroB;
  gyroChart.update("none");
}

function renderEventsTable(events) {
  const tbody = document.getElementById("eventsTableBody");
  document.getElementById("eventTabCount").textContent = events.length;

  if (events.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-zinc-400 italic font-normal">Belum ada gangguan yang tercatat pada sesi ini.</td></tr>`;
    return;
  }

  let html = "";
  events.forEach((ev, idx) => {
    html += `
      <tr class="hover:bg-zinc-50 transition">
        <td class="py-2.5 px-3 font-semibold text-zinc-500">${idx + 1}</td>
        <td class="py-2.5 px-3 font-mono">${ev.start_str || "-"}</td>
        <td class="py-2.5 px-3 font-mono">${ev.end_str || "-"}</td>
        <td class="py-2.5 px-3 font-bold text-zinc-900">${Math.round(ev.duration_sec)} detik</td>
        <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[11px] font-bold bg-zinc-100 text-zinc-800 border border-zinc-200">${translateInterruptionType(ev.type)}</span></td>
        <td class="py-2.5 px-3 text-zinc-500">${ev.description || "-"}</td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

function translateInterruptionType(type) {
  if (!type) return "Gangguan Fisik";
  if (type.includes("HP_DIANGKAT")) return "HP di Meja Diangkat";
  if (type.includes("PINDAH_MEMBAWA_HP")) return "Berpindah Membawa HP";
  if (type.includes("PENGGUNA_AWAY") || type.includes("MENINGGALKAN_MEJA")) return "Meninggalkan Meja";
  return "Aktivitas Fisik";
}

// =============================================================================
// 3. KONTROL SESI BELAJAR
// =============================================================================
async function startSession() {
  const title = document.getElementById("sessionTitleInput").value.trim() || "Sesi Belajar Mandiri";
  try {
    await fetch("/api/session/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title })
    });
    fetchStatus();
  } catch (err) {
    alert("Gagal memulai sesi: " + err);
  }
}

async function togglePauseSession() {
  const endpoint = currentSessionState === "RUNNING" ? "/api/session/pause" : "/api/session/resume";
  try {
    await fetch(endpoint, { method: "POST" });
    fetchStatus();
  } catch (err) {
    alert("Gagal mengubah status sesi: " + err);
  }
}

async function stopSession() {
  if (!confirm("Akhiri sesi belajar dan simpan laporannya?")) return;
  try {
    await fetch("/api/session/stop", { method: "POST" });
    fetchStatus();
    refreshHistory();
  } catch (err) {
    alert("Gagal mengakhiri sesi: " + err);
  }
}

// =============================================================================
// 4. NAVIGASI TAB & RIWAYAT SESI
// =============================================================================
function switchTab(tab) {
  currentTab = tab;
  const tabEvents = document.getElementById("tabEvents");
  const tabHistory = document.getElementById("tabHistory");
  const tabBtnEvents = document.getElementById("tabBtnEvents");
  const tabBtnHistory = document.getElementById("tabBtnHistory");
  const historyActionWrap = document.getElementById("historyActionWrap");

  if (tab === "events") {
    tabEvents.classList.remove("hidden");
    tabHistory.classList.add("hidden");
    if (historyActionWrap) historyActionWrap.classList.add("hidden");

    tabBtnEvents.className = "pb-3 border-b-2 border-zinc-900 text-zinc-900 transition";
    tabBtnHistory.className = "pb-3 border-b-2 border-transparent text-zinc-500 hover:text-zinc-900 transition";
  } else {
    tabEvents.classList.add("hidden");
    tabHistory.classList.remove("hidden");
    if (historyActionWrap) historyActionWrap.classList.remove("hidden");

    tabBtnHistory.className = "pb-3 border-b-2 border-zinc-900 text-zinc-900 transition";
    tabBtnEvents.className = "pb-3 border-b-2 border-transparent text-zinc-500 hover:text-zinc-900 transition";
    refreshHistory();
  }
}

async function clearHistoryLog() {
  if (!confirm("Hapus seluruh log dan riwayat sesi belajar yang tersimpan?")) return;
  try {
    const res = await fetch("/api/history/clear", { method: "POST" });
    if (res.ok) {
      refreshHistory();
    }
  } catch (err) {
    alert("Gagal menghapus riwayat: " + err);
  }
}

async function refreshHistory() {
  const tbody = document.getElementById("historyTableBody");
  try {
    const res = await fetch("/api/history");
    const sessions = await res.json();

    if (!sessions || sessions.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-zinc-400 italic font-normal">Belum ada riwayat sesi belajar yang tersimpan.</td></tr>`;
      return;
    }

    let html = "";
    sessions.forEach((s) => {
      const m = s.metrics || {};
      const score = Math.round(m.continuity_ratio !== undefined ? m.continuity_ratio : 100);

      html += `
        <tr class="hover:bg-zinc-50 transition">
          <td class="py-2.5 px-3 text-zinc-500 font-mono text-[11px]">${s.start_time_iso || "-"}</td>
          <td class="py-2.5 px-3 font-semibold text-zinc-800">${s.title || "Sesi Belajar"}</td>
          <td class="py-2.5 px-3 font-mono text-zinc-800">${m.formatted_t_s || "00:00:00"}</td>
          <td class="py-2.5 px-3 font-mono text-zinc-500">${m.formatted_t_i || "00:00:00"} (${Math.round(m.t_i_sec || 0)}s)</td>
          <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[11px] font-bold bg-zinc-100 text-zinc-800 border border-zinc-200">${score}%</span></td>
          <td class="py-2.5 px-3 text-zinc-800">${m.interruption_count || 0} kali</td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-rose-600 italic">Gagal memuat riwayat: ${err}</td></tr>`;
  }
}
