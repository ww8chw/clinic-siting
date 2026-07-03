// 選址評估前端：讀 data/history.json + data/geo.json
// 依「行業組 → 行業」切換，顯示排名、加權拆解、地點/行業因子、趨勢、地圖
"use strict";

const GROUP_LABELS = {
  medical: "醫療", food: "餐飲", fitness: "健身",
  education: "教育", service: "服務",
};

const FACTOR_LABELS = {
  population_density: "人口密度",
  age_gender: "年齡/性別",
  day_night_gap: "晝夜落差",
  school_proximity: "學校鄰近",
  purchasing_power: "消費力",
  business_density: "商業密度",
  land_use_mix: "土地混合",
  competition: "競爭對手",
  complementary_anchors: "互補錨點",
  convenience_density: "超商密度",
  accessibility: "交通可及",
  redevelopment_stage: "重劃/屋齡",
  visibility: "能見度",
};

const SOURCE_LABELS = {
  real: "real", degraded: "degraded", manual: "manual", missing: "missing",
};

const SERIES_COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];

function groupLabel(k) { return GROUP_LABELS[k] || k; }
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

// 攤平 groups → { iid: {group, ...entry} }，保留插入順序
function flatIndustries(payload) {
  const out = {};
  const groups = payload.groups || {};
  Object.entries(groups).forEach(([g, gd]) => {
    Object.entries(gd.industries || {}).forEach(([iid, entry]) => {
      out[iid] = { group: g, ...entry };
    });
  });
  return out;
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
  const dates = payload.dates || [];
  const last = dates.length ? dates[dates.length - 1] : null;
  if (!last) { el.textContent = ""; return; }
  const ageDays = Math.floor((Date.now() - new Date(last).getTime()) / 86400000);
  const stale = ageDays > STALE_DAYS;
  el.classList.toggle("stale", stale);
  el.classList.toggle("fresh", !stale);
  const ageTxt = ageDays <= 0 ? "今日更新" : `${ageDays} 天前`;
  el.textContent = `資料更新於 ${last}（${ageTxt}）${stale ? "　⚠ 已逾 " + STALE_DAYS + " 天，建議重新刷新" : ""}`;
}

// 某行業相對全體的「因子貢獻優勢」：contribution 減去全體平均 → 贏在哪些因子
function factorEdges(flat, iid) {
  const target = flat[iid];
  if (!target || !target.breakdown || !target.breakdown.rows) return [];
  const all = Object.values(flat).filter(d => d.breakdown && d.breakdown.rows);
  const contrib = {}, score = {};
  target.breakdown.rows.forEach(r => { contrib[r.factor] = r.contribution; score[r.factor] = r.score; });
  return Object.keys(contrib).map(f => {
    const vals = all.map(d => {
      const row = d.breakdown.rows.find(r => r.factor === f);
      return row ? row.contribution : 0;
    });
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    return { factor: f, score: score[f], edge: contrib[f] - mean };
  }).sort((a, b) => b.edge - a.edge);
}

