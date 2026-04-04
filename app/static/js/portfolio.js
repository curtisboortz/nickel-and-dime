/* Nickel&Dime - Portfolio analysis: projections, TA, monte carlo, drawdown, TLH, goals */

var PROJ_CURRENT = 0;
var _projStartingSetByUser = false;
var projectionChart = null;
var projectionData = { labels: [], values: [] };

function projFV(initial, monthly, annualRate, months) {
  if (annualRate <= 0) return initial + monthly * months;
  var r = annualRate / 100 / 12;
  var n = months;
  return initial * Math.pow(1 + r, n) + monthly * ((Math.pow(1 + r, n) - 1) / r);
}

function rebuildProjectionData() {
  var projMonthlyEl = document.getElementById("proj-monthly");
  if (!projMonthlyEl) return null;
  var startEl = document.getElementById("proj-starting");
  var current = startEl ? (parseFloat(startEl.value) || 0) : PROJ_CURRENT;
  var monthly = parseFloat(projMonthlyEl.value) || 0;
  var ratePct = parseFloat(document.getElementById("proj-rate").value) || 7;
  var years = parseInt(document.getElementById("proj-years").value, 10) || 30;
  var months = years * 12;
  var labels = [];
  var values = [];
  for (var m = 0; m <= months; m += 3) {
    labels.push((m / 12).toFixed(1) + "Y");
    values.push(Math.round(projFV(current, monthly, ratePct, m)));
  }
  if (months > 0 && labels[labels.length - 1] !== (years + "Y")) {
    labels.push(years + "Y");
    values.push(Math.round(projFV(current, monthly, ratePct, months)));
  }
  projectionData = { labels: labels, values: values };
  return { labels: labels, values: values, years: years, monthly: monthly, ratePct: ratePct };
}

function updateProjectionSummary(data) {
  var startEl = document.getElementById("proj-starting");
  var current = startEl ? (parseFloat(startEl.value) || 0) : PROJ_CURRENT;
  var endVal = data.values[data.values.length - 1];
  var totalContrib = data.monthly * (data.years * 12);
  var growth = endVal - current - totalContrib;
  document.getElementById("proj-start-val").textContent = "$" + current.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  document.getElementById("proj-end-val").textContent = "$" + endVal.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  document.getElementById("proj-total-contrib").textContent = "$" + totalContrib.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  document.getElementById("proj-growth").textContent = "$" + growth.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function updateProjectionChart() {
  var data = rebuildProjectionData();
  if (!data) return;
  document.getElementById("proj-rate-val").textContent = data.ratePct + "%";
  document.getElementById("proj-years-val").textContent = data.years;
  var timelineEl = document.getElementById("proj-timeline");
  timelineEl.max = data.years;
  if (parseInt(timelineEl.value, 10) > data.years) timelineEl.value = data.years;
  updateProjectionTimelineLabel();

  if (projectionChart) {
    projectionChart.data.labels = data.labels;
    projectionChart.data.datasets[0].data = data.values;
    projectionChart.update();
  } else {
    var ctx = document.getElementById("projection-chart");
    if (!ctx || typeof Chart === "undefined") return;
    projectionChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [{
          label: "Projected value",
          data: data.values,
          borderColor: "rgba(212,160,23,0.9)",
          backgroundColor: "rgba(212,160,23,0.1)",
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          pointHoverRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(c) { return "$" + c.raw.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 }); }
            }
          }
        },
        scales: {
          x: { ticks: { color: "#64748b", font: { size: 10 }, maxTicksLimit: 12 }, grid: { display: false } },
          y: { ticks: { color: "#64748b", font: { size: 10 }, callback: function(v) { return "$" + (v/1000).toFixed(0) + "K"; } }, grid: { color: "rgba(255,255,255,0.03)" } }
        }
      }
    });
  }
  updateProjectionSummary(data);
  setTimeout(updateProjectionTimelineLabel, 50);
}

function updateProjectionTimelineLabel() {
  var year = parseInt(document.getElementById("proj-timeline").value, 10);
  document.getElementById("proj-timeline-val").textContent = "Year " + year;
  var data = projectionData;
  if (!data.values || data.values.length === 0) return;
  var years = parseInt(document.getElementById("proj-years").value, 10) || 30;
  var idx = Math.round((year / years) * (data.values.length - 1));
  idx = Math.min(idx, data.values.length - 1);
  var val = data.values[idx];
  var crosshair = document.getElementById("projection-crosshair");
  var label = document.getElementById("projection-crosshair-label");
  if (crosshair && label && projectionChart) {
    var xScale = projectionChart.scales.x;
    if (xScale && data.labels.length > 0) {
      var left = xScale.getPixelForValue(data.labels[idx]);
      crosshair.style.left = left + "px";
      crosshair.style.display = "block";
      label.textContent = "Year " + year + ": $" + (val || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
      label.style.display = "block";
    }
  }
}

var _projListenersBound = false;
function buildProjectionChart() {
  NDDiag.track("projection", "loading");
  updateProjectionChart();
  NDDiag.track("projection", "ok");
  if (_projListenersBound) return;
  _projListenersBound = true;
  ["proj-starting", "proj-rate", "proj-monthly", "proj-years"].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener("input", updateProjectionChart);
  });
  var startingEl = document.getElementById("proj-starting");
  if (startingEl) startingEl.addEventListener("input", function() { _projStartingSetByUser = true; });
  var timelineEl = document.getElementById("proj-timeline");
  if (timelineEl) {
    timelineEl.addEventListener("input", updateProjectionTimelineLabel);
  }
}
buildProjectionChart();



