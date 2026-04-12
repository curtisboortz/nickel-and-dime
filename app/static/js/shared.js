/* Nickel&Dime - Shared utilities, diagnostics, currency, globals */
/* Core chart building, data fetching, and UI interactions */

/* ── Pro-gate helper ── */
function ndCheckProResponse(response) {
  if (response.status === 403) {
    return response.json().then(function(d) {
      if (d && d.upgrade) {
        var t = document.createElement("div");
        t.className = "toast";
        t.style.background = "rgba(212,160,23,0.15)";
        t.style.color = "var(--accent-primary)";
        t.style.borderColor = "rgba(212,160,23,0.3)";
        t.innerHTML = 'This feature requires <strong>Pro</strong>. <a href="/billing/pricing" style="color:var(--accent-primary);text-decoration:underline;margin-left:6px;">Upgrade</a>';
        document.body.appendChild(t);
        setTimeout(function() { t.remove(); }, 6000);
      }
      return Promise.reject(d);
    });
  }
  return response;
}

/* ── Diagnostic Logger ── */
var NDDiag = (function() {
  var _log = [];
  var _widgetStatus = {};
  var _start = Date.now();
  function _ts() { return ((Date.now() - _start) / 1000).toFixed(2) + "s"; }

  function track(widget, status, detail) {
    var entry = { widget: widget, status: status, detail: detail || "", time: _ts(), ts: Date.now() };
    _log.push(entry);
    _widgetStatus[widget] = status;
    if (status === "error") {
      console.error("[ND:" + widget + "] " + (detail || "unknown error"));
    } else if (status === "warn") {
      console.warn("[ND:" + widget + "] " + (detail || ""));
    } else {
      console.log("[ND:" + widget + "] " + status + (detail ? " - " + detail : ""));
    }
  }

  function summary() {
    var ok = 0, err = 0, warn = 0, pending = 0;
    var widgets = Object.keys(_widgetStatus);
    widgets.forEach(function(w) {
      var s = _widgetStatus[w];
      if (s === "ok" || s === "loaded") ok++;
      else if (s === "error") err++;
      else if (s === "warn") warn++;
      else pending++;
    });
    return { total: widgets.length, ok: ok, errors: err, warnings: warn, pending: pending, widgets: Object.assign({}, _widgetStatus) };
  }

  function getLog() { return _log.slice(); }

  function report() {
    var s = summary();
    var payload = { widgets: s.widgets, errors: _log.filter(function(e) { return e.status === "error"; }), url: window.location.href };
    fetch("/api/client-errors", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).catch(function() {});
  }

  function showPanel() {
    var existing = document.getElementById("nd-diag-panel");
    if (existing) { existing.remove(); return; }
    var s = summary();
    var panel = document.createElement("div");
    panel.id = "nd-diag-panel";
    panel.style.cssText = "position:fixed;top:10px;right:10px;width:420px;max-height:80vh;overflow:auto;background:rgba(9,9,11,0.97);border:1px solid rgba(255,255,255,0.15);border-radius:12px;padding:16px;z-index:99999;font-family:monospace;font-size:12px;color:#e2e8f0;box-shadow:0 8px 32px rgba(0,0,0,0.5);";
    var statusColor = s.errors > 0 ? "#f87171" : s.warnings > 0 ? "#fbbf24" : "#34d399";
    var html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">';
    html += '<span style="font-size:14px;font-weight:600;">System Diagnostics</span>';
    html += '<span style="cursor:pointer;font-size:18px;opacity:0.6;" onclick="document.getElementById(\'nd-diag-panel\').remove();">&times;</span></div>';
    html += '<div style="display:flex;gap:12px;margin-bottom:12px;">';
    html += '<div style="background:rgba(52,211,153,0.15);padding:6px 12px;border-radius:6px;"><span style="color:#34d399;font-weight:600;">' + s.ok + '</span> OK</div>';
    html += '<div style="background:rgba(248,113,113,0.15);padding:6px 12px;border-radius:6px;"><span style="color:#f87171;font-weight:600;">' + s.errors + '</span> Errors</div>';
    html += '<div style="background:rgba(251,191,36,0.15);padding:6px 12px;border-radius:6px;"><span style="color:#fbbf24;font-weight:600;">' + s.warnings + '</span> Warn</div></div>';
    html += '<div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:8px;">';
    Object.keys(s.widgets).forEach(function(w) {
      var st = s.widgets[w];
      var c = st === "ok" || st === "loaded" ? "#34d399" : st === "error" ? "#f87171" : st === "warn" ? "#fbbf24" : "#94a3b8";
      html += '<div style="display:flex;justify-content:space-between;padding:3px 0;"><span>' + w + '</span><span style="color:' + c + ';">' + st + '</span></div>';
    });
    html += '</div>';
    var errors = _log.filter(function(e) { return e.status === "error"; });
    if (errors.length > 0) {
      html += '<div style="border-top:1px solid rgba(255,255,255,0.1);margin-top:8px;padding-top:8px;"><div style="color:#f87171;font-weight:600;margin-bottom:4px;">Errors (' + errors.length + ')</div>';
      errors.slice(-10).forEach(function(e) {
        html += '<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05);"><span style="color:#94a3b8;">[' + e.time + ']</span> <span style="color:#fbbf24;">' + e.widget + '</span>: ' + (e.detail || "").substring(0, 120) + '</div>';
      });
      html += '</div>';
    }
    html += '<div style="margin-top:12px;display:flex;gap:8px;">';
    html += '<button onclick="NDDiag.report();this.textContent=\'Sent!\'" style="background:rgba(99,102,241,0.2);border:1px solid rgba(99,102,241,0.4);color:#818cf8;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:11px;">Send Report</button>';
    html += '<button onclick="fetch(\'/api/diag\').then(r=>r.json()).then(d=>{var w=window.open(\'\',\'_blank\');w.document.write(\'<pre>\'+JSON.stringify(d,null,2)+\'</pre>\');})" style="background:rgba(52,211,153,0.2);border:1px solid rgba(52,211,153,0.4);color:#34d399;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:11px;">Server Health</button>';
    html += '</div>';
    panel.innerHTML = html;
    document.body.appendChild(panel);
  }

  return { track: track, summary: summary, getLog: getLog, report: report, showPanel: showPanel };
})();