// 觀察評語：從現有資料自動生成白話觀察（排名、贏在哪、組別、趨勢、地點強弱項）
function renderInsights(payload, flat) {
  const card = document.getElementById("insights-card");
  const list = document.getElementById("insights-list");
  if (!card || !list) return;
  const rankedEntries = Object.entries(flat)
    .filter(([, d]) => d.score != null)
    .sort((a, b) => b[1].score - a[1].score);
  if (!rankedEntries.length) { card.hidden = true; return; }
  const ranked = rankedEntries.map(([, d]) => d);

  const items = [];
  const top = ranked[0], bottom = ranked[ranked.length - 1];
  const topIid = rankedEntries[0][0];
  items.push(`最適合的是<b>${top.label}</b>（${groupLabel(top.group)}），總分 <b>${fmt(top.score)}</b>。` +
    `全 ${ranked.length} 個行業落在 ${fmt(bottom.score)}–${fmt(top.score)} 分，差距僅 ${fmt(top.score - bottom.score)} 分，選擇彈性大。`);

  // 贏在哪：它較看重、且本地點分數突出的因子（貢獻高於全體平均）
  const edges = factorEdges(flat, topIid)
    .filter(e => e.edge > 0.3 && e.score >= 70).slice(0, 3);
  if (edges.length) {
    const txt = edges.map(e => `${factorLabel(e.factor)}（${fmt(e.score)} 分）`).join("、");
    items.push(`<b>${top.label}</b>能勝出，是因為它特別看重、而本地點又剛好分數特別高的幾項：${txt}——這些因子它給的權重高於其他行業，因此拉開差距。`);
  }

  // 領先組別（組內平均分）
  const byGroup = {};
  ranked.forEach(d => { (byGroup[d.group] = byGroup[d.group] || []).push(d.score); });
  const groupAvg = Object.entries(byGroup)
    .map(([g, a]) => [g, a.reduce((x, y) => x + y, 0) / a.length, a.length])
    .filter(([, , n]) => n >= 2)   // 單一行業的組不納入「平均最高」比較，避免以偏概全
    .sort((a, b) => b[1] - a[1]);
  if (groupAvg.length > 1) {
    const [g, avg, n] = groupAvg[0];
    items.push(`<b>${groupLabel(g)}</b>組平均最高（${fmt(avg)} 分，${n} 個行業），此地點偏向適合${groupLabel(g)}類店面。`);
  }

  // 趨勢變化：找有兩筆以上可比資料、變化最大的行業
  let mover = null;
  Object.values(flat).forEach(d => {
    const t = (d.trend || []).filter(v => v != null);
    if (t.length >= 2) {
      const delta = t[t.length - 1] - t[t.length - 2];
      if (!mover || Math.abs(delta) > Math.abs(mover.delta)) mover = { label: d.label, delta };
    }
  });
  if (mover && Math.abs(mover.delta) >= 0.1) {
    const dir = mover.delta > 0 ? "上升" : "下降";
    items.push(`較上次刷新，變化最大的是<b>${mover.label}</b>，${dir} ${fmt(Math.abs(mover.delta))} 分。`);
  } else if ((payload.dates || []).length <= 1) {
    items.push(`目前為本評分機制的首批資料，尚無可比較的歷史；後續每月刷新後會在此顯示分數升降。`);
  }

  // 地點強弱項
  const lf = (payload.location_factors || []).filter(f => f.score != null);
  if (lf.length) {
    const sorted = lf.slice().sort((a, b) => b.score - a.score);
    const strong = sorted.slice(0, 3).map(f => `${factorLabel(f.factor)} ${fmt(f.score)}`);
    items.push(`地點最突出的優勢：${strong.join("、")}。`);
    const weak = sorted.filter(f =>
      f.source === "missing" || f.source === "degraded" || f.score <= 50);
    if (weak.length) {
      const weakTxt = weak.map(f =>
        `${factorLabel(f.factor)}（${SOURCE_LABELS[f.source] || f.source}）`);
      items.push(`待補強或資料待確認：${weakTxt.join("、")}。`);
    }
  }

  list.innerHTML = items.map(t => `<li>${t}</li>`).join("");
  card.hidden = false;
}

// 全行業排名：用最新分數排序（跨所有組），點選可切換至該行業
function renderRanking(flat, onPick) {
  const el = document.getElementById("ranking");
  const rows = Object.entries(flat)
    .map(([iid, d]) => [iid, d.label, d.group, d.score])
    .filter(([, , , v]) => v != null)
    .sort((a, b) => b[3] - a[3]);
  if (!rows.length) { el.textContent = "尚無資料"; return; }
  const max = rows[0][3] || 100;
  el.innerHTML = rows.map(([iid, label, g, v], i) => `
    <div class="rank-row rank-pick" data-iid="${iid}">
      <span class="rank-no">${i + 1}</span>
      <span class="rank-name">${label}<span class="rank-group">${groupLabel(g)}</span></span>
      <span class="rank-bar"><span style="width:${(v / max * 100).toFixed(1)}%"></span></span>
      <span class="rank-score">${fmt(v)}</span>
    </div>`).join("");
  el.querySelectorAll(".rank-pick").forEach(row => {
    row.addEventListener("click", () => onPick(row.dataset.iid));
  });
}

// 數值權重 → 等級標籤（對齊 config weight_levels）
const WEIGHT_LEVEL = { 5: "最高", 4: "高", 3: "中", 2: "低", 1: "極低", 0: "無" };
function levelLabel(w) { return WEIGHT_LEVEL[w] != null ? WEIGHT_LEVEL[w] : String(w); }