/* ── Technical Analysis (TradingView) ── */
var _tvScriptLoaded = false;
var _tvInitDone = false;
var _tvCurrentSymbol = "SPY";
var TA_TICKERS = [];

function initTechnicalTab() {
  if (!_tvInitDone) {
    _tvInitDone = true;
    fetch("/api/ta-tickers").then(function(r) { return r.json(); }).then(function(d) {
      TA_TICKERS = d.tickers || [];
      _buildTATickerButtons();
    }).catch(function() {
      TA_TICKERS = ["SPY","GC=F","SI=F","BTC-USD","DX=F","^TNX"];
      _buildTATickerButtons();
    });
  }
  if (!document.getElementById("tv_chart_container")) return;
  if (!_tvScriptLoaded) {
    var s = document.createElement("script");
    s.src = "https://s3.tradingview.com/tv.js";
    s.onload = function() {
      _tvScriptLoaded = true;
      _createTVWidget(_tvCurrentSymbol);
    };
    s.onerror = function() {
      document.getElementById("tv_chart_container").innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);">Failed to load TradingView. Check your internet connection.</div>';
    };
    document.head.appendChild(s);
  } else {
    _createTVWidget(_tvCurrentSymbol);
  }
}

function _createTVWidget(symbol) {
  var container = document.getElementById("tv_chart_container");
  if (!container || typeof TradingView === "undefined") return;
  container.innerHTML = '<div id="tv_chart" style="height:100%;"></div>';
  _tvCurrentSymbol = symbol;
  _highlightTABtn(symbol);
  new TradingView.widget({
    "autosize": true,
    "symbol": symbol,
    "interval": "D",
    "timezone": "America/New_York",
    "theme": document.documentElement.classList.contains("light") ? "light" : "dark",
    "style": "1",
    "locale": "en",
    "enable_publishing": false,
    "allow_symbol_change": true,
    "hide_side_toolbar": false,
    "details": true,
    "hotlist": false,
    "calendar": false,
    "studies": [],
    "show_popup_button": true,
    "popup_width": "1200",
    "popup_height": "800",
    "withdateranges": true,
    "save_image": true,
    "hide_volume": false,
    "container_id": "tv_chart"
  });
}

function _buildTATickerButtons() {
  var wrap = document.getElementById("ta-ticker-btns");
  if (!wrap) return;
  var html = "";
  if (!TA_TICKERS || !TA_TICKERS.forEach) return;
  TA_TICKERS.forEach(function(t) {
    html += '<span class="ta-tkr-wrap" style="display:inline-flex;align-items:center;gap:0;border:1px solid rgba(255,255,255,0.15);border-radius:4px;overflow:hidden;">';
    html += '<button type="button" class="ta-tkr" data-symbol="' + t + '" style="padding:3px 8px;font-size:0.75rem;border:none;background:rgba(255,255,255,0.04);color:#94a3b8;cursor:pointer;transition:all 0.15s;">' + t + '</button>';
    html += '<button type="button" class="ta-tkr-rm" data-rm="' + t + '" style="padding:2px 5px;font-size:0.65rem;border:none;border-left:1px solid rgba(255,255,255,0.1);background:transparent;color:#64748b;cursor:pointer;line-height:1;" title="Remove">&times;</button>';
    html += '</span>';
  });
  html += '<button type="button" id="ta-add-btn" style="padding:3px 8px;font-size:0.75rem;border:1px dashed rgba(255,255,255,0.2);border-radius:4px;background:transparent;color:#64748b;cursor:pointer;">+ Add</button>';
  wrap.innerHTML = html;
  wrap.onclick = function(ev) {
    var rmBtn = ev.target.closest(".ta-tkr-rm");
    if (rmBtn) { _removeTATicker(rmBtn.getAttribute("data-rm")); return; }
    var tkrBtn = ev.target.closest(".ta-tkr");
    if (tkrBtn) { _createTVWidget(tkrBtn.getAttribute("data-symbol")); return; }
    if (ev.target.id === "ta-add-btn") { _addTATicker(); return; }
  };
}