function _esc(s) {
  if (typeof s !== "string") return String(s == null ? "" : s);
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function _skeletonRows(rows, cols) {
  var html = "";
  for (var r = 0; r < (rows || 5); r++) {
    html += '<tr>';
    for (var c = 0; c < (cols || 4); c++) {
      var w = c === 0 ? "60%" : (30 + Math.random() * 40) + "%";
      html += '<td style="padding:10px 10px;"><div class="skeleton" style="height:14px;width:' + w + ';"></div></td>';
    }
    html += '</tr>';
  }
  return '<table style="width:100%;">' + html + '</table>';
}

function _skeletonCard() {
  return '<div style="display:flex;flex-direction:column;gap:12px;padding:8px 0;">' +
    '<div class="skeleton" style="height:20px;width:35%;"></div>' +
    '<div class="skeleton" style="height:14px;width:80%;"></div>' +
    '<div class="skeleton" style="height:14px;width:65%;"></div>' +
    '<div class="skeleton" style="height:180px;width:100%;border-radius:8px;"></div>' +
    '</div>';
}

window.addEventListener("error", function(e) {
  NDDiag.track("global", "error", (e.filename || "") + ":" + (e.lineno || "") + " " + (e.message || ""));
});
window.addEventListener("unhandledrejection", function(e) {
  NDDiag.track("global", "error", "Unhandled promise: " + (e.reason ? (e.reason.message || String(e.reason)) : "unknown"));
});

/* ── Animated Number Counter ── */
function ndCountUp(el, target, opts) {
  if (!el) return;
  opts = opts || {};
  var duration = opts.duration || 600;
  var decimals = typeof opts.decimals === "number" ? opts.decimals : 2;
  var prefix = opts.prefix || "";
  var start = parseFloat(el.dataset.ndCurrent || "0") || 0;
  if (Math.abs(target - start) < 0.01) return;
  el.dataset.ndCurrent = target;

  var direction = target > start ? "up" : "down";
  el.classList.remove("value-tick-up", "value-tick-down");

  var startTime = null;
  function step(ts) {
    if (!startTime) startTime = ts;
    var progress = Math.min((ts - startTime) / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    var current = start + (target - start) * eased;
    el.textContent = prefix + current.toLocaleString(undefined, {
      minimumFractionDigits: decimals, maximumFractionDigits: decimals
    });
    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      if (opts.tickClass !== false) {
        el.classList.add(direction === "up" ? "value-tick-up" : "value-tick-down");
        setTimeout(function() { el.classList.remove("value-tick-up", "value-tick-down"); }, 450);
      }
    }
  }
  requestAnimationFrame(step);
}

/* ── Top Loading Bar ── */
(function() {
  var bar = document.createElement("div");
  bar.id = "nd-loading-bar";
  document.body.appendChild(bar);

  var overlay = document.createElement("div");
  overlay.id = "nd-page-transition";
  document.body.appendChild(overlay);
})();

var _ndLoadingCount = 0;
function ndLoadingStart() {
  _ndLoadingCount++;
  var bar = document.getElementById("nd-loading-bar");
  if (bar) {
    bar.classList.remove("done");
    bar.classList.add("active");
  }
}
function ndLoadingDone() {
  _ndLoadingCount = Math.max(0, _ndLoadingCount - 1);
  if (_ndLoadingCount > 0) return;
  var bar = document.getElementById("nd-loading-bar");
  if (bar) {
    bar.classList.remove("active");
    bar.classList.add("done");
    setTimeout(function() { bar.classList.remove("done"); }, 500);
  }
}

/* ── Soft Reload: view-transition-wrapped page reload ── */
function ndSoftReload() {
  var overlay = document.getElementById("nd-page-transition");
  if (overlay) {
    overlay.classList.add("active");
    setTimeout(function() { location.reload(); }, 160);
  } else {
    location.reload();
  }
}

/* ── Auto-inject CSRF token on every mutating fetch ── */
(function() {
  var _origFetch = window.fetch;
  window.fetch = function(url, opts) {
    opts = opts || {};
    var method = (opts.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
      var meta = document.querySelector('meta[name="csrf-token"]');
      var token = meta ? meta.getAttribute("content") : "";
      if (token) {
        if (opts.headers instanceof Headers) {
          if (!opts.headers.has("X-CSRFToken")) opts.headers.set("X-CSRFToken", token);
        } else {
          opts.headers = opts.headers || {};
          if (!opts.headers["X-CSRFToken"]) opts.headers["X-CSRFToken"] = token;
        }
      }
    }
    return _origFetch.call(window, url, opts);
  };
})();

/* ── Canonical category color palette ── */
var _ND_DEFAULT_COLORS = {
  "Equities": "#34d399",
  "International": "#2dd4bf",
  "Fixed Income": "#60a5fa",
  "Cash": "#94a3b8",
  "Alternatives": "#818cf8",
  "Crypto": "#a78bfa",
  "Real Assets": "#f59e0b",
  "Gold": "#eab308",
  "Silver": "#a8a29e",
  "Real Estate": "#06b6d4",
  "Art": "#e879f9",
  "Managed Blend": "#4ade80",
  "Retirement Blend": "#86efac",
  "Commodities": "#fb923c",
  "Private Equity": "#c084fc",
  "Venture Capital": "#e879f9"
};
window.ND_CATEGORY_COLORS = {};
var _ndColorFallback = ["#f87171","#fbbf24","#2dd4bf","#a3e635","#f472b6","#fb923c","#84cc16"];
function _ndHashStr(s) { var h = 0; for (var i = 0; i < s.length; i++) h = ((h << 5) - h) + s.charCodeAt(i); return h; }

function ndCategoryColor(label) {
  if (window.ND_CATEGORY_COLORS[label]) return window.ND_CATEGORY_COLORS[label];
  if (_ND_DEFAULT_COLORS[label]) return _ND_DEFAULT_COLORS[label];
  return _ndColorFallback[Math.abs(_ndHashStr(label)) % _ndColorFallback.length];
}

function ndDefaultCategoryColor(label) {
  return _ND_DEFAULT_COLORS[label] || _ndColorFallback[Math.abs(_ndHashStr(label)) % _ndColorFallback.length];
}

/* ── Centralized Chart Theme ── */
function ndIsLight() {
  return document.documentElement.classList.contains("light");
}

function ndChartTheme() {
  var light = ndIsLight();
  return {
    text:        light ? "#6e7490" : "#94a3b8",
    textMuted:   light ? "#9098b0" : "#64748b",
    textBright:  light ? "#1b1e2f" : "#f1f5f9",
    grid:        light ? "rgba(0,0,0,0.05)" : "rgba(255,255,255,0.05)",
    gridLight:   light ? "rgba(0,0,0,0.025)" : "rgba(255,255,255,0.025)",
    border:      light ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.08)",
    tooltipBg:   light ? "#ffffff" : "rgba(15,15,20,0.96)",
    tooltipText: light ? "#1b1e2f" : "#f1f5f9",
    tooltipBody: light ? "#414665" : "#cbd5e1",
    tooltipBorder: light ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.06)",
    cardBg:      light ? "#ffffff" : "#161619",
    accent:      light ? "#b8860b" : "#d4a017",
    accentLight: light ? "#d4a017" : "#f5c842",
    success:     light ? "#16a34a" : "#34d399",
    danger:      light ? "#dc2626" : "#f87171",
    warning:     light ? "#d97706" : "#fbbf24",
    candleUp:    light ? "#16a34a" : "#34d399",
    candleDown:  light ? "#dc2626" : "#f87171",
    candleFlat:  light ? "#6e7490" : "#94a3b8",
    donutBorder: light ? "#ffffff" : "rgba(9,9,11,0.85)",
    light: light,
  };
}

