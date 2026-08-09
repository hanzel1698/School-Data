#!/usr/bin/env python3
"""Generate schools_road_adjacent_maps_check.html from schools_road_adjacent_maps_check.xlsx.

The output is a single self-contained mobile-friendly HTML page for reviewing
schools whose DB coordinates and Google-matched coordinates disagree. It uses
the Google Maps JavaScript API (Google Maps = source of truth) to show both
points on a map, lets the reviewer tap the map (or use their phone GPS) to
capture a corrected coordinate, and persists review progress in the browser's
localStorage with CSV/JSON export. The Google Maps API key is entered by the
user at runtime in the page itself and stored only in their browser's
localStorage - it is never embedded in this file or committed to the repo.

Usage:
    python3 scripts/gen_road_check_html.py
"""
import json
import math
import pandas as pd

SRC_XLSX = "schools_road_adjacent_maps_check.xlsx"
OUT_HTML = "schools_road_adjacent_maps_check.html"

BUCKET_ORDER = [
    "Credible Error Candidate (300m-3km)",
    "Probably Match Noise (>3km)",
    "Low-Confidence / Unverifiable",
    "Likely Correct (<=300m)",
]

BUCKET_META = {
    "Credible Error Candidate (300m-3km)": {"short": "Credible Error", "color": "#d64545"},
    "Probably Match Noise (>3km)": {"short": "Match Noise", "color": "#8a8f98"},
    "Low-Confidence / Unverifiable": {"short": "Low-Confidence", "color": "#c99a2e"},
    "Likely Correct (<=300m)": {"short": "Likely Correct", "color": "#3a9d5d"},
}


def clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return v


def load_records():
    df = pd.read_excel(SRC_XLSX, sheet_name="Road-Adjacent Schools Check")
    order_index = {b: i for i, b in enumerate(BUCKET_ORDER)}
    df["_bucket_order"] = df["Bucket"].map(order_index)
    df = df.sort_values(["_bucket_order", "Distance Meters"], ascending=[True, False])

    records = []
    for i, (_, row) in enumerate(df.iterrows()):
        records.append(
            {
                "id": i,
                "bucket": clean(row["Bucket"]),
                "school": clean(row["School Name"]),
                "subdistrict": clean(row["Educational Sub-District"]),
                "block": clean(row["Block Name"]),
                "dbLat": round(float(row["DB Latitude"]), 6),
                "dbLng": round(float(row["DB Longitude"]), 6),
                "googleName": clean(row["Google Matched Name"]),
                "googleLat": round(float(row["Google Latitude"]), 6),
                "googleLng": round(float(row["Google Longitude"]), 6),
                "distance": round(float(row["Distance Meters"]), 1),
                "similarity": round(float(row["Name Similarity"]), 3),
                "mismatch": clean(row["Management Mismatch"]),
                "notes": clean(row["Notes"]),
            }
        )
    return records