function _highlightTABtn(symbol) {
  document.querySelectorAll(".ta-tkr").forEach(function(b) {
    var isActive = b.getAttribute("data-symbol") === symbol;
    b.style.background = isActive ? "rgba(99,102,241,0.2)" : "rgba(255,255,255,0.04)";
    b.style.borderColor = isActive ? "rgba(99,102,241,0.5)" : "";
    b.style.color = isActive ? "#a5b4fc" : "#94a3b8";
    b.style.fontWeight = isActive ? "600" : "400";
    var parent = b.parentElement;
    if (parent && parent.classList.contains("ta-tkr-wrap")) {
      parent.style.borderColor = isActive ? "rgba(99,102,241,0.5)" : "rgba(255,255,255,0.15)";
    }
  });
}

function _addTATicker() {
  var sym = prompt("Enter ticker symbol (e.g. AAPL, TSLA, ETH-USD):");
  if (!sym) return;
  sym = sym.trim().toUpperCase();
  if (!sym) return;
  if (TA_TICKERS.indexOf(sym) >= 0) { _createTVWidget(sym); return; }
  TA_TICKERS.push(sym);
  _saveTATickers();
  _buildTATickerButtons();
  _createTVWidget(sym);
}

function _removeTATicker(sym) {
  TA_TICKERS = TA_TICKERS.filter(function(t) { return t !== sym; });
  _saveTATickers();
  _buildTATickerButtons();
  _highlightTABtn(_tvCurrentSymbol);
}

function _saveTATickers() {
  fetch("/api/ta-tickers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tickers: TA_TICKERS })
  }).catch(function() {});
}

/* ── Phase 3: Price Alerts ── */

var PRICE_ALERTS = window.PRICE_ALERTS || [];
function checkAlerts(prices) {
  PRICE_ALERTS.forEach(function(a) {
    var current = prices[a.symbol];
    if (!current) return;
    if ((a.direction==="above" && current >= a.target) || (a.direction==="below" && current <= a.target)) {
      if (!a.triggered) {
        a.triggered = true;
        showAlertNotification(a.symbol + " is " + a.direction + " $" + a.target + " (now $" + current.toFixed(2) + ")");
      }
    }
  });
}
function showAlertNotification(msg) {
  var div = document.createElement("div");
  div.className = "toast";
  div.style.background = "rgba(212,160,23,0.15)";
  div.style.color = "var(--accent-primary)";
  div.style.borderColor = "rgba(212,160,23,0.3)";
  div.textContent = msg;
  document.body.appendChild(div);
  setTimeout(function() { div.remove(); }, 5000);
}

/* ── Phase 4: PWA Service Worker Registration ── */
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(function(){});
}

/* ── Phase 4: Onboarding detection ── */
(function() {
  if (!localStorage.getItem("wos-onboarded") && (window.NUM_HOLDINGS || 0) === 0) {
    var overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:400;display:flex;align-items:center;justify-content:center;";
    overlay.innerHTML = '<div style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:16px;padding:36px;max-width:460px;width:90%;text-align:center;">' +
      '<h2 style="color:var(--accent-primary);margin-bottom:12px;">Welcome to Nickel&amp;Dime</h2>' +
      '<p style="color:var(--text-secondary);margin-bottom:20px;font-size:0.9rem;">Get started in 3 easy steps:</p>' +
      '<div style="text-align:left;color:var(--text-secondary);font-size:0.88rem;line-height:1.8;">' +
      '<div style="margin-bottom:8px;"><span style="color:var(--accent-primary);font-weight:700;">1.</span> Set up your <b>Budget</b> (income &amp; expenses)</div>' +
      '<div style="margin-bottom:8px;"><span style="color:var(--accent-primary);font-weight:700;">2.</span> <b>Import</b> a CSV from your brokerage or add holdings manually</div>' +
      '<div style="margin-bottom:8px;"><span style="color:var(--accent-primary);font-weight:700;">3.</span> Update <b>Balances</b> for blended accounts</div>' +
      '</div>' +
      '<button id="wos-onboard-btn" style="margin-top:20px;padding:10px 28px;background:var(--accent-primary);color:#09090b;border:none;border-radius:8px;font-weight:600;cursor:pointer;">Get Started</button>' +
      '</div>';
    document.body.appendChild(overlay);
    document.getElementById("wos-onboard-btn").onclick = function() { overlay.remove(); localStorage.setItem("wos-onboarded","1"); };
  }
})();

/* ── Phase 4: Multi-currency stub ── */
var WOS_CURRENCY = localStorage.getItem("wos-currency") || "USD";

