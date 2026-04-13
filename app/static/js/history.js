/* Nickel&Dime - Portfolio history chart */
function _histDateTs(d) {
  if (!d) return 0;
  if (d.length === 10) return new Date(d + "T12:00:00").getTime();
  return new Date(d).getTime();
}
var _histChartType = "line";
var _histRange = "all";

function _histAggregateOHLC(data, range) {
  if (range !== "1d") return null;
  var bucketMs = 3600000; // 1-hour candles

  var buckets = {};
  for (var i = 0; i < data.length; i++) {
    var r = data[i];
    var val = r.close || r.total;
    if (!val) continue;
    var ts = _histDateTs(r.date);
    var key = Math.floor(ts / bucketMs) * bucketMs;
    if (!buckets[key]) {
      buckets[key] = { o: val, h: val, l: val, c: val, x: key };
    } else {
      var b = buckets[key];
      b.h = Math.max(b.h, val);
      b.l = Math.min(b.l, val);
      b.c = val;
    }
  }
  var keys = Object.keys(buckets).sort(function(a, b) { return +a - +b; });
  var result = keys.map(function(k) { return buckets[k]; });

  for (var j = 1; j < result.length; j++) {
    result[j].o = result[j - 1].c;
    result[j].l = Math.min(result[j].l, result[j].o);
    result[j].h = Math.max(result[j].h, result[j].o);
  }
  return result;
}

function _histTimeUnit(range, pointCount) {
  switch (range) {
    case "1d": return "hour";
    case "1w": return "day";
    case "1m": return "day";
    case "3m": return pointCount > 90 ? "week" : "day";
    case "1y": return "week";
    case "3y": case "5y": return "month";
    case "all": return pointCount > 365 ? "month" : (pointCount > 90 ? "week" : "day");
    default: return "day";
  }
}

function _updateHistPnL() {
  var el = document.getElementById("hist-pnl-badge");
  if (!el) return;
  var data = window.PRICE_HISTORY_DATA;
  if (!data || data.length < 2) { el.textContent = ""; return; }
  var first = data[0];
  var last = data[data.length - 1];
  var startVal = first.close || first.total;
  var endVal = last.close || last.total;
  if (!startVal || !endVal) { el.textContent = ""; return; }
  var change = endVal - startVal;
  var pct = (change / startVal) * 100;
  var sign = change >= 0 ? "+" : "";
  var _t = ndChartTheme();
  var color = change >= 0 ? _t.success : _t.danger;
  el.style.color = color;
  el.textContent = sign + "$" + Math.abs(change).toLocaleString(undefined, {maximumFractionDigits: 0})
    + " (" + sign + pct.toFixed(1) + "%)";
}

function setHistoryChartType(type) {
  _histChartType = type;
  document.getElementById("hist-line-btn").classList.toggle("active", type === "line");
  document.getElementById("hist-candle-btn").classList.toggle("active", type === "candlestick");
  buildHistoryChart("total");
}