def build_html(records):
    data_json = json.dumps(records, ensure_ascii=False)
    bucket_meta_json = json.dumps(BUCKET_META, ensure_ascii=False)
    bucket_order_json = json.dumps(BUCKET_ORDER, ensure_ascii=False)

    html = HTML_TEMPLATE
    html = html.replace("__DATA_JSON__", data_json)
    html = html.replace("__BUCKET_META_JSON__", bucket_meta_json)
    html = html.replace("__BUCKET_ORDER_JSON__", bucket_order_json)
    return html


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Road-Adjacent Schools Check</title>
<style>
  :root {
    --bg: #f4f5f7;
    --card-bg: #ffffff;
    --text: #1c1e21;
    --muted: #667085;
    --border: #e3e5e9;
    --accent: #2563eb;
    --accent-text: #ffffff;
    --danger: #d64545;
    --success: #3a9d5d;
    --warn: #c99a2e;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body { padding-bottom: 40px; }
  header { position: sticky; top: 0; z-index: 20; background: var(--card-bg);
    border-bottom: 1px solid var(--border); padding: 10px 12px 8px; }
  h1 { font-size: 17px; margin: 0 0 8px; }
  .progress-wrap { margin-bottom: 8px; }
  .progress-bar { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
  .progress-fill { height: 100%; background: var(--accent); width: 0%; transition: width .2s; }
  .progress-label { font-size: 12px; color: var(--muted); margin-top: 4px; display: flex; justify-content: space-between; }
  #search { width: 100%; padding: 9px 10px; font-size: 14px; border: 1px solid var(--border);
    border-radius: 8px; margin-bottom: 8px; background: #fafafa; }
  .chips { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 2px; }
  .chip { flex: 0 0 auto; font-size: 12px; padding: 6px 10px; border-radius: 999px;
    border: 1px solid var(--border); background: #fff; color: var(--text); white-space: nowrap; cursor: pointer; }
  .chip.active { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
  .maps-status { font-size: 11px; color: var(--muted); margin-top: 6px; }
  .maps-status a, .maps-status button.link { color: var(--accent); background: none; border: none; padding: 0;
    font-size: 11px; cursor: pointer; text-decoration: underline; }

  .key-panel { margin: 10px 12px; padding: 12px; border: 1px solid var(--border); border-radius: 10px;
    background: var(--card-bg); display: none; }
  .key-panel.show { display: block; }
  .key-panel-title { font-weight: 700; font-size: 14px; margin-bottom: 6px; }
  .key-panel-body { font-size: 12px; color: var(--muted); margin-bottom: 10px; line-height: 1.5; }
  .key-panel-body a { color: var(--accent); }
  .key-panel-row { display: flex; gap: 6px; margin-bottom: 8px; }
  #apiKeyInput { flex: 1 1 auto; min-width: 0; padding: 9px 10px; font-size: 14px; border: 1px solid var(--border);
    border-radius: 8px; background: #fafafa; }
  #toggleKeyVis { flex: 0 0 auto; border: 1px solid var(--border); background: #fff; border-radius: 8px; font-size: 15px; padding: 0 12px; cursor: pointer; }
  .key-error { font-size: 12px; color: var(--danger); margin-top: 8px; min-height: 14px; }

  #list { padding: 10px; display: flex; flex-direction: column; gap: 8px; }
  .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
  .card-head { display: flex; align-items: center; gap: 8px; padding: 10px 12px; cursor: pointer; }
  .bucket-dot { width: 10px; height: 10px; border-radius: 50%; flex: 0 0 auto; }
  .card-title { flex: 1 1 auto; min-width: 0; }
  .card-title .name { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .card-title .sub { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dist-badge { font-size: 11px; font-weight: 600; color: var(--muted); flex: 0 0 auto; text-align: right; }
  .status-badge { font-size: 10px; padding: 2px 7px; border-radius: 999px; font-weight: 600; margin-top: 3px; display: inline-block; }
  .status-unreviewed { background: #eef0f3; color: var(--muted); }
  .status-db_correct { background: #e2f3e8; color: var(--success); }
  .status-google_correct { background: #e2ecfb; color: var(--accent); }
  .status-corrected { background: #fde9d0; color: #a15b0a; }
  .status-flagged { background: #fbe4e4; color: var(--danger); }
  .chevron { transition: transform .15s; color: var(--muted); }
  .card.open .chevron { transform: rotate(90deg); }

  .card-body { display: none; border-top: 1px solid var(--border); padding: 10px 12px 14px; }
  .card.open .card-body { display: block; }
  .map { width: 100%; height: 260px; border-radius: 8px; margin-bottom: 10px; background: #eee; }
  .tap-readout { font-size: 12px; color: var(--muted); margin-bottom: 8px; min-height: 16px; }
  .info-grid { font-size: 12.5px; color: var(--text); display: grid; grid-template-columns: auto 1fr; gap: 3px 8px; margin-bottom: 10px; }
  .info-grid .k { color: var(--muted); }
  .info-grid a { color: var(--accent); text-decoration: none; }
  .btn-row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 8px; }
  .btn-row.single { grid-template-columns: 1fr; }
  button.action { font-size: 12.5px; padding: 9px 6px; border-radius: 8px; border: 1px solid var(--border);
    background: #fff; color: var(--text); cursor: pointer; font-weight: 600; }
  button.action.primary { background: var(--success); color: #fff; border-color: var(--success); }
  button.action.blue { background: var(--accent); color: #fff; border-color: var(--accent); }
  button.action.warn { background: var(--warn); color: #fff; border-color: var(--warn); }
  button.action.ghost { background: #fff; color: var(--danger); border-color: var(--danger); }
  button.action.neutral { background: #f4f5f7; color: var(--muted); }
  textarea.note { width: 100%; font-size: 12.5px; border: 1px solid var(--border); border-radius: 8px;
    padding: 8px; resize: vertical; min-height: 44px; font-family: inherit; }
  .note-label { font-size: 11px; color: var(--muted); margin: 6px 0 3px; }

  .toolbar { display: flex; gap: 6px; padding: 0 12px 8px; flex-wrap: wrap; }
  .toolbar button { flex: 1 1 auto; font-size: 12.5px; padding: 9px 8px; border-radius: 8px;
    border: 1px solid var(--border); background: #fff; font-weight: 600; cursor: pointer; }
  #importFile { display: none; }
  .empty { text-align: center; color: var(--muted); font-size: 13px; padding: 30px 10px; }

  @media (prefers-color-scheme: dark) {
    :root { --bg:#111317; --card-bg:#1b1e24; --text:#e8e9ec; --muted:#9aa1ac; --border:#2a2d34; }
    #search { background:#20232a; color: var(--text); }
    .chip { background:#1b1e24; color: var(--text); }
    .status-unreviewed { background:#262a31; }
    .map { background:#222; }
    button.action { background:#20232a; color: var(--text); }
    button.action.neutral { background:#20232a; }
    .toolbar button { background:#20232a; color: var(--text); }
    #apiKeyInput { background:#20232a; color: var(--text); }
    #toggleKeyVis { background:#20232a; color: var(--text); }
  }
</style>
</head>
<body>

<header>
  <h1>Road-Adjacent Schools Check</h1>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="progress-label"><span id="progressText">0 / 0 reviewed</span><span id="progressPct">0%</span></div>
  </div>
  <input id="search" type="search" placeholder="Search school, sub-district, block...">
  <div class="chips" id="chips"></div>
  <div class="maps-status" id="mapsStatus"></div>
</header>

<div id="keyPanel" class="key-panel">
  <div class="key-panel-title">🔑 Google Maps API key required</div>
  <div class="key-panel-body">
    Paste a Google Maps <b>JavaScript API</b> key to load maps. It's saved only in this
    browser (localStorage) — never sent anywhere else, never stored in this file/repo.
    <a href="https://console.cloud.google.com/google/maps-apis/credentials" target="_blank" rel="noopener">Get a key</a>.
  </div>
  <div class="key-panel-row">
    <input id="apiKeyInput" type="password" placeholder="AIza…" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false">
    <button id="toggleKeyVis" type="button" title="Show/hide">👁</button>
  </div>
  <button id="loadMapsBtn" class="action blue" style="width:100%">Save &amp; Load Maps</button>
  <div id="keyError" class="key-error"></div>
</div>

<div class="toolbar">
  <button id="exportCsvBtn">⬇ Export CSV</button>
  <button id="exportJsonBtn">⬇ Export JSON</button>
  <button id="importBtn">⬆ Import JSON</button>
  <input id="importFile" type="file" accept="application/json">
</div>

<div id="list"></div>

<script>
const SCHOOLS = __DATA_JSON__;
const BUCKET_META = __BUCKET_META_JSON__;
const BUCKET_ORDER = __BUCKET_ORDER_JSON__;
const STORAGE_KEY = "roadCheckReviews_v1";

let reviews = {};
try { reviews = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch (e) { reviews = {}; }

function saveReviews() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(reviews));
}
function getReview(id) {
  return reviews[id] || { status: "unreviewed", correctedLat: null, correctedLng: null, note: "" };
}
function setReview(id, patch) {
  const cur = getReview(id);
  reviews[id] = Object.assign({}, cur, patch, { reviewedAt: new Date().toISOString() });
  saveReviews();
  renderCard(id);
  renderProgress();
}

const STATUS_LABEL = {
  unreviewed: "Unreviewed",
  db_correct: "DB Confirmed",
  google_correct: "Google Confirmed",
  corrected: "Corrected",
  flagged: "Flagged"
};

let activeBucket = "All";
let searchTerm = "";
let mapsReady = false;
const mapInstances = {};

function matchesFilter(s) {
  if (activeBucket !== "All" && s.bucket !== activeBucket) return false;
  if (searchTerm) {
    const hay = (s.school + " " + s.subdistrict + " " + s.block).toLowerCase();
    if (!hay.includes(searchTerm)) return false;
  }
  return true;
}

function renderChips() {
  const chips = document.getElementById("chips");
  const counts = { All: SCHOOLS.length };
  BUCKET_ORDER.forEach(b => counts[b] = SCHOOLS.filter(s => s.bucket === b).length);
  const items = ["All", ...BUCKET_ORDER];
  chips.innerHTML = items.map(b => {
    const label = b === "All" ? "All" : BUCKET_META[b].short;
    return `<div class="chip ${b === activeBucket ? "active" : ""}" data-bucket="${escapeAttr(b)}">${label} (${counts[b]})</div>`;
  }).join("");
  chips.querySelectorAll(".chip").forEach(el => {
    el.addEventListener("click", () => {
      activeBucket = el.getAttribute("data-bucket");
      renderChips();
      renderList();
    });
  });
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function escapeAttr(str) { return escapeHtml(str); }

function gmapsLink(lat, lng) {
  return `https://www.google.com/maps?q=${lat},${lng}`;
}

function cardHtml(s) {
  const rev = getReview(s.id);
  const meta = BUCKET_META[s.bucket];
  return `
  <div class="card" id="card-${s.id}" data-id="${s.id}">
    <div class="card-head">
      <div class="bucket-dot" style="background:${meta.color}"></div>
      <div class="card-title">
        <div class="name">${escapeHtml(s.school)}</div>
        <div class="sub">${escapeHtml(s.subdistrict)}${s.block ? " · " + escapeHtml(s.block) : ""}</div>
        <span class="status-badge status-${rev.status}">${STATUS_LABEL[rev.status]}</span>
      </div>
      <div class="dist-badge">${s.distance.toLocaleString()} m<div class="chevron">▸</div></div>
    </div>
    <div class="card-body">
      <div class="map" id="map-${s.id}"></div>
      <div class="tap-readout" id="tap-${s.id}">Tap the map to drop a candidate pin, or use your GPS below.</div>
      <div class="info-grid">
        <div class="k">DB coords</div><div>${s.dbLat}, ${s.dbLng} — <a href="${gmapsLink(s.dbLat, s.dbLng)}" target="_blank" rel="noopener">open</a></div>
        <div class="k">Google match</div><div>${escapeHtml(s.googleName)} — <a href="${gmapsLink(s.googleLat, s.googleLng)}" target="_blank" rel="noopener">open</a></div>
        <div class="k">Google coords</div><div>${s.googleLat}, ${s.googleLng}</div>
        <div class="k">Distance</div><div>${s.distance.toLocaleString()} m</div>
        <div class="k">Name similarity</div><div>${s.similarity}</div>
        ${s.mismatch ? `<div class="k">Mismatch</div><div>${escapeHtml(s.mismatch)}</div>` : ""}
        ${s.notes ? `<div class="k">Notes</div><div>${escapeHtml(s.notes)}</div>` : ""}
        ${rev.status === "corrected" && rev.correctedLat != null ? `<div class="k">Corrected</div><div>${rev.correctedLat}, ${rev.correctedLng} — <a href="${gmapsLink(rev.correctedLat, rev.correctedLng)}" target="_blank" rel="noopener">open</a></div>` : ""}
      </div>
      <div class="btn-row">
        <button class="action primary" data-act="confirm-db">✓ DB is Correct</button>
        <button class="action blue" data-act="confirm-google">✓ Google is Correct</button>
      </div>
      <div class="btn-row">
        <button class="action warn" data-act="use-gps">📍 Use My GPS Location</button>
        <button class="action neutral" data-act="save-tap" id="saveTap-${s.id}" disabled>💾 Save Tapped Pin</button>
      </div>
      <div class="btn-row">
        <button class="action ghost" data-act="flag">🚩 Flag / Unclear</button>
        <button class="action neutral" data-act="reset">↺ Reset</button>
      </div>
      <div class="note-label">Your note</div>
      <textarea class="note" data-act="note" placeholder="Optional notes...">${escapeHtml(rev.note || "")}</textarea>
    </div>
  </div>`;
}

function renderList() {
  const list = document.getElementById("list");
  const filtered = SCHOOLS.filter(matchesFilter);
  if (!filtered.length) {
    list.innerHTML = `<div class="empty">No schools match this filter/search.</div>`;
    return;
  }
  list.innerHTML = filtered.map(cardHtml).join("");
  filtered.forEach(s => wireCard(s));
}

function renderCard(id) {
  const el = document.getElementById(`card-${id}`);
  if (!el) return;
  const wasOpen = el.classList.contains("open");
  const s = SCHOOLS.find(x => x.id == id);
  const html = cardHtml(s);
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  const newEl = tmp.firstElementChild;
  if (wasOpen) newEl.classList.add("open");
  el.replaceWith(newEl);
  wireCard(s);
  if (wasOpen && mapsReady) initMap(s);
}

function wireCard(s) {
  const el = document.getElementById(`card-${s.id}`);
  const head = el.querySelector(".card-head");
  head.addEventListener("click", () => {
    const isOpen = el.classList.contains("open");
    if (isOpen) {
      el.classList.remove("open");
      return;
    }
    el.classList.add("open");
    if (mapsReady) {
      setTimeout(() => initMap(s), 30);
    }
  });

  el.querySelector('[data-act="confirm-db"]').addEventListener("click", (e) => {
    e.stopPropagation();
    setReview(s.id, { status: "db_correct", correctedLat: null, correctedLng: null });
  });
  el.querySelector('[data-act="confirm-google"]').addEventListener("click", (e) => {
    e.stopPropagation();
    setReview(s.id, { status: "google_correct", correctedLat: null, correctedLng: null });
  });
  el.querySelector('[data-act="flag"]').addEventListener("click", (e) => {
    e.stopPropagation();
    setReview(s.id, { status: "flagged" });
  });
  el.querySelector('[data-act="reset"]').addEventListener("click", (e) => {
    e.stopPropagation();
    delete reviews[s.id];
    saveReviews();
    renderCard(s.id);
    renderProgress();
  });
  el.querySelector('[data-act="note"]').addEventListener("change", (e) => {
    const cur = getReview(s.id);
    reviews[s.id] = Object.assign({}, cur, { note: e.target.value, reviewedAt: new Date().toISOString() });
    saveReviews();
  });
  el.querySelector('[data-act="use-gps"]').addEventListener("click", (e) => {
    e.stopPropagation();
    if (!navigator.geolocation) {
      alert("GPS not available on this device/browser.");
      return;
    }
    const btn = e.currentTarget;
    btn.textContent = "📍 Locating…";
    navigator.geolocation.getCurrentPosition((pos) => {
      btn.textContent = "📍 Use My GPS Location";
      const lat = +pos.coords.latitude.toFixed(6);
      const lng = +pos.coords.longitude.toFixed(6);
      placeCandidate(s.id, lat, lng);
    }, () => {
      btn.textContent = "📍 Use My GPS Location";
      alert("Couldn't get GPS location. Check location permissions.");
    }, { enableHighAccuracy: true, timeout: 10000 });
  });
  el.querySelector('[data-act="save-tap"]').addEventListener("click", (e) => {
    e.stopPropagation();
    const mi = mapInstances[s.id];
    if (!mi || !mi.candidateMarker) return;
    const pos = mi.candidateMarker.getPosition();
    setReview(s.id, {
      status: "corrected",
      correctedLat: +pos.lat().toFixed(6),
      correctedLng: +pos.lng().toFixed(6)
    });
  });
}

function renderProgress() {
  const total = SCHOOLS.length;
  const reviewed = SCHOOLS.filter(s => getReview(s.id).status !== "unreviewed").length;
  const pct = total ? Math.round((reviewed / total) * 100) : 0;
  document.getElementById("progressFill").style.width = pct + "%";
  document.getElementById("progressText").textContent = `${reviewed} / ${total} reviewed`;
  document.getElementById("progressPct").textContent = pct + "%";
}

// ---- Google Maps ----
function initMap(s) {
  const el = document.getElementById(`map-${s.id}`);
  if (!el || mapInstances[s.id]) return;
  const dbPos = { lat: s.dbLat, lng: s.dbLng };
  const gPos = { lat: s.googleLat, lng: s.googleLng };
  const map = new google.maps.Map(el, {
    center: dbPos,
    zoom: 14,
    mapTypeControl: false,
    streetViewControl: true,
    fullscreenControl: false
  });

  const dbMarker = new google.maps.Marker({
    position: dbPos, map, title: "DB Location: " + s.school,
    icon: { path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: "#d64545", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 }
  });
  const gMarker = new google.maps.Marker({
    position: gPos, map, title: "Google Match: " + s.googleName,
    icon: { path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: "#2563eb", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 }
  });
  new google.maps.Polyline({
    path: [dbPos, gPos], map, strokeColor: "#8a8f98", strokeOpacity: 0.8, strokeWeight: 2,
    icons: [{ icon: { path: "M 0,-1 0,1", strokeOpacity: 1, scale: 3 }, offset: "0", repeat: "12px" }]
  });

  const bounds = new google.maps.LatLngBounds();
  bounds.extend(dbPos);
  bounds.extend(gPos);
  map.fitBounds(bounds, 60);
  google.maps.event.addListenerOnce(map, "idle", () => {
    if (map.getZoom() > 17) map.setZoom(17);
  });

  const readout = document.getElementById(`tap-${s.id}`);
  const saveBtn = document.getElementById(`saveTap-${s.id}`);
  const mi = { map, candidateMarker: null };
  mapInstances[s.id] = mi;

  const rev = getReview(s.id);
  if (rev.status === "corrected" && rev.correctedLat != null) {
    dropCandidate(s.id, { lat: rev.correctedLat, lng: rev.correctedLng });
  }

  map.addListener("click", (ev) => {
    dropCandidate(s.id, { lat: ev.latLng.lat(), lng: ev.latLng.lng() });
  });
}

function dropCandidate(id, pos) {
  const mi = mapInstances[id];
  if (!mi) return;
  const map = mi.map;
  const lat = +pos.lat.toFixed(6);
  const lng = +pos.lng.toFixed(6);
  if (mi.candidateMarker) {
    mi.candidateMarker.setPosition({ lat, lng });
  } else {
    mi.candidateMarker = new google.maps.Marker({
      position: { lat, lng }, map, draggable: true, title: "Candidate location (drag to fine-tune)",
      icon: { path: google.maps.SymbolPath.CIRCLE, scale: 9, fillColor: "#3a9d5d", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 }
    });
    mi.candidateMarker.addListener("dragend", (ev) => {
      updateReadout(id, ev.latLng.lat(), ev.latLng.lng());
    });
  }
  updateReadout(id, lat, lng);
}

function placeCandidate(id, lat, lng) {
  const mi = mapInstances[id];
  if (!mi) return;
  mi.map.panTo({ lat, lng });
  dropCandidate(id, { lat, lng });
}

function updateReadout(id, lat, lng) {
  lat = +lat.toFixed(6); lng = +lng.toFixed(6);
  const readout = document.getElementById(`tap-${id}`);
  const saveBtn = document.getElementById(`saveTap-${id}`);
  if (readout) readout.textContent = `Candidate pin: ${lat}, ${lng}`;
  if (saveBtn) saveBtn.disabled = false;
}

const API_KEY_STORAGE = "gmapsApiKey_v1";

window.initGoogleMaps = function () {
  mapsReady = true;
  document.getElementById("keyPanel").classList.remove("show");
  const statusEl = document.getElementById("mapsStatus");
  statusEl.innerHTML = 'Google Maps ready — tap a school to open its map. <button class="link" id="changeKeyBtn" type="button">change key</button>';
  document.getElementById("changeKeyBtn").addEventListener("click", showKeyPanel);
};

window.gm_authFailure = function () {
  mapsReady = false;
  localStorage.removeItem(API_KEY_STORAGE);
  document.getElementById("keyError").textContent =
    "Google rejected this key (invalid, restricted, or Maps JavaScript API not enabled). Fix it in Cloud Console and try again.";
  showKeyPanel();
};

function loadGoogleMapsScript(key) {
  const existing = document.getElementById("gmapsScript");
  if (existing) existing.remove();
  const s = document.createElement("script");
  s.id = "gmapsScript";
  s.async = true;
  s.defer = true;
  s.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(key) + "&callback=initGoogleMaps";
  s.onerror = () => {
    document.getElementById("keyError").textContent = "Could not load Google Maps — check your internet connection and the key.";
    showKeyPanel();
  };
  document.head.appendChild(s);
  document.getElementById("mapsStatus").textContent = "Loading Google Maps…";
}

function showKeyPanel() {
  document.getElementById("keyPanel").classList.add("show");
  const stored = localStorage.getItem(API_KEY_STORAGE);
  if (stored) document.getElementById("apiKeyInput").value = stored;
}

document.getElementById("loadMapsBtn").addEventListener("click", () => {
  const key = document.getElementById("apiKeyInput").value.trim();
  document.getElementById("keyError").textContent = "";
  if (!key) {
    document.getElementById("keyError").textContent = "Paste a key first.";
    return;
  }
  localStorage.setItem(API_KEY_STORAGE, key);
  loadGoogleMapsScript(key);
});

document.getElementById("toggleKeyVis").addEventListener("click", () => {
  const input = document.getElementById("apiKeyInput");
  input.type = input.type === "password" ? "text" : "password";
});

(function bootMaps() {
  const stored = localStorage.getItem(API_KEY_STORAGE);
  if (stored) {
    loadGoogleMapsScript(stored);
  } else {
    showKeyPanel();
  }
})();

// ---- search ----
document.getElementById("search").addEventListener("input", (e) => {
  searchTerm = e.target.value.trim().toLowerCase();
  renderList();
});

// ---- export / import ----
function currentExportRows() {
  return SCHOOLS.map(s => {
    const r = getReview(s.id);
    return {
      Bucket: s.bucket,
      "School Name": s.school,
      "Educational Sub-District": s.subdistrict,
      "Block Name": s.block,
      "DB Latitude": s.dbLat,
      "DB Longitude": s.dbLng,
      "Google Matched Name": s.googleName,
      "Google Latitude": s.googleLat,
      "Google Longitude": s.googleLng,
      "Distance Meters": s.distance,
      "Name Similarity": s.similarity,
      "Management Mismatch": s.mismatch,
      "Notes": s.notes,
      "Review Status": STATUS_LABEL[r.status],
      "Corrected Latitude": r.correctedLat ?? "",
      "Corrected Longitude": r.correctedLng ?? "",
      "Reviewer Note": r.note || "",
      "Reviewed At": r.reviewedAt || ""
    };
  });
}

function downloadBlob(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

document.getElementById("exportCsvBtn").addEventListener("click", () => {
  const rows = currentExportRows();
  const headers = Object.keys(rows[0]);
  const csvEsc = (v) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const csv = [headers.join(",")].concat(rows.map(r => headers.map(h => csvEsc(r[h])).join(","))).join("\n");
  downloadBlob(csv, "schools_road_adjacent_maps_check_reviewed.csv", "text/csv");
});

document.getElementById("exportJsonBtn").addEventListener("click", () => {
  downloadBlob(JSON.stringify(reviews, null, 2), "schools_road_adjacent_maps_reviews.json", "application/json");
});

document.getElementById("importBtn").addEventListener("click", () => {
  document.getElementById("importFile").click();
});
document.getElementById("importFile").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const imported = JSON.parse(reader.result);
      reviews = Object.assign({}, reviews, imported);
      saveReviews();
      renderList();
      renderProgress();
      alert("Import complete.");
    } catch (err) {
      alert("Could not read that file as valid review JSON.");
    }
  };
  reader.readAsText(file);
  e.target.value = "";
});

// ---- init ----
renderChips();
renderList();
renderProgress();
</script>
</body>
</html>
"""


def main():
    records = load_records()
    html = build_html(records)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUT_HTML} with {len(records)} schools.")


if __name__ == "__main__":
    main()