/* ── Recurring Transactions ── */
function showRecurringForm() {
  var f = document.getElementById("recurring-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}
function saveRecurring() {
  var name = document.getElementById("rec-name").value.trim();
  var amount = parseFloat(document.getElementById("rec-amount").value) || 0;
  var category = document.getElementById("rec-cat").value;
  var frequency = document.getElementById("rec-freq").value;
  if (!name || amount <= 0) { alert("Name and amount are required."); return; }
  fetch("/api/recurring", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name, amount: amount, category: category, frequency: frequency })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.ok) location.reload();
    else alert(d.error || "Error saving recurring transaction.");
  }).catch(function() { alert("Network error."); });
}
function deleteRecurring(idx) {
  if (!confirm("Remove this recurring transaction?")) return;
  fetch("/api/recurring?idx=" + idx, { method: "DELETE" })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (d.ok) location.reload(); })
    .catch(function() {});
}
function applyRecurring() {
  fetch("/api/recurring/apply", { method: "POST" })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) { alert("Added " + d.count + " recurring transactions for this month."); location.reload(); }
      else alert(d.error || "Error applying recurring transactions.");
    }).catch(function() { alert("Network error."); });
}

/* ── Detect Recurring from Transaction History ── */
var _suggestedRecurring = [];
function detectRecurring() {
  var btn = event.target;
  btn.textContent = "Scanning...";
  btn.disabled = true;
  fetch("/api/recurring/detect")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      btn.textContent = "Detect from History";
      btn.disabled = false;
      _suggestedRecurring = d.suggestions || [];
      if (_suggestedRecurring.length === 0) {
        alert("No recurring patterns detected. Import more bank statements to build history.");
        return;
      }
      renderSuggestions();
    }).catch(function() {
      btn.textContent = "Detect from History";
      btn.disabled = false;
      alert("Error scanning transactions.");
    });
}
function renderSuggestions() {
  var container = document.getElementById("recurring-suggestions");
  var tbody = document.getElementById("suggested-recurring-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  _suggestedRecurring.forEach(function(s, idx) {
    var tr = document.createElement("tr");
    tr.innerHTML = '<td>' + s.name + '</td>' +
      '<td class="mono" style="text-align:right">$' + s.amount.toFixed(2) + '</td>' +
      '<td>' + s.category + '</td>' +
      '<td>' + s.frequency + '</td>' +
      '<td class="hint">' + s.occurrences + 'x in ' + s.months.length + ' months</td>' +
      '<td style="white-space:nowrap;">' +
        '<button type="button" class="success" style="padding:2px 8px;font-size:0.7rem;margin-right:4px;" onclick="acceptSuggestion(' + idx + ')">Add</button>' +
        '<button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;" onclick="dismissSuggestion(' + idx + ')">Skip</button>' +
      '</td>';
    tbody.appendChild(tr);
  });
  container.style.display = _suggestedRecurring.length > 0 ? "block" : "none";
}
function acceptSuggestion(idx) {
  var s = _suggestedRecurring[idx];
  if (!s) return;
  fetch("/api/recurring", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: s.name, amount: s.amount, category: s.category, frequency: s.frequency })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.ok) {
      _suggestedRecurring.splice(idx, 1);
      renderSuggestions();
      // Add to the main recurring table immediately
      var mainBody = document.getElementById("recurring-body");
      if (mainBody) {
        var tr = document.createElement("tr");
        var newIdx = mainBody.children.length;
        tr.innerHTML = '<td>' + s.name + '</td><td class="mono">$' + s.amount.toFixed(2) + '</td><td>' + s.category + '</td><td>' + s.frequency + '</td><td><button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;" onclick="deleteRecurring(' + newIdx + ')">x</button></td>';
        mainBody.appendChild(tr);
      }
    }
  }).catch(function() {});
}
function dismissSuggestion(idx) {
  _suggestedRecurring.splice(idx, 1);
  renderSuggestions();
}
// Auto-detect recurring after statement import
(function() {
  var params = new URLSearchParams(window.location.search);
  if (params.get("detect_recurring") === "1") {
    setTimeout(function() { detectRecurring(); }, 800);
  }
})();

/* ── Physical Metals ── */

function toggleMetalForm() {
  var f = document.getElementById("metal-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}
function saveMetalPurchase() {
  var metal = document.getElementById("metal-type").value;
  var form = document.getElementById("metal-form-desc").value.trim();
  var qty = parseFloat(document.getElementById("metal-qty").value) || 0;
  var cost = parseFloat(document.getElementById("metal-cost").value) || 0;
  var date = document.getElementById("metal-date").value;
  var note = document.getElementById("metal-note").value.trim();
  if (qty <= 0) { alert("Quantity must be greater than 0."); return; }
  fetch("/api/physical-metals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ metal: metal, form: form, qty_oz: qty, cost_per_oz: cost, date: date, note: note })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.ok) location.reload();
    else alert(d.error || "Error saving.");
  }).catch(function() { alert("Network error."); });
}
function deleteMetalRow(idx) {
  if (!confirm("Remove this metals entry?")) return;
  fetch("/api/physical-metals", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ index: idx })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.ok) location.reload();
    else alert(d.error || "Error removing.");
  }).catch(function() { alert("Network error."); });
}