function setHistoryRange(range) {
  _histRange = range;
  var btns = document.querySelectorAll(".chart-range-btn");
  for (var i = 0; i < btns.length; i++) {
    btns[i].classList.toggle("active", btns[i].getAttribute("data-range") === range);
  }
  var tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  fetch("/api/portfolio-history?range=" + encodeURIComponent(range) + "&tz=" + encodeURIComponent(tz))
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d && d.history) {
        window.PRICE_HISTORY_DATA = d.history;
        buildHistoryChart("total");
      }
    })
    .catch(function(e) {
      if (typeof NDDiag !== "undefined") NDDiag.track("history-range", "error", e.message || String(e));
    });
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
    var aggregated = _histAggregateOHLC(PRICE_HISTORY_DATA, _histRange);
    var ohlcData;
    if (aggregated && aggregated.length >= 2) {
      ohlcData = aggregated;
    } else {
      ohlcData = PRICE_HISTORY_DATA.map(function(r) {
        return {
          x: _histDateTs(r.date),
          o: r.open || r.total,
          h: r.high || r.total,
          l: r.low || r.total,
          c: r.close || r.total,
        };
      });
      for (var ci = 1; ci < ohlcData.length; ci++) {
        ohlcData[ci].o = ohlcData[ci - 1].c;
        ohlcData[ci].l = Math.min(ohlcData[ci].l, ohlcData[ci].o);
        ohlcData[ci].h = Math.max(ohlcData[ci].h, ohlcData[ci].o);
      }
    }
    var _t = ndChartTheme();
    window.historyChart = new Chart(ctx, {
      type: "candlestick",
      data: {
        datasets: [{
          label: "Portfolio Value",
          data: ohlcData,
          backgroundColors: { up: _t.candleUp, down: _t.candleDown, unchanged: _t.candleFlat },
          borderColors: { up: _t.candleUp, down: _t.candleDown, unchanged: _t.candleFlat },
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
            if (_histRange === "1d") {
              dStr += "  " + dt.toLocaleTimeString(undefined, {hour:"numeric", minute:"2-digit"});
            }
            var f = function(v) { return "$" + v.toLocaleString(undefined, {maximumFractionDigits:0}); };
            var chg = d.c - d.o;
            var color = chg >= 0 ? _t.success : _t.danger;
            el.innerHTML = '<span style="color:' + _t.textBright + '">' + dStr + '</span>'
              + '&ensp;O: ' + f(d.o) + '&ensp;H: ' + f(d.h) + '&ensp;L: ' + f(d.l)
              + '&ensp;<span style="color:' + color + '">C: ' + f(d.c) + '</span>';
            el.style.opacity = "1";
          } }
        },
        scales: {
          x: Object.assign(ndScaleOpts(_t, "x"), { type: "time", time:{ unit: _histTimeUnit(_histRange, PRICE_HISTORY_DATA.length), tooltipFormat:"MMM d, yyyy" }, ticks:{ maxTicksLimit:8, color:_t.text, font:{size:10.5, weight:"500"}, padding:6 } }),
          y: Object.assign(ndScaleOpts(_t, "y"), { ticks:{ color:_t.text, font:{size:10.5, weight:"500"}, padding:6, callback: function(v) { return "$" + (v/1000).toFixed(0) + "K"; } } })
        }
      }
    });
  } else {
    // Line mode using close/total values with proper time-based x-axis
    var pointData = PRICE_HISTORY_DATA.map(function(r) { return { x: _histDateTs(r.date), y: r.close || r.total }; });
    var fmt = function(v) { return v != null ? "$" + v.toLocaleString(undefined, {maximumFractionDigits:0}) : "N/A"; };
    var validData = pointData.filter(function(p) { return p.y != null && isFinite(p.y); });
    var vals = validData.map(function(p) { return p.y; });
    var dataMin = vals.length ? Math.min.apply(null, vals) : 0;
    var dataMax = vals.length ? Math.max.apply(null, vals) : 0;
    var padding = dataMin === dataMax ? Math.max(dataMax * 0.02, 500) : Math.max((dataMax - dataMin) * 0.15, dataMax * 0.005);
    var _t = ndChartTheme();
    var _gradFill = ndGradient(ctx.getContext("2d"), _t.accent, ctx.parentElement ? ctx.parentElement.offsetHeight : 260);
    window.historyChart = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [{ label: "Portfolio Value", data: pointData, borderColor: _t.accent, backgroundColor: _gradFill, fill: true, tension: 0.38, pointRadius: PRICE_HISTORY_DATA.length < 30 ? 3 : 0, pointHoverRadius: 5, pointHoverBackgroundColor: _t.accent, pointBackgroundColor: _t.accent, borderWidth: 2.2 }]
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
            try {
              var _dt = new Date(dp.raw.x);
              dStr = _dt.toLocaleDateString(undefined, {month:"short", day:"numeric", year:"numeric"});
              if (_histRange === "1d") {
                dStr += "  " + _dt.toLocaleTimeString(undefined, {hour:"numeric", minute:"2-digit"});
              }
            } catch(e){}
            if (r && r.open) {
              el.innerHTML = '<span style="color:' + _t.textBright + '">' + dStr + '</span>'
                + '&ensp;' + fmt(val)
                + '&ensp;<span style="color:' + _t.textMuted + '">(' + fmt(r.low) + ' \u2013 ' + fmt(r.high) + ')</span>';
            } else {
              el.innerHTML = '<span style="color:' + _t.textBright + '">' + dStr + '</span>&ensp;' + fmt(val);
            }
            el.style.opacity = "1";
          } }
        },
        scales: {
          x: Object.assign(ndScaleOpts(_t, "x"), { type: "time", time: { unit: _histTimeUnit(_histRange, PRICE_HISTORY_DATA.length), tooltipFormat: "yyyy-MM-dd" }, ticks:{ maxTicksLimit:8, color:_t.text, font:{size:10.5, weight:"500"}, padding:6 } }),
          y: Object.assign(ndScaleOpts(_t, "y"), { min: Math.floor((dataMin - padding) / 1000) * 1000, max: Math.ceil((dataMax + padding) / 1000) * 1000, ticks:{ color:_t.text, font:{size:10.5, weight:"500"}, padding:6, callback: function(v) { return "$" + (v/1000).toFixed(0) + "K"; } } })
        }
      }
    });
  }
  _updateHistPnL();
}
