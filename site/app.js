// 診所選址評估前端：讀 data/history.json + data/geo.json
// 顯示排名、各科加權拆解、因子原始數據、趨勢、地圖
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
  competition: "西醫診所競爭",
  competition_aesthetic: "醫美/美容競爭",
  complementary_anchors: "互補錨點",
  convenience_density: "超商密度",
  accessibility: "交通可及",
  redevelopment_stage: "重劃/屋齡",
  visibility: "能見度",
  school_proximity: "學校鄰近",
};

const SOURCE_LABELS = {
  real: "real", degraded: "degraded", manual: "manual", missing: "missing",
};

const SERIES_COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed"];

function specLabel(k) { return SPECIALTY_LABELS[k] || k; }
function factorLabel(k) { return FACTOR_LABELS[k] || k; }
function fmt(n) { return n == null ? "—" : (Math.round(n * 10) / 10).toFixed(1); }

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
  renderFreshness(payload);
}

// 資料新鮮度徽章：顯示最新快照日期，超過 STALE_DAYS 天標紅提醒該刷新
const STALE_DAYS = 40;
function renderFreshness(payload) {
  const el = document.getElementById("freshness");
  if (!el) return;
  const dates = (payload.trend && payload.trend.dates) || [];
  const last = dates.length ? dates[dates.length - 1] : null;
  if (!last) { el.textContent = ""; return; }
  const ageDays = Math.floor((Date.now() - new Date(last).getTime()) / 86400000);
  const stale = ageDays > STALE_DAYS;
  el.classList.toggle("stale", stale);
  el.classList.toggle("fresh", !stale);
  const ageTxt = ageDays <= 0 ? "今日更新" : `${ageDays} 天前`;
  el.textContent = `資料更新於 ${last}（${ageTxt}）${stale ? "　⚠ 已逾 " + STALE_DAYS + " 天，建議重新刷新" : ""}`;
}

// 排名：用最新趨勢值排序
function renderRanking(payload) {
  const el = document.getElementById("ranking");
  const trend = payload.trend || { dates: [], specialties: {} };
  const n = trend.dates.length;
  if (!n) { el.textContent = "尚無資料"; return; }
  const rows = Object.entries(trend.specialties)
    .map(([k, arr]) => [k, arr[n - 1]])
    .filter(([, v]) => v != null)
    .sort((a, b) => b[1] - a[1]);
  const max = rows.length ? rows[0][1] : 100;
  el.innerHTML = rows.map(([k, v], i) => `
    <div class="rank-row">
      <span class="rank-no">${i + 1}</span>
      <span class="rank-name">${specLabel(k)}</span>
      <span class="rank-bar"><span style="width:${(v / max * 100).toFixed(1)}%"></span></span>
      <span class="rank-score">${fmt(v)}</span>
    </div>`).join("");
}

// 數值權重 → 等級標籤（對齊 config weight_levels）
const WEIGHT_LEVEL = { 5: "最高", 4: "高", 3: "中", 2: "低", 1: "極低", 0: "無" };
function levelLabel(w) { return WEIGHT_LEVEL[w] != null ? WEIGHT_LEVEL[w] : String(w); }

// 各科加權拆解表 + what-if 權重試算滑桿
function renderBreakdown(payload) {
  const breakdowns = payload.breakdowns || {};
  const names = Object.keys(breakdowns);
  const sel = document.getElementById("specialty-select");
  const tbody = document.querySelector("#breakdown-table tbody");
  const tfoot = document.querySelector("#breakdown-table tfoot");
  const resetBtn = document.getElementById("whatif-reset");
  if (!names.length) { tbody.innerHTML = "<tr><td colspan='4'>尚無資料</td></tr>"; return; }

  // 預設選總分最高的科別
  const ranked = names.slice().sort(
    (a, b) => breakdowns[b].total - breakdowns[a].total);
  sel.innerHTML = ranked.map(k => `<option value="${k}">${specLabel(k)}</option>`).join("");

  // 目前科別的 what-if 權重狀態：factor -> 權重（初始＝原始權重）
  let current = null;       // 科別名
  let liveWeights = {};     // 試算中的權重

  function weightedTotal(rows, weights) {
    let num = 0, den = 0;
    rows.forEach(r => {
      const w = weights[r.factor];
      if (r.score != null) { num += r.score * w; den += w; }
    });
    return den ? num / den : 0;
  }

  function rowsFor(name) { return breakdowns[name].rows; }

  function redraw() {
    const rows = rowsFor(current);
    const total = weightedTotal(rows, liveWeights);
    const orig = breakdowns[current].total;
    // 依「試算貢獻」排序
    const den = Object.values(liveWeights).reduce((a, b) => a + b, 0) || 1;
    const view = rows.map(r => ({
      ...r,
      w: liveWeights[r.factor],
      contribution: r.score != null ? r.score * liveWeights[r.factor] / den : 0,
    })).sort((a, b) => b.contribution - a.contribution);

    tbody.innerHTML = view.map(r => `
      <tr class="${r.w === 0 ? 'muted' : ''}">
        <td>${factorLabel(r.factor)}</td>
        <td class="wcell">
          <input type="range" min="0" max="5" step="1" value="${r.w}"
                 data-factor="${r.factor}" class="wslider" aria-label="${factorLabel(r.factor)} 權重">
          <span class="wlevel">${levelLabel(r.w)}<span class="wnum">(${r.w})</span></span>
        </td>
        <td>${fmt(r.score)}</td>
        <td><span class="contrib-bar"><span style="width:${Math.min(total ? r.contribution / total * 100 : 0, 100).toFixed(1)}%"></span></span>${fmt(r.contribution)}</td>
      </tr>`).join("");

    const changed = rows.some(r => liveWeights[r.factor] !== r.weight);
    const diff = total - orig;
    const diffTxt = changed
      ? `（原始 ${fmt(orig)}　<span class="${diff >= 0 ? 'up' : 'down'}">${diff >= 0 ? '+' : ''}${fmt(diff)}</span>）`
      : "";
    tfoot.innerHTML =
      `<tr><th colspan="3">${changed ? '試算總分' : '總分'}（加權平均）</th>` +
      `<th>${fmt(total)} ${diffTxt}</th></tr>`;
    if (resetBtn) resetBtn.disabled = !changed;

    // 綁定滑桿
    tbody.querySelectorAll(".wslider").forEach(sl => {
      sl.addEventListener("input", () => {
        liveWeights[sl.dataset.factor] = parseInt(sl.value, 10);
        redraw();
      });
    });
  }

  function load(name) {
    current = name;
    liveWeights = {};
    rowsFor(name).forEach(r => { liveWeights[r.factor] = r.weight; });
    redraw();
  }

  sel.onchange = () => load(sel.value);
  if (resetBtn) resetBtn.onclick = () => load(current);
  load(ranked[0]);
}

