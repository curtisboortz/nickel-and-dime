/* Nickel&Dime — Dashboard JavaScript */
/* Core chart building, data fetching, and UI interactions */

/* Fix candlestick wick-through-body artifact: redraw opaque bodies over wicks.
   CandlestickElement pixel props: x, open, high, low, close, width.
   In canvas coords lower y = higher price, so close < open means price went UP. */
(function() {
  if (typeof Chart === "undefined") return;
  Chart.register({
    id: "candleBodyOverlay",
    afterDatasetsDraw: function(chart) {
      if (chart.config.type !== "candlestick") return;
      var defaults = Chart.defaults.elements.candlestick || {};
      var defBg = defaults.backgroundColors || {};
      chart.data.datasets.forEach(function(ds, dsIdx) {
        var meta = chart.getDatasetMeta(dsIdx);
        if (!meta || meta.hidden) return;
        var ctx = chart.ctx;
        meta.data.forEach(function(el) {
          if (!el || typeof el.x === "undefined") return;
          var openPx = el.open, closePx = el.close;
          var x = el.x, w = el.width || 6;
          if (openPx == null || closePx == null) return;
          var bg = (el.options && el.options.backgroundColors) || {};
          var fill;
          if (closePx < openPx) fill = bg.up || defBg.up || "#34d399";
          else if (closePx > openPx) fill = bg.down || defBg.down || "#f87171";
          else fill = bg.unchanged || defBg.unchanged || "#94a3b8";
          ctx.save();
          ctx.fillStyle = fill;
          ctx.fillRect(x - w / 2, closePx, w, openPx - closePx);
          ctx.restore();
        });
      });
    }
  });
})();

var PRICE_HISTORY_DATA = window.PRICE_HISTORY_DATA || [];
var BUCKETS_DATA = window.BUCKETS_DATA || {};
var TARGETS_DATA = window.TARGETS_DATA || {};

/* ── Manual Refresh ── */
window.refreshData = function() {
  var btn = document.getElementById("refresh-btn");
  if (btn) btn.style.opacity = "0.5";
  fetch("/api/refresh", { method: "POST" })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (btn) btn.style.opacity = "1";
      if (d.success) {
        window.location.reload();
      }
    })
    .catch(function() {
      if (btn) btn.style.opacity = "1";
    });
};

/* ── Budget lazy-load ── */
var _budgetDataLoaded = false;
window._initBudgetListeners = function() {
  if (_budgetDataLoaded) return;
  _budgetDataLoaded = true;
  fetch("/api/budget-data")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      TRANSACTIONS = d.transactions || [];
      BUDGET_LIMITS = d.budget_limits || {};
      BUDGET_CATS = d.budget_cats || [];
      if (typeof renderTxns === "function") renderTxns();
      if (typeof renderSpendingBreakdown === "function") renderSpendingBreakdown();
      if (typeof buildSpendingChart === "function") buildSpendingChart();
    })
    .catch(function() { _budgetDataLoaded = false; });
};

/* ── Summary Tab Data (allocation table + monthly investments) ── */
var _summaryDataLoaded = false;
function loadSummaryData() {
  if (_summaryDataLoaded) return;
  _summaryDataLoaded = true;
  loadAllocationTable();
  loadMonthlyInvestments();
  if (window.BUCKETS_DATA && Object.keys(window.BUCKETS_DATA).length > 0) {
    if (typeof buildDonut === "function") buildDonut();
  }
}

function loadAllocationTable() {
  var tbody = document.getElementById("alloc-table-body");
  if (!tbody) return;
  fetch("/api/allocation-targets")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var rows = d.rows || [];
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted);">No allocation data yet. Add holdings to see your breakdown.</td></tr>';
        return;
      }
      var html = "";
      rows.forEach(function(r) {
        var driftCls = r.drift > 1 ? "color:var(--success)" : r.drift < -1 ? "color:var(--danger)" : "color:var(--text-muted)";
        var driftStr = (r.drift > 0 ? "+" : "") + r.drift.toFixed(1) + "%";
        html += '<tr>';
        html += '<td style="padding:8px 6px;">' + r.bucket + '</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">$' + r.value.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">' + r.pct.toFixed(1) + '%</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">' + r.target + '%</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);' + driftCls + '">' + driftStr + '</td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;
    })
    .catch(function() {});
}

function loadMonthlyInvestments() {
  var tbody = document.getElementById("invest-table-body");
  var subtitle = document.getElementById("invest-subtitle");
  if (!tbody) return;
  fetch("/api/investments")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var cats = d.categories || [];
      var budget = d.monthly_budget || 0;
      var month = d.month || "";
      var monthLabel = month ? new Date(month + "-01").toLocaleDateString(undefined, {year:"numeric", month:"long"}) : "";
      if (subtitle) subtitle.textContent = monthLabel + " - Budget: $" + budget.toLocaleString(undefined, {maximumFractionDigits:0}) + " / $" + budget.toLocaleString(undefined, {maximumFractionDigits:0});

      if (cats.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted);">No investment categories set up for this month.</td></tr>';
        return;
      }

      var totalTarget = 0, totalContrib = 0;
      var html = "";
      cats.forEach(function(c) {
        var pct = budget > 0 ? Math.round((c.target / budget) * 100) : 0;
        var diff = c.contributed - c.target;
        var diffStr = (diff >= 0 ? "+" : "") + "$" + Math.abs(diff).toFixed(1);
        var diffCls = diff >= 0 ? "color:var(--success)" : "color:var(--warning)";
        var progressPct = c.target > 0 ? Math.min((c.contributed / c.target) * 100, 100) : 0;
        var barCls = progressPct < 40 ? "low" : progressPct < 90 ? "mid" : "done";
        totalTarget += c.target;
        totalContrib += c.contributed;
        html += '<tr>';
        html += '<td style="padding:8px 6px;"><strong>' + c.category + '</strong> <span style="color:var(--text-muted);font-size:0.75rem;">(' + pct + '%)</span></td>';
        html += '<td style="padding:8px 6px;text-align:right;font-family:var(--mono);">$' + c.target.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
        html += '<td style="padding:8px 6px;text-align:right;"><input type="number" class="contrib-input num" data-id="' + c.id + '" data-target="' + c.target + '" value="' + c.contributed + '" style="width:80px;text-align:right;" onchange="updateInvestTotals()"></td>';
        html += '<td style="padding:8px 6px;text-align:right;font-family:var(--mono);' + diffCls + '">' + diffStr + '</td>';
        html += '<td style="padding:8px 6px;text-align:center;"><div class="progress-bar" style="width:80px;display:inline-block;"><div class="progress-fill mini-fill ' + barCls + '" style="width:' + progressPct + '%"></div></div></td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;

      var totalRem = totalTarget - totalContrib;
      var totalPct = totalTarget > 0 ? Math.min((totalContrib / totalTarget) * 100, 100) : 0;
      var itgt = document.getElementById("invest-total-target"); if (itgt) itgt.textContent = "$" + totalTarget.toLocaleString(undefined, {maximumFractionDigits:0});
      var icnt = document.getElementById("invest-total-contrib"); if (icnt) icnt.textContent = "$" + totalContrib.toLocaleString(undefined, {maximumFractionDigits:0});
      var istat = document.getElementById("invest-total-status"); if (istat) { istat.textContent = "$" + totalRem.toLocaleString(undefined, {maximumFractionDigits:0}) + " left"; istat.style.color = totalRem > 0 ? "var(--warning)" : "var(--success)"; }
      var pf = document.getElementById("total-progress-fill"); if (pf) pf.style.width = totalPct + "%";
      var pp = document.getElementById("total-progress-pct"); if (pp) pp.textContent = Math.round(totalPct) + "%";
    })
    .catch(function() {});
}

function updateInvestTotals() {
  var tc = 0, tt = 0;
  document.querySelectorAll(".contrib-input").forEach(function(i) { tc += parseFloat(i.value) || 0; tt += parseFloat(i.dataset.target) || 0; });
  var rem = tt - tc, pct = tt > 0 ? Math.min((tc / tt) * 100, 100) : 0;
  var itgt = document.getElementById("invest-total-target"); if (itgt) itgt.textContent = "$" + tt.toLocaleString(undefined, {maximumFractionDigits:0});
  var icnt = document.getElementById("invest-total-contrib"); if (icnt) icnt.textContent = "$" + tc.toLocaleString(undefined, {maximumFractionDigits:0});
  var istat = document.getElementById("invest-total-status"); if (istat) { istat.textContent = "$" + Math.abs(rem).toLocaleString(undefined, {maximumFractionDigits:0}) + (rem > 0 ? " left" : ""); istat.style.color = rem > 0 ? "var(--warning)" : "var(--success)"; }
  var pf = document.getElementById("total-progress-fill"); if (pf) pf.style.width = pct + "%";
  var pp = document.getElementById("total-progress-pct"); if (pp) pp.textContent = Math.round(pct) + "%";
}

function saveContributionsAPI() {
  var categories = [];
  document.querySelectorAll(".contrib-input").forEach(function(i) {
    categories.push({ id: parseInt(i.dataset.id), contributed: parseFloat(i.value) || 0 });
  });
  fetch("/api/investments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categories: categories })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      var btn = document.querySelector("button[onclick*='saveContributions']");
      if (btn) { btn.textContent = "Saved!"; setTimeout(function() { btn.textContent = "Save Changes"; }, 2000); }
    }
  });
}

function newMonthAPI() {
  var now = new Date();
  var month = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  if (!confirm("Start investment tracking for " + month + "? Targets will carry over, contributions reset to $0.")) return;
  fetch("/api/investments/new-month", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ month: month })
  }).then(function(r) { return r.json(); }).then(function() {
    _summaryDataLoaded = false;
    loadMonthlyInvestments();
  });
}

/* ── Add Investment Category ── */
function showAddCategoryForm() {
  var form = document.getElementById("add-category-form");
  if (form) form.style.display = form.style.display === "none" ? "block" : "none";
}
function addInvestCategory() {
  var name = document.getElementById("new-cat-name").value.trim();
  var target = parseFloat(document.getElementById("new-cat-target").value) || 0;
  if (!name) { alert("Enter a category name."); return; }
  fetch("/api/investments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categories: [{ category: name, target: target, contributed: 0 }] })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      document.getElementById("new-cat-name").value = "";
      document.getElementById("new-cat-target").value = "";
      document.getElementById("add-category-form").style.display = "none";
      _summaryDataLoaded = false;
      loadMonthlyInvestments();
    }
  });
}

/* ── Edit Allocation Targets ── */
var _editingTargets = false;
function toggleEditTargets() {
  if (_editingTargets) {
    cancelEditTargets();
  } else {
    _editingTargets = true;
    var btn = document.getElementById("edit-targets-btn");
    btn.textContent = "Cancel";
    loadAllocationTableEditable();
  }
}
function cancelEditTargets() {
  _editingTargets = false;
  var btn = document.getElementById("edit-targets-btn");
  btn.textContent = "Edit Targets";
  loadAllocationTable();
}
function loadAllocationTableEditable() {
  var tbody = document.getElementById("alloc-table-body");
  if (!tbody) return;
  fetch("/api/allocation-targets")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var rows = d.rows || [];
      var html = "";
      rows.forEach(function(r) {
        html += '<tr>';
        html += '<td style="padding:8px 6px;">' + r.bucket + '</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">$' + r.value.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">' + r.pct.toFixed(1) + '%</td>';
        html += '<td style="padding:8px 6px;"><input type="number" class="target-input num" data-bucket="' + r.bucket + '" value="' + r.target + '" style="width:60px;text-align:right;" min="0" max="100">%</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">' + ((r.drift > 0 ? "+" : "") + r.drift.toFixed(1)) + '%</td>';
        html += '</tr>';
      });
      html += '<tr><td colspan="5" style="padding:10px 6px;text-align:right;"><button type="button" onclick="saveAllocationTargets()" style="padding:6px 16px;font-size:0.8rem;">Save Targets</button></td></tr>';
      tbody.innerHTML = html;
    });
}
function saveAllocationTargets() {
  var inputs = document.querySelectorAll(".target-input");
  if (inputs.length === 0) return;
  var tactical = {};
  inputs.forEach(function(i) {
    var val = parseFloat(i.value);
    if (!isNaN(val) && val > 0) {
      tactical[i.dataset.bucket] = { target: val, min: 0, max: 100 };
    }
  });
  if (Object.keys(tactical).length === 0) {
    alert("No targets to save. Enter at least one target percentage.");
    return;
  }
  fetch("/api/allocation-targets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ targets: { tactical: tactical } })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      _editingTargets = false;
      var btn = document.getElementById("edit-targets-btn");
      btn.textContent = "Edit Targets";
      loadAllocationTable();
    }
  });
}

/* ── Allocation Donut ── */
var _donutChart = null;
function buildDonut() {
  var data = window.BUCKETS_DATA;
  if (!data || typeof data !== "object") return;
  var labels = Object.keys(data);
  var values = Object.values(data);
  if (labels.length === 0) return;
  var colorMap = {
    "Gold":"#d4a017", "Silver":"#c0c0c0", "Equities":"#34d399", "Crypto":"#818cf8",
    "Cash":"#64748b", "RealEstate":"#06b6d4", "Art":"#e879f9", "ManagedBlend":"#fb923c",
    "RetirementBlend":"#a78bfa", "RealAssets":"#06b6d4"
  };
  var fallback = ["#f87171","#fbbf24","#2dd4bf","#a3e635","#f472b6"];
  var fi = 0;
  var colors = labels.map(function(l) { return colorMap[l] || fallback[fi++ % fallback.length]; });
  var ctx = document.getElementById("allocation-donut");
  if (!ctx) { console.warn("buildDonut: canvas #allocation-donut not found"); return; }
  if (typeof Chart === "undefined") { console.warn("buildDonut: Chart.js not loaded"); return; }
  if (_donutChart) { try { _donutChart.destroy(); } catch(e) {} }
  _donutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{ data: values, backgroundColor: colors.slice(0, labels.length), borderWidth: 0, hoverBorderWidth: 2, hoverBorderColor: "#fff" }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "65%",
      plugins: {
        legend: { position: "right", labels: { color: "#94a3b8", font: { size: 11, family: "Inter" }, padding: 12, usePointStyle: true, pointStyle: "circle" } },
        tooltip: {
          backgroundColor: "rgba(9,9,11,0.95)",
          titleColor: "#f1f5f9", bodyColor: "#94a3b8",
          borderColor: "rgba(255,255,255,0.1)", borderWidth: 1,
          padding: 12, cornerRadius: 8,
          callbacks: { label: function(c) { return c.label + ": $" + c.raw.toLocaleString(undefined,{maximumFractionDigits:0}); } }
        }
      }
    }
  });
}

/* ── Portfolio History Chart ── */
var _histChartType = "line";
function setHistoryChartType(type) {
  _histChartType = type;
  document.getElementById("hist-line-btn").classList.toggle("active", type === "line");
  document.getElementById("hist-candle-btn").classList.toggle("active", type === "candlestick");
  buildHistoryChart("total");
}
function buildHistoryChart(metric) {
  metric = metric || "total";
  var ctx = document.getElementById("history-chart");
  if (window.historyChart) window.historyChart.destroy();

  var labels = PRICE_HISTORY_DATA.map(function(r) { return r.date; });

  if (_histChartType === "candlestick" && PRICE_HISTORY_DATA.length >= 2) {
    // Candlestick mode using OHLC data with timestamps
    var ohlcData = PRICE_HISTORY_DATA.map(function(r) {
      return {
        x: new Date(r.date).getTime(),
        o: r.open || r.total,
        h: r.high || r.total,
        l: r.low || r.total,
        c: r.close || r.total,
      };
    });
    window.historyChart = new Chart(ctx, {
      type: "candlestick",
      data: {
        datasets: [{
          label: "Portfolio Value",
          data: ohlcData,
          backgroundColors: {
            up: "rgba(52,211,153,1)",
            down: "rgba(248,113,113,1)",
            unchanged: "rgba(148,163,184,1)",
          },
          borderColors: {
            up: "rgba(52,211,153,1)",
            down: "rgba(248,113,113,1)",
            unchanged: "rgba(148,163,184,1)",
          },
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: "nearest", axis: "x" },
        plugins: {
          legend: { display: false },
          tooltip: { enabled: false, external: function(context) {
            var el = document.getElementById("hist-hover-info");
            if (!el) return;
            if (context.tooltip.opacity === 0) { el.style.opacity = "0"; return; }
            var dp = context.tooltip.dataPoints && context.tooltip.dataPoints[0];
            if (!dp) return;
            var d = dp.raw;
            var dt = new Date(d.x);
            var dStr = dt.toLocaleDateString(undefined, {month:"short", day:"numeric", year:"numeric"});
            var f = function(v) { return "$" + v.toLocaleString(undefined, {maximumFractionDigits:0}); };
            var chg = d.c - d.o;
            var color = chg >= 0 ? "var(--accent-green,#34d399)" : "var(--danger,#f87171)";
            el.innerHTML = '<span style="color:#f1f5f9">' + dStr + '</span>'
              + '&ensp;O: ' + f(d.o) + '&ensp;H: ' + f(d.h) + '&ensp;L: ' + f(d.l)
              + '&ensp;<span style="color:' + color + '">C: ' + f(d.c) + '</span>';
            el.style.opacity = "1";
          } }
        },
        scales: {
          x: { type: "time", time:{ unit:"day", tooltipFormat:"MMM d, yyyy" }, ticks:{ maxTicksLimit:8, color:"#64748b", font:{size:10} }, grid:{ color:"rgba(255,255,255,0.03)" } },
          y: { ticks:{ color:"#64748b", font:{size:10}, callback: function(v) { return "$" + (v/1000).toFixed(0) + "K"; } }, grid:{ color:"rgba(255,255,255,0.03)" } }
        }
      }
    });
  } else {
    // Line mode using close/total values with proper time-based x-axis
    var pointData = PRICE_HISTORY_DATA.map(function(r) { return { x: r.date, y: r.close || r.total }; });
    var fmt = function(v) { return v != null ? "$" + v.toLocaleString(undefined, {maximumFractionDigits:0}) : "—"; };
    var validData = pointData.filter(function(p) { return p.y != null && isFinite(p.y); });
    var vals = validData.map(function(p) { return p.y; });
    var dataMin = vals.length ? Math.min.apply(null, vals) : 0;
    var dataMax = vals.length ? Math.max.apply(null, vals) : 0;
    var padding = dataMin === dataMax ? Math.max(dataMax * 0.02, 500) : Math.max((dataMax - dataMin) * 0.15, dataMax * 0.005);
    window.historyChart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [{ label: "Portfolio Value", data: pointData, borderColor: "#d4a017", backgroundColor: "rgba(212,160,23,0.12)", fill: true, tension: 0.35, pointRadius: PRICE_HISTORY_DATA.length < 30 ? 4 : 0, pointHoverRadius: 6, pointHoverBackgroundColor: "#d4a017", pointBackgroundColor: "#d4a017", borderWidth: 2.5 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: "nearest", axis: "x" },
      plugins: {
          legend: { display: false },
          tooltip: { enabled: false, external: function(context) {
            var el = document.getElementById("hist-hover-info");
            if (!el) return;
            if (context.tooltip.opacity === 0) { el.style.opacity = "0"; return; }
            var dp = context.tooltip.dataPoints && context.tooltip.dataPoints[0];
            if (!dp) return;
            var val = dp.raw.y;
            var r = PRICE_HISTORY_DATA[dp.dataIndex];
            var dStr = dp.raw.x;
            try { dStr = new Date(dp.raw.x).toLocaleDateString(undefined, {month:"short", day:"numeric", year:"numeric"}); } catch(e){}
            if (r && r.open) {
              var chg = (r.close || val) - r.open;
              var color = chg >= 0 ? "var(--accent-green,#34d399)" : "var(--danger,#f87171)";
              el.innerHTML = '<span style="color:#f1f5f9">' + dStr + '</span>'
                + '&ensp;' + fmt(val)
                + '&ensp;<span style="color:#64748b">(' + fmt(r.low) + ' – ' + fmt(r.high) + ')</span>';
            } else {
              el.innerHTML = '<span style="color:#f1f5f9">' + dStr + '</span>&ensp;' + fmt(val);
            }
            el.style.opacity = "1";
          } }
      },
      scales: {
          x: { type: "time", time: { unit: PRICE_HISTORY_DATA.length > 90 ? "week" : "day", tooltipFormat: "yyyy-MM-dd" }, ticks:{ maxTicksLimit:8, color:"#64748b", font:{size:10} }, grid:{ color:"rgba(255,255,255,0.03)" } },
          y: { min: Math.floor((dataMin - padding) / 1000) * 1000, max: Math.ceil((dataMax + padding) / 1000) * 1000, ticks:{ color:"#64748b", font:{size:10}, callback: function(v) { return "$" + (v/1000).toFixed(0) + "K"; } }, grid:{ color:"rgba(255,255,255,0.03)" } }
        }
      }
    });
  }
}