// 單一行業加權拆解表 + what-if 權重試算滑桿
function renderBreakdown(entry) {
  const tbody = document.querySelector("#breakdown-table tbody");
  const tfoot = document.querySelector("#breakdown-table tfoot");
  const resetBtn = document.getElementById("whatif-reset");
  document.getElementById("breakdown-title").textContent =
    `${entry.label}：加權運算明細`;
  const bd = entry.breakdown;
  if (!bd || !bd.rows || !bd.rows.length) {
    tbody.innerHTML = "<tr><td colspan='4'>尚無資料</td></tr>";
    tfoot.innerHTML = "";
    if (resetBtn) resetBtn.disabled = true;
    return;
  }

  let liveWeights = {};
  bd.rows.forEach(r => { liveWeights[r.factor] = r.weight; });

  function weightedTotal(rows, weights) {
    let num = 0, den = 0;
    rows.forEach(r => {
      const w = weights[r.factor];
      if (r.score != null) { num += r.score * w; den += w; }
    });
    return den ? num / den : 0;
  }

  function redraw() {
    const rows = bd.rows;
    const total = weightedTotal(rows, liveWeights);
    const orig = bd.total;
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

    tbody.querySelectorAll(".wslider").forEach(sl => {
      sl.addEventListener("input", () => {
        liveWeights[sl.dataset.factor] = parseInt(sl.value, 10);
        redraw();
      });
    });
  }

  if (resetBtn) {
    resetBtn.onclick = () => {
      bd.rows.forEach(r => { liveWeights[r.factor] = r.weight; });
      redraw();
    };
  }
  redraw();
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

// 通用因子明細表渲染（地點因子與行業因子共用）
function renderFactorRows(tableSel, factors) {
  const tbody = document.querySelector(`${tableSel} tbody`);
  const list = factors || [];
  if (!list.length) { tbody.innerHTML = "<tr><td colspan='6'>尚無資料</td></tr>"; return; }
  tbody.innerHTML = list.map(f => `
    <tr>
      <td>${factorLabel(f.factor)}</td>
      <td>${f.raw_text}</td>
      <td class="basis">${f.basis_text}</td>
      <td>${fmt(f.score)}</td>
      <td>${deltaCell(f)}</td>
      <td><span class="src ${f.source}">${SOURCE_LABELS[f.source] || f.source}</span></td>
    </tr>`).join("");
}

function renderIndustryFactorTable(entry) {
  document.getElementById("industry-factor-title").textContent =
    `${entry.label}：行業因子`;
  renderFactorRows("#industry-factor-table", entry.factors);
}

// 選定行業的醒目給分（切換行業即時更新），附全行業排名名次
function renderSelectedScore(entry, flat, iid) {
  const box = document.getElementById("selected-score");
  if (!box) return;
  document.getElementById("ss-name").textContent = entry.label;
  document.getElementById("ss-group").textContent = groupLabel(entry.group);
  document.getElementById("ss-number").textContent = fmt(entry.score);
  const ranked = Object.entries(flat)
    .filter(([, d]) => d.score != null)
    .sort((a, b) => b[1].score - a[1].score)
    .map(([id]) => id);
  const pos = ranked.indexOf(iid);
  const rankEl = document.getElementById("ss-rank");
  rankEl.textContent = (entry.score != null && pos >= 0)
    ? `全行業第 ${pos + 1} / ${ranked.length} 名` : "";
  box.hidden = false;
}

// 競爭距離權重（與後端 aggregate.proximity_weight 一致）
const WALK_KM = 1.0, DRIVE_KM = 3.0, COMPETITION_FLOOR = 0.2;
function proximityWeight(d) {
  if (d == null) return null;
  if (d <= WALK_KM) return 1.0;
  if (d >= DRIVE_KM) return COMPETITION_FLOOR;
  return 1.0 - (1.0 - COMPETITION_FLOOR) * (d - WALK_KM) / (DRIVE_KM - WALK_KM);
}

// 通用「鄰近點位清單」：名稱／地址／距離／權重／評分，近者在前
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

// 分數趨勢：畫所選行業組內各行業的分數折線
let trendChart = null;
function renderTrend(payload, flat, group) {
  const ctx = document.getElementById("trendChart");
  const dates = payload.dates || [];
  document.getElementById("trend-title").textContent =
    `${groupLabel(group)}各行業分數趨勢`;
  if (!dates.length) return;
  const members = Object.entries(flat).filter(([, d]) => d.group === group);
  const datasets = members.map(([iid, d], i) => ({
    label: d.label,
    data: d.trend || [],
    borderColor: SERIES_COLORS[i % SERIES_COLORS.length],
    backgroundColor: SERIES_COLORS[i % SERIES_COLORS.length],
    tension: 0.25,
    spanGaps: true,
  }));
  const vals = members.flatMap(([, d]) => (d.trend || [])).filter(v => v != null);
  let yMin, yMax;
  if (vals.length) {
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = Math.max((hi - lo) * 0.15, 2);
    yMin = Math.max(0, Math.floor(lo - pad));
    yMax = Math.min(100, Math.ceil(hi + pad));
  }
  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: "line",
    data: { labels: dates, datasets },
    options: { responsive: true, scales: { y: { min: yMin, max: yMax } } },
  });
}

