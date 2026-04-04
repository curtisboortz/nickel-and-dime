/* Nickel&Dime - Sentiment gauges and history charts */
var _sentimentLoaded = false;
var _sentimentRetries = 0;
function loadSentimentGauges() {
  if (_sentimentLoaded) return;
  NDDiag.track("sentiment", "loading", "attempt " + (_sentimentRetries + 1));
  fetch("/api/sentiment")
    .then(function(r) {
      if (!r.ok) { NDDiag.track("sentiment", "error", "HTTP " + r.status); throw new Error("HTTP " + r.status); }
      return r.json();
    })
    .then(function(d) {
      if (d._error) { NDDiag.track("sentiment", "error", "Server: " + d._error); return; }
      var keys = ["stock", "crypto", "gold", "vix", "yield_curve"];
      var filled = 0;
      var missing = [];
      keys.forEach(function(k) {
        var info = d[k];
        if (!info) {
          missing.push(k);
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
        NDDiag.track("sentiment", "ok", filled + "/5 gauges" + (missing.length ? ", missing: " + missing.join(",") : ""));
      } else if (_sentimentRetries < 5) {
        NDDiag.track("sentiment", "warn", "0 gauges, retrying (" + (_sentimentRetries+1) + "/5)");
        _sentimentRetries++;
        setTimeout(loadSentimentGauges, 8000);
      } else {
        NDDiag.track("sentiment", "error", "Gave up after 5 retries, 0 gauges");
      }
    })
    .catch(function(e) {
      NDDiag.track("sentiment", "error", e.message || String(e));
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