/* ── Sparklines ── */
function renderSparkCanvas(canvasId, values) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || !values || values.length < 2) return;
  var ctx = canvas.getContext("2d");
  var w = canvas.width = canvas.offsetWidth * 2;
  var h = canvas.height = canvas.offsetHeight * 2;
  ctx.scale(2, 2);
  var cw = canvas.offsetWidth, ch = canvas.offsetHeight;
  var mn = Math.min.apply(null, values), mx = Math.max.apply(null, values);
  var range = mx - mn || 1;
  var up = values[values.length-1] >= values[0];
  ctx.beginPath();
  ctx.strokeStyle = up ? "#34d399" : "#f87171";
  ctx.lineWidth = 1.5; ctx.lineJoin = "round";
  for (var i = 0; i < values.length; i++) {
    var x = (i / (values.length - 1)) * cw;
    var y = ch - ((values[i] - mn) / range) * (ch - 4) - 2;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.lineTo(cw, ch); ctx.lineTo(0, ch); ctx.closePath();
  var grad = ctx.createLinearGradient(0, 0, 0, ch);
  grad.addColorStop(0, up ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = grad; ctx.fill();
}
function loadAllSparklines() {
  // Dynamically build spark map from all pulse items with spark canvases
  var map = {};
  var cryptoSymbols = [];
  document.querySelectorAll(".pulse-spark").forEach(function(c) {
    var id = c.id;
    if (id) {
      var sym = id.substring(6); // remove "spark-"
      if (sym.match(/^[A-Z]{1,3}-F$/)) sym = sym.replace("-F", "=F");
      var parent = c.closest(".pulse-item");
      var ptype = parent && parent.dataset.pulseType ? parent.dataset.pulseType : "stock";
      map[sym] = id;
      if (ptype === "crypto") cryptoSymbols.push(sym);
    }
  });
  if (Object.keys(map).length === 0) return;
  var url = "/api/sparklines?symbols=" + encodeURIComponent(Object.keys(map).join(","));
  if (cryptoSymbols.length) url += "&crypto=" + encodeURIComponent(cryptoSymbols.join(","));
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      for (var sym in map) {
        if (data[sym] && data[sym].length > 1) renderSparkCanvas(map[sym], data[sym]);
      }
    })
    .catch(function() {});
}

/* ── Investment Tracker ── */
function updateProgressBar(input) {
  var key=input.dataset.key, target=parseFloat(input.dataset.target)||1, contributed=parseFloat(input.value)||0;
  var pct=Math.min((contributed/target)*100,100), diff=contributed-target;
  var bar=document.getElementById("progress-"+key);
  if(bar) { bar.style.width=pct+"%"; bar.className="mini-fill "+(pct<40?"low":pct<90?"mid":"done"); }
  var st=document.getElementById("status-"+key);
  if(st) {
    if(diff>=0) { st.textContent="+$"+diff.toFixed(0); st.className=diff>0?"surplus":"complete"; }
    else { st.textContent="-$"+Math.abs(diff).toFixed(0); st.className="shortage"; }
  }
  updateTotals();
}
function updateTotals() {
  var tc=0, tt=0;
  document.querySelectorAll(".contrib-input").forEach(function(i) { tc+=parseFloat(i.value)||0; tt+=parseFloat(i.dataset.target)||0; });
  var rem=tt-tc, pct=tt>0?Math.min((tc/tt)*100,100):0;
  var row=document.querySelector(".invest-table tfoot tr");
  if(row) {
    var cells=row.querySelectorAll("td");
    if(cells[2]) cells[2].innerHTML="<span class='mono' style='color:var(--accent-primary)'>$"+tc.toFixed(0)+"</span>";
    if(cells[3]) cells[3].innerHTML="<span class='mono' style='color:"+(rem>0?"var(--warning)":"var(--success)")+"'>$"+rem.toFixed(0)+" left</span>";
  }
  var pf=document.getElementById("total-progress-fill"); if(pf) pf.style.width=pct+"%";
  var pl=document.getElementById("total-progress-pct"); if(pl) pl.textContent=Math.round(pct)+"%";
}
function saveContributions() {
  var data={};
  document.querySelectorAll(".contrib-input").forEach(function(i) { data[i.dataset.key]=parseFloat(i.value)||0; });
  fetch("/api/save-contributions",{ method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data) })
  .then(function(r){ return r.json(); })
  .then(function(res){
    if(res.success) {
      var btn=document.querySelector("button[onclick*='saveContributions']");
      if(btn) { btn.textContent="Saved!"; }
      setTimeout(function() { location.reload(); }, 600);
    }
  });
}
function newMonth() {
  if(!confirm("Start a new month? This resets all investment contributions to $0.")) return;
  fetch("/api/new-month",{method:"POST"}).then(function(r){return r.json();}).then(function(d){ if(d.success) location.reload(); });
}
function newBudgetMonth() {
  if(!confirm("Start a new budget month? This updates both budget and investment months, and resets contributions.")) return;
  fetch("/api/new-budget-month",{method:"POST"}).then(function(r){return r.json();}).then(function(d){ if(d.success) location.reload(); });
}
var saveTimeout;
function _autoSaveContributions() {
  var data={};
  document.querySelectorAll(".contrib-input").forEach(function(i) { data[i.dataset.key]=parseFloat(i.value)||0; });
  fetch("/api/save-contributions",{ method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data) });
}
document.querySelectorAll(".contrib-input").forEach(function(input) {
  input.addEventListener("input", function() { updateProgressBar(this); clearTimeout(saveTimeout); saveTimeout=setTimeout(_autoSaveContributions,1000); });
  input.addEventListener("change", function() { updateProgressBar(this); clearTimeout(saveTimeout); saveTimeout=setTimeout(_autoSaveContributions,500); });
});

/* ── Investment Quick-Log Chat ── */
var INVEST_ALIASES = {
  "gold etf": "gold_etf", "gold": "gold_etf", "gld": "gold_etf", "gldm": "gold_etf", "iau": "gold_etf",
  "gold savings": "gold_phys_save", "gold save": "gold_phys_save", "gold physical": "gold_phys_save", "physical gold": "gold_phys_save",
  "silver etf": "silver_etf", "silver": "silver_etf", "slv": "silver_etf", "pslv": "silver_etf",
  "silver savings": "silver_phys_save", "silver save": "silver_phys_save", "silver physical": "silver_phys_save", "physical silver": "silver_phys_save",
  "crypto": "crypto", "bitcoin": "crypto", "btc": "crypto", "eth": "crypto", "ethereum": "crypto", "coinbase": "crypto",
  "equities": "equities", "stocks": "equities", "stock": "equities", "spy": "equities", "voo": "equities",
  "xar": "equities", "fidelity": "equities", "etf": "equities", "index": "equities",
  "real assets": "real_assets", "real estate": "real_assets", "fundrise": "real_assets", "masterworks": "real_assets", "art": "real_assets",
  "cash": "cash", "cash reserve": "cash", "savings": "cash", "emergency": "cash",
  "stash": "equities", "stash personal": "equities", "stash smart": "equities",
  "stash retirement": "equities", "retirement": "equities", "401k": "equities", "ira": "equities",
  "acorns": "equities", "acorns invest": "equities", "acorns later": "equities",
};
var INVEST_NAMES = {
  "gold_etf": "Gold ETF", "gold_phys_save": "Gold Savings",
  "silver_etf": "Silver ETF", "silver_phys_save": "Silver Savings",
  "crypto": "Crypto", "equities": "Equities",
  "real_assets": "Real Assets", "cash": "Cash Reserve",
};
function matchCategory(text) {
  var t = text.toLowerCase().trim();
  // Exact match first
  if (INVEST_ALIASES[t]) return INVEST_ALIASES[t];
  // Partial match
  for (var alias in INVEST_ALIASES) {
    if (t.indexOf(alias) !== -1 || alias.indexOf(t) !== -1) return INVEST_ALIASES[alias];
  }
  // Fuzzy: check each word
  var words = t.split(/\s+/);
  for (var w = 0; w < words.length; w++) {
    if (INVEST_ALIASES[words[w]]) return INVEST_ALIASES[words[w]];
  }
  return null;
}
function processInvestChat() {
  var input = document.getElementById("invest-chat-input");
  var log = document.getElementById("chat-log");
  var raw = input.value.trim();
  if (!raw) return;

  // Split by comma for multiple entries
  var entries = raw.split(",");
  var results = [];
  var hasMetalEntry = false;
  var hasContribEntry = false;
  entries.forEach(function(entry) {
    entry = entry.trim();
    if (!entry) return;

    // ── Physical metals purchase detection ──
    // Patterns: "bought 5oz silver at $31", "bought 1oz gold for $2700",
    //           "added 10oz silver bar", "5oz gold at $2800"
    var metalMatch = entry.match(/(?:bought|added|purchased|buy)?\s*(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)\s+(?:of\s+)?(gold|silver)(?:\s+([\w\s]+?))?(?:\s+(?:at|for|@)\s+\$?\s*(\d+(?:\.\d{1,2})?))?/i);
    if (!metalMatch) {
      // Also try: "gold 5oz at $2800"
      metalMatch = entry.match(/(?:bought|added|purchased|buy)?\s*(gold|silver)\s+(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)(?:\s+([\w\s]+?))?(?:\s+(?:at|for|@)\s+\$?\s*(\d+(?:\.\d{1,2})?))?/i);
      if (metalMatch) {
        // Rearrange so [1]=qty, [2]=metal, [3]=form, [4]=price
        var _m = metalMatch;
        metalMatch = [_m[0], _m[2], _m[1], _m[3], _m[4]];
      }
    }
    if (metalMatch) {
      var mQty = parseFloat(metalMatch[1]);
      var mMetal = metalMatch[2].charAt(0).toUpperCase() + metalMatch[2].slice(1).toLowerCase();
      var mForm = (metalMatch[3] || "").trim();
      var mCost = metalMatch[4] ? parseFloat(metalMatch[4]) : 0;
      if (mQty <= 0) {
        results.push({ ok: false, msg: "Quantity must be > 0" });
        return;
      }
      // POST to physical metals API
      fetch("/api/physical-metals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metal: mMetal, form: mForm, qty_oz: mQty, cost_per_oz: mCost, date: "", note: "Logged via chat" })
      }).then(function(r) { return r.json(); }).then(function(d) {
        var div = document.createElement("div");
        if (d.ok) {
          var priceNote = mCost > 0 ? " at $" + mCost.toFixed(2) + "/oz" : "";
          div.className = "chat-msg ok";
          div.innerHTML = '<span class="chat-label">&#10003;</span>Logged ' + mQty + 'oz ' + mMetal + priceNote;
        } else {
          div.className = "chat-msg err";
          div.innerHTML = '<span class="chat-label">&#10007;</span>' + (d.error || "Error saving metal");
        }
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
      }).catch(function() {
        var div = document.createElement("div");
        div.className = "chat-msg err";
        div.innerHTML = '<span class="chat-label">&#10007;</span>Network error saving metal';
        log.appendChild(div);
      });
      hasMetalEntry = true;
      return;  // Don't process as contribution
    }

    // ── Normal contribution + holdings/balance processing ──
    // Extract dollar amount: $100, 100, etc.
    var amountMatch = entry.match(/\$?\s*(\d+(?:\.\d{1,2})?)/);
    if (!amountMatch) {
      results.push({ ok: false, msg: 'No amount found in "' + entry + '"' });
      return;
    }
    var amount = parseFloat(amountMatch[1]);
    // Remove the amount portion to get the category text
    var catText = entry.replace(amountMatch[0], "").replace(/^\s*to\s+/i, "").replace(/\s*to\s*$/i, "").trim();
    catText = catText.replace(/^to\s+/i, "").replace(/^add\s+/i, "").trim();
    if (!catText) {
      results.push({ ok: false, msg: 'No category found in "' + entry + '"' });
      return;
    }
    // Parse optional "in [account]" suffix: "100 to pslv in fidelity"
    var acctMatch = catText.match(/^(.+?)\s+(?:in|at|for)\s+(.+)$/i);
    var rawTarget = acctMatch ? acctMatch[1].trim() : catText;
    var acctHint = acctMatch ? acctMatch[2].trim() : "";

    // Try contribution category match
    var key = matchCategory(rawTarget);
    if (key) {
      var field = document.querySelector('.contrib-input[data-key="' + key + '"]');
      if (field) {
        var oldVal = parseFloat(field.value) || 0;
        var newVal = oldVal + amount;
        field.value = Math.round(newVal);
        updateProgressBar(field);
        hasContribEntry = true;
        results.push({ ok: true, msg: '+$' + amount.toFixed(0) + ' to ' + INVEST_NAMES[key] + ' (now $' + Math.round(newVal) + ')' });
      }
    }

    // Also try to update holdings/balances via quick-update API
    // (rawTarget could be a ticker like PSLV, or a balance account like Fundrise)
    fetch("/api/quick-update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: amount, target: rawTarget, account: acctHint })
    }).then(function(r) { return r.json(); }).then(function(d) {
      var div = document.createElement("div");
      if (d.ok && d.type === "holding") {
        div.className = "chat-msg ok";
        var sharesNote = d.shares_added ? ' (+' + d.shares_added + ' shares @ $' + d.price.toFixed(2) + ')' : '';
        var cashNote = d.cash_deducted ? ' | SPAXX: $' + d.old_cash.toLocaleString(undefined, {maximumFractionDigits:0}) + ' &rarr; $' + d.new_cash.toLocaleString(undefined, {maximumFractionDigits:0}) : '';
        div.innerHTML = '<span class="chat-label">&#10003;</span>' + d.ticker + (d.account ? ' (' + d.account + ')' : '') + ': $' + d.old_value.toLocaleString(undefined, {maximumFractionDigits:0}) + ' &rarr; $' + d.new_value.toLocaleString(undefined, {maximumFractionDigits:0}) + sharesNote + cashNote;
        log.appendChild(div);
      } else if (d.ok && d.type === "balance") {
        div.className = "chat-msg ok";
        div.innerHTML = '<span class="chat-label">&#10003;</span>' + d.name + ': $' + d.old_value.toLocaleString(undefined, {maximumFractionDigits:0}) + ' &rarr; $' + d.new_value.toLocaleString(undefined, {maximumFractionDigits:0});
        log.appendChild(div);
      } else if (!key) {
        // Only show error if we also failed the contribution match
        div.className = "chat-msg err";
        div.innerHTML = '<span class="chat-label">&#10007;</span>No match for "' + rawTarget + '" in contributions, holdings, or balances';
        log.appendChild(div);
      }
      log.scrollTop = log.scrollHeight;
    }).catch(function() {});
  });

  // Render results in chat log
  results.forEach(function(r) {
    var div = document.createElement("div");
    div.className = "chat-msg " + (r.ok ? "ok" : "err");
    div.innerHTML = '<span class="chat-label">' + (r.ok ? "&#10003;" : "&#10007;") + '</span>' + r.msg;
    log.appendChild(div);
  });
  log.scrollTop = log.scrollHeight;

  // Clear input and auto-save contributions if any
  input.value = "";
  if (hasContribEntry && results.some(function(r) { return r.ok; })) {
    clearTimeout(saveTimeout);
    // Save contributions then reload to reflect updated totals
    var cdata={};
    document.querySelectorAll(".contrib-input").forEach(function(i) { cdata[i.dataset.key]=parseFloat(i.value)||0; });
    fetch("/api/save-contributions",{ method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(cdata) })
    .then(function() { setTimeout(function() { location.reload(); }, 800); });
    updateTotals();
  }
}
// Allow Enter key to submit
var _investInput = document.getElementById("invest-chat-input");
if (_investInput) _investInput.addEventListener("keydown", function(e) {
  if (e.key === "Enter") { e.preventDefault(); processInvestChat(); }
});

/* ── Pulse Card Drag & Drop + Add/Remove ── */
(function() {
  var bar = document.getElementById("pulse-bar");
  if (!bar) return;
  var pulseDragSrc = null;

  function setupPulseDrag() {
    bar.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {
      item.addEventListener("dragstart", function(e) {
        pulseDragSrc = item;
        item.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", item.dataset.pulseId);
      });
      item.addEventListener("dragend", function() {
        item.classList.remove("dragging");
        bar.querySelectorAll(".drag-over").forEach(function(el) { el.classList.remove("drag-over"); });
        pulseDragSrc = null;
      });
      item.addEventListener("dragover", function(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (item !== pulseDragSrc && !item.classList.contains("pulse-add")) item.classList.add("drag-over");
      });
      item.addEventListener("dragleave", function() { item.classList.remove("drag-over"); });
      item.addEventListener("drop", function(e) {
        e.preventDefault();
        item.classList.remove("drag-over");
        if (!pulseDragSrc || pulseDragSrc === item || item.classList.contains("pulse-add")) return;
        // Insert before or after based on position
        var rect = item.getBoundingClientRect();
        var midX = rect.left + rect.width / 2;
        if (e.clientX < midX) {
          bar.insertBefore(pulseDragSrc, item);
        } else {
          bar.insertBefore(pulseDragSrc, item.nextSibling);
        }
        savePulseOrder();
      });
    });
  }

  function savePulseOrder() {
    var order = [];
    bar.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {
      order.push(item.dataset.pulseId);
    });
    fetch("/api/pulse-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order: order })
    });
  }

  setupPulseDrag();
  window._setupPulseDrag = setupPulseDrag;
})();

function showAddPulseCard() {
  var modal = document.getElementById("pulse-add-modal");
  modal.style.display = "flex";
  document.getElementById("pulse-add-ticker").value = "";
  document.getElementById("pulse-add-label").value = "";
  document.getElementById("pulse-add-ticker").focus();
}
function hideAddPulseCard() {
  document.getElementById("pulse-add-modal").style.display = "none";
}
function addPulseCard() {
  var ticker = document.getElementById("pulse-add-ticker").value.trim().toUpperCase();
  var label = document.getElementById("pulse-add-label").value.trim();
  if (!ticker) return alert("Please enter a ticker symbol.");
  fetch("/api/pulse-cards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: ticker, label: label })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) location.reload();
    else alert(d.error || "Failed to add ticker.");
  });
}
function removePulseCard(id) {
  if (!confirm("Remove this card from the pulse bar?")) return;
  var el = document.querySelector('[data-pulse-id="' + id + '"]');
  if (el) el.style.display = "none";
  fetch("/api/pulse-cards/" + encodeURIComponent(id), { method: "DELETE" })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (d.success && el) el.remove(); });
}
function setPulseSize(size) {
  var bar = document.getElementById("pulse-bar");
  if (!bar) return;
  bar.className = "pulse-bar size-" + size;
  document.querySelectorAll(".pulse-size-btn").forEach(function(b) {
    b.classList.toggle("active", b.getAttribute("data-size") === size);
  });
  localStorage.setItem("nd-pulse-size", size);
  fetch("/api/pulse-size", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ size: size })
  }).catch(function() {});
  setTimeout(loadAllSparklines, 200);
}

function restoreAllPulseCards() {
  if (!confirm("Restore all hidden pulse cards?")) return;
  fetch("/api/pulse-cards/restore-all", { method: "POST" })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (d.success) location.reload(); });
}