// 地圖：建立一次，切換行業時只更新 competitors/anchors 兩圖層
let mapState = null;
function initMap(payload) {
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
    competitors: { color: "#dc2626", label: "競爭對手" },
    anchors: { color: "#7c3aed", label: "互補錨點" },
  };
  const layers = {};
  Object.keys(groups).forEach(key => {
    const lg = L.layerGroup().addTo(map);
    layers[key] = lg;
  });

  const legend = L.control({ position: "bottomright" });
  legend.onAdd = function () {
    const div = L.DomUtil.create("div", "map-legend");
    L.DomEvent.disableClickPropagation(div);
    const head = `<div class="lg-row"><span class="lg-pin">📍</span>候選點</div>`;
    const groupRows = Object.entries(groups).map(([key, cfg]) =>
      `<div class="lg-row lg-toggle" data-key="${key}" title="點擊隱藏/顯示">` +
      `<span class="lg-dot" style="background:${cfg.color}"></span>` +
      `<span class="lg-label" data-key="${key}">${cfg.label}（0）</span></div>`).join("");
    const lines =
      `<div class="lg-row"><span class="lg-line" style="border-color:#2563eb"></span>步行 1km</div>` +
      `<div class="lg-row"><span class="lg-line" style="border-color:#16a34a"></span>車程 3km</div>`;
    div.innerHTML = head + groupRows + lines;
    div.querySelectorAll(".lg-toggle").forEach(row => {
      row.addEventListener("click", () => {
        const lg = layers[row.getAttribute("data-key")];
        if (!lg) return;
        if (map.hasLayer(lg)) { map.removeLayer(lg); row.classList.add("lg-off"); }
        else { lg.addTo(map); row.classList.remove("lg-off"); }
      });
    });
    return div;
  };
  legend.addTo(map);
  mapState = { map, layers, groups };
}

function updateMap(geoForIndustry) {
  if (!mapState) return;
  const { layers, groups } = mapState;
  Object.entries(groups).forEach(([key, cfg]) => {
    const lg = layers[key];
    lg.clearLayers();
    (geoForIndustry[key] || []).forEach(p => {
      if (p.lat == null || p.lon == null) return;
      L.circleMarker([p.lat, p.lon], { radius: 5, color: cfg.color, fillOpacity: 0.7 })
        .bindPopup(`${cfg.label}${p.name ? "：" + p.name : ""}`)
        .addTo(lg);
    });
    const lbl = document.querySelector(`.lg-label[data-key="${key}"]`);
    if (lbl) lbl.textContent = `${cfg.label}（${(geoForIndustry[key] || []).length}）`;
  });
}

async function main() {
  const payload = await loadJSON("data/history.json", {
    meta: {}, dates: [], location_factors: [], groups: {},
  });
  const geo = await loadJSON("data/geo.json", {});
  const flat = flatIndustries(payload);

  renderMeta(payload);
  renderInsights(payload, flat);
  renderFactorRows("#location-factor-table", payload.location_factors);
  initMap(payload);

  const groupSel = document.getElementById("group-select");
  const tabsEl = document.getElementById("industry-tabs");
  const iids = Object.keys(flat);
  if (!iids.length) {
    renderRanking(flat, () => {});
    return;
  }

  const presentGroups = [];
  Object.keys(payload.groups || {}).forEach(g => {
    if (!presentGroups.includes(g)) presentGroups.push(g);
  });
  groupSel.innerHTML = presentGroups
    .map(g => `<option value="${g}">${groupLabel(g)}</option>`).join("");

  let currentGroup = null;
  let currentIid = null;

  function selectIndustry(iid) {
    currentIid = iid;
    const entry = flat[iid];
    if (!entry) return;
    if (entry.group !== currentGroup) {
      currentGroup = entry.group;
      groupSel.value = currentGroup;
      renderTabs(currentGroup);
      renderTrend(payload, flat, currentGroup);
    }
    tabsEl.querySelectorAll(".tab").forEach(t =>
      t.classList.toggle("active", t.dataset.iid === iid));
    renderSelectedScore(entry, flat, iid);
    renderBreakdown(entry);
    renderIndustryFactorTable(entry);
    document.getElementById("competitor-title").innerHTML =
      `${entry.label}：3km 內競爭對手清單（<span id="competitor-count">0</span> 家）`;
    const g = geo[iid] || {};
    updateMap(g);
    renderProximityList(g.competitors, "#competitor-table", "competitor-count");
    renderProximityList(g.anchors, "#anchor-table", "anchor-count");
  }

  function renderTabs(group) {
    const members = Object.entries(flat).filter(([, d]) => d.group === group);
    tabsEl.innerHTML = members.map(([iid, d]) =>
      `<button type="button" class="tab" data-iid="${iid}">${d.label}</button>`).join("");
    tabsEl.querySelectorAll(".tab").forEach(t =>
      t.addEventListener("click", () => selectIndustry(t.dataset.iid)));
  }

  groupSel.onchange = () => {
    const g = groupSel.value;
    const first = Object.keys(flat).find(iid => flat[iid].group === g);
    if (first) selectIndustry(first);
  };

  renderRanking(flat, selectIndustry);

  // 預設選最高分行業
  const top = Object.entries(flat)
    .filter(([, d]) => d.score != null)
    .sort((a, b) => b[1].score - a[1].score)[0];
  selectIndustry(top ? top[0] : iids[0]);
}

main();
