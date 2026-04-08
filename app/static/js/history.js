/* Nickel&Dime - Portfolio history chart */
var _histChartType = "line";
function setHistoryChartType(type) {
  _histChartType = type;
  document.getElementById("hist-line-btn").classList.toggle("active", type === "line");
  document.getElementById("hist-candle-btn").classList.toggle("active", type === "candlestick");
  buildHistoryChart("total");
}
function buildHistoryChart(metric) {
  metric = metric || "total";
  NDDiag.track("history-chart", "loading", _histChartType + "/" + metric);
  var ctx = document.getElementById("history-chart");
  if (window.historyChart) window.historyChart.destroy();
  if (!ctx) { NDDiag.track("history-chart", "warn", "no canvas"); return; }

  var _todayStr = new Date().toLocaleDateString("en-CA");
  var _liveTotal = window.PORTFOLIO_TOTAL;
  if (PRICE_HISTORY_DATA.length > 0 && _liveTotal && _liveTotal > 0) {
    var _last = PRICE_HISTORY_DATA[PRICE_HISTORY_DATA.length - 1];
    if (_last.date === _todayStr) {
      _last.close = _liveTotal; _last.total = _liveTotal;
      _last.high = Math.max(_last.high || _liveTotal, _liveTotal);
      _last.low = Math.min(_last.low || _liveTotal, _liveTotal);
    } else if (_last.date < _todayStr) {
      PRICE_HISTORY_DATA.push({
        date: _todayStr, total: _liveTotal, open: _liveTotal,
        high: _liveTotal, low: _liveTotal, close: _liveTotal, gold: null, silver: null
      });
    }
  }

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