/* ── Pulse Chart Modal ── */
(function() {
  var PCM_SYMBOL_MAP = {
    "gold": "GC=F", "silver": "SI=F", "au_ag": "AUAG-RATIO", "gold_oil": "GOLDOIL-RATIO",
    "dxy": "DX=F", "vix": "^VIX", "oil": "CL=F", "copper": "HG=F",
    "tnx_10y": "^TNX", "tnx_2y": "2YY=F", "btc": "BTC", "spy": "SPY"
  };
  var pcmChart = null;
  var pcmPollId = null;
  var pcmState = { symbol: "", label: "", type: "stock", period: "1d", interval: "1m", chartType: "line" };

  function pcmResolveSymbol(pulseId, pulseType) {
    if (PCM_SYMBOL_MAP[pulseId]) return { sym: PCM_SYMBOL_MAP[pulseId], type: pulseId === "btc" ? "crypto" : "stock" };
    if (pulseId.startsWith("custom-")) {
      return { sym: pulseId, type: pulseType || "stock" };
    }
    return { sym: pulseId, type: pulseType || "stock" };
  }

  function openPulseChart(pulseId, label, pulseType) {
    var resolved = pcmResolveSymbol(pulseId, pulseType);
    pcmState.symbol = resolved.sym;
    pcmState.type = resolved.type;
    pcmState.label = label;
    pcmState.period = "1d";
    pcmState.interval = "1m";
    pcmState.chartType = "line";
    document.getElementById("pcm-title").textContent = label;
    document.getElementById("pcm-price").textContent = "";
    document.getElementById("pcm-type-toggle").textContent = "Candlestick";
    var pills = document.querySelectorAll(".pcm-pill");
    pills.forEach(function(p) { p.classList.remove("active"); });
    if (pills.length > 0) pills[0].classList.add("active");
    document.getElementById("pcm-overlay").classList.add("active");
    document.body.style.overflow = "hidden";
    loadPulseChart();
    startPcmPoll();
  }
  window.openPulseChart = openPulseChart;

  function closePulseChart() {
    document.getElementById("pcm-overlay").classList.remove("active");
    document.body.style.overflow = "";
    stopPcmPoll();
    if (pcmChart) { pcmChart.destroy(); pcmChart = null; }
  }
  window.closePulseChart = closePulseChart;

  function togglePcmChartType() {
    var btn = document.getElementById("pcm-type-toggle");
    if (pcmState.chartType === "line") {
      pcmState.chartType = "candlestick";
      btn.textContent = "Line";
    } else {
      pcmState.chartType = "line";
      btn.textContent = "Candlestick";
    }
    loadPulseChart();
  }
  window.togglePcmChartType = togglePcmChartType;

  function startPcmPoll() {
    stopPcmPoll();
    if (pcmState.period === "1d") {
      pcmPollId = setInterval(function() {
        if (document.getElementById("pcm-overlay").classList.contains("active")) loadPulseChart(true);
        else stopPcmPoll();
      }, 60000);
    }
  }

  function stopPcmPoll() {
    if (pcmPollId) { clearInterval(pcmPollId); pcmPollId = null; }
  }

  function loadPulseChart(silent) {
    var spinner = document.getElementById("pcm-spinner");
    if (!silent) spinner.classList.add("show");
    var url = "/api/historical?symbol=" + encodeURIComponent(pcmState.symbol)
      + "&period=" + pcmState.period
      + "&interval=" + pcmState.interval
      + "&type=" + pcmState.type;
    fetch(url).then(function(r) { return r.json(); }).then(function(resp) {
      spinner.classList.remove("show");
      if (resp.error || !resp.data || resp.data.length === 0) {
        if (pcmChart) { pcmChart.destroy(); pcmChart = null; }
        document.getElementById("pcm-price").textContent = "(no data)";
        return;
      }
      var d = resp.data;
      var lastPrice = d[d.length - 1].c;
      var firstPrice = d[0].o || d[0].c;
      var chg = lastPrice - firstPrice;
      var chgPct = firstPrice ? ((chg / firstPrice) * 100) : 0;
      var sign = chg >= 0 ? "+" : "";
      var noDollar = ["AUAG-RATIO","GOLDOIL-RATIO","^VIX","^TNX","2YY=F","10Y2Y-SPREAD","DX=F"].indexOf(pcmState.symbol) >= 0;
      var prefix = noDollar ? "" : "$";
      document.getElementById("pcm-price").textContent = prefix + lastPrice.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})
        + "  " + sign + chg.toFixed(2) + " (" + sign + chgPct.toFixed(2) + "%)";
      document.getElementById("pcm-price").style.color = chg >= 0 ? "var(--accent-green, #22c55e)" : "var(--danger, #ef4444)";
      renderPcmChart(d);
    }).catch(function() {
      spinner.classList.remove("show");
    });
  }

  function renderPcmChart(data) {
    var canvas = document.getElementById("pcm-canvas");
    if (pcmChart) { pcmChart.destroy(); pcmChart = null; }
    var isIntraday = pcmState.interval && ["1m","2m","5m","15m","30m","60m","1h"].indexOf(pcmState.interval) >= 0;
    var timeUnit = "day";
    if (isIntraday) timeUnit = "minute";
    else if (["1wk"].indexOf(pcmState.interval) >= 0) timeUnit = "week";
    else if (["1mo"].indexOf(pcmState.interval) >= 0) timeUnit = "month";

    if (pcmState.chartType === "candlestick") {
      var candles = data.map(function(p) {
        return { x: new Date(p.date).getTime(), o: p.o, h: p.h, l: p.l, c: p.c };
      });
      var candleXScale = isIntraday
        ? { type: "timeseries", time: { unit: timeUnit }, grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 10 } }
        : { type: "time", time: { unit: timeUnit, tooltipFormat: "MMM d, yyyy" }, grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 10 } };
      pcmChart = new Chart(canvas.getContext("2d"), {
        type: "candlestick",
        data: { datasets: [{
          label: pcmState.label,
          data: candles,
          backgroundColors: { up: "rgba(34,197,94,1)", down: "rgba(239,68,68,1)", unchanged: "rgba(100,116,139,1)" },
          borderColors: { up: "rgba(34,197,94,1)", down: "rgba(239,68,68,1)", unchanged: "rgba(100,116,139,1)" }
        }] },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            x: candleXScale,
            y: { position: "right", grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)" } }
          },
          plugins: {
            legend: { display: false },
            tooltip: { yAlign: "bottom", caretPadding: 8, backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0", borderColor: "rgba(99,102,241,0.4)", borderWidth: 1 }
          }
        }
      });
    } else {
      var closes = data.map(function(p) { return p.c; });
      var first = closes[0]; var last = closes[closes.length - 1];
      var lineColor = last >= first ? "rgba(34,197,94,0.9)" : "rgba(239,68,68,0.9)";
      var fillColor = last >= first ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)";

      // Intraday: even spacing (no gaps for closed hours), show simplified tick labels
      // Daily+: proportional time axis so weekends/holidays show proper gaps
      var xScale, chartData;
      if (isIntraday) {
        // Format labels: show date at session boundaries, time otherwise
        var tickLabels = data.map(function(p, i) {
          var dt = new Date(p.date);
          var prev = i > 0 ? new Date(data[i-1].date) : null;
          if (!prev || dt.toDateString() !== prev.toDateString()) {
            return dt.toLocaleDateString(undefined, {month:"short", day:"numeric"});
          }
          return "";
        });
        xScale = { type: "category", labels: tickLabels,
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 8, autoSkip: true, maxRotation: 0 }
        };
        chartData = { labels: tickLabels, datasets: [{
          label: pcmState.label, data: closes,
          borderColor: lineColor, backgroundColor: fillColor,
          borderWidth: 2, pointRadius: 0, pointHitRadius: 8,
          fill: true, tension: 0.15
        }] };
      } else {
        var pointData = data.map(function(p) { return { x: p.date, y: p.c }; });
        xScale = { type: "time", time: { unit: timeUnit, tooltipFormat: "MMM d, yyyy" },
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 8 }
        };
        chartData = { datasets: [{
          label: pcmState.label, data: pointData,
          borderColor: lineColor, backgroundColor: fillColor,
          borderWidth: 2, pointRadius: 0, pointHitRadius: 8,
          fill: true, tension: 0.15
        }] };
      }

      pcmChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: chartData,
        options: {
          responsive: true, maintainAspectRatio: false,
          interaction: { mode: "nearest", axis: "x", intersect: false },
          scales: {
            x: xScale,
            y: { position: "right", grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)" } }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              yAlign: "bottom", caretPadding: 8,
              backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0",
              borderColor: "rgba(99,102,241,0.4)", borderWidth: 1,
              callbacks: {
                title: function(items) {
                  var idx = items[0] ? items[0].dataIndex : 0;
                  var p = data[idx];
                  if (!p) return "";
                  var dt = new Date(p.date);
                  return isIntraday ? dt.toLocaleString(undefined, {month:"short", day:"numeric", hour:"numeric", minute:"2-digit"}) : p.date;
                },
                label: function(ctx) {
                  var noDollar = ["AUAG-RATIO","GOLDOIL-RATIO","^VIX","^TNX","2YY=F","10Y2Y-SPREAD","DX=F"].indexOf(pcmState.symbol) >= 0;
                  var prefix = noDollar ? "" : "$";
                  var val = isIntraday ? ctx.raw : ctx.raw.y;
                  return pcmState.label + ": " + prefix + Number(val).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                }
              }
            },
            crosshair: false
          }
        }
      });
    }
  }

  // Timescale pill click handlers
  document.getElementById("pcm-controls").addEventListener("click", function(e) {
    var pill = e.target.closest(".pcm-pill");
    if (!pill) return;
    document.querySelectorAll(".pcm-pill").forEach(function(p) { p.classList.remove("active"); });
    pill.classList.add("active");
    pcmState.period = pill.dataset.pcmP;
    pcmState.interval = pill.dataset.pcmI;
    stopPcmPoll();
    loadPulseChart();
    startPcmPoll();
  });

  // Attach click handlers to all pulse items (guard against drag)
  var pcmDragHappened = false;
  document.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {
    item.addEventListener("dragstart", function() { pcmDragHappened = true; });
    item.addEventListener("click", function(e) {
      if (e.target.closest(".pulse-remove")) return;
      if (pcmDragHappened) { pcmDragHappened = false; return; }
      var pid = item.dataset.pulseId;
      var label = item.querySelector(".pulse-label") ? item.querySelector(".pulse-label").textContent : pid;
      var ptype = item.dataset.pulseType || "stock";
      openPulseChart(pid, label, ptype);
    });
    item.style.cursor = "pointer";
  });

  // Close on Escape key
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && document.getElementById("pcm-overlay").classList.contains("active")) {
      closePulseChart();
    }
  });
})();

/* ── Init on load ── */
buildDonut();
if (PRICE_HISTORY_DATA.length > 0) buildHistoryChart("total");
(function() {
  var savedSize = localStorage.getItem("nd-pulse-size") || "compact";
  var bar = document.getElementById("pulse-bar");
  if (bar) bar.className = "pulse-bar size-" + savedSize;
  document.querySelectorAll(".pulse-size-btn").forEach(function(b) {
    b.classList.toggle("active", b.getAttribute("data-size") === savedSize);
  });
})();
setTimeout(loadAllSparklines, 300);
var toast = document.getElementById("toast-msg");
if (toast) setTimeout(function() { toast.style.display="none"; }, 4000);

/* ── Auto-Refresh Settings ── */
function toggleAutoRefreshSettings() {
  var pop = document.getElementById("auto-refresh-popover");
  pop.style.display = pop.style.display === "none" ? "block" : "none";
}
function saveAutoRefresh() {
  var enabled = document.getElementById("auto-enabled").checked;
  var intervalSec = parseInt(document.getElementById("auto-interval").value);
  var dot = document.getElementById("auto-dot");
  var label = document.getElementById("auto-label");
  dot.className = "auto-dot " + (enabled ? "on" : "off");
  label.textContent = intervalSec >= 60 ? (intervalSec / 60) + "m" : intervalSec + "s";
  try { localStorage.setItem("nd_auto_refresh", JSON.stringify({enabled: enabled, interval: intervalSec})); } catch(e) {}
  var t = document.createElement("div");
  t.className = "toast";
  t.style.background = "rgba(52,211,153,0.15)";
  t.style.color = "var(--success)";
  t.textContent = "Auto-refresh " + (enabled ? "every " + label.textContent : "off");
  document.body.appendChild(t);
  setTimeout(function() { t.remove(); }, 2500);
  if (window._periodicPollInterval) clearInterval(window._periodicPollInterval);
  if (enabled && intervalSec >= 15) startPeriodicLivePoll(intervalSec);
}
// Close popover when clicking outside
document.addEventListener("click", function(e) {
  var pop = document.getElementById("auto-refresh-popover");
  var ind = document.getElementById("auto-refresh-indicator");
  if (pop && ind && !pop.contains(e.target) && !ind.contains(e.target)) {
    pop.style.display = "none";
  }
});

function applyLiveDataToDOM(d) {
  if (!d) return;
  window._lastLiveData = d;
  var ts = document.getElementById("last-refresh-time");
  if (ts) {
    var now = new Date();
    var opts = { year:"numeric", month:"long", day:"numeric", hour:"numeric", minute:"2-digit", hour12:true };
    ts.textContent = now.toLocaleDateString("en-US", opts);
  }
  var fxRate = (typeof BASE_CURRENCY !== "undefined" && BASE_CURRENCY !== "USD" && typeof FX_RATES !== "undefined" && FX_RATES[BASE_CURRENCY]) ? FX_RATES[BASE_CURRENCY] : 1;
  var sym = (typeof CURRENCY_SYMBOLS !== "undefined" && BASE_CURRENCY !== "USD" && CURRENCY_SYMBOLS[BASE_CURRENCY]) ? CURRENCY_SYMBOLS[BASE_CURRENCY] : "$";
  var nw = document.getElementById("net-worth-counter");
  if (nw && typeof d.total === "number") {
    nw.dataset.target = d.total;
    nw.textContent = sym + (d.total * fxRate).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    window.PORTFOLIO_TOTAL = d.total;
    PROJ_CURRENT = d.total;
    var projStartEl = document.getElementById("proj-starting");
    if (projStartEl && !_projStartingSetByUser) {
      projStartEl.value = Math.round(d.total);
      if (typeof updateProjectionChart === "function") updateProjectionChart();
    }
  }
  var heroChange = document.getElementById("hero-change-badge");
  if (heroChange && typeof d.daily_change === "number" && typeof d.daily_change_pct === "number") {
    var dc = d.daily_change;
    var sign = dc >= 0 ? "+" : "";
    heroChange.textContent = sign + "$" + Math.abs(dc).toLocaleString(undefined, {maximumFractionDigits:0}) + " (" + sign + d.daily_change_pct.toFixed(1) + "%)";
    heroChange.className = "hero-change " + (dc >= 0 ? "pos" : "neg");
  }
  var pulseMap = {
    "gold": {val: d.gold, fmt: "dollar0"},
    "silver": {val: d.silver, fmt: "dollar2"},
    "au_ag": {val: d.gold_silver_ratio, fmt: "raw2"},
    "gold_oil": {val: d.gold_oil_ratio, fmt: "raw2"},
    "btc": {val: d.btc, fmt: "dollar0"},
    "spy": {val: d.spy, fmt: "dollar2"},
    "dxy": {val: d.dxy, fmt: "nodollar2"},
    "vix": {val: d.vix, fmt: "nodollar2"},
    "oil": {val: d.oil, fmt: "dollar2"},
    "copper": {val: d.copper, fmt: "dollar2"},
    "tnx_10y": {val: d.tnx_10y, fmt: "pct"},
    "tnx_2y": {val: d.tnx_2y, fmt: "pct"}
  };
  var ratioIds = d._ratio_ids || [];
  for (var dKey in d) {
    if (dKey.indexOf("custom-") === 0 && d[dKey] != null) {
      var isRatio = ratioIds.indexOf(dKey) >= 0;
      pulseMap[dKey] = {val: d[dKey], fmt: isRatio ? "nodollar2" : "dollar2"};
    }
  }
  document.querySelectorAll("[data-pulse-price]").forEach(function(el) {
    var pid = el.getAttribute("data-pulse-price");
    var entry = pulseMap[pid];
    if (!entry || !entry.val) return;
    var v = entry.val;
    if (entry.fmt === "dollar0") el.textContent = "$" + v.toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0});
    else if (entry.fmt === "dollar2") el.textContent = "$" + v.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    else if (entry.fmt === "nodollar2") el.textContent = v.toFixed(2);
    else if (entry.fmt === "pct") el.textContent = v.toFixed(2) + "%";
    else if (entry.fmt === "raw2") el.textContent = v.toFixed(2);
    else if (entry.fmt === "raw1") el.textContent = v.toFixed(1);
  });
  // Update physical metals spot prices on holdings page
  var metalsTotalVal = 0, metalsTotalCost = 0, metalsAu = 0, metalsAg = 0;
  var spotCells = document.querySelectorAll(".metal-spot-cell");
  spotCells.forEach(function(cell) {
    var metal = cell.getAttribute("data-metal-spot");
    var newSpot = (metal === "gold") ? d.gold : d.silver;
    if (!newSpot || newSpot <= 0) return;
    cell.textContent = "$" + newSpot.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    var qty = parseFloat(cell.getAttribute("data-metal-qty")) || 0;
    var cost = parseFloat(cell.getAttribute("data-metal-cost")) || 0;
    var newVal = qty * newSpot;
    metalsTotalVal += newVal;
    metalsTotalCost += (cost > 0 ? qty * cost : 0);
    if (metal === "gold") metalsAu += qty; else metalsAg += qty;
    var valCell = cell.nextElementSibling;
    if (valCell) {
      valCell.textContent = "$" + newVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
      var glCell = valCell.nextElementSibling;
      if (glCell && cost > 0) {
        var gl = newVal - (qty * cost);
        var sign = gl >= 0 ? "" : "-";
        glCell.textContent = sign + "$" + Math.abs(gl).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
        glCell.style.color = gl >= 0 ? "var(--success)" : "var(--danger)";
      }
    }
  });
  if (spotCells.length > 0) {
    var mhAu = document.getElementById("metals-header-au");
    var mhAg = document.getElementById("metals-header-ag");
    if (mhAu) mhAu.textContent = metalsAu.toFixed(1);
    if (mhAg) mhAg.textContent = metalsAg.toFixed(0);
    var mhTotal = document.getElementById("metals-header-total");
    if (mhTotal) mhTotal.textContent = "$" + metalsTotalVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    var mhGl = document.getElementById("metals-header-gl");
    if (mhGl) {
      var gl = metalsTotalVal - metalsTotalCost;
      var glSign = gl >= 0 ? "" : "-";
      mhGl.textContent = glSign + "$" + Math.abs(gl).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
      mhGl.style.color = gl >= 0 ? "var(--success)" : "var(--danger)";
    }
  }
  // Update crypto holdings prices on holdings page
  if (d.crypto_prices) {
    var cRows = document.querySelectorAll(".crypto-row");
    var cryptoTotal = 0;
    cRows.forEach(function(row) {
      var sym = row.getAttribute("data-crypto-sym");
      var qty = parseFloat(row.getAttribute("data-crypto-qty")) || 0;
      var price = d.crypto_prices[sym];
      if (!price || price <= 0) return;
      var val = qty * price;
      cryptoTotal += val;
      var priceCell = row.querySelector(".crypto-price-cell");
      if (priceCell) priceCell.textContent = "$" + price.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
      var valCell = row.querySelector(".crypto-val-cell");
      if (valCell) valCell.textContent = val >= 0.01 ? ("$" + val.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})) : "<$0.01";
    });
    if (cryptoTotal > 0) {
      cRows.forEach(function(row) {
        var sym = row.getAttribute("data-crypto-sym");
        var qty = parseFloat(row.getAttribute("data-crypto-qty")) || 0;
        var price = d.crypto_prices[sym] || 0;
        var val = qty * price;
        var pct = (val / cryptoTotal * 100);
        var pctCell = row.querySelector(".crypto-pct-cell");
        if (pctCell) pctCell.textContent = pct.toFixed(1) + "%";
        var bar = row.querySelector(".crypto-bar-fill");
        if (bar) bar.style.width = Math.min(100, pct).toFixed(1) + "%";
      });
      var ctv = document.getElementById("crypto-total-val");
      if (ctv) ctv.textContent = "$" + cryptoTotal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
      var cht = document.getElementById("crypto-header-total");
      if (cht) cht.textContent = "$" + cryptoTotal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    }
  }
}
function startPeriodicLivePoll(intervalSec) {
  if (window._periodicPollInterval) clearInterval(window._periodicPollInterval);
  var ms = Math.max(15, intervalSec) * 1000;
  window._periodicPollInterval = setInterval(function() {
    fetch("/api/live-data").then(function(r) { return r.json(); }).then(function(d) {
      applyLiveDataToDOM(d);
      _flashUpdatedPulseCards();
    }).catch(function() {});
  }, ms);
}
window._prevPulseValues = window._prevPulseValues || {};
function _flashUpdatedPulseCards() {
  document.querySelectorAll("[data-pulse-price]").forEach(function(el) {
    var pid = el.getAttribute("data-pulse-price");
    var cur = el.textContent;
    if (window._prevPulseValues[pid] && window._prevPulseValues[pid] !== cur) {
      el.classList.remove("price-flash");
      void el.offsetWidth;
      el.classList.add("price-flash");
    }
    window._prevPulseValues[pid] = cur;
  });
  var nw = document.getElementById("net-worth-counter");
  if (nw) {
    var cur = nw.textContent;
    if (window._prevPulseValues._nw && window._prevPulseValues._nw !== cur) {
      nw.classList.remove("price-flash");
      void nw.offsetWidth;
      nw.classList.add("price-flash");
    }
    window._prevPulseValues._nw = cur;
  }
}

/* ── Phase 1: Theme Toggle ── */
function toggleTheme() {
  document.documentElement.classList.toggle("light");
  var isLight = document.documentElement.classList.contains("light");
  localStorage.setItem("wos-theme", isLight ? "light" : "dark");
  var icon = document.getElementById("theme-icon");
  if (icon) icon.innerHTML = isLight
    ? '<path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z"/>'
    : '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
  // Rebuild charts for theme
  if (window.historyChart) buildHistoryChart("total");
}
if (localStorage.getItem("wos-theme") === "light") { document.documentElement.classList.add("light"); }

/* ── Phase 1: Command Palette (Ctrl+K) ── */
var cmdItems = [
  { label:"Summary", tab:"summary", keys:"" },
  { label:"Balances", tab:"balances", keys:"" },
  { label:"Budget", tab:"budget", keys:"" },
  { label:"Holdings", tab:"holdings", keys:"" },
  { label:"Import CSV", tab:"import", keys:"" },
  { label:"Technical Analysis", tab:"technical", keys:"" },
  { label:"Economics", tab:"economics", keys:"" },
  { label:"Refresh Prices", action:"refresh", keys:"" },
];
// Add holdings as searchable items
(window.HOLDINGS_TICKERS || []).forEach(function(t) {
  if (t) cmdItems.push({ label:t + " (holding)", tab:"holdings", keys:t });
});
var cmdActive = 0;
function openCmd() {
  var o = document.getElementById("cmd-overlay");
  o.classList.add("open");
  var inp = document.getElementById("cmd-input");
  inp.value = ""; inp.focus();
  filterCmd("");
}
function closeCmd() { document.getElementById("cmd-overlay").classList.remove("open"); }
function filterCmd(q) {
  q = q.toLowerCase();
  var results = cmdItems.filter(function(i) { return !q || i.label.toLowerCase().includes(q) || i.keys.toLowerCase().includes(q); });
  var container = document.getElementById("cmd-results");
  cmdActive = 0;
  container.innerHTML = results.slice(0,8).map(function(r,i) {
    return '<div class="cmd-result'+(i===0?' active':'')+'" data-idx="'+i+'" onclick="execCmd('+i+')">'+r.label+'</div>';
  }).join("");
  window._cmdFiltered = results.slice(0,8);
}
function execCmd(i) {
  var item = window._cmdFiltered[i];
  if (!item) return;
  closeCmd();
  if (item.action === "refresh") { document.querySelector(".refresh-btn").closest("form").submit(); return; }
  if (item.tab) showTab(item.tab);
}
document.getElementById("cmd-input").addEventListener("input", function() { filterCmd(this.value); });
document.getElementById("cmd-input").addEventListener("keydown", function(e) {
  var items = document.querySelectorAll(".cmd-result");
  if (e.key === "ArrowDown") { e.preventDefault(); cmdActive = Math.min(cmdActive+1, items.length-1); items.forEach(function(el,i){ el.classList.toggle("active",i===cmdActive); }); }
  else if (e.key === "ArrowUp") { e.preventDefault(); cmdActive = Math.max(cmdActive-1, 0); items.forEach(function(el,i){ el.classList.toggle("active",i===cmdActive); }); }
  else if (e.key === "Enter") { e.preventDefault(); execCmd(cmdActive); }
  else if (e.key === "Escape") { closeCmd(); }
});
document.getElementById("cmd-overlay").addEventListener("click", function(e) { if(e.target===this) closeCmd(); });
document.addEventListener("keydown", function(e) {
  if ((e.ctrlKey||e.metaKey) && e.key==="k") { e.preventDefault(); openCmd(); }
  else if (e.key==="Escape") closeCmd();
});