/* ── Dividend & Fee Tracking ── */
var DIVIDENDS = window.DIVIDENDS || [];
function showDivForm() {
  var f = document.getElementById("div-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}
function saveDividend() {
  var date = document.getElementById("div-date").value;
  var ticker = document.getElementById("div-ticker").value.trim().toUpperCase();
  var amount = parseFloat(document.getElementById("div-amount").value) || 0;
  var dtype = document.getElementById("div-type").value;
  var note = document.getElementById("div-note").value.trim();
  if (!ticker || amount <= 0) { alert("Ticker and amount are required."); return; }
  fetch("/api/dividends", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: date, ticker: ticker, amount: amount, type: dtype, note: note })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.ok) location.reload();
    else alert(d.error || "Error saving.");
  }).catch(function() { alert("Network error."); });
}
var _divChart = null;
function buildDivChart() {
  var ctx = document.getElementById("div-chart");
  if (!ctx || typeof Chart === "undefined" || DIVIDENDS.length === 0) return;
  var months = {};
  DIVIDENDS.forEach(function(d) {
    var m = d.date ? d.date.substring(0, 7) : "unknown";
    if (!months[m]) months[m] = { div: 0, fee: 0 };
    if (d.type === "dividend") months[m].div += d.amount || 0;
    else months[m].fee += d.amount || 0;
  });
  var labels = Object.keys(months).sort().slice(-12);
  var divData = labels.map(function(m) { return months[m].div; });
  var feeData = labels.map(function(m) { return -months[m].fee; });
  if (_divChart) { _divChart.destroy(); _divChart = null; }
  _divChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        { label: "Dividends", data: divData, backgroundColor: "rgba(52,211,153,0.7)" },
        { label: "Fees", data: feeData, backgroundColor: "rgba(248,113,113,0.7)" }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#94a3b8", font: { size: 10 } } } },
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: "#64748b", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.03)" } }
      }
    }
  });
  // Update summary totals
  var totalDiv = 0, totalFee = 0;
  DIVIDENDS.forEach(function(d) {
    if (d.type === "dividend") totalDiv += d.amount || 0;
    else totalFee += d.amount || 0;
  });
  var netInc = totalDiv - totalFee;
  var fmt = function(v) { return "$" + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
  var elInc = document.getElementById("div-total-inc"); if (elInc) elInc.textContent = fmt(totalDiv);
  var elFee = document.getElementById("div-total-fee"); if (elFee) elFee.textContent = fmt(totalFee);
  var elNet = document.getElementById("div-total-net");
  if (elNet) { elNet.textContent = (netInc >= 0 ? "+" : "-") + fmt(Math.abs(netInc)); elNet.style.color = netInc >= 0 ? "var(--success)" : "var(--danger)"; }
}
buildDivChart();

/* ── Drag-to-Reorder Dashboard Widgets ── */
(function() {
  var dragSrc = null;
  function setupDrag() {
    document.querySelectorAll(".widget-card").forEach(function(card) {
      card.addEventListener("dragstart", function(e) {
        dragSrc = card;
        card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", card.dataset.widget);
      });
      card.addEventListener("dragend", function() {
        card.classList.remove("dragging");
        document.querySelectorAll(".drag-over").forEach(function(el) { el.classList.remove("drag-over"); });
        dragSrc = null;
      });
      card.addEventListener("dragover", function(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (card !== dragSrc) card.classList.add("drag-over");
      });
      card.addEventListener("dragleave", function() {
        card.classList.remove("drag-over");
      });
      card.addEventListener("drop", function(e) {
        e.preventDefault();
        card.classList.remove("drag-over");
        if (!dragSrc || dragSrc === card) return;
        // Swap positions
        var parent = card.parentNode;
        var srcParent = dragSrc.parentNode;
        var srcNext = dragSrc.nextElementSibling;
        if (srcNext === card) {
          parent.insertBefore(dragSrc, card.nextElementSibling);
        } else {
          var cardNext = card.nextElementSibling;
          srcParent.insertBefore(card, srcNext);
          parent.insertBefore(dragSrc, cardNext);
        }
        saveWidgetOrder();
      });
    });
  }
  function saveWidgetOrder() {
    var order = {};
    document.querySelectorAll(".widget-col").forEach(function(col) {
      var colId = col.id;
      var widgets = [];
      col.querySelectorAll(".widget-card").forEach(function(w) {
        widgets.push(w.dataset.widget);
      });
      order[colId] = widgets;
    });
    localStorage.setItem("wos-widget-order", JSON.stringify(order));
    // Also persist to server
    fetch("/api/widget-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(order)
    }).catch(function() {});
  }
  function restoreWidgetOrder() {
    // Try localStorage first (faster), fall back to server-saved order
    var saved = localStorage.getItem("wos-widget-order");
    if (!saved) {
      // Try from server-rendered config
      var serverOrder = window.WIDGET_ORDER || null;
      if (serverOrder && Object.keys(serverOrder).length > 0) {
        saved = JSON.stringify(serverOrder);
      }
    }
    if (!saved) return;
    try {
      var order = JSON.parse(saved);
      for (var colId in order) {
        var col = document.getElementById(colId);
        if (!col) continue;
        order[colId].forEach(function(widgetId) {
          var widget = document.querySelector('[data-widget="' + widgetId + '"]');
          if (widget) col.appendChild(widget);
        });
      }
    } catch(e) {}
  }
  restoreWidgetOrder();
  setupDrag();
})();