// 較上筆變化的文字（含漲跌色與比率）
function deltaCell(f) {
  if (f.delta == null) return `<span class="delta flat">—</span>`;
  const cls = f.delta > 0 ? "up" : (f.delta < 0 ? "down" : "flat");
  const arrow = f.delta > 0 ? "▲" : (f.delta < 0 ? "▼" : "—");
  const sign = f.delta > 0 ? "+" : "";
  const pct = f.delta_pct == null ? "" :
    `<span class="delta-pct">(${sign}${fmt(f.delta_pct)}%)</span>`;
  return `<span class="delta ${cls}">${arrow} ${sign}${fmt(f.delta)}</span>${pct}`;
}

// 因子原始數據表
function renderFactorTable(payload) {
  const tbody = document.querySelector("#factor-table tbody");
  const factors = payload.factors || [];
  if (!factors.length) { tbody.innerHTML = "<tr><td colspan='6'>尚無資料</td></tr>"; return; }
  tbody.innerHTML = factors.map(f => `
    <tr>
      <td>${factorLabel(f.factor)}</td>
      <td>${f.raw_text}</td>
      <td class="basis">${f.basis_text}</td>
      <td>${fmt(f.score)}</td>
      <td>${deltaCell(f)}</td>
      <td><span class="src ${f.source}">${SOURCE_LABELS[f.source] || f.source}</span></td>
    </tr>`).join("");
}

// 單因子分數趨勢：下拉選因子，畫該因子跨快照折線
function renderFactorTrend(payload) {
  const ft = payload.factor_trend || { dates: [], factors: {} };
  const sel = document.getElementById("factor-select");
  const ctx = document.getElementById("factorTrendChart");
  if (!ft.dates.length) return;

  // 只列出有任一資料點的因子
  const names = Object.keys(ft.factors).filter(
    n => (ft.factors[n] || []).some(v => v != null));
  if (!names.length) return;
  sel.innerHTML = names.map(n => `<option value="${n}">${factorLabel(n)}</option>`).join("");

  let chart = null;
  function draw(name) {
    const data = ft.factors[name] || [];
    const cfg = {
      type: "line",
      data: {
        labels: ft.dates,
        datasets: [{
          label: factorLabel(name),
          data,
          borderColor: "#2563eb",
          backgroundColor: "#2563eb",
          tension: 0.25,
          spanGaps: true,
        }],
      },
      options: { responsive: true, scales: { y: { suggestedMin: 0, suggestedMax: 100 } } },
    };
    if (chart) { chart.destroy(); }
    chart = new Chart(ctx, cfg);
  }
  sel.onchange = () => draw(sel.value);
  draw(names[0]);
}

// 競爭距離權重（與後端 aggregate.proximity_weight 一致）
const WALK_KM = 1.0, DRIVE_KM = 3.0, COMPETITION_FLOOR = 0.2;
function proximityWeight(d) {
  if (d == null) return null;
  if (d <= WALK_KM) return 1.0;
  if (d >= DRIVE_KM) return COMPETITION_FLOOR;
  return 1.0 - (1.0 - COMPETITION_FLOOR) * (d - WALK_KM) / (DRIVE_KM - WALK_KM);
}