/* ── Phase 1: Keyboard Shortcuts ── */
document.addEventListener("keydown", function(e) {
  if (document.getElementById("cmd-overlay").classList.contains("open")) return;
  if (e.target.tagName==="INPUT"||e.target.tagName==="SELECT"||e.target.tagName==="TEXTAREA") return;
  if (e.key==="1") showTab("summary");
  else if (e.key==="2") showTab("balances");
  else if (e.key==="3") showTab("budget");
  else if (e.key==="4") showTab("holdings");
  else if (e.key==="5") showTab("import");
  else if (e.key==="6") showTab("history");
  else if (e.key==="r"&&!e.ctrlKey) { document.querySelector(".refresh-btn").closest("form").submit(); }
});

/* ── Phase 2: Transaction Tracking ── */
var TRANSACTIONS = [];
var BUDGET_LIMITS = {};
var BUDGET_CATS = [];
/* ── Debt Tracker ── */
function addDebtRow() {
  var tbody = document.getElementById("debt-tbody");
  var idx = tbody.querySelectorAll("tr").length;
  var row = document.createElement("tr");
  row.innerHTML = '<td><input type="text" name="debt_name_' + idx + '" value="" placeholder="e.g. Student Loan" style="width:100%;border:none;background:transparent;color:var(--text-primary);font-size:0.85rem;"></td>'
    + '<td><input type="text" name="debt_bal_' + idx + '" value="0.00" class="num"></td>'
    + '<td><input type="text" name="debt_pmt_' + idx + '" value="0.00" class="num"></td>'
    + '<td class="mono hint" style="text-align:center;">\u2014</td>'
    + '<td><button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;color:var(--danger);">x</button></td>';
  tbody.appendChild(row);
  row.querySelector("button").addEventListener("click", function() { this.closest("tr").remove(); });
  row.querySelector("input").focus();
}
function removeDebt(idx) {
  // Submit form with that row removed — we mark it for deletion
  var row = document.getElementById("debt-tbody").querySelectorAll("tr")[idx];
  if (row) row.remove();
  // Re-index remaining rows
  var rows = document.getElementById("debt-tbody").querySelectorAll("tr");
  rows.forEach(function(r, i) {
    var inputs = r.querySelectorAll("input");
    if (inputs[0]) inputs[0].name = "debt_name_" + i;
    if (inputs[1]) inputs[1].name = "debt_bal_" + i;
    if (inputs[2]) inputs[2].name = "debt_pmt_" + i;
  });
}

function addTransaction() { document.getElementById("txn-form").style.display = document.getElementById("txn-form").style.display==="none"?"block":"none"; }
function renderTxns() {
  var body = document.getElementById("txn-body");
  if (!body) return;
  body.innerHTML = TRANSACTIONS.slice().reverse().slice(0,50).map(function(t) {
    return "<tr><td class='mono'>"+t.date+"</td><td>"+t.category+"</td><td class='mono'>$"+parseFloat(t.amount).toFixed(2)+"</td><td class='hint'>"+( t.note||"")+"</td></tr>";
  }).join("");
}
function saveTxn() {
  var txn = {
    date: document.getElementById("txn-date").value,
    category: document.getElementById("txn-cat").value,
    amount: parseFloat(document.getElementById("txn-amount").value)||0,
    note: document.getElementById("txn-note").value
  };
  if (!txn.amount) return;
  fetch("/api/add-transaction", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(txn) })
    .then(function(r){ return r.json(); })
    .then(function(d) {
      if(d.success) {
        TRANSACTIONS.push(txn);
        renderTxns();
        document.getElementById("txn-amount").value="";
        document.getElementById("txn-note").value="";
        buildSpendingChart();
        renderSpendingBreakdown();
      }
    });
}
/* ── Spending vs Budget Breakdown ── */
function renderSpendingBreakdown() {
  var container = document.getElementById("spending-breakdown");
  var monthSelect = document.getElementById("spend-month-select");
  if (!container) return;

  // Build month options from transactions
  var monthSet = {};
  TRANSACTIONS.forEach(function(t) {
    if (t.date) monthSet[t.date.substring(0,7)] = true;
  });
  var months = Object.keys(monthSet).sort().reverse();
  if (months.length === 0) {
    container.innerHTML = '<div class="spend-empty">No transactions logged yet. Import statements or add transactions to see spending breakdown.</div>';
    return;
  }

  // Populate month selector if empty
  if (monthSelect && monthSelect.options.length === 0) {
    months.forEach(function(m) {
      var opt = document.createElement("option");
      var d = new Date(m + "-15");
      opt.value = m;
      opt.textContent = d.toLocaleDateString("en-US", { year:"numeric", month:"long" });
      monthSelect.appendChild(opt);
    });
  }

  var selectedMonth = monthSelect ? monthSelect.value : months[0];
  if (!selectedMonth) selectedMonth = months[0];

  // Filter transactions for selected month
  var monthTxns = TRANSACTIONS.filter(function(t) {
    return t.date && t.date.substring(0,7) === selectedMonth;
  });

  // Separate income (negative amounts) from expenses (positive amounts)
  var byExpenseCat = {};
  var incomeTxns = [];
  var totalExpenses = 0;
  var totalIncome = 0;
  monthTxns.forEach(function(t) {
    var amt = parseFloat(t.amount) || 0;
    var cat = t.category || "Other";
    var isIncome = amt < 0 || t.type === "income" || cat === "Income";
    if (isIncome) {
      incomeTxns.push(t);
      totalIncome += Math.abs(amt);
    } else {
      if (!byExpenseCat[cat]) byExpenseCat[cat] = { total: 0, txns: [] };
      byExpenseCat[cat].total += amt;
      byExpenseCat[cat].txns.push(t);
      totalExpenses += amt;
    }
  });

  // Sort expense categories: budgeted ones first (by spent desc), then Other at end
  var cats = Object.keys(byExpenseCat).sort(function(a, b) {
    if (a === "Other") return 1;
    if (b === "Other") return -1;
    return byExpenseCat[b].total - byExpenseCat[a].total;
  });

  var totalBudget = 0;
  Object.values(BUDGET_LIMITS).forEach(function(v) { totalBudget += v; });

  var html = '';

  // ── Income section (if any) ──
  if (incomeTxns.length > 0) {
    var incomeSorted = incomeTxns.slice().sort(function(a,b) { return b.date.localeCompare(a.date); });
    html += '<div class="spend-row">';
    html += '  <div class="spend-header" style="background:rgba(52,211,153,0.04);">';
    html += '    <span class="spend-chevron">&#9654;</span>';
    html += '    <span class="spend-cat" style="color:var(--success);">&#9660; Income / Credits</span>';
    html += '    <div class="spend-amounts">';
    html += '      <span style="color:var(--success);font-family:var(--mono);font-size:0.82rem;">+$' + totalIncome.toLocaleString(undefined, {minimumFractionDigits:2}) + '</span>';
    html += '      <span class="spend-budget">' + incomeTxns.length + ' transaction' + (incomeTxns.length > 1 ? 's' : '') + '</span>';
    html += '    </div>';
    html += '    <div style="flex:0 0 120px;"></div>';
    html += '  </div>';
    html += '  <div class="spend-details">';
    html += '    <table><thead><tr><th>Date</th><th>Description / Note</th><th style="text-align:right">Amount</th></tr></thead><tbody>';
    incomeSorted.forEach(function(t) {
      var desc = t.description || t.note || "—";
      var amt = Math.abs(parseFloat(t.amount));
      html += '<tr><td class="mono">' + t.date + '</td><td>' + desc + '</td><td class="mono" style="text-align:right;color:var(--success);">+$' + amt.toFixed(2) + '</td></tr>';
    });
    html += '    </tbody></table>';
    html += '  </div>';
    html += '</div>';
    html += '<div style="height:6px;border-bottom:2px solid var(--border-subtle);margin-bottom:2px;"></div>';
  }

  // ── Expense categories ──
  cats.forEach(function(cat) {
    var spent = byExpenseCat[cat].total;
    var limit = BUDGET_LIMITS[cat] || 0;
    var pct = limit > 0 ? Math.min((spent / limit) * 100, 100) : (spent > 0 ? 100 : 0);
    var barClass = pct >= 100 ? "over" : pct >= 75 ? "near" : "under";
    var overAmt = limit > 0 && spent > limit ? spent - limit : 0;

    var budgetText = limit > 0
      ? "/ $" + limit.toLocaleString(undefined, {minimumFractionDigits:0})
      : '<span style="color:var(--text-muted);font-style:italic;">no budget</span>';

    var overTag = overAmt > 0
      ? ' <span style="color:var(--danger);font-size:0.72rem;font-weight:600;">+$' + overAmt.toFixed(0) + ' over</span>'
      : '';

    // Sort transactions by date descending
    var txns = byExpenseCat[cat].txns.slice().sort(function(a,b) { return b.date.localeCompare(a.date); });

    html += '<div class="spend-row">';
    html += '  <div class="spend-header">';
    html += '    <span class="spend-chevron">&#9654;</span>';
    html += '    <span class="spend-cat">' + cat + '</span>';
    html += '    <div class="spend-amounts">';
    html += '      <span class="spend-spent">$' + spent.toLocaleString(undefined, {minimumFractionDigits:2}) + '</span>';
    html += '      <span class="spend-budget">' + budgetText + overTag + '</span>';
    html += '    </div>';
    html += '    <div class="spend-bar-wrap"><div class="spend-bar ' + barClass + '" style="width:' + pct + '%"></div></div>';
    html += '  </div>';
    html += '  <div class="spend-details">';
    html += '    <table><thead><tr><th>Date</th><th>Description / Note</th><th style="text-align:right">Amount</th></tr></thead><tbody>';
    txns.forEach(function(t) {
      var desc = t.description || t.note || "—";
      html += '<tr><td class="mono">' + t.date + '</td><td>' + desc + '</td><td class="mono" style="text-align:right">$' + parseFloat(t.amount).toFixed(2) + '</td></tr>';
    });
    html += '    </tbody></table>';
    html += '  </div>';
    html += '</div>';
  });

  // Also show budgeted categories with $0 spent
  Object.keys(BUDGET_LIMITS).forEach(function(cat) {
    if (!byExpenseCat[cat] && BUDGET_LIMITS[cat] > 0) {
      html += '<div class="spend-row">';
      html += '  <div class="spend-header">';
      html += '    <span class="spend-chevron" style="visibility:hidden">&#9654;</span>';
      html += '    <span class="spend-cat" style="color:var(--text-muted)">' + cat + '</span>';
      html += '    <div class="spend-amounts">';
      html += '      <span class="spend-spent" style="color:var(--text-muted)">$0.00</span>';
      html += '      <span class="spend-budget">/ $' + BUDGET_LIMITS[cat].toLocaleString(undefined, {minimumFractionDigits:0}) + '</span>';
      html += '    </div>';
      html += '    <div class="spend-bar-wrap"><div class="spend-bar under" style="width:0%"></div></div>';
      html += '  </div>';
      html += '</div>';
    }
  });

  // ── Summary: Income / Expenses / Net Cash Flow ──
  html += '<div class="spend-total" style="flex-direction:column;gap:4px;">';
  if (totalIncome > 0) {
    html += '<div style="display:flex;justify-content:space-between;width:100%;color:var(--success);">';
    html += '  <span>Income / Credits</span>';
    html += '  <span class="mono">+$' + totalIncome.toLocaleString(undefined, {minimumFractionDigits:2}) + '</span>';
    html += '</div>';
  }
  html += '<div style="display:flex;justify-content:space-between;width:100%;">';
  html += '  <span>Total Expenses</span>';
  html += '  <span class="mono">$' + totalExpenses.toLocaleString(undefined, {minimumFractionDigits:2}) + (totalBudget > 0 ? ' / $' + totalBudget.toLocaleString(undefined, {minimumFractionDigits:0}) : '') + '</span>';
  html += '</div>';
  if (totalIncome > 0) {
    var netCashFlow = totalIncome - totalExpenses;
    var netColor = netCashFlow >= 0 ? "var(--success)" : "var(--danger)";
    var netSign = netCashFlow >= 0 ? "+" : "-";
    html += '<div style="display:flex;justify-content:space-between;width:100%;border-top:1px solid var(--border-subtle);padding-top:6px;margin-top:2px;">';
    html += '  <span style="font-weight:700;">Net Cash Flow</span>';
    html += '  <span class="mono" style="color:' + netColor + ';font-weight:700;">' + netSign + '$' + Math.abs(netCashFlow).toLocaleString(undefined, {minimumFractionDigits:2}) + '</span>';
    html += '</div>';
  }
  html += '</div>';

  container.innerHTML = html;
  // Event delegation for expand/collapse
  container.querySelectorAll(".spend-header").forEach(function(header) {
    header.addEventListener("click", function() {
      var row = this.closest(".spend-row");
      if (row) row.classList.toggle("open");
    });
  });
}
/* ── Statement Import ── */
var stmtData = null;
function previewStatement() {
  var fileInput = document.getElementById("stmt-file");
  if (!fileInput.files.length) { alert("Please select a CSV or PDF file first."); return; }
  var files = fileInput.files;
  var allTransactions = [];
  var totalAmount = 0;
  var byCat = {};
  var processed = 0;
  var errors = [];

  document.getElementById("stmt-preview").style.display = "none";
  document.getElementById("stmt-summary").textContent = "Processing " + files.length + " file(s)...";

  function processNext(idx) {
    if (idx >= files.length) {
      // All files processed — merge results
      if (errors.length > 0 && allTransactions.length === 0) {
        alert("Errors:\\n" + errors.join("\\n"));
        return;
      }
      stmtData = {
        transactions: allTransactions,
        total_count: allTransactions.length,
        total_amount: Math.round(totalAmount * 100) / 100,
        by_category: byCat
      };
      var errNote = errors.length > 0 ? " (" + errors.length + " file(s) had issues)" : "";
      var incomeAmt = 0, expenseAmt = 0;
      allTransactions.forEach(function(t) { if (t.amount < 0) incomeAmt += Math.abs(t.amount); else expenseAmt += t.amount; });
      var summaryParts = allTransactions.length + " transactions from " + files.length + " file(s)";
      if (incomeAmt > 0) summaryParts += " | Expenses: $" + expenseAmt.toLocaleString(undefined, {minimumFractionDigits:2}) + " | Income: +$" + incomeAmt.toLocaleString(undefined, {minimumFractionDigits:2});
      else summaryParts += ", $" + expenseAmt.toLocaleString(undefined, {minimumFractionDigits:2}) + " total";
      document.getElementById("stmt-summary").textContent = summaryParts + errNote;
      var catParts = [];
      for (var cat in byCat) { catParts.push(cat + ": $" + byCat[cat].toFixed(0)); }
      document.getElementById("stmt-cat-summary").textContent = catParts.join(" | ");
      var cats = BUDGET_CATS.slice();
      // Add "Income" to category list if not already present
      if (cats.indexOf("Income") === -1) cats = ["Income"].concat(cats);
      var rows = allTransactions.map(function(t, i) {
        // If detected category doesn't exist in budget, map to "Other" (unless it's Income)
        var effectiveCat = t.category;
        if (cats.indexOf(effectiveCat) === -1) effectiveCat = "Other";
        var opts = cats.map(function(c) { return "<option" + (c === effectiveCat ? " selected" : "") + ">" + c + "</option>"; }).join("");
        var isIncome = t.amount < 0 || t.type === "income" || effectiveCat === "Income";
        var amtDisplay = isIncome ? '<span style="color:var(--success);">+$' + Math.abs(t.amount).toFixed(2) + '</span>' : '$' + t.amount.toFixed(2);
        return "<tr" + (isIncome ? " style='background:rgba(52,211,153,0.03);'" : "") + "><td class='mono'>" + t.date + "</td><td style='max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>" + t.description + "</td><td class='mono'>" + amtDisplay + "</td><td><select class='stmt-cat' data-idx='" + i + "' style='padding:4px 6px;font-size:0.78rem;'>" + opts + "</select></td></tr>";
      }).join("");
      document.getElementById("stmt-rows").innerHTML = rows;
      document.getElementById("stmt-preview").style.display = "block";
      return;
    }

    var formData = new FormData();
    formData.append("statement_file", files[idx]);
    fetch("/api/statement-preview", { method:"POST", body:formData })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.error) {
          errors.push(files[idx].name + ": " + data.error);
        } else {
          // Merge transactions
          allTransactions = allTransactions.concat(data.transactions || []);
          totalAmount += data.total_amount || 0;
          for (var cat in (data.by_category || {})) {
            byCat[cat] = (byCat[cat] || 0) + data.by_category[cat];
          }
        }
        processNext(idx + 1);
      })
      .catch(function(e) {
        errors.push(files[idx].name + ": " + e.message);
        processNext(idx + 1);
      });
  }
  processNext(0);
}
function undoLastImport() {
  if (!confirm("Undo the last statement import? This will remove all transactions added in the most recent import.")) return;
  fetch("/api/undo-import", { method:"POST" })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.success) {
        alert(d.message);
        location.reload();
      } else {
        alert(d.error || "Nothing to undo.");
      }
    }).catch(function(e) { alert("Error: " + e.message); });
}
function clearAllTransactions() {
  var count = TRANSACTIONS.length;
  if (!count) { alert("No transactions to clear."); return; }
  if (!confirm("Delete ALL " + count + " transactions and reset spending history? This cannot be undone.")) return;
  fetch("/api/clear-transactions", { method:"POST" })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.success) {
        alert(d.message);
        location.reload();
      } else {
        alert(d.error || "Failed to clear.");
      }
    }).catch(function(e) { alert("Error: " + e.message); });
}
function importStatement() {
  if (!stmtData || !stmtData.transactions.length) return;
  // Collect category overrides
  var overrides = {};
  document.querySelectorAll(".stmt-cat").forEach(function(sel) {
    var idx = parseInt(sel.dataset.idx);
    var txn = stmtData.transactions[idx];
    if (txn && sel.value !== txn.category) {
      overrides[txn.description] = sel.value;
    }
  });
  // Use fetch API to submit all transactions at once
  fetch("/import/statement-batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transactions: stmtData.transactions, category_overrides: overrides })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      location.href = "/?saved=" + encodeURIComponent(d.message) + "&tab=import" + (d.detect_recurring ? "&detect_recurring=1" : "");
    } else {
      alert(d.error || "Import failed");
    }
  }).catch(function(e) { alert("Import error: " + e.message); });
}

/* ── Phase 2: Spending Trends Chart ── */
function buildSpendingChart() {
  var ctx = document.getElementById("spending-chart");
  if (!ctx || typeof Chart==="undefined") return;
  // Aggregate transactions by month/category
  var months = {};
  TRANSACTIONS.forEach(function(t) {
    var m = t.date ? t.date.substring(0,7) : "unknown";
    if (!months[m]) months[m] = {};
    months[m][t.category] = (months[m][t.category]||0) + (parseFloat(t.amount)||0);
  });
  var labels = Object.keys(months).sort().slice(-6);
  var cats = BUDGET_CATS.length ? BUDGET_CATS : [];
  var colors = ["#d4a017","#f5c842","#34d399","#818cf8","#f87171","#06b6d4","#a78bfa","#fb923c"];
  var datasets = cats.map(function(cat,i) {
    return { label:cat, data:labels.map(function(m){ return months[m]&&months[m][cat]?months[m][cat]:0; }), backgroundColor:colors[i%colors.length] };
  });
  if (window._spendChart) window._spendChart.destroy();
  window._spendChart = new Chart(ctx, {
    type:"bar",
    data:{ labels:labels, datasets:datasets },
    options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{ labels:{ color:"#94a3b8", font:{size:10} } } },
      scales:{ x:{ stacked:true, ticks:{color:"#64748b",font:{size:10}}, grid:{display:false} }, y:{ stacked:true, ticks:{color:"#64748b",font:{size:10}}, grid:{color:"rgba(255,255,255,0.03)"} } }
    }
  });
}
/* ── Phase 2: Benchmark Overlay ── */
function addBenchmark() {
  if (!window.historyChart || PRICE_HISTORY_DATA.length < 2) return;
  fetch("/api/historical?symbol=SPY&period=1y")
    .then(function(r){ return r.json(); })
    .then(function(json) {
      if (!json.data || json.data.length < 2) return;
      // Normalize to percentage change from first value
      var spyFirst = json.data[0].c;
      var spyPct = json.data.map(function(d) { return ((d.c / spyFirst) - 1) * 100; });
      var spyLabels = json.data.map(function(d) { return d.date; });
      if (window.historyChart.data.datasets.length < 2) {
        var spyPoints = json.data.map(function(d, i) { return { x: d.date, y: spyPct[i] }; }).slice(-PRICE_HISTORY_DATA.length);
        window.historyChart.data.datasets.push({
          label: "SPY Benchmark", data: spyPoints,
          borderColor: "#64748b", borderDash:[5,3], borderWidth:1.5, fill:false, tension:0.3, pointRadius:0
        });
        window.historyChart.update();
      }
    }).catch(function(){});
}

/* ── Phase 3: Projected Growth Chart (interactive) ── */
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

