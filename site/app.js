// 診所選址評估前端：讀 data/history.json + data/geo.json，畫雷達／趨勢／因子圖 + 地圖
"use strict";

const SPECIALTY_LABELS = {
  family_medicine: "家醫科",
  functional_medicine: "功能醫學",
  weight_loss: "減重",
  psychiatry: "精神/身心",
  aesthetics: "醫美",
};

const FACTOR_LABELS = {
  population_density: "人口密度",
  age_gender: "年齡/性別",
  day_night_gap: "晝夜落差",
  purchasing_power: "消費力",
  business_density: "商業密度",
  land_use_mix: "土地混合",
  competition: "同業競爭",
  complementary_anchors: "互補錨點",
  convenience_density: "超商密度",
  accessibility: "交通可及",
  redevelopment_stage: "重劃/屋齡",
  visibility: "能見度",
};

const SOURCE_COLORS = {
  real: "#16a34a",
  degraded: "#d97706",
  manual: "#6366f1",
  missing: "#9ca3af",
};

const SERIES_COLORS = [
  "#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed",
];

function specLabel(key) { return SPECIALTY_LABELS[key] || key; }
function factorLabel(key) { return FACTOR_LABELS[key] || key; }

async function loadJSON(path, fallback) {
  try {
    const resp = await fetch(path, { cache: "no-store" });
    if (!resp.ok) return fallback;
    return await resp.json();
  } catch (e) {
    return fallback;
  }
}

function renderMeta(payload) {
  const m = payload.meta || {};
  document.getElementById("meta-line").textContent =
    `${m.address || ""}　${(m.latlon || []).join(", ")}`;
  if (payload.generated) {
    document.getElementById("generated").textContent =
      `資料產生時間：${payload.generated}`;
  }
}

function renderRadar(radar) {
  const ctx = document.getElementById("radarChart");
  if (!radar.labels.length) return;
  new Chart(ctx, {
    type: "radar",
    data: {
      labels: radar.labels.map(specLabel),
      datasets: [{
        label: "適合度",
        data: radar.scores,
        backgroundColor: "rgba(37,99,235,0.18)",
        borderColor: "#2563eb",
        pointBackgroundColor: "#2563eb",
      }],
    },
    options: {
      responsive: true,
      scales: { r: { suggestedMin: 0, suggestedMax: 100 } },
    },
  });
}

function renderTrend(trend) {
  const ctx = document.getElementById("trendChart");
  if (!trend.dates.length) return;
  const names = Object.keys(trend.specialties);
  const datasets = names.map((name, i) => ({
    label: specLabel(name),
    data: trend.specialties[name],
    borderColor: SERIES_COLORS[i % SERIES_COLORS.length],
    backgroundColor: SERIES_COLORS[i % SERIES_COLORS.length],
    tension: 0.25,
    spanGaps: true,
  }));
  new Chart(ctx, {
    type: "line",
    data: { labels: trend.dates, datasets },
    options: {
      responsive: true,
      scales: { y: { suggestedMin: 0, suggestedMax: 100 } },
    },
  });
}

function renderFactors(factors) {
  const ctx = document.getElementById("factorChart");
  if (!factors.length) return;
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: factors.map(f => factorLabel(f.factor)),
      datasets: [{
        label: "因子分數",
        data: factors.map(f => f.score),
        backgroundColor: factors.map(f => SOURCE_COLORS[f.source] || "#9ca3af"),
      }],
    },
    options: {
      responsive: true,
      indexAxis: "y",
      scales: { x: { suggestedMin: 0, suggestedMax: 100 } },
      plugins: { legend: { display: false } },
    },
  });
}

function renderMap(payload, geo) {
  const card = document.getElementById("map-card");
  const center = (payload.meta && payload.meta.latlon) || null;
  if (!center) { card.style.display = "none"; return; }

  const map = L.map("map").setView(center, 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  L.marker(center).addTo(map).bindPopup("候選點").openPopup();
  L.circle(center, { radius: 1000, color: "#2563eb", fill: false }).addTo(map);
  L.circle(center, { radius: 3000, color: "#16a34a", fill: false }).addTo(map);

  const groups = {
    clinics: { color: "#dc2626", label: "競爭診所" },
    anchors: { color: "#7c3aed", label: "互補錨點" },
    convenience: { color: "#d97706", label: "便利商店" },
    transit: { color: "#0891b2", label: "公車站" },
  };
  Object.entries(groups).forEach(([key, cfg]) => {
    (geo[key] || []).forEach(p => {
      if (p.lat == null || p.lon == null) return;
      L.circleMarker([p.lat, p.lon], {
        radius: 5, color: cfg.color, fillOpacity: 0.7,
      }).addTo(map).bindPopup(`${cfg.label}${p.name ? "：" + p.name : ""}`);
    });
  });
}

async function main() {
  const payload = await loadJSON("data/history.json", {
    meta: {}, trend: { dates: [], specialties: {} },
    radar: { labels: [], scores: [] }, factors: [],
  });
  const geo = await loadJSON("data/geo.json", {});

  renderMeta(payload);
  renderRadar(payload.radar);
  renderTrend(payload.trend);
  renderFactors(payload.factors);
  renderMap(payload, geo);
}

main();