// 通用「鄰近點位清單」：名稱／地址／距離／（競爭或綜效）權重／評分，近者在前
function renderProximityList(items, tableSel, countId) {
  const tbody = document.querySelector(`${tableSel} tbody`);
  const countEl = document.getElementById(countId);
  const list = (items || []).slice();
  if (countEl) countEl.textContent = String(list.length);
  if (!tbody) return;
  if (!list.length) {
    tbody.innerHTML = "<tr><td colspan='5'>尚無資料</td></tr>";
    return;
  }
  // 距離越近影響越強 → 近者在前（無距離者排最後）
  list.sort((a, b) =>
    (a.dist_km == null ? Infinity : a.dist_km) -
    (b.dist_km == null ? Infinity : b.dist_km));
  tbody.innerHTML = list.map(c => {
    const rating = c.rating == null ? "—" :
      `${fmt(c.rating)}${c.rating_count ? `（${c.rating_count}）` : ""}`;
    const dist = c.dist_km == null ? "—" :
      `<span style="white-space:nowrap">${c.dist_km.toFixed(2)} km</span>`;
    const w = proximityWeight(c.dist_km);
    const wTxt = w == null ? "—" :
      `<span class="contrib-bar"><span style="width:${(w * 100).toFixed(0)}%"></span></span>${w.toFixed(2)}`;
    return `<tr>
      <td>${c.name || "—"}</td>
      <td class="addr">${c.address || "—"}</td>
      <td>${dist}</td>
      <td>${wTxt}</td>
      <td>${rating}</td>
    </tr>`;
  }).join("");
}

function renderTrend(payload) {
  const trend = payload.trend || { dates: [], specialties: {} };
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
  // 各科分數常落在窄區間，自動縮放 Y 軸到實際範圍（含上下緩衝）讓線分開
  const vals = names.flatMap(n => (trend.specialties[n] || []))
    .filter(v => v != null);
  let yMin, yMax;
  if (vals.length) {
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.15, 2);
    yMin = Math.max(0, Math.floor(lo - pad));
    yMax = Math.min(100, Math.ceil(hi + pad));
  }
  new Chart(ctx, {
    type: "line",
    data: { labels: trend.dates, datasets },
    options: { responsive: true, scales: { y: { min: yMin, max: yMax } } },
  });
}

function renderMap(payload, geo) {
  const card = document.getElementById("map-card");
  const center = (payload.meta && payload.meta.latlon) || null;
  if (!center) { card.style.display = "none"; return; }

  const map = L.map("map").setView(center, 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap",
  }).addTo(map);

  L.marker(center).addTo(map).bindPopup("候選點").openPopup();
  L.circle(center, { radius: 1000, color: "#2563eb", fill: false }).addTo(map);
  L.circle(center, { radius: 3000, color: "#16a34a", fill: false }).addTo(map);

  const groups = {
    clinics: { color: "#dc2626", label: "西醫診所" },
    aesthetic: { color: "#db2777", label: "醫美/美容" },
    anchors: { color: "#7c3aed", label: "互補錨點" },
    convenience: { color: "#d97706", label: "便利商店" },
    transit: { color: "#0891b2", label: "公車站" },
    schools: { color: "#65a30d", label: "學校" },
  };
  Object.entries(groups).forEach(([key, cfg]) => {
    (geo[key] || []).forEach(p => {
      if (p.lat == null || p.lon == null) return;
      L.circleMarker([p.lat, p.lon], { radius: 5, color: cfg.color, fillOpacity: 0.7 })
        .addTo(map).bindPopup(`${cfg.label}${p.name ? "：" + p.name : ""}`);
    });
  });

  // 圖例：說明各色點點與範圍圈的類別
  const legend = L.control({ position: "bottomright" });
  legend.onAdd = function () {
    const div = L.DomUtil.create("div", "map-legend");
    const dot = (color, count) =>
      `<span class="lg-dot" style="background:${color}"></span>`;
    const items = [
      `<span class="lg-pin">📍</span>候選點`,
      ...Object.entries(groups).map(([key, cfg]) =>
        `${dot(cfg.color)}${cfg.label}（${(geo[key] || []).length}）`),
      `<span class="lg-line" style="border-color:#2563eb"></span>步行 1km`,
      `<span class="lg-line" style="border-color:#16a34a"></span>車程 3km`,
    ];
    div.innerHTML = items.map(t => `<div class="lg-row">${t}</div>`).join("");
    return div;
  };
  legend.addTo(map);
}

async function main() {
  const payload = await loadJSON("data/history.json", {
    meta: {}, trend: { dates: [], specialties: {} },
    factors: [], breakdowns: {},
  });
  const geo = await loadJSON("data/geo.json", {});

  renderMeta(payload);
  renderRanking(payload);
  renderBreakdown(payload);
  renderFactorTable(payload);
  renderFactorTrend(payload);
  renderTrend(payload);
  renderMap(payload, geo);
  renderProximityList(geo.clinics, "#clinic-table", "clinic-count");
  renderProximityList(geo.aesthetic, "#aesthetic-table", "aesthetic-count");
  renderProximityList(geo.anchors, "#anchor-table", "anchor-count");
}

main();