function buildProjectionChart() {
  updateProjectionChart();
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

/* FRED_JS_START */
/* ── FRED Economics ── */
var fredTooltipOpts = { yAlign: "bottom", caretPadding: 8, backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0", borderColor: "rgba(99,102,241,0.4)", borderWidth: 1 };
var fredCharts = {};
function fredSeries(data, id) { var e = data[id]; return (e && e.data) ? e.data : []; }
function fredLatest(arr) { for (var i = (arr && arr.length) ? arr.length - 1 : -1; i >= 0; i--) if (arr[i].value != null) return arr[i].value; return null; }
function fredLineChart(canvasId, points, label, yFmt) {
  var ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === "undefined") return;
  var labels = (points || []).map(function(p) { return p.date; });
  var values = (points || []).map(function(p) { return p.value; });
  if (fredCharts[canvasId]) {
    fredCharts[canvasId].data.labels = labels;
    fredCharts[canvasId].data.datasets[0].data = values;
    fredCharts[canvasId].update();
    return;
  }
  var yCallback = yFmt === "billions" ? function(v) { return (v/1e3).toFixed(1) + "T"; } : yFmt === "pct" ? function(v) { return v != null ? Number(v).toFixed(1) + "%" : ""; } : function(v) { return v != null ? Number(v).toLocaleString() : ""; };
  fredCharts[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels: labels, datasets: [{ label: label, data: values, borderColor: "rgba(212,160,23,0.9)", backgroundColor: "rgba(212,160,23,0.1)", fill: true, tension: 0.2, pointRadius: 0, pointHitRadius: 20 }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { display: false }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 8 }, grid: { display: false } }, y: { ticks: { color: "#64748b", callback: yCallback }, grid: { color: "rgba(255,255,255,0.03)" } } } }
  });
}
function fredBarChart(canvasId, points, label, colorFn) {
  var ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === "undefined") return;
  var labels = (points || []).map(function(p) { return p.date; });
  var values = (points || []).map(function(p) { return p.value; });
  var colors = (colorFn && values) ? values.map(colorFn) : "rgba(212,160,23,0.6)";
  if (fredCharts[canvasId]) {
    fredCharts[canvasId].data.labels = labels;
    fredCharts[canvasId].data.datasets[0].data = values;
    fredCharts[canvasId].data.datasets[0].backgroundColor = colors;
    fredCharts[canvasId].update();
    return;
  }
  fredCharts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels: labels, datasets: [{ label: label, data: values, backgroundColor: colors }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { display: false }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 8 }, grid: { display: false } }, y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.03)" } } } }
  });
}
function renderFredDebt(data) {
  var debt = fredSeries(data, "GFDEBTN");
  var debtGdp = fredSeries(data, "GFDEGDQ188S");
  var deficit = fredSeries(data, "FYFSD");
  var interest = fredSeries(data, "A091RC1Q027SBEA");
  var gdp = fredSeries(data, "GDP");
  var receipts = fredSeries(data, "W006RC1Q027SBEA");
  var outlays = fredSeries(data, "W068RCQ027SBEA");
  var deficitPct = fredSeries(data, "FYFSGDA188S");
  var spendingPct = fredSeries(data, "FYONGDA188S");
  var interestPct = fredSeries(data, "FYOIGDA188S");
  var latestDebt = fredLatest(debt);
  var latestGdp = fredLatest(gdp);
  var latestDeficit = fredLatest(deficit);
  var latestInterest = fredLatest(interest);
  var latestDeficitPct = fredLatest(deficitPct);
  var latestSpendingPct = fredLatest(spendingPct);
  var latestInterestPct = fredLatest(interestPct);
  var debtPct = (latestGdp && latestDebt) ? (latestDebt / (latestGdp * 1e3) * 100).toFixed(1) : null;
  var defPctStr = latestDeficitPct != null ? (Math.abs(latestDeficitPct).toFixed(1) + '% of GDP') : null;
  var el = document.getElementById("fred-debt-stats");
  var subStyle = 'style="font-size:0.7rem;color:var(--text-muted);font-family:var(--mono);margin-top:2px;"';
  if (el) el.innerHTML =
    (latestDebt != null ? '<div class="pulse-item"><span class="pulse-label">Total Debt</span><span class="pulse-price">$' + (latestDebt/1e6).toFixed(2) + 'T</span>' + (debtPct ? '<span ' + subStyle + '>' + debtPct + '% of GDP</span>' : '') + '</div>' : '')
    + (fredLatest(gdp) != null ? '<div class="pulse-item"><span class="pulse-label">GDP</span><span class="pulse-price">$' + (fredLatest(gdp)/1e3).toFixed(2) + 'T</span></div>' : '')
    + (latestSpendingPct != null && latestDeficitPct != null ? (function() { var revPct = latestSpendingPct + latestDeficitPct; var revDollar = latestGdp ? (latestGdp * 1e3 * revPct / 100 / 1e6).toFixed(2) : '?'; return '<div class="pulse-item"><span class="pulse-label">Gov Revenue</span><span class="pulse-price">$' + revDollar + 'T</span><span ' + subStyle + '>' + revPct.toFixed(1) + '% of GDP</span></div>'; })() : '')
    + (latestSpendingPct != null ? '<div class="pulse-item"><span class="pulse-label">Gov Spending</span><span class="pulse-price">$' + (latestGdp ? (latestGdp * 1e3 * latestSpendingPct / 100 / 1e6).toFixed(2) : '?') + 'T</span><span ' + subStyle + '>' + latestSpendingPct.toFixed(1) + '% of GDP</span></div>' : '')
    + (latestDeficit != null ? '<div class="pulse-item"><span class="pulse-label">Annual Deficit</span><span class="pulse-price">$' + (latestDeficit/1e6).toFixed(2) + 'T</span>' + (defPctStr ? '<span ' + subStyle + '>' + defPctStr + '</span>' : '') + '</div>' : '')
    + (latestInterest != null ? (function() { var intSpendPct = (latestSpendingPct != null && latestGdp && latestInterest) ? ((latestInterest * 4) / (latestGdp * 1e3 * latestSpendingPct / 100) * 100).toFixed(1) : null; return '<div class="pulse-item"><span class="pulse-label">Interest (Q)</span><span class="pulse-price">$' + (latestInterest/1e3).toFixed(2) + 'T</span>' + (intSpendPct ? '<span ' + subStyle + '>' + intSpendPct + '% of spending</span>' : '') + '</div>'; })() : '');
  fredLineChart("fred-chart-debt", debt, "Debt", "billions");
  fredLineChart("fred-chart-debt-gdp", debtGdp, "Debt/GDP %", "pct");
  fredBarChart("fred-chart-deficit", deficit, "Deficit", function(v) { return v >= 0 ? "rgba(52,211,153,0.6)" : "rgba(248,113,113,0.6)"; });
  fredLineChart("fred-chart-interest", interest, "Interest", "billions");
  fredLineChart("fred-chart-deficit-pct", deficitPct, "Deficit/Surplus % GDP", "pct");
  fredLineChart("fred-chart-spending-pct", spendingPct, "Spending % GDP", "pct");
  fredLineChart("fred-chart-interest-pct", interestPct, "Interest % GDP", "pct");
  if (receipts.length && outlays.length) {
    fredCharts["fred-chart-revenue-spending"] && fredCharts["fred-chart-revenue-spending"].destroy();
    var allDates = {};
    receipts.forEach(function(p) { allDates[p.date] = true; });
    outlays.forEach(function(p) { allDates[p.date] = true; });
    var dates = Object.keys(allDates).sort();
    var rVals = dates.map(function(d) { var p = receipts.find(function(x) { return x.date === d; }); return p ? p.value : null; });
    var oVals = dates.map(function(d) { var p = outlays.find(function(x) { return x.date === d; }); return p ? p.value : null; });
    var ctx = document.getElementById("fred-chart-revenue-spending");
    if (ctx) { fredCharts["fred-chart-revenue-spending"] = new Chart(ctx, { type: "line", data: { labels: dates, datasets: [{ label: "Receipts", data: rVals, borderColor: "rgba(52,211,153,0.9)", fill: false, tension: 0.2, pointRadius: 0 }, { label: "Outlays", data: oVals, borderColor: "rgba(248,113,113,0.9)", fill: false, tension: 0.2, pointRadius: 0 }] }, options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: "#94a3b8" } }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 8 }, grid: { display: false } }, y: { ticks: { color: "#64748b", callback: function(v) { return v != null ? v.toFixed(0) + " B" : ""; } }, grid: { color: "rgba(255,255,255,0.03)" } } } } }); }
  }
}
function renderFredInflation(data) {
  var cpi = fredSeries(data, "CPIAUCSL");
  var core = fredSeries(data, "CPILFESL");
  var pce = fredSeries(data, "PCEPI");
  var el = document.getElementById("fred-inflation-stats");
  if (el) el.innerHTML = (fredLatest(cpi) != null ? '<div class="pulse-item"><span class="pulse-label">CPI-U</span><span class="pulse-price">' + fredLatest(cpi).toFixed(2) + '</span></div>' : '') + (fredLatest(core) != null ? '<div class="pulse-item"><span class="pulse-label">Core CPI</span><span class="pulse-price">' + fredLatest(core).toFixed(2) + '</span></div>' : '') + (fredLatest(pce) != null ? '<div class="pulse-item"><span class="pulse-label">PCE</span><span class="pulse-price">' + fredLatest(pce).toFixed(2) + '</span></div>' : '');
  fredCharts["fred-chart-inflation"] && fredCharts["fred-chart-inflation"].destroy();
  var ctx = document.getElementById("fred-chart-inflation");
  if (!ctx || !cpi.length) return;
  var labels = cpi.map(function(p) { return p.date; });
  var cpiV = cpi.map(function(p) { return p.value; });
  var coreV = labels.map(function(d) { var p = core.find(function(x) { return x.date === d; }); return p ? p.value : null; });
  var pceV = labels.map(function(d) { var p = pce.find(function(x) { return x.date === d; }); return p ? p.value : null; });
  fredCharts["fred-chart-inflation"] = new Chart(ctx, {
    type: "line",
    data: { labels: labels, datasets: [{ label: "CPI-U", data: cpiV, borderColor: "rgba(212,160,23,0.9)", fill: false, pointRadius: 0 }, { label: "Core CPI", data: coreV, borderColor: "rgba(100,116,139,0.9)", fill: false, pointRadius: 0 }, { label: "PCE", data: pceV, borderColor: "rgba(52,211,153,0.7)", fill: false, pointRadius: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: "#94a3b8" } } }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 10 }, grid: { display: false } }, y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.03)" } } } }
  });
}
function fredValueAt(arr, dateStr) { for (var i = (arr && arr.length) ? arr.length - 1 : -1; i >= 0; i--) if (arr[i].date <= dateStr) return arr[i].value; return null; }
function renderFredMonetary(data) {
  var fed = fredSeries(data, "FEDFUNDS");
  var m2 = fredSeries(data, "M2SL");
  var el = document.getElementById("fred-monetary-stats");
  if (el) el.innerHTML = (fredLatest(fed) != null ? '<div class="pulse-item"><span class="pulse-label">Fed Funds</span><span class="pulse-price">' + fredLatest(fed).toFixed(2) + '%</span></div>' : '') + (fredLatest(m2) != null ? '<div class="pulse-item"><span class="pulse-label">M2</span><span class="pulse-price">$' + (fredLatest(m2)/1e3).toFixed(2) + 'T</span></div>' : '');
  fredLineChart("fred-chart-fedfunds", fed, "Fed Funds Rate", "pct");
  fredLineChart("fred-chart-m2", m2, "M2", "billions");
  var ycLabels = ["1M","3M","6M","1Y","2Y","5Y","10Y","20Y","30Y"];
  var ycIds = ["DGS1MO","DGS3MO","DGS6MO","DGS1","DGS2","DGS5","DGS10","DGS20","DGS30"];
  var now = new Date();
  var nowStr = now.getFullYear() + "-" + String(now.getMonth()+1).padStart(2,"0") + "-" + String(now.getDate()).padStart(2,"0");
  var pastStr = (now.getFullYear()-1) + "-" + String(now.getMonth()+1).padStart(2,"0") + "-" + String(now.getDate()).padStart(2,"0");
  var currentRates = ycIds.map(function(id) { return fredLatest(fredSeries(data, id)); });
  var pastRates = ycIds.map(function(id) { return fredValueAt(fredSeries(data, id), pastStr); });
  var hasCurrent = currentRates.some(function(v) { return v != null; });
  var ctx = document.getElementById("fred-chart-yield-curve");
  if (ctx && typeof Chart !== "undefined" && hasCurrent) {
    fredCharts["fred-chart-yield-curve"] && fredCharts["fred-chart-yield-curve"].destroy();
    fredCharts["fred-chart-yield-curve"] = new Chart(ctx, {
      type: "line",
      data: { labels: ycLabels, datasets: [{ label: "Current", data: currentRates, borderColor: "rgba(212,160,23,0.9)", backgroundColor: "rgba(212,160,23,0.1)", fill: true, tension: 0.2, pointRadius: 3 }, { label: "1Y ago", data: pastRates, borderColor: "rgba(100,116,139,0.7)", borderDash: [4,2], fill: false, pointRadius: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: "#94a3b8" } }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b" }, grid: { display: false } }, y: { ticks: { color: "#64748b", callback: function(v) { return v != null ? Number(v).toFixed(1) + "%" : ""; } }, grid: { color: "rgba(255,255,255,0.03)" } } } }
    });
  }
}
function renderFredCredit(data) {
  var hy = fredSeries(data, "BAMLH0A0HYM2");
  var el = document.getElementById("fred-credit-stats");
  var latest = fredLatest(hy);
  if (el) {
    var cls = latest != null && latest >= 5 ? "neg" : "pos";
    el.innerHTML = (latest != null ? '<div class="pulse-item"><span class="pulse-label">HY OAS</span><span class="pulse-price">' + latest.toFixed(2) + '%</span></div><div class="pulse-item"><span class="pulse-label">Signal</span><span class="pulse-price ' + cls + '">' + (latest >= 5 ? "STRESS" : latest >= 4 ? "ELEVATED" : "NORMAL") + '</span></div>' : '');
  }
  fredCharts["fred-chart-hy-spread"] && fredCharts["fred-chart-hy-spread"].destroy();
  var ctx = document.getElementById("fred-chart-hy-spread");
  if (!ctx || !hy.length) return;
  var labels = hy.map(function(p) { return p.date; });
  var values = hy.map(function(p) { return p.value; });
  var threshold5 = values.map(function() { return 5; });
  fredCharts["fred-chart-hy-spread"] = new Chart(ctx, {
    type: "line",
    data: { labels: labels, datasets: [{ label: "HY OAS %", data: values, borderColor: "rgba(248,113,113,0.9)", backgroundColor: "rgba(248,113,113,0.1)", fill: true, tension: 0.2, pointRadius: 0 }, { label: "Stress (5%)", data: threshold5, borderColor: "rgba(248,113,113,0.4)", borderDash: [6,3], borderWidth: 1, pointRadius: 0, fill: false }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: "#94a3b8" } }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 8 }, grid: { display: false } }, y: { ticks: { color: "#64748b", callback: function(v) { return v != null ? Number(v).toFixed(1) + "%" : ""; } }, grid: { color: "rgba(255,255,255,0.03)" } } } }
  });
}
function renderFredRealYields(data) {
  var realY = fredSeries(data, "DFII10");
  var be5 = fredSeries(data, "T5YIE");
  var be10 = fredSeries(data, "T10YIE");
  var el = document.getElementById("fred-realyield-stats");
  var latestReal = fredLatest(realY);
  var latestBE5 = fredLatest(be5);
  var latestBE10 = fredLatest(be10);
  if (el) el.innerHTML = (latestReal != null ? '<div class="pulse-item"><span class="pulse-label">10Y Real Yield</span><span class="pulse-price">' + latestReal.toFixed(2) + '%</span></div>' : '') + (latestBE5 != null ? '<div class="pulse-item"><span class="pulse-label">5Y Breakeven</span><span class="pulse-price">' + latestBE5.toFixed(2) + '%</span></div>' : '') + (latestBE10 != null ? '<div class="pulse-item"><span class="pulse-label">10Y Breakeven</span><span class="pulse-price">' + latestBE10.toFixed(2) + '%</span></div>' : '');
  fredLineChart("fred-chart-real-yield", realY, "10Y Real Yield %", "pct");
  fredCharts["fred-chart-breakeven"] && fredCharts["fred-chart-breakeven"].destroy();
  var ctx = document.getElementById("fred-chart-breakeven");
  if (!ctx) return;
  var labels = be10.length ? be10.map(function(p) { return p.date; }) : be5.map(function(p) { return p.date; });
  var be5V = labels.map(function(d) { var p = be5.find(function(x) { return x.date === d; }); return p ? p.value : null; });
  var be10V = labels.map(function(d) { var p = be10.find(function(x) { return x.date === d; }); return p ? p.value : null; });
  fredCharts["fred-chart-breakeven"] = new Chart(ctx, {
    type: "line",
    data: { labels: labels, datasets: [{ label: "5Y Breakeven", data: be5V, borderColor: "rgba(96,165,250,0.9)", fill: false, tension: 0.2, pointRadius: 0 }, { label: "10Y Breakeven", data: be10V, borderColor: "rgba(212,160,23,0.9)", fill: false, tension: 0.2, pointRadius: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: "#94a3b8" } }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 8 }, grid: { display: false } }, y: { ticks: { color: "#64748b", callback: function(v) { return v != null ? Number(v).toFixed(1) + "%" : ""; } }, grid: { color: "rgba(255,255,255,0.03)" } } } }
  });
}
function renderFredFedBS(data) {
  var walcl = fredSeries(data, "WALCL");
  var el = document.getElementById("fred-fedbs-stats");
  var latest = fredLatest(walcl);
  if (el) el.innerHTML = (latest != null ? '<div class="pulse-item"><span class="pulse-label">Fed Total Assets</span><span class="pulse-price">$' + (latest/1e6).toFixed(2) + 'T</span></div>' : '');
  fredLineChart("fred-chart-fedbs", walcl, "Fed Balance Sheet", "billions");
}
function renderFredSahm(data) {
  var sahm = fredSeries(data, "SAHMREALTIME");
  var el = document.getElementById("fred-sahm-stats");
  var latest = fredLatest(sahm);
  if (el) {
    var cls = latest != null && latest >= 0.5 ? "neg" : "pos";
    el.innerHTML = (latest != null ? '<div class="pulse-item"><span class="pulse-label">Sahm Rule</span><span class="pulse-price">' + latest.toFixed(2) + '</span></div><div class="pulse-item"><span class="pulse-label">Signal</span><span class="pulse-price ' + cls + '">' + (latest >= 0.5 ? "RECESSION" : "NORMAL") + '</span></div>' : '');
  }
  fredCharts["fred-chart-sahm"] && fredCharts["fred-chart-sahm"].destroy();
  var ctx = document.getElementById("fred-chart-sahm");
  if (!ctx || !sahm.length) return;
  var labels = sahm.map(function(p) { return p.date; });
  var values = sahm.map(function(p) { return p.value; });
  var threshold50 = values.map(function() { return 0.5; });
  fredCharts["fred-chart-sahm"] = new Chart(ctx, {
    type: "line",
    data: { labels: labels, datasets: [{ label: "Sahm Rule", data: values, borderColor: "rgba(251,191,36,0.9)", backgroundColor: "rgba(251,191,36,0.1)", fill: true, tension: 0.2, pointRadius: 0 }, { label: "Recession Threshold (0.50)", data: threshold50, borderColor: "rgba(248,113,113,0.6)", borderDash: [6,3], borderWidth: 2, pointRadius: 0, fill: false }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: "#94a3b8" } }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 8 }, grid: { display: false } }, y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.03)" } } } }
  });
}
function renderFredLabor(data) {
  var unrate = fredSeries(data, "UNRATE");
  var claims = fredSeries(data, "ICSA");
  var el = document.getElementById("fred-labor-stats");
  if (el) el.innerHTML = (fredLatest(unrate) != null ? '<div class="pulse-item"><span class="pulse-label">Unemployment</span><span class="pulse-price">' + fredLatest(unrate).toFixed(1) + '%</span></div>' : '') + (fredLatest(claims) != null ? '<div class="pulse-item"><span class="pulse-label">Jobless Claims</span><span class="pulse-price">' + (fredLatest(claims)/1000).toFixed(1) + 'K</span></div>' : '');
  fredLineChart("fred-chart-unemployment", unrate, "Unemployment %", "pct");
  fredLineChart("fred-chart-claims", claims, "Initial Claims", null);
}
function renderFredGrowth(data) {
  var gdpGr = fredSeries(data, "A191RL1Q225SBEA");
  var sent = fredSeries(data, "UMCSENT");
  var el = document.getElementById("fred-growth-stats");
  if (el) el.innerHTML = (fredLatest(gdpGr) != null ? '<div class="pulse-item"><span class="pulse-label">Real GDP Growth</span><span class="pulse-price">' + fredLatest(gdpGr).toFixed(1) + '%</span></div>' : '') + (fredLatest(sent) != null ? '<div class="pulse-item"><span class="pulse-label">Consumer Sentiment</span><span class="pulse-price">' + fredLatest(sent).toFixed(1) + '</span></div>' : '');
  fredLineChart("fred-chart-gdp-growth", gdpGr, "Real GDP Growth %", "pct");
  fredLineChart("fred-chart-sentiment", sent, "Sentiment", null);
}
/* ── FedWatch ── */
var _fedwatchLoaded = false;
var _fwData = null;
var _fwChart = null;
var _fwIdx = 0;
function loadFedWatchData() {
  if (_fedwatchLoaded) return;
  _fedwatchLoaded = true;
  fetch("/api/fedwatch")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      _fwData = d;
      _fwIdx = 0;
      _fwBuildTabs();
      _fwRender(0);
    })
    .catch(function(e) { console.error("FedWatch fetch:", e); _fedwatchLoaded = false; });
}
function _fwBuildTabs() {
  var el = document.getElementById("fw-tabs");
  if (!el || !_fwData || !_fwData.meetings) return;
  var html = '';
  _fwData.meetings.forEach(function(m, i) {
    html += '<button class="range-btn' + (i === 0 ? ' active' : '') + '" data-fwidx="' + i + '" style="font-size:0.72rem;padding:5px 10px;">' + m.label + '</button>';
  });
  el.innerHTML = html;
}
function _fwRender(idx) {
  if (!_fwData || !_fwData.meetings || !_fwData.meetings[idx]) return;
  _fwIdx = idx;
  var m = _fwData.meetings[idx];

  // Highlight active tab
  document.querySelectorAll("#fw-tabs .range-btn").forEach(function(b, i) {
    b.classList.toggle("active", i === idx);
  });

  // Info row
  var infoEl = document.getElementById("fw-info");
  if (infoEl) {
    var sub = 'style="font-size:0.7rem;color:var(--text-muted);font-family:var(--mono);"';
    infoEl.innerHTML =
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">' +
      '<div class="pulse-bar" style="flex-wrap:wrap;gap:10px;">' +
        '<div class="pulse-item"><span class="pulse-label">Meeting Date</span><span class="pulse-price" style="font-size:0.85rem;">' + m.date + '</span></div>' +
        '<div class="pulse-item"><span class="pulse-label">Contract</span><span class="pulse-price" style="font-size:0.85rem;">' + m.contract + '</span></div>' +
        (m.price != null ? '<div class="pulse-item"><span class="pulse-label">Mid Price</span><span class="pulse-price" style="font-size:0.85rem;">' + (100 - m.price).toFixed(4) + '</span></div>' : '') +
      '</div>' +
      '<div class="pulse-bar" style="flex-wrap:wrap;gap:10px;justify-content:flex-end;">' +
        '<div class="pulse-item" style="text-align:center;"><span class="pulse-label">Ease</span><span class="pulse-price" style="font-size:0.85rem;color:rgba(52,211,153,0.9);">' + m.cut.toFixed(1) + ' %</span></div>' +
        '<div class="pulse-item" style="text-align:center;"><span class="pulse-label">No Change</span><span class="pulse-price" style="font-size:0.85rem;">' + m.hold.toFixed(1) + ' %</span></div>' +
        '<div class="pulse-item" style="text-align:center;"><span class="pulse-label">Hike</span><span class="pulse-price" style="font-size:0.85rem;color:rgba(239,68,68,0.9);">' + m.hike.toFixed(1) + ' %</span></div>' +
      '</div></div>';
  }

  var titleEl = document.getElementById("fw-title");
  if (titleEl) titleEl.textContent = "Target Rate Probabilities for " + m.date + " Fed Meeting";
  var subEl = document.getElementById("fw-subtitle");
  if (subEl) subEl.textContent = "Current target rate is " + _fwData.current_range_bps;

  // Bar chart
  if (_fwChart) _fwChart.destroy();
  var ctx = document.getElementById("fw-bar-chart");
  if (!ctx || typeof Chart === "undefined" || !m.ranges || !m.ranges.length) return;

  var labels = m.ranges.map(function(r) { return r.range; });
  var data = m.ranges.map(function(r) { return r.prob; });
  var currentBps = _fwData.current_range_bps;
  var colors = m.ranges.map(function(r) {
    if (r.range === currentBps) return "rgba(99,102,241,0.85)";
    if (r.lo < parseInt(currentBps)) return "rgba(52,211,153,0.7)";
    return "rgba(239,68,68,0.7)";
  });

  _fwChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors,
        borderRadius: 4,
        maxBarThickness: 80
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(30,30,30,0.95)",
          titleColor: "#e2e8f0", bodyColor: "#e2e8f0",
          callbacks: {
            label: function(ctx) { return ctx.parsed.y.toFixed(1) + "%"; }
          }
        },
        datalabels: false
      },
      scales: {
        x: {
          ticks: { color: "#94a3b8", font: { size: 11 } },
          grid: { display: false },
          title: { display: true, text: "Target Rate (in bps)", color: "#64748b", font: { size: 11 } }
        },
        y: {
          min: 0, max: 100,
          ticks: { color: "#64748b", callback: function(v) { return v + "%"; }, stepSize: 20 },
          grid: { color: "rgba(148,163,184,0.08)" },
          title: { display: true, text: "Probability", color: "#64748b", font: { size: 11 } }
        }
      }
    },
    plugins: [{
      afterDatasetsDraw: function(chart) {
        var _ctx = chart.ctx;
        chart.data.datasets[0].data.forEach(function(val, i) {
          if (val < 1) return;
          var meta = chart.getDatasetMeta(0).data[i];
          _ctx.save();
          _ctx.fillStyle = "#e2e8f0";
          _ctx.font = "bold 11px sans-serif";
          _ctx.textAlign = "center";
          _ctx.fillText(val.toFixed(1) + "%", meta.x, meta.y - 6);
          _ctx.restore();
        });
      }
    }]
  });
}