/* ── Goal Tracking ── */
var GOALS = window.GOALS || [];
function showGoalForm() {
  var f = document.getElementById("goal-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}
function saveGoal() {
  var name = document.getElementById("goal-name").value.trim();
  var target = parseFloat(document.getElementById("goal-target").value) || 0;
  var current = parseFloat(document.getElementById("goal-current").value) || 0;
  var date = document.getElementById("goal-date").value;
  if (!name || target <= 0) { alert("Name and target amount are required."); return; }
  fetch("/api/goals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name, target: target, current: current, target_date: date })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.ok) location.reload();
  }).catch(function() { alert("Error saving goal."); });
}
function deleteGoal(idx) {
  if (!confirm("Remove this goal?")) return;
  fetch("/api/goals?idx=" + idx, { method: "DELETE" })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (d.ok) location.reload(); });
}
function updateGoalAmount(idx) {
  var val = prompt("Enter current amount for this goal:");
  if (val === null) return;
  var amount = parseFloat(val);
  if (isNaN(amount)) return;
  fetch("/api/goals/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idx: idx, current: amount })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.ok) location.reload();
  });
}

/* ── Monte Carlo Simulation ── */

function runMonteCarlo() {
  NDDiag.track("monte-carlo", "loading");
  var mcYearsEl = document.getElementById("mc-years");
  if (!mcYearsEl) { NDDiag.track("monte-carlo", "warn", "no #mc-years element"); return; }
  var years = parseInt(mcYearsEl.value) || 10;
  var contrib = parseFloat(document.getElementById("mc-contrib").value) || 0;
  var current = window.PORTFOLIO_TOTAL || 0;
  var annualReturn = 0.07;
  var annualVol = 0.15;  // ~15% annual volatility (historical S&P)
  var monthlyReturn = annualReturn / 12;
  var monthlyVol = annualVol / Math.sqrt(12);
  var months = years * 12;
  var sims = 1000;
  var allPaths = [];
  for (var s = 0; s < sims; s++) {
    var path = [current];
    var val = current;
    for (var m = 0; m < months; m++) {
      // Box-Muller for normal random
      var u1 = Math.random(), u2 = Math.random();
      var z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      var ret = monthlyReturn + monthlyVol * z;
      val = val * (1 + ret) + contrib;
      path.push(Math.max(val, 0));
    }
    allPaths.push(path);
  }
  // Calculate percentiles at each month
  var labels = [];
  var p10 = [], p25 = [], p50 = [], p75 = [], p90 = [];
  for (var m = 0; m <= months; m++) {
    if (m % (months > 120 ? 6 : 3) === 0 || m === months) {
      labels.push(m < 12 ? m + "mo" : (m/12).toFixed(0) + "Y");
      var vals = allPaths.map(function(p) { return p[m]; }).sort(function(a,b) { return a - b; });
      p10.push(vals[Math.floor(sims * 0.1)]);
      p25.push(vals[Math.floor(sims * 0.25)]);
      p50.push(vals[Math.floor(sims * 0.5)]);
      p75.push(vals[Math.floor(sims * 0.75)]);
      p90.push(vals[Math.floor(sims * 0.9)]);
    }
  }
  var ctx = document.getElementById("mc-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (window._mcChart) window._mcChart.destroy();
  window._mcChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        { label: "90th %ile", data: p90, borderColor: "rgba(212,160,23,0.3)", backgroundColor: "rgba(212,160,23,0.05)", fill: "+1", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.6)", tension: 0.3 },
        { label: "75th %ile", data: p75, borderColor: "rgba(212,160,23,0.5)", backgroundColor: "rgba(212,160,23,0.08)", fill: "+1", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.8)", tension: 0.3 },
        { label: "Median", data: p50, borderColor: "var(--accent-primary)", borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: "#d4a017", tension: 0.3, fill: false },
        { label: "25th %ile", data: p25, borderColor: "rgba(212,160,23,0.5)", backgroundColor: "rgba(212,160,23,0.08)", fill: "+1", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.8)", tension: 0.3 },
        { label: "10th %ile", data: p10, borderColor: "rgba(212,160,23,0.3)", backgroundColor: "transparent", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.6)", tension: 0.3 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { size: 10 } } },
        tooltip: {
          yAlign: "bottom", caretPadding: 8,
          mode: "index", intersect: false,
          backgroundColor: "rgba(15,23,42,0.95)",
          titleColor: "#e2e8f0",
          bodyColor: "#cbd5e1",
          borderColor: "rgba(212,160,23,0.4)",
          borderWidth: 1,
          padding: 12,
          bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
          callbacks: {
            title: function(items) { return items[0].label; },
            label: function(ctx) {
              var val = ctx.raw;
              var formatted = val >= 1000000
                ? "$" + (val/1000000).toFixed(2) + "M"
                : "$" + Math.round(val).toLocaleString();
              return " " + ctx.dataset.label + ":  " + formatted;
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 10 }, maxTicksLimit: 12 }, grid: { display: false } },
        y: { ticks: { color: "#64748b", font: { size: 10 }, callback: function(v) { return "$" + (v >= 1000000 ? (v/1000000).toFixed(1) + "M" : (v/1000).toFixed(0) + "K"); } }, grid: { color: "rgba(255,255,255,0.03)" } }
      }
    }
  });
  NDDiag.track("monte-carlo", "ok");
}
setTimeout(runMonteCarlo, 500);