function ndTooltipOpts(theme) {
  theme = theme || ndChartTheme();
  return {
    backgroundColor: theme.tooltipBg,
    titleColor: theme.tooltipText,
    bodyColor: theme.tooltipBody,
    borderColor: theme.tooltipBorder,
    borderWidth: 1,
    padding: 12,
    cornerRadius: 10,
    displayColors: true,
    boxPadding: 5,
    titleFont: { size: 12, weight: "600" },
    bodyFont: { size: 11.5 },
    caretSize: 6,
    caretPadding: 8,
  };
}

function ndScaleOpts(theme, axis) {
  theme = theme || ndChartTheme();
  var isX = axis === "x";
  return {
    ticks: { color: theme.text, font: { size: 10.5, weight: "500" }, padding: 6 },
    grid: {
      color: isX ? theme.gridLight : theme.grid,
      drawBorder: false,
      lineWidth: 1,
      borderDash: isX ? [] : [3, 3],
    },
    border: { display: false },
  };
}

function ndGradient(ctx, hex, height) {
  height = height || 300;
  var r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  var light = ndIsLight();
  var grad = ctx.createLinearGradient(0, 0, 0, height);
  grad.addColorStop(0, "rgba("+r+","+g+","+b+","+(light ? 0.12 : 0.22)+")");
  grad.addColorStop(0.6, "rgba("+r+","+g+","+b+","+(light ? 0.03 : 0.06)+")");
  grad.addColorStop(1, "rgba("+r+","+g+","+b+",0)");
  return grad;
}

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
  if (btn) btn.classList.add("spinning");
  ndLoadingStart();

  fetch("/api/refresh", { method: "POST" })
    .then(function(r) { return r.json(); })
    .then(function() {
      return fetch("/api/live-data").then(function(r) { return r.json(); });
    })
    .then(function(d) {
      if (btn) btn.classList.remove("spinning");
      ndLoadingDone();
      if (typeof applyLiveDataToDOM === "function") applyLiveDataToDOM(d);
      _flashUpdatedPulseCards();
    })
    .catch(function() {
      if (btn) btn.classList.remove("spinning");
      ndLoadingDone();
    });
};