var _capeLoaded = false;
function loadCapeData() {
  if (_capeLoaded) return;
  _capeLoaded = true;
  fetch("/api/cape").then(function(r) { return r.json(); }).then(function(d) {
    renderCape(d);
  }).catch(function(e) { console.error("CAPE fetch error:", e); _capeLoaded = false; });
}
function renderCape(d) {
  var el = document.getElementById("cape-stats");
  if (el) {
    var labelClass = "";
    if (d.label === "Very Expensive") labelClass = "color:var(--danger);font-weight:600;";
    else if (d.label === "Expensive") labelClass = "color:#f59e0b;font-weight:600;";
    else if (d.label === "Above Average") labelClass = "color:#fbbf24;";
    else if (d.label === "Below Average" || d.label === "Cheap") labelClass = "color:var(--success);font-weight:600;";
    el.innerHTML = (d.current != null ? '<div class="pulse-item"><span class="pulse-label">Current CAPE</span><span class="pulse-price">' + d.current.toFixed(1) + '</span></div>' : '')
      + '<div class="pulse-item"><span class="pulse-label">Historic Median</span><span class="pulse-price">' + d.median + '</span></div>'
      + (d.label ? '<div class="pulse-item"><span class="pulse-label">Valuation</span><span class="pulse-price" style="' + labelClass + '">' + d.label + '</span></div>' : '');
  }
  var pts = d.history || [];
  if (!pts.length) return;
  fredCharts["cape-chart"] && fredCharts["cape-chart"].destroy();
  var ctx = document.getElementById("cape-chart");
  if (!ctx || typeof Chart === "undefined") return;
  var labels = pts.map(function(p) { return p.date; });
  var values = pts.map(function(p) { return p.value; });
  fredCharts["cape-chart"] = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        { label: "CAPE Ratio", data: values, borderColor: "rgba(99,102,241,0.9)", backgroundColor: "rgba(99,102,241,0.08)", fill: true, tension: 0.25, pointRadius: 0 },
        { label: "Median (16.8)", data: labels.map(function() { return 16.8; }), borderColor: "rgba(248,113,113,0.5)", borderDash: [6,4], pointRadius: 0, fill: false }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#94a3b8" } },
        tooltip: fredTooltipOpts
      },
      scales: {
        x: { ticks: { color: "#64748b", maxTicksLimit: 10 }, grid: { display: false } },
        y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.03)" } }
      }
    }
  });
}
var _buffettLoaded = false;
function loadBuffettData() {
  if (_buffettLoaded) return;
  _buffettLoaded = true;
  fetch("/api/buffett").then(function(r) { return r.json(); }).then(function(d) {
    renderBuffett(d);
  }).catch(function(e) { console.error("Buffett fetch error:", e); _buffettLoaded = false; });
}
function renderBuffett(d) {
  var el = document.getElementById("buffett-stats");
  if (el) {
    var labelClass = "";
    if (d.label === "Significantly Overvalued") labelClass = "color:var(--danger);font-weight:600;";
    else if (d.label === "Overvalued") labelClass = "color:#f59e0b;font-weight:600;";
    else if (d.label === "Undervalued" || d.label === "Significantly Undervalued") labelClass = "color:var(--success);font-weight:600;";
    el.innerHTML = (d.current != null ? '<div class="pulse-item"><span class="pulse-label">Current</span><span class="pulse-price">' + d.current.toFixed(0) + '%</span></div>' : '')
      + '<div class="pulse-item"><span class="pulse-label">Historic Average</span><span class="pulse-price">' + d.median + '%</span></div>'
      + (d.label ? '<div class="pulse-item"><span class="pulse-label">Valuation</span><span class="pulse-price" style="' + labelClass + '">' + d.label + '</span></div>' : '');
  }
  var pts = d.history || [];
  if (!pts.length) return;
  fredCharts["buffett-chart"] && fredCharts["buffett-chart"].destroy();
  var ctx = document.getElementById("buffett-chart");
  if (!ctx || typeof Chart === "undefined") return;
  var labels = pts.map(function(p) { return p.date; });
  var values = pts.map(function(p) { return p.value; });
  fredCharts["buffett-chart"] = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        { label: "Buffett Indicator %", data: values, borderColor: "rgba(52,211,153,0.9)", backgroundColor: "rgba(52,211,153,0.08)", fill: true, tension: 0.25, pointRadius: 0 },
        { label: "Average (120%)", data: labels.map(function() { return 120; }), borderColor: "rgba(248,113,113,0.5)", borderDash: [6,4], pointRadius: 0, fill: false }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#94a3b8" } },
        tooltip: { yAlign: "bottom", caretPadding: 8, backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0", borderColor: "rgba(52,211,153,0.4)", borderWidth: 1, callbacks: { label: function(ctx) { return ctx.dataset.label + ": " + (ctx.parsed.y != null ? ctx.parsed.y.toFixed(1) + "%" : "N/A"); } } }
      },
      scales: {
        x: { ticks: { color: "#64748b", maxTicksLimit: 10 }, grid: { display: false } },
        y: { ticks: { color: "#64748b", callback: function(v) { return v + "%"; } }, grid: { color: "rgba(255,255,255,0.03)" } }
      }
    }
  });
}
function renderFredWui(data) {
  var wui = fredSeries(data, "WUIGLOBALWEIGHTAVG");
  var el = document.getElementById("fred-wui-stats");
  var latest = fredLatest(wui);
  if (el) {
    var cls = latest != null && latest > 30000 ? "neg" : "pos";
    el.innerHTML = (latest != null ? '<div class="pulse-item"><span class="pulse-label">Current</span><span class="pulse-price ' + cls + '">' + latest.toLocaleString(undefined, {maximumFractionDigits: 0}) + '</span></div>' : '');
  }
  fredCharts["fred-chart-wui"] && fredCharts["fred-chart-wui"].destroy();
  var ctx = document.getElementById("fred-chart-wui");
  if (!ctx || !wui.length) return;
  var labels = wui.map(function(p) { return p.date; });
  var values = wui.map(function(p) { return p.value; });
  fredCharts["fred-chart-wui"] = new Chart(ctx, {
    type: "line",
    data: { labels: labels, datasets: [{ label: "World Uncertainty Index", data: values, borderColor: "rgba(251,146,60,0.9)", backgroundColor: "rgba(251,146,60,0.1)", fill: true, tension: 0.25, pointRadius: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { labels: { color: "#94a3b8" } }, tooltip: fredTooltipOpts }, scales: { x: { ticks: { color: "#64748b", maxTicksLimit: 10 }, grid: { display: false } }, y: { ticks: { color: "#64748b", callback: function(v) { return (v/1000).toFixed(0) + "K"; } }, grid: { color: "rgba(255,255,255,0.03)" } } } }
  });
}
function renderFredHousing(data) {
  var cs = fredSeries(data, "CSUSHPINSA");
  var mort = fredSeries(data, "MORTGAGE30US");
  var el = document.getElementById("fred-housing-stats");
  if (el) el.innerHTML = (fredLatest(cs) != null ? '<div class="pulse-item"><span class="pulse-label">Case-Shiller</span><span class="pulse-price">' + fredLatest(cs).toFixed(1) + '</span></div>' : '') + (fredLatest(mort) != null ? '<div class="pulse-item"><span class="pulse-label">30Y Mortgage</span><span class="pulse-price">' + fredLatest(mort).toFixed(2) + '%</span></div>' : '');
  fredLineChart("fred-chart-housing", cs, "Case-Shiller", null);
  fredLineChart("fred-chart-mortgage", mort, "30Y Mortgage %", "pct");
}
var fredDataCache = {};
var fredSectionsLoaded = {};
var FRED_SECTION_SERIES = {
  debt: "GFDEBTN,GFDEGDQ188S,FYFSD,A091RC1Q027SBEA,GDP,W006RC1Q027SBEA,W068RCQ027SBEA,FYFSGDA188S,FYONGDA188S,FYOIGDA188S",
  inflation: "CPIAUCSL,CPILFESL,PCEPI",
  monetary: "FEDFUNDS,M2SL,WALCL",
  monetary_yc: "DGS1MO,DGS3MO,DGS6MO,DGS1,DGS2,DGS5,DGS10,DGS20,DGS30",
  credit: "BAMLH0A0HYM2",
  realyields: "DFII10,T5YIE,T10YIE",
  fedbs: "WALCL",
  sahm: "SAHMREALTIME",
  labor: "UNRATE,ICSA",
  growth: "A191RL1Q225SBEA,UMCSENT",
  housing: "CSUSHPINSA,MORTGAGE30US",
  wui: "WUIGLOBALWEIGHTAVG"
};
function fredMergeData(target, incoming) { for (var k in incoming) if (incoming[k] && incoming[k].data) target[k] = incoming[k]; }
function fredSafeJson(r) {
  if (!r.ok) return Promise.reject(new Error("HTTP " + r.status));
  return r.json().catch(function(e) { return Promise.reject(new Error("Invalid JSON: " + e.message)); });
}
function fredFetchSection(sectionId, horizon, statusEl) {
  if (fredSectionsLoaded[sectionId]) return Promise.resolve();
  var ids = FRED_SECTION_SERIES[sectionId];
  if (!ids) return Promise.resolve();
  var url = "/api/fred-data?series_ids=" + encodeURIComponent(ids);
  if (horizon) url += "&horizon=" + encodeURIComponent(horizon);
  var p = fetch(url).then(fredSafeJson).then(function(data) {
    fredMergeData(fredDataCache, data);
    fredSectionsLoaded[sectionId] = true;
    return data;
  });
  if (sectionId === "monetary") {
    var ycIds = FRED_SECTION_SERIES["monetary_yc"];
    if (ycIds && !fredSectionsLoaded["monetary_yc"]) {
      var ycUrl = "/api/fred-data?series_ids=" + encodeURIComponent(ycIds);
      if (horizon) ycUrl += "&horizon=" + encodeURIComponent(horizon);
      p = Promise.all([p, fetch(ycUrl).then(fredSafeJson).then(function(data) {
        fredMergeData(fredDataCache, data);
        fredSectionsLoaded["monetary_yc"] = true;
        return data;
      })]);
    }
  }
  return p;
}
function fredRefreshSectionPeriod(sectionId, horizon) {
  var ids = FRED_SECTION_SERIES[sectionId];
  if (!ids) return;
  var url = "/api/fred-data?series_ids=" + encodeURIComponent(ids) + "&horizon=" + encodeURIComponent(horizon);
  fetch(url).then(fredSafeJson).then(function(data) {
    fredMergeData(fredDataCache, data);
    fredRenderAll();
  }).catch(function() {});
}
function fredRenderAll(data) {
  if (!data) data = fredDataCache;
  renderFredDebt(data);
  renderFredInflation(data);
  renderFredMonetary(data);
  renderFredCredit(data);
  renderFredRealYields(data);
  renderFredFedBS(data);
  renderFredSahm(data);
  renderFredLabor(data);
  renderFredGrowth(data);
  renderFredWui(data);
  renderFredHousing(data);
}
var _fredObserver = null;
var _fredInited = false;
function loadFredData() {
  var status = document.getElementById("fred-load-status");
  var horizonSelect = document.getElementById("fred-horizon");
  function getHorizon() { return (horizonSelect && horizonSelect.value) || "1y"; }
  if (_fredInited) {
    if (Object.keys(fredDataCache).length > 0) fredRenderAll();
    if (typeof loadFedWatchData === "function") loadFedWatchData();
    if (typeof loadCapeData === "function") loadCapeData();
    if (typeof loadBuffettData === "function") loadBuffettData();
    return;
  }
  _fredInited = true;
  if (status) status.textContent = "Loading… (debt & inflation first)";
  fredFetchSection("debt", getHorizon()).then(function() {
    return fredFetchSection("inflation", getHorizon());
  }).then(function() {
    if (status) status.textContent = "Data loaded. Scroll for more sections.";
    fredRenderAll();
  }).catch(function(err) {
    console.error("FRED load error:", err);
    if (status) status.textContent = "Failed: " + (err.message || err);
    _fredInited = false;
  });
  _fredObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(e) {
      if (!e.isIntersecting) return;
      var m = e.target.id && e.target.id.match(/^fred-section-(.+)$/);
      if (!m) return;
      var sectionId = m[1];
      if (sectionId === "econcal") { loadEconCalendar(); return; }
      if (sectionId === "fedwatch") { loadFedWatchData(); return; }
      if (sectionId === "cape") { loadCapeData(); return; }
      if (sectionId === "buffett") { loadBuffettData(); return; }
      if (fredSectionsLoaded[sectionId]) return;
      fredFetchSection(sectionId, getHorizon()).then(function() {
        fredRenderAll();
      }).catch(function() {});
    });
  }, { rootMargin: "100px", threshold: 0.1 });
  ["econcal","debt","inflation","monetary","fedwatch","credit","realyields","fedbs","sahm","labor","growth","cape","buffett","wui","housing"].forEach(function(id) {
    var el = document.getElementById("fred-section-" + id);
    if (el) _fredObserver.observe(el);
  });
  // Explicitly load standalone sections that don't depend on FRED data
  setTimeout(function() {
    if (typeof loadFedWatchData === "function") loadFedWatchData();
  }, 500);
  document.querySelectorAll(".fred-period-select").forEach(function(sel) {
    sel.addEventListener("change", function() {
      var section = this.getAttribute("data-section");
      var horizon = this.value;
      fredRefreshSectionPeriod(section, horizon);
    });
  });
  var btn = document.getElementById("fred-refresh-btn");
  if (btn) btn.onclick = function() {
    fredDataCache = {};
    fredSectionsLoaded = {};
    var sections = Object.keys(FRED_SECTION_SERIES);
    var done = 0;
    var total = sections.length;
    if (status) status.textContent = "Refreshing (0/" + total + ")…";
    var chain = Promise.resolve();
    sections.forEach(function(sec) {
      chain = chain.then(function() {
        var ids = FRED_SECTION_SERIES[sec];
        return fetch("/api/fred-data?series_ids=" + encodeURIComponent(ids) + "&refresh=1&horizon=" + encodeURIComponent(getHorizon()))
          .then(fredSafeJson)
          .then(function(data) {
            fredMergeData(fredDataCache, data);
            fredSectionsLoaded[sec] = true;
            done++;
            if (status) status.textContent = "Refreshing (" + done + "/" + total + ")…";
            fredRenderAll();
          });
      });
    });
    chain.then(function() {
      if (status) status.textContent = "Refreshed.";
    }).catch(function(err) {
      if (status) status.textContent = "Refresh error: " + (err.message || err);
    });
  };
  if (horizonSelect) horizonSelect.onchange = function() {
    var h = getHorizon();
    if (status) status.textContent = "Loading " + (h === "max" ? "full history" : h) + "…";
    fetch("/api/fred-data?horizon=" + encodeURIComponent(h)).then(fredSafeJson).then(function(data) {
      fredDataCache = data;
      Object.keys(FRED_SECTION_SERIES).forEach(function(k) { fredSectionsLoaded[k] = true; });
      if (status) status.textContent = "Data loaded.";
      fredRenderAll();
    }).catch(function(err) { if (status) status.textContent = "Load failed: " + (err.message || err); });
  };
}
/* ── Economic Calendar ── */
var _econCalLoaded = false;
var _econCalOffset = 0;
function loadEconCalendar(offset) {
  if (typeof offset === "undefined") offset = 0;
  _econCalOffset = offset;
  var body = document.getElementById("econcal-body");
  if (body && !_econCalLoaded) body.innerHTML = '<p class="hint">Loading economic events&hellip;</p>';
  _econCalLoaded = true;
  _updateEconCalButtons();
  fetch("/api/economic-calendar?offset=" + offset)
    .then(function(r) { return r.json(); })
    .then(function(d) { renderEconCalendar(d); })
    .catch(function(e) {
      console.error("[EconCal]", e);
      if (body) body.innerHTML = '<p class="hint">Failed to load calendar.</p>';
    });
}
function _updateEconCalButtons() {
  var prev = document.getElementById("econcal-prev");
  var thisBtn = document.getElementById("econcal-this");
  var next = document.getElementById("econcal-next");
  var active = "border:1px solid rgba(99,102,241,0.5);background:rgba(99,102,241,0.15);color:#a5b4fc;font-weight:600;";
  var normal = "border:1px solid rgba(255,255,255,0.2);background:rgba(255,255,255,0.06);color:#e2e8f0;font-weight:400;";
  if (prev) prev.style.cssText = "padding:5px 10px;font-size:0.82rem;border-radius:6px;cursor:pointer;" + (_econCalOffset < 0 ? active : normal);
  if (thisBtn) thisBtn.style.cssText = "padding:5px 10px;font-size:0.82rem;border-radius:6px;cursor:pointer;" + (_econCalOffset === 0 ? active : normal);
  if (next) next.style.cssText = "padding:5px 10px;font-size:0.82rem;border-radius:6px;cursor:pointer;" + (_econCalOffset > 0 ? active : normal);
  if (prev) prev.disabled = _econCalOffset <= -8;
  if (next) next.disabled = _econCalOffset >= 4;
}
(function() {
  document.addEventListener("click", function(ev) {
    if (ev.target.id === "econcal-prev") loadEconCalendar(_econCalOffset - 1);
    else if (ev.target.id === "econcal-this") loadEconCalendar(0);
    else if (ev.target.id === "econcal-next") loadEconCalendar(_econCalOffset + 1);
  });
})();
function renderEconCalendar(d) {
  var body = document.getElementById("econcal-body");
  if (!body) return;
  var weekEl = document.getElementById("econcal-week");
  if (weekEl) weekEl.textContent = d.week_label ? d.week_label : "";
  if (!d || !d.events || !d.events.length) {
    body.innerHTML = '<p class="hint">' + (_econCalOffset === 0 ? "No US economic events available." : "No cached data for this week.") + '</p>';
    return;
  }
  var today = new Date().toISOString().slice(0, 10);
  var impactColor = { high: "#ef4444", medium: "#f59e0b", low: "#64748b" };
  var grouped = {};
  d.events.forEach(function(e) {
    if (!grouped[e.date]) grouped[e.date] = [];
    grouped[e.date].push(e);
  });
  var dates = Object.keys(grouped).sort();
  var html = '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">';
  html += '<thead><tr style="border-bottom:1px solid rgba(255,255,255,0.08);text-align:left;">';
  html += '<th style="padding:6px 8px;color:#94a3b8;font-weight:600;width:32px;"></th>';
  html += '<th style="padding:6px 8px;color:#94a3b8;font-weight:600;">Time</th>';
  html += '<th style="padding:6px 8px;color:#94a3b8;font-weight:600;">Event</th>';
  html += '<th style="padding:6px 4px;color:#94a3b8;font-weight:600;text-align:right;">Actual</th>';
  html += '<th style="padding:6px 4px;color:#94a3b8;font-weight:600;text-align:right;">Forecast</th>';
  html += '<th style="padding:6px 4px;color:#94a3b8;font-weight:600;text-align:right;">Previous</th>';
  html += '</tr></thead><tbody>';
  dates.forEach(function(dt) {
    var dayLabel = new Date(dt + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    var isToday = dt === today;
    html += '<tr><td colspan="6" style="padding:8px 8px 4px;font-weight:700;color:' + (isToday ? "var(--gold)" : "#e2e8f0") + ';font-size:0.82rem;border-top:1px solid rgba(255,255,255,0.06);">' + dayLabel + (isToday ? " (Today)" : "") + '</td></tr>';
    grouped[dt].forEach(function(e) {
      var ic = impactColor[e.impact] || "#64748b";
      var actualVal = e.actual || "-";
      var actualColor = "#94a3b8";
      if (e.actual && e.actual !== "-") {
        actualColor = "#22c55e";
        if (e.forecast && e.forecast !== "-") {
          var af = parseFloat(e.actual.replace(/[%KMB,]/g, ""));
          var ff = parseFloat(e.forecast.replace(/[%KMB,]/g, ""));
          if (!isNaN(af) && !isNaN(ff) && af < ff) actualColor = "#ef4444";
        }
      }
      html += '<tr style="border-bottom:1px solid rgba(255,255,255,0.03);">';
      html += '<td style="padding:4px 8px;"><span style="display:inline-block;width:8px;height:8px;background:' + ic + ';border-radius:50%;"></span></td>';
      html += '<td style="padding:4px 8px;color:#94a3b8;white-space:nowrap;">' + (e.time || "-") + '</td>';
      html += '<td style="padding:4px 8px;color:#e2e8f0;">' + e.event + '</td>';
      html += '<td style="padding:4px 4px;text-align:right;color:' + actualColor + ';font-weight:' + (e.actual ? "600" : "400") + ';">' + actualVal + '</td>';
      html += '<td style="padding:4px 4px;text-align:right;color:#94a3b8;">' + (e.forecast || "-") + '</td>';
      html += '<td style="padding:4px 4px;text-align:right;color:#64748b;">' + (e.previous || "-") + '</td>';
      html += '</tr>';
    });
  });
  html += '</tbody></table>';
  body.innerHTML = html;
}
/* FRED_JS_END */

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
function buildDivChart() {
  var ctx = document.getElementById("div-chart");
  if (!ctx || typeof Chart === "undefined" || DIVIDENDS.length === 0) return;
  // Group by month
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
  new Chart(ctx, {
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
  var mcYearsEl = document.getElementById("mc-years");
  if (!mcYearsEl) return;
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
}
// Auto-run on Charts tab
setTimeout(runMonteCarlo, 500);

/* ── Drawdown Analysis ── */
function buildDrawdownChart() {
  if (PRICE_HISTORY_DATA.length < 3) return;
  if (!document.getElementById("drawdown-chart")) return;
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
}
buildDrawdownChart();

/* ── Performance Attribution ── */
var PERF_DATA = window.PERF_DATA || {};
function buildPerfAttribution() {
  if (!document.getElementById("perf-attr-chart")) return;
  if (!PERF_DATA.buckets) {
    fetch("/api/perf-attribution")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        PERF_DATA = d;
        buildPerfAttribution();
      })
      .catch(function(e) { console.error("Perf attribution fetch:", e); });
    return;
  }
  var buckets = PERF_DATA.buckets;
  var total = PERF_DATA.total;
  if (!buckets || total <= 0) return;
  var labels = Object.keys(buckets);
  var values = labels.map(function(b) { return buckets[b]; });
  var pcts = labels.map(function(b) { return ((buckets[b] / total) * 100).toFixed(1); });
  var colorMap = { "Cash":"#64748b","Equities":"#34d399","Gold":"#d4a017","Silver":"#a0a0a0","Crypto":"#818cf8","RealAssets":"#06b6d4","Art":"#f472b6","ManagedBlend":"#fb923c" };
  var colors = labels.map(function(b) { return colorMap[b] || "#94a3b8"; });
  var ctx = document.getElementById("perf-attr-chart");
  if (!ctx || typeof Chart === "undefined") return;
  new Chart(ctx, {
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
}
buildPerfAttribution();

/* ── Tax-Loss Harvesting ── */
function loadTLH() {
  var tbody = document.getElementById("tlh-tbody");
  if (!tbody) return;
  fetch("/api/tax-loss-harvesting")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var rows = d.rows || [];
      if (!rows.length) return;
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
    })
    .catch(function() {});
}
loadTLH();

/* ── Multi-Currency ── */
var FX_RATES = {};
var BASE_CURRENCY = localStorage.getItem("wos-currency") || "USD";
var CURRENCY_SYMBOLS = { "USD":"$", "EUR":"\u20ac", "GBP":"\u00a3", "JPY":"\u00a5", "CAD":"C$", "AUD":"A$", "CHF":"Fr" };
(function() {
  var sel = document.getElementById("currency-selector");
  if (sel) sel.value = BASE_CURRENCY;
  if (BASE_CURRENCY !== "USD") fetchFxAndConvert(BASE_CURRENCY);
})();
function changeCurrency(currency) {
  localStorage.setItem("wos-currency", currency);
  BASE_CURRENCY = currency;
  if (currency === "USD") {
    location.reload();
    return;
  }
  fetchFxAndConvert(currency);
}
function fetchFxAndConvert(currency) {
  fetch("/api/fx-rate?to=" + currency)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.rate) {
        FX_RATES[currency] = d.rate;
        convertDisplayCurrency(d.rate, CURRENCY_SYMBOLS[currency] || currency + " ");
      }
    }).catch(function() {});
}
function convertDisplayCurrency(rate, symbol) {
  // Convert net worth
  var nw = document.getElementById("net-worth-counter");
  if (nw) {
    var usdVal = parseFloat(nw.dataset.target) || 0;
    var converted = usdVal * rate;
    nw.textContent = symbol + converted.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  // Convert dollar amounts in portfolio-value contexts (not market prices)
  // Target: allocation table values, holdings totals, goal amounts, budget values
  document.querySelectorAll("td, .mono, .goal-card .mono, .hero-change").forEach(function(el) {
    var text = el.textContent.trim();
    // Only convert values that start with $ and haven't been converted yet
    if (text.match(/^\$[\d,]+/) && !el.dataset.fxDone) {
      el.dataset.fxDone = "1";
      el.dataset.fxOriginal = text;
      var num = parseFloat(text.replace(/[$,]/g, ""));
      if (!isNaN(num) && num > 0) {
        el.textContent = symbol + (num * rate).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
      }
    }
  });
}

/* ── Background price refresh on page load ── */
(function() {
  function _startLongPoll() {
    var enabled = document.getElementById("auto-enabled") && document.getElementById("auto-enabled").checked;
    var intervalSec = parseInt((document.getElementById("auto-interval") && document.getElementById("auto-interval").value) || 60);
    if (enabled !== false && intervalSec >= 15) startPeriodicLivePoll(intervalSec);
  }
  fetch("/api/live-data").then(function(r) { return r.json(); }).then(applyLiveDataToDOM).catch(function() {});
  fetch("/api/bg-refresh", { method:"POST" }).then(function() {
    var polls = 0;
    var maxPolls = 6;
    function pollLive() {
      polls++;
      fetch("/api/live-data").then(function(r) { return r.json(); }).then(function(d) {
        applyLiveDataToDOM(d);
        _flashUpdatedPulseCards();
        if (polls < maxPolls) { setTimeout(pollLive, 3000); } else { _startLongPoll(); }
      }).catch(function() {
        if (polls < maxPolls) setTimeout(pollLive, 3000); else _startLongPoll();
      });
    }
    setTimeout(pollLive, 4000);
  }).catch(function() {
    _startLongPoll();
  });
})();

/* ── Sentiment Gauges ── */
var _sentimentLoaded = false;
var _sentimentRetries = 0;
function loadSentimentGauges() {
  if (_sentimentLoaded) return;
  fetch("/api/sentiment")
    .then(function(r) {
      if (!r.ok) { console.error("[Sentiment] HTTP " + r.status); throw new Error("HTTP " + r.status); }
      return r.json();
    })
    .then(function(d) {
      console.log("[Sentiment] response:", JSON.stringify(d));
      var keys = ["stock", "crypto", "gold", "vix", "yield_curve"];
      var filled = 0;
      keys.forEach(function(k) {
        var info = d[k];
        if (!info) {
          return;
        }
        filled++;
        var score = (k === "vix") ? info.score : info.value;
        drawGauge("gauge-" + k, score);
        var valEl = document.getElementById("gv-" + k);
        if (valEl) valEl.textContent = score;
        var lblEl = document.getElementById("gl-" + k);
        if (lblEl) {
          lblEl.textContent = info.label;
          lblEl.className = "gauge-label " + info.label.toLowerCase().replace(/\s+/g, "-");
        }
        var subEl = document.getElementById("gs-" + k);
        if (subEl) {
          if (k === "vix") subEl.textContent = "VIX: " + info.value;
          if (k === "yield_curve" && info.spread != null) subEl.textContent = "Spread: " + (info.spread > 0 ? "+" : "") + info.spread.toFixed(2) + "%";
        }
      });
      if (filled > 0) {
        _sentimentLoaded = true;
      } else if (_sentimentRetries < 5) {
        _sentimentRetries++;
        setTimeout(loadSentimentGauges, 8000);
      }
    })
    .catch(function(e) {
      console.warn("[Sentiment] fetch failed:", e);
      if (_sentimentRetries < 5) {
        _sentimentRetries++;
        setTimeout(loadSentimentGauges, 8000);
      }
    });
}

function drawGauge(canvasId, value) {
  var c = document.getElementById(canvasId);
  if (!c) return;
  var dpr = window.devicePixelRatio || 1;
  var w = c.clientWidth || 140;
  var h = c.clientHeight || 85;
  c.width = w * dpr;
  c.height = h * dpr;
  var ctx = c.getContext("2d");
  ctx.scale(dpr, dpr);

  var cx = w / 2;
  var cy = h - 8;
  var r = Math.min(cx - 6, cy - 4);
  var startAngle = Math.PI;
  var endAngle = 2 * Math.PI;
  var lineW = 10;

  // Background track
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.lineWidth = lineW;
  ctx.strokeStyle = "rgba(255,255,255,0.06)";
  ctx.lineCap = "round";
  ctx.stroke();

  // Gradient arc
  var grad = ctx.createLinearGradient(cx - r, cy, cx + r, cy);
  grad.addColorStop(0,   "#ef4444");
  grad.addColorStop(0.25,"#f97316");
  grad.addColorStop(0.5, "#eab308");
  grad.addColorStop(0.75,"#22c55e");
  grad.addColorStop(1,   "#10b981");
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.lineWidth = lineW;
  ctx.strokeStyle = grad;
  ctx.lineCap = "round";
  ctx.stroke();

  // Needle
  var pct = Math.max(0, Math.min(100, value)) / 100;
  var needleAngle = Math.PI + pct * Math.PI;
  var needleLen = r - 6;
  var nx = cx + Math.cos(needleAngle) * needleLen;
  var ny = cy + Math.sin(needleAngle) * needleLen;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(nx, ny);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "rgba(255,255,255,0.85)";
  ctx.lineCap = "round";
  ctx.stroke();

  // Center dot
  ctx.beginPath();
  ctx.arc(cx, cy, 4, 0, 2 * Math.PI);
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.fill();
}

/* ── Sentiment History (click-to-expand) ── */
var _sentHistCache = {};  // keyed by range: { "1y": data, "3y": data, ... }
var _sentHistChart = null;
var _sentHistActive = null;
var _sentHistRange = "1y";
var _sentGaugeNames = {
  stock: "Stocks (CNN Fear & Greed)",
  crypto: "Crypto Fear & Greed",
  gold: "Gold Sentiment",
  vix: "VIX Sentiment",
  yield_curve: "Yield Curve Sentiment"
};
var _sentGaugeColors = {
  stock: "rgba(99,102,241,0.9)",
  crypto: "rgba(245,158,11,0.9)",
  gold: "rgba(234,179,8,0.9)",
  vix: "rgba(239,68,68,0.9)",
  yield_curve: "rgba(52,211,153,0.9)"
};

function _sentFetchAndRender(key, range) {
  var panel = document.getElementById("sentiment-detail");
  var titleEl = document.getElementById("sentiment-detail-title");
  if (_sentHistCache[range]) {
    _sentRender(key, _sentHistCache[range]);
    if (panel) panel.classList.add("open");
    return;
  }
  if (titleEl) titleEl.textContent = (_sentGaugeNames[key] || key) + " - loading…";
  fetch("/api/sentiment-history?range=" + range)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      _sentHistCache[range] = d;
      if (titleEl) titleEl.textContent = _sentGaugeNames[key] || key;
      _sentRender(key, d);
      if (panel) panel.classList.add("open");
    })
    .catch(function(e) {
      console.error("Sentiment history fetch:", e);
      if (titleEl) titleEl.textContent = "Failed to load history";
      if (panel) panel.classList.add("open");
    });
}