/* ── Drawdown Analysis ── */
function buildDrawdownChart() {
  NDDiag.track("drawdown", "loading");
  if (PRICE_HISTORY_DATA.length < 3) { NDDiag.track("drawdown", "warn", "insufficient data (" + PRICE_HISTORY_DATA.length + " pts)"); return; }
  if (!document.getElementById("drawdown-chart")) { NDDiag.track("drawdown", "warn", "no canvas"); return; }
  var labels = [], drawdowns = [];
  var peak = 0;
  var maxDD = 0, maxDDDate = "", recoveryDays = 0, inDD = false, ddStart = "";
  PRICE_HISTORY_DATA.forEach(function(e) {
    var t = e.total || 0;
    if (t > peak) { peak = t; inDD = false; }
    var dd = peak > 0 ? ((t - peak) / peak) * 100 : 0;
    if (dd < maxDD) { maxDD = dd; maxDDDate = e.date; }
    labels.push(e.date);
    drawdowns.push(dd);
  });
  var ctx = document.getElementById("drawdown-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (window._ddChart) window._ddChart.destroy();
  window._ddChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Drawdown %",
        data: drawdowns,
        borderColor: "rgba(248,113,113,0.8)",
        backgroundColor: "rgba(248,113,113,0.15)",
        fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.3
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { yAlign: "bottom", caretPadding: 8 }},
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 9 }, maxTicksLimit: 10 }, grid: { display: false } },
        y: { max: 0, ticks: { color: "#64748b", font: { size: 10 }, callback: function(v) { return v.toFixed(1) + "%"; } }, grid: { color: "rgba(255,255,255,0.03)" } }
      }
    }
  });
  // Stats
  var statsEl = document.getElementById("drawdown-stats");
  if (statsEl) {
    statsEl.innerHTML = '<div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
      '<div class="hint" style="margin-bottom:4px;">Max Drawdown</div>' +
      '<div class="mono" style="font-size:1.1rem;color:var(--danger);">' + maxDD.toFixed(1) + '%</div>' +
      '<div class="hint" style="margin-top:2px;">' + maxDDDate + '</div>' +
      '</div>' +
      '<div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
      '<div class="hint" style="margin-bottom:4px;">Current from Peak</div>' +
      '<div class="mono" style="font-size:1.1rem;color:' + (drawdowns.length > 0 && drawdowns[drawdowns.length-1] < -1 ? 'var(--danger)' : 'var(--success)') + ';">' +
      (drawdowns.length > 0 ? drawdowns[drawdowns.length-1].toFixed(1) : '0') + '%</div>' +
      '</div>' +
      '<div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
      '<div class="hint" style="margin-bottom:4px;">Data Points</div>' +
      '<div class="mono" style="font-size:1.1rem;">' + PRICE_HISTORY_DATA.length + '</div>' +
      '</div>';
  }
  NDDiag.track("drawdown", "ok", PRICE_HISTORY_DATA.length + " data points");
}
buildDrawdownChart();

