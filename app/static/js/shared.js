/* Nickel&Dime - Shared utilities, diagnostics, currency, globals */
/* Nickel&Dime — Dashboard JavaScript */
/* Core chart building, data fetching, and UI interactions */

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
  fetch("/api/live-data").then(function(r) { return r.json(); }).then(function(d) { if (typeof applyLiveDataToDOM === "function") applyLiveDataToDOM(d); }).catch(function() {});
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