function _sentToggle(key) {
  var panel = document.getElementById("sentiment-detail");
  if (!panel) return;

  if (_sentHistActive === key) {
    panel.classList.remove("open");
    document.querySelectorAll(".sentiment-gauge").forEach(function(g) { g.classList.remove("active"); });
    _sentHistActive = null;
    return;
  }

  document.querySelectorAll(".sentiment-gauge").forEach(function(g) {
    g.classList.toggle("active", g.getAttribute("data-gauge") === key);
  });
  _sentHistActive = key;

  var titleEl = document.getElementById("sentiment-detail-title");
  if (titleEl) titleEl.textContent = _sentGaugeNames[key] || key;

  _sentFetchAndRender(key, _sentHistRange);
}

function _sentRender(key, data) {
  var pts = (data && data[key]) || [];
  if (!pts.length) return;
  if (_sentHistChart) _sentHistChart.destroy();
  var ctx = document.getElementById("sentiment-history-chart");
  if (!ctx || typeof Chart === "undefined") return;
  var labels = pts.map(function(p) { return p.date; });
  var values = pts.map(function(p) { return p.value; });
  var baseColor = _sentGaugeColors[key] || "rgba(99,102,241,0.9)";
  var fillColor = baseColor.replace("0.9)", "0.1)");

  _sentHistChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: _sentGaugeNames[key] || key,
        data: values,
        borderColor: baseColor,
        backgroundColor: fillColor,
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          yAlign: "bottom", caretPadding: 8,
          backgroundColor: "rgba(30,30,30,0.95)",
          titleColor: "#e2e8f0", bodyColor: "#e2e8f0",
          borderColor: baseColor.replace("0.9)", "0.4)"), borderWidth: 1,
          callbacks: {
            label: function(ctx) { return (ctx.parsed.y != null ? ctx.parsed.y.toFixed(0) : "N/A") + " / 100"; }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: "#64748b", maxTicksLimit: 10 },
          grid: { display: false }
        },
        y: {
          min: 0, max: 100,
          ticks: {
            color: "#64748b",
            stepSize: 25,
            callback: function(v) {
              if (v === 0) return "Extreme Fear";
              if (v === 25) return "Fear";
              if (v === 50) return "Neutral";
              if (v === 75) return "Greed";
              if (v === 100) return "Extreme Greed";
              return "";
            }
          },
          grid: { color: "rgba(255,255,255,0.04)" }
        }
      }
    }
  });
}

// Wire up click handlers via event delegation (gauges are lazy-loaded)
document.addEventListener("click", function(e) {
  var gauge = e.target.closest(".sentiment-gauge");
  if (gauge) {
    var key = gauge.getAttribute("data-gauge");
    if (key) _sentToggle(key);
    return;
  }
  var fwTab = e.target.closest("#fw-tabs .range-btn");
  if (fwTab) {
    var idx = parseInt(fwTab.getAttribute("data-fwidx"), 10);
    if (!isNaN(idx)) _fwRender(idx);
    return;
  }
  var rangeBtn = e.target.closest("#sent-range-btns .range-btn");
  if (rangeBtn) {
    var newRange = rangeBtn.getAttribute("data-range");
    if (newRange && newRange !== _sentHistRange) {
      _sentHistRange = newRange;
      document.querySelectorAll("#sent-range-btns .range-btn").forEach(function(b) {
        b.classList.toggle("active", b.getAttribute("data-range") === newRange);
      });
      if (_sentHistActive) {
        _sentFetchAndRender(_sentHistActive, newRange);
      }
    }
    return;
  }
  if (e.target.id === "sentiment-detail-close" || e.target.closest("#sentiment-detail-close")) {
    var panel = document.getElementById("sentiment-detail");
    if (panel) panel.classList.remove("open");
    document.querySelectorAll(".sentiment-gauge").forEach(function(g) { g.classList.remove("active"); });
    _sentHistActive = null;
  }
});

/* ══════════════════════════════════════════════════════
   Balances Tab — fetch /api/balances, render editable table, save
   ══════════════════════════════════════════════════════ */
var _balancesLoaded = false;
var _balOpenMenu = null;

function _closeBalsMenu() {
  if (_balOpenMenu) { _balOpenMenu.remove(); _balOpenMenu = null; }
  document.removeEventListener("click", _closeBalsMenu);
}

function _openBalMenu(e, id, name, idx, total) {
  e.stopPropagation();
  _closeBalsMenu();
  var btn = e.currentTarget;
  var menu = document.createElement("div");
  menu.className = "bal-menu";
  var items = [];
  items.push('<button onclick="renameBalance(' + id + ',this)">Rename</button>');
  if (idx > 0) items.push('<button onclick="moveBalance(' + id + ',\'up\')">Move Up</button>');
  if (idx < total - 1) items.push('<button onclick="moveBalance(' + id + ',\'down\')">Move Down</button>');
  items.push('<button class="danger" onclick="deleteBalance(' + id + ')">Delete</button>');
  menu.innerHTML = items.join("");
  btn.parentElement.appendChild(menu);
  _balOpenMenu = menu;
  setTimeout(function() { document.addEventListener("click", _closeBalsMenu); }, 0);
}

function loadBalances() {
  if (_balancesLoaded) return;
  _balancesLoaded = true;
  var wrap = document.getElementById("balances-table-wrap");
  if (!wrap) return;
  fetch("/api/balances")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var accts = d.accounts || [];
      var html = "";
      if (accts.length > 0) {
        html += '<table style="width:100%;border-collapse:collapse;">';
        html += '<thead><tr>';
        html += '<th style="width:28px;padding:10px 0;"></th>';
        html += '<th style="text-align:left;padding:10px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600;">Account</th>';
        html += '<th style="text-align:right;padding:10px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600;">Value ($)</th>';
        html += '</tr></thead><tbody>';
        accts.forEach(function(a, idx) {
          html += '<tr class="bal-row" data-acct-id="' + a.id + '">';
          html += '<td style="width:28px;padding:10px 0;border-bottom:1px solid var(--border-subtle);position:relative;">';
          html += '<button class="bal-kebab" onclick="_openBalMenu(event,' + a.id + ',\'' + (a.name || "").replace(/'/g, "\\'") + '\',' + idx + ',' + accts.length + ')" title="Options">&#8942;</button>';
          html += '</td>';
          html += '<td class="bal-name-cell" data-acct-id="' + a.id + '" style="padding:14px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.92rem;font-weight:500;">' + (a.name || "Account") + '</td>';
          html += '<td style="text-align:right;padding:14px 10px;border-bottom:1px solid var(--border-subtle);font-family:var(--mono);font-size:0.92rem;font-weight:500;">';
          html += '<input type="number" step="0.01" class="bal-input" data-acct-id="' + a.id + '" value="' + (a.value || 0) + '" style="width:140px;text-align:right;padding:6px 10px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);font-family:var(--mono);font-size:0.92rem;">';
          html += '</td></tr>';
        });
        html += '</tbody></table>';
      } else {
        html += '<p class="hint" style="margin-bottom:14px;">No accounts yet. Add one below to start tracking your balances.</p>';
      }
      html += '<div style="display:flex;gap:8px;align-items:end;margin-top:16px;flex-wrap:wrap;">';
      html += '<input type="text" id="new-acct-name" placeholder="Account name (e.g. Fidelity IRA)" style="flex:1;min-width:160px;padding:8px 12px;font-size:0.88rem;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);">';
      html += '<input type="number" id="new-acct-value" placeholder="Balance" step="0.01" style="width:120px;padding:8px 12px;font-size:0.88rem;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);text-align:right;">';
      html += '<button onclick="addBalance()" style="padding:8px 16px;font-size:0.85rem;background:var(--accent-primary);color:#fff;border:none;border-radius:6px;cursor:pointer;white-space:nowrap;">+ Add Account</button>';
      html += '</div>';
      wrap.innerHTML = html;
    })
    .catch(function() {
      wrap.innerHTML = '<p class="hint" style="color:var(--danger);">Failed to load accounts.</p>';
      _balancesLoaded = false;
    });
}