/* ── Performance Attribution ── */
var PERF_DATA = window.PERF_DATA || {};
var _perfAttrChart = null;
function buildPerfAttribution() {
  NDDiag.track("perf-attr", "loading");
  if (!document.getElementById("perf-attr-chart")) { NDDiag.track("perf-attr", "warn", "no canvas element"); return; }
  if (!PERF_DATA.buckets) {
    fetch("/api/perf-attribution")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        PERF_DATA = d;
        buildPerfAttribution();
      })
      .catch(function(e) { NDDiag.track("perf-attr", "error", e.message || String(e)); });
    return;
  }
  var buckets = PERF_DATA.buckets;
  var total = PERF_DATA.total;
  if (!buckets || total <= 0) return;
  var labels = Object.keys(buckets);
  var values = labels.map(function(b) { return buckets[b]; });
  var pcts = labels.map(function(b) { return ((buckets[b] / total) * 100).toFixed(1); });
  var colorMap = { "Cash":"#94a3b8","Equities":"#34d399","Gold":"#eab308","Silver":"#a8a29e","Crypto":"#a78bfa","Alternatives":"#818cf8","Fixed Income":"#60a5fa","International":"#2dd4bf","Real Assets":"#06b6d4","Art":"#e879f9","Managed Blend":"#4ade80","Retirement Blend":"#86efac","Real Estate":"#22d3ee" };
  var colors = labels.map(function(b) { return colorMap[b] || "#94a3b8"; });
  var ctx = document.getElementById("perf-attr-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (_perfAttrChart) { _perfAttrChart.destroy(); _perfAttrChart = null; }
  _perfAttrChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{ label: "Value ($)", data: values, backgroundColor: colors }]
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: function(ctx) { return "$" + ctx.raw.toLocaleString() + " (" + pcts[ctx.dataIndex] + "%)"; } } }
      },
      scales: {
        x: { ticks: { color: "#64748b", font: { size: 10 }, callback: function(v) { return "$" + (v/1000).toFixed(0) + "K"; } }, grid: { color: "rgba(255,255,255,0.03)" } },
        y: { ticks: { color: "#94a3b8", font: { size: 11 } }, grid: { display: false } }
      }
    }
  });
  // Build table
  var tableEl = document.getElementById("perf-attr-table");
  if (tableEl) {
    var rows = '<table><thead><tr><th>Asset Class</th><th style="text-align:right">Value</th><th style="text-align:right">Weight</th></tr></thead><tbody>';
    labels.forEach(function(b, i) {
      rows += '<tr><td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' + colors[i] + ';margin-right:8px;"></span>' + b + '</td><td class="mono" style="text-align:right">$' + values[i].toLocaleString() + '</td><td class="mono" style="text-align:right">' + pcts[i] + '%</td></tr>';
    });
    rows += '</tbody></table>';
    if (PERF_DATA.overall_return !== 0) {
      rows += '<div style="margin-top:12px;padding:10px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
        '<span class="hint">Overall Return: </span><strong class="mono" style="color:' + (PERF_DATA.overall_return >= 0 ? 'var(--success)' : 'var(--danger)') + ';">' + (PERF_DATA.overall_return >= 0 ? '+' : '') + PERF_DATA.overall_return.toFixed(1) + '%</strong>' +
        '</div>';
    }
    tableEl.innerHTML = rows;
  }
  NDDiag.track("perf-attr", "ok", labels.length + " buckets, $" + total.toLocaleString());
}
buildPerfAttribution();

/* ── Tax-Loss Harvesting ── */
function loadTLH() {
  NDDiag.track("tlh", "loading");
  var tbody = document.getElementById("tlh-tbody");
  if (!tbody) { NDDiag.track("tlh", "warn", "no #tlh-tbody element"); return; }
  fetch("/api/tax-loss-harvesting")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var rows = d.rows || [];
      if (!rows.length) { NDDiag.track("tlh", "ok", "no harvesting opportunities"); return; }
      document.getElementById("tlh-card").style.display = "";
      var html = "";
      rows.forEach(function(r) {
        html += '<tr><td><strong>' + r.ticker + '</strong></td>' +
          '<td class="mono">' + r.qty.toFixed(3) + '</td>' +
          '<td class="mono">$' + r.cost_basis.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>' +
          '<td class="mono">$' + r.current.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>' +
          '<td class="mono danger">$' + r.unrealized.toLocaleString() + '</td></tr>';
      });
      tbody.innerHTML = html;
      NDDiag.track("tlh", "ok", rows.length + " opportunities");
    })
    .catch(function(e) { NDDiag.track("tlh", "error", e.message || String(e)); });
}
loadTLH();

/* ── Multi-Currency ── */