var FX_RATES = {};
var BASE_CURRENCY = localStorage.getItem("wos-currency") || "USD";
var CURRENCY_SYMBOLS = { "USD":"$", "EUR":"\u20ac", "GBP":"\u00a3", "JPY":"\u00a5", "CAD":"C$", "AUD":"A$", "CHF":"Fr", "CNY":"\u00a5", "INR":"\u20b9", "KRW":"\u20a9", "MXN":"MX$", "BRL":"R$", "SEK":"kr", "NOK":"kr", "NZD":"NZ$" };
var _fxRate = 1;
var _fxSymbol = "$";
(function() {
  var sel = document.getElementById("currency-selector");
  if (sel) sel.value = BASE_CURRENCY;
  if (BASE_CURRENCY !== "USD") fetchFxAndConvert(BASE_CURRENCY);
})();
function changeCurrency(currency) {
  localStorage.setItem("wos-currency", currency);
  BASE_CURRENCY = currency;
  if (currency === "USD") {
    _fxRate = 1; _fxSymbol = "$";
    ndSoftReload();
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
        _fxRate = d.rate;
        _fxSymbol = CURRENCY_SYMBOLS[currency] || currency + " ";
        convertDisplayCurrency(d.rate, _fxSymbol);
      }
    }).catch(function(e) { console.error("[FX] fetch failed:", e); });
}
function fxFmt(usdVal, decimals) {
  if (typeof decimals === "undefined") decimals = 2;
  var v = usdVal * _fxRate;
  return _fxSymbol + v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
function _fxConvertDollarText(el) {
  var text = el.textContent.trim();
  var m = text.match(/^([+-]?)[\s]*\$([\d,]+\.?\d*)/);
  if (!m) return;
  if (!el.dataset.fxUsd) el.dataset.fxUsd = text;
  var sign = m[1] || "";
  var num = parseFloat(m[2].replace(/,/g, ""));
  if (isNaN(num)) return;
  var converted = num * _fxRate;
  var dec = text.indexOf(".") >= 0 ? 2 : 0;
  el.textContent = sign + _fxSymbol + converted.toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
}
function convertDisplayCurrency(rate, symbol) {
  _fxRate = rate;
  _fxSymbol = symbol;

  var nw = document.getElementById("net-worth-counter");
  if (nw) {
    var usdVal = parseFloat(nw.dataset.target) || 0;
    nw.textContent = symbol + (usdVal * rate).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  var hero = document.getElementById("hero-change-badge");
  if (hero && hero.dataset.fxUsd) {
    _fxConvertDollarText(hero);
  } else if (hero) {
    var ht = hero.textContent;
    var hm = ht.match(/([+-]?)\$([\d,]+)/);
    if (hm) {
      hero.dataset.fxUsd = ht;
      var hval = parseFloat(hm[2].replace(/,/g, "")) * rate;
      var rest = ht.substring(ht.indexOf("("));
      hero.textContent = hm[1] + symbol + Math.round(hval).toLocaleString() + " " + rest;
    }
  }

  document.querySelectorAll("[data-pulse-price]").forEach(function(el) {
    var pid = el.getAttribute("data-pulse-price");
    if (pid === "dxy" || pid === "vix" || pid === "au_ag" || pid === "gold_oil" || pid === "tnx_10y" || pid === "tnx_2y") return;
    if (pid && pid.indexOf("custom-") === 0) {
      if (el.textContent.indexOf("$") === -1) return;
    }
    if (!el.dataset.fxUsd) el.dataset.fxUsd = el.textContent;
    var orig = el.dataset.fxUsd;
    var pm = orig.match(/^\$([\d,]+\.?\d*)/);
    if (pm) {
      var pv = parseFloat(pm[1].replace(/,/g, "")) * rate;
      var pdec = orig.indexOf(".") >= 0 ? 2 : 0;
      el.textContent = symbol + pv.toLocaleString(undefined, { minimumFractionDigits: pdec, maximumFractionDigits: pdec });
    }
  });

  document.querySelectorAll("#holdings-table-wrap td, #crypto-tbody td, #metals-tbody td, .alloc-table td, .goal-card .mono, #budget-stats .mono, #monthly-inv-table td").forEach(function(el) {
    if (el.querySelector("input, button, select")) return;
    _fxConvertDollarText(el);
  });

  document.querySelectorAll("#holdings-table-wrap span, #crypto-tbody span, #metals-tbody span").forEach(function(el) {
    _fxConvertDollarText(el);
  });

  document.querySelectorAll(".bal-total, .balances-grand-total, #balances-total").forEach(function(el) {
    _fxConvertDollarText(el);
  });

  document.querySelectorAll("#crypto-total-value, #metals-total-value, #metals-gl").forEach(function(el) {
    _fxConvertDollarText(el);
  });
}

/* ── Background price refresh on page load ── */
(function() {
  function _startLongPoll() {
    var enabled = document.getElementById("auto-enabled") && document.getElementById("auto-enabled").checked;
    var intervalSec = parseInt((document.getElementById("auto-interval") && document.getElementById("auto-interval").value) || 60);
    if (enabled !== false && intervalSec >= 15) startPeriodicLivePoll(intervalSec);
  }
  ndLoadingStart();
  fetch("/api/live-data").then(function(r) { return r.json(); }).then(function(d) {
    if (typeof applyLiveDataToDOM === "function") applyLiveDataToDOM(d);
    ndLoadingDone();
  }).catch(function() { ndLoadingDone(); });
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