function addBalance() {
  var name = document.getElementById("new-acct-name");
  var value = document.getElementById("new-acct-value");
  if (!name || !name.value.trim()) { if (name) name.focus(); return; }
  fetch("/api/balances", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_account: { name: name.value.trim(), value: parseFloat(value && value.value || 0) } })
  }).then(function() {
    _balancesLoaded = false;
    loadBalances();
  });
}

function deleteBalance(id) {
  _closeBalsMenu();
  if (!confirm("Remove this account?")) return;
  fetch("/api/balances/" + id, { method: "DELETE" })
    .then(function() { _balancesLoaded = false; loadBalances(); });
}

function renameBalance(id) {
  _closeBalsMenu();
  var cell = document.querySelector('.bal-name-cell[data-acct-id="' + id + '"]');
  if (!cell) return;
  var current = cell.textContent.trim();
  var input = document.createElement("input");
  input.type = "text";
  input.value = current;
  input.className = "bal-rename-input";
  input.style.cssText = "width:100%;padding:6px 10px;font-size:0.92rem;font-weight:500;background:var(--bg-input);border:1px solid var(--accent-primary);border-radius:6px;color:var(--text-primary);";
  cell.textContent = "";
  cell.appendChild(input);
  input.focus();
  input.select();
  function commit() {
    var newName = input.value.trim();
    if (!newName || newName === current) { cell.textContent = current; return; }
    cell.textContent = newName;
    fetch("/api/balances/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id, name: newName })
    });
  }
  input.addEventListener("blur", commit);
  input.addEventListener("keydown", function(e) {
    if (e.key === "Enter") { e.preventDefault(); input.blur(); }
    if (e.key === "Escape") { cell.textContent = current; }
  });
}

function moveBalance(id, direction) {
  _closeBalsMenu();
  var rows = document.querySelectorAll(".bal-row");
  var order = [];
  rows.forEach(function(r) { order.push(parseInt(r.getAttribute("data-acct-id"))); });
  var idx = order.indexOf(id);
  if (idx < 0) return;
  var swapIdx = direction === "up" ? idx - 1 : idx + 1;
  if (swapIdx < 0 || swapIdx >= order.length) return;
  var tmp = order[idx];
  order[idx] = order[swapIdx];
  order[swapIdx] = tmp;
  fetch("/api/balances/reorder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order: order })
  }).then(function() { _balancesLoaded = false; loadBalances(); });
}

function saveAllBalances() {
  var inputs = document.querySelectorAll(".bal-input");
  var accounts = [];
  inputs.forEach(function(inp) {
    accounts.push({ id: parseInt(inp.getAttribute("data-acct-id")), value: parseFloat(inp.value) || 0 });
  });
  fetch("/api/balances", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accounts: accounts })
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.success) {
        var btn = document.querySelector('#tab-balances .success');
        if (btn) { btn.textContent = "Saved!"; setTimeout(function(){ btn.textContent = "Save Balances"; }, 2000); }
      }
    });
}

/* ══════════════════════════════════════════════════════
   Holdings Tab — fetch /api/holdings, render tables
   ══════════════════════════════════════════════════════ */
var _holdingsLoaded = false;
function loadHoldings() {
  if (_holdingsLoaded) return;
  _holdingsLoaded = true;

  var stockWrap = document.getElementById("holdings-table-wrap");
  var cryptoWrap = document.getElementById("crypto-tbody");

  fetch("/api/holdings")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      _renderStockHoldings(stockWrap, d.holdings || []);
      _renderCryptoHoldings(cryptoWrap, d.crypto || []);
      _loadPhysicalMetals();
    })
    .catch(function() {
      if (stockWrap) stockWrap.innerHTML = '<p class="hint" style="color:var(--danger);">Failed to load holdings.</p>';
      _holdingsLoaded = false;
    });
}

function _renderStockHoldings(wrap, holdings) {
  if (!wrap) return;
  var fmtMoney = function(v) { return v ? "$" + v.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : ""; };
  var inputStyle = 'style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;"';

  var html = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.82rem;">';
  html += '<thead><tr style="border-bottom:1px solid var(--border-subtle);">';
  html += '<th style="padding:8px 6px;text-align:left;">Account</th>';
  html += '<th style="padding:8px 6px;text-align:left;">Ticker</th>';
  html += '<th style="padding:8px 6px;text-align:left;">Class</th>';
  html += '<th style="padding:8px 6px;text-align:right;">Qty</th>';
  html += '<th style="padding:8px 6px;text-align:right;">Price</th>';
  html += '<th style="padding:8px 6px;text-align:right;">Total</th>';
  html += '<th style="padding:8px 6px;text-align:right;">Override</th>';
  html += '<th style="padding:8px 6px;text-align:left;">Notes</th>';
  html += '</tr></thead><tbody>';

  var grandTotal = 0;
  holdings.forEach(function(h) {
    grandTotal += (h.total || 0);
    var priceStr = h.price ? fmtMoney(h.price) : "";
    var totalStr = h.total ? fmtMoney(h.total) : "";
    var qtyStr = (h.shares !== null && h.shares !== undefined) ? h.shares : "";
    var voStr = (h.value_override !== null && h.value_override !== undefined) ? h.value_override : "";
    html += '<tr data-hid="' + h.id + '">';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="account" value="' + (h.account || "") + '" ' + inputStyle + '></td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="ticker" value="' + (h.ticker || "") + '" ' + inputStyle + '></td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="bucket" value="' + (h.bucket || "") + '" ' + inputStyle + '></td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="shares" value="' + qtyStr + '" class="num" ' + inputStyle + '></td>';
    html += '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);font-family:var(--mono);white-space:nowrap;">' + priceStr + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;color:var(--text-primary);font-family:var(--mono);font-weight:600;white-space:nowrap;">' + totalStr + '</td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="value_override" value="' + voStr + '" class="num" ' + inputStyle + '></td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="notes" value="' + (h.notes || "") + '" ' + inputStyle + '></td>';
    html += '</tr>';
  });

  html += '<tr>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="account" placeholder="Account" ' + inputStyle + '></td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="ticker" placeholder="Ticker" style="text-transform:uppercase;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;"></td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="bucket" placeholder="Asset class" ' + inputStyle + '></td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="shares" placeholder="Qty" class="num" ' + inputStyle + '></td>';
  html += '<td></td><td></td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="value_override" placeholder="Override" class="num" ' + inputStyle + '></td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="notes" placeholder="Notes" ' + inputStyle + '></td>';
  html += '</tr>';

  html += '<tr style="font-weight:600;border-top:2px solid var(--border-subtle);">';
  html += '<td colspan="4" style="padding:8px 6px;">Holdings Total</td>';
  html += '<td></td>';
  html += '<td style="padding:8px 6px;text-align:right;color:#58a6ff;font-family:var(--mono);">' + fmtMoney(grandTotal) + '</td>';
  html += '<td colspan="2"></td>';
  html += '</tr>';

  html += '</tbody></table></div>';
  wrap.innerHTML = html;
}

function _fmtCryptoQty(qty) {
  var n = parseFloat(qty);
  if (isNaN(n)) return qty;
  if (n >= 1) return n.toLocaleString(undefined, {maximumFractionDigits: 4});
  if (n >= 0.001) return n.toFixed(6);
  return n.toFixed(6);
}

function _renderCryptoHoldings(wrap, crypto) {
  if (!wrap) return;
  var countEl = document.getElementById("crypto-count");
  var subEl = document.getElementById("crypto-subtitle");
  var headerTotal = document.getElementById("crypto-header-total");
  if (countEl) countEl.textContent = crypto.length;
  var hasCb = crypto.some(function(c) { return c.source === "coinbase"; });
  if (subEl) subEl.textContent = hasCb ? "Synced from Coinbase - " + crypto.length + " assets" : crypto.length + " assets";

  if (crypto.length === 0) {
    wrap.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted);">No crypto holdings. Connect Coinbase in Settings (gear icon) to auto-sync.</td></tr>';
    return;
  }

  var totalVal = 0;
  var rows = "";
  crypto.forEach(function(c) {
    var val = c.value || 0;
    totalVal += val;
    var qtyStr = _fmtCryptoQty(c.quantity);
    var priceStr = c.price ? "$" + c.price.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : "-";
    var valStr = val ? "$" + val.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : "-";
    var pctStr = "";
    rows += '<tr class="crypto-row" data-cid="' + c.id + '" data-cgid="' + (c.coingecko_id || "") + '">';
    rows += '<td style="padding:8px 10px;font-weight:600;">' + c.symbol + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + qtyStr + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);color:var(--text-muted);">' + priceStr + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + valStr + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;color:var(--text-muted);">' + pctStr + '</td>';
    rows += '</tr>';
  });

  if (totalVal > 0) {
    crypto.forEach(function(c, i) {
      var pct = ((c.value || 0) / totalVal * 100).toFixed(1) + "%";
      var row = wrap.parentElement ? null : undefined;
    });
    var rowsWithPct = "";
    crypto.forEach(function(c) {
      var val = c.value || 0;
      var priceStr = c.price ? "$" + c.price.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : "-";
      var valStr = val ? "$" + val.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : "-";
      var pctStr = totalVal > 0 ? ((val / totalVal) * 100).toFixed(1) + "%" : "";
      rowsWithPct += '<tr class="crypto-row" data-cid="' + c.id + '" data-cgid="' + (c.coingecko_id || "") + '">';
      rowsWithPct += '<td style="padding:8px 10px;font-weight:600;">' + c.symbol + '</td>';
      rowsWithPct += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + _fmtCryptoQty(c.quantity) + '</td>';
      rowsWithPct += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);color:var(--text-muted);">' + priceStr + '</td>';
      rowsWithPct += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + valStr + '</td>';
      rowsWithPct += '<td style="padding:8px 10px;text-align:right;color:var(--text-muted);">' + pctStr + '</td>';
      rowsWithPct += '</tr>';
    });
    rows = rowsWithPct;
  }

  rows += '<tr style="font-weight:600;border-top:2px solid var(--border-subtle);">';
  rows += '<td style="padding:8px 10px;" colspan="3">Total</td>';
  rows += '<td style="padding:8px 10px;text-align:right;color:#58a6ff;font-family:var(--mono);">$' + totalVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
  rows += '<td style="padding:8px 10px;text-align:right;">100%</td>';
  rows += '</tr>';

  wrap.innerHTML = rows;
  if (headerTotal) headerTotal.textContent = "$" + totalVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
}

function _loadPhysicalMetals() {
  var tbody = document.getElementById("metals-tbody");
  if (!tbody) return;
  fetch("/api/physical-metals")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var metals = d.metals || [];
      if (metals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;color:var(--text-muted);">No physical metals yet. Click "+ Add Purchase" to start.</td></tr>';
        return;
      }
      var goldSpot = window._lastLiveData && window._lastLiveData.gold ? window._lastLiveData.gold : 0;
      var silverSpot = window._lastLiveData && window._lastLiveData.silver ? window._lastLiveData.silver : 0;
      var totalAu = 0, totalAg = 0, totalVal = 0, totalCost = 0;
      var html = "";
      metals.forEach(function(m) {
        var oz = parseFloat(m.oz) || 0;
        var cost = parseFloat(m.purchase_price) || 0;
        var isGold = m.metal && m.metal.toLowerCase() === "gold";
        var spot = isGold ? goldSpot : silverSpot;
        var val = oz * spot;
        var totalItemCost = oz * cost;
        var gl = val - totalItemCost;
        if (isGold) totalAu += oz; else totalAg += oz;
        totalVal += val;
        totalCost += totalItemCost;
        var glColor = gl >= 0 ? "var(--success)" : "var(--danger)";
        var glSign = gl >= 0 ? "" : "-";
        var noteText = (m.note || m.description || "").replace(/"/g, "&quot;");
        var rowTitle = noteText ? ' title="' + noteText + '" style="cursor:help;"' : '';
        html += '<tr' + rowTitle + '>';
        var noteHint = noteText ? '<span style="display:block;font-size:0.72rem;color:var(--text-muted);font-weight:400;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + noteText + '">' + noteText + '</span>' : '';
        html += '<td style="padding:8px 6px;text-transform:capitalize;font-weight:500;">' + (m.metal || "") + noteHint + '</td>';
        html += '<td style="padding:8px 6px;">' + (m.form || "") + '</td>';
        html += '<td style="padding:8px 6px;text-align:right;" class="mono">' + oz + '</td>';
        html += '<td style="padding:8px 6px;text-align:right;" class="mono">$' + cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
        html += '<td style="padding:8px 6px;text-align:right;" class="mono metal-spot-cell" data-metal-spot="' + (isGold ? 'gold' : 'silver') + '" data-metal-qty="' + oz + '" data-metal-cost="' + cost + '">$' + spot.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
        html += '<td style="padding:8px 6px;text-align:right;" class="mono">$' + val.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
        html += '<td style="padding:8px 6px;text-align:right;color:' + glColor + ';" class="mono">' + glSign + '$' + Math.abs(gl).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
        html += '<td style="padding:8px 6px;color:var(--text-muted);font-size:0.82rem;">' + (m.date || "") + '</td>';
        html += '<td style="padding:8px 4px;text-align:center;"><button onclick="deleteMetal(' + m.id + ')" style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:0.75rem;opacity:0.5;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.5">&#10005;</button></td>';
        html += '</tr>';
      });
      var totalGL = totalVal - totalCost;
      var tglColor = totalGL >= 0 ? "var(--success)" : "var(--danger)";
      var tglSign = totalGL >= 0 ? "" : "-";
      html += '<tr style="font-weight:600;border-top:2px solid var(--border-subtle);">';
      html += '<td style="padding:8px 6px;">Totals</td>';
      html += '<td style="padding:8px 6px;"></td>';
      html += '<td style="padding:8px 6px;text-align:right;" class="mono">Au ' + totalAu.toFixed(1) + ' / Ag ' + totalAg.toFixed(0) + '</td>';
      html += '<td style="padding:8px 6px;text-align:right;" class="mono">$' + totalCost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
      html += '<td style="padding:8px 6px;"></td>';
      html += '<td style="padding:8px 6px;text-align:right;color:#58a6ff;" class="mono">$' + totalVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
      html += '<td style="padding:8px 6px;text-align:right;color:' + tglColor + ';" class="mono">' + tglSign + '$' + Math.abs(totalGL).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
      html += '<td colspan="2"></td>';
      html += '</tr>';
      tbody.innerHTML = html;
      var elAu = document.getElementById("metals-header-au");
      var elAg = document.getElementById("metals-header-ag");
      var elTotal = document.getElementById("metals-header-total");
      var elGL = document.getElementById("metals-header-gl");
      if (elAu) elAu.textContent = totalAu.toFixed(1);
      if (elAg) elAg.textContent = totalAg.toFixed(0);
      if (elTotal) elTotal.textContent = "$" + totalVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
      if (elGL) { elGL.textContent = tglSign + "$" + Math.abs(totalGL).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}); elGL.style.color = tglColor; }
    });
}

function deleteHolding(id) {
  if (!confirm("Remove this holding?")) return;
  fetch("/api/holdings/" + id, { method: "DELETE" })
    .then(function() { _holdingsLoaded = false; loadHoldings(); });
}

function deleteMetal(id) {
  if (!confirm("Remove this metal?")) return;
  fetch("/api/physical-metals?id=" + id, { method: "DELETE" })
    .then(function() { _loadPhysicalMetals(); });
}

function saveAllHoldings() {
  var wrap = document.getElementById("holdings-table-wrap");
  if (!wrap) return;
  var allRows = wrap.querySelectorAll("tbody tr");
  var holdings = [];
  allRows.forEach(function(tr) {
    if (tr.style && tr.style.fontWeight) return;
    if (tr.querySelector("td[colspan]")) return;
    var hid = tr.getAttribute("data-hid");
    var fields = {};
    tr.querySelectorAll("input[data-field]").forEach(function(inp) {
      fields[inp.getAttribute("data-field")] = inp.value;
    });
    if (!fields.ticker || !fields.ticker.trim()) return;
    var row = {
      ticker: fields.ticker.trim().toUpperCase(),
      shares: fields.shares ? parseFloat(fields.shares) || null : null,
      bucket: fields.bucket || "",
      account: fields.account || "",
      value_override: fields.value_override ? parseFloat(fields.value_override) || null : null,
      notes: fields.notes || ""
    };
    if (hid) row.id = parseInt(hid);
    holdings.push(row);
  });
  fetch("/api/holdings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holdings: holdings })
  }).then(function(r) { return r.json(); }).then(function() {
    _holdingsLoaded = false;
    loadHoldings();
  });
}

function addHolding() {
  saveAllHoldings();
}

function toggleMetalForm() {
  var f = document.getElementById("metal-form");
  if (f) f.style.display = f.style.display === "none" ? "block" : "none";
}

function saveMetalPurchase() {
  var data = {
    metal: (document.getElementById("metal-type") || {}).value || "Gold",
    form: (document.getElementById("metal-form-desc") || {}).value || "",
    oz: parseFloat((document.getElementById("metal-qty") || {}).value) || 0,
    purchase_price: parseFloat((document.getElementById("metal-cost") || {}).value) || 0,
    date: (document.getElementById("metal-date") || {}).value || "",
    note: (document.getElementById("metal-note") || {}).value || ""
  };
  fetch("/api/physical-metals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  }).then(function() {
    toggleMetalForm();
    _loadPhysicalMetals();
  });
}

function showDivForm() {
  var f = document.getElementById("div-form");
  if (f) f.style.display = f.style.display === "none" ? "block" : "none";
}

function saveDividend() {
  /* placeholder until dividend API is built */
  showDivForm();
}

/* ═══════════════════════════════════════════════
   Settings & Integrations (Coinbase)
   ═══════════════════════════════════════════════ */

function openSettingsModal() {
  var m = document.getElementById("settings-modal");
  if (!m) return;
  m.style.display = "flex";
  _loadIntegrationStatus();
}

function closeSettingsModal() {
  var m = document.getElementById("settings-modal");
  if (m) m.style.display = "none";
}

function _loadIntegrationStatus() {
  var badge = document.getElementById("cb-status-badge");
  var connPanel = document.getElementById("cb-connected-panel");
  var setupPanel = document.getElementById("cb-setup-panel");
  fetch("/api/settings/integrations").then(function(r) { return r.json(); }).then(function(d) {
    if (d.coinbase && d.coinbase.connected) {
      if (badge) { badge.textContent = "Connected"; badge.style.background = "rgba(46,160,67,0.15)"; badge.style.color = "#3fb950"; }
      if (connPanel) connPanel.style.display = "block";
      if (setupPanel) setupPanel.style.display = "none";
      var hint = document.getElementById("cb-key-hint");
      if (hint && d.coinbase.key_hint) hint.textContent = d.coinbase.key_hint;
    } else {
      if (badge) { badge.textContent = "Not connected"; badge.style.background = "var(--bg-input)"; badge.style.color = "var(--text-muted)"; }
      if (connPanel) connPanel.style.display = "none";
      if (setupPanel) setupPanel.style.display = "block";
    }
  }).catch(function() {
    if (badge) { badge.textContent = "Error"; badge.style.color = "var(--danger)"; }
  });
}

function saveCoinbaseKeys() {
  var keyName = document.getElementById("cb-key-name");
  var privKey = document.getElementById("cb-private-key");
  var btn = document.getElementById("cb-save-btn");
  if (!keyName || !keyName.value.trim() || !privKey || !privKey.value.trim()) {
    alert("Please enter both the API Key Name and Private Key.");
    return;
  }
  if (btn) { btn.disabled = true; btn.textContent = "Connecting..."; }
  fetch("/api/settings/coinbase-keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      key_name: keyName.value.trim(),
      private_key: privKey.value.trim()
    })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      alert(d.error);
      if (btn) { btn.disabled = false; btn.textContent = "Connect & Sync"; }
      return;
    }
    keyName.value = "";
    privKey.value = "";
    syncCoinbaseNow(true);
    _loadIntegrationStatus();
  }).catch(function() {
    alert("Failed to save keys. Please try again.");
    if (btn) { btn.disabled = false; btn.textContent = "Connect & Sync"; }
  });
}

function syncCoinbaseNow(isInitial) {
  var btn = document.getElementById("cb-sync-btn");
  var status = document.getElementById("cb-sync-status");
  if (btn) { btn.disabled = true; btn.textContent = "Syncing..."; }
  if (status) { status.textContent = "Fetching balances from Coinbase..."; status.style.color = "var(--text-secondary)"; }
  fetch("/api/coinbase-sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      if (status) { status.textContent = d.error; status.style.color = "var(--danger)"; }
    } else {
      var msg = "Synced " + d.synced + " asset" + (d.synced !== 1 ? "s" : "");
      if (d.removed > 0) msg += ", removed " + d.removed;
      if (status) { status.textContent = msg; status.style.color = "var(--success)"; }
      _holdingsLoaded = false;
      if (typeof loadHoldings === "function") loadHoldings();
    }
    if (btn) { btn.disabled = false; btn.textContent = "Sync Now"; }
    if (isInitial) {
      var saveBtn = document.getElementById("cb-save-btn");
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Connect & Sync"; }
    }
  }).catch(function() {
    if (status) { status.textContent = "Sync failed. Please try again."; status.style.color = "var(--danger)"; }
    if (btn) { btn.disabled = false; btn.textContent = "Sync Now"; }
  });
}

function disconnectCoinbase() {
  if (!confirm("Disconnect Coinbase? Your crypto holdings data will remain, but auto-sync will stop.")) return;
  fetch("/api/settings/coinbase-keys", { method: "DELETE" }).then(function() {
    _loadIntegrationStatus();
    var status = document.getElementById("cb-sync-status");
    if (status) status.textContent = "";
  });
}

