/* Nickel&Dime - Economics tab: FRED charts, FedWatch, CAPE, Buffett, calendar */
/* FRED_JS_START */
/* ── FRED Economics ── */
function _fredTooltip() {
  var t = (typeof ndChartTheme === "function") ? ndChartTheme() : null;
  return t
    ? Object.assign(ndTooltipOpts(t), { yAlign: "bottom", caretPadding: 8 })
    : { yAlign: "bottom", caretPadding: 8, backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0", borderColor: "rgba(99,102,241,0.4)", borderWidth: 1, cornerRadius: 10, padding: 12 };
}
function _fredScale() {
  var t = (typeof ndChartTheme === "function") ? ndChartTheme() : null;
  return { text: t ? t.text : "#64748b", grid: t ? t.gridLight : "rgba(255,255,255,0.03)" };
}
var fredTooltipOpts = _fredTooltip();
var fredCharts = {};
function fredDateLabel(d) { return d ? d.replace(/T.*$/, "") : d; }
function fredSeries(data, id) { var e = data[id]; return (e && e.data) ? e.data : []; }
function fredLatest(arr) { for (var i = (arr && arr.length) ? arr.length - 1 : -1; i >= 0; i--) if (arr[i].value != null) return arr[i].value; return null; }
function fredLineChart(canvasId, points, label, yFmt) {
  var ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === "undefined") return;
  var labels = (points || []).map(function(p) { return fredDateLabel(p.date); });
  var values = (points || []).map(function(p) { return p.value; });
  if (fredCharts[canvasId]) {
    fredCharts[canvasId].data.labels = labels;
    fredCharts[canvasId].data.datasets[0].data = values;
    fredCharts[canvasId].update();
    return;
  }
  var yCallback = yFmt === "billions" ? function(v) { return (v/1e3).toFixed(1) + "T"; } : yFmt === "pct" ? function(v) { return v != null ? Number(v).toFixed(1) + "%" : ""; } : function(v) { return v != null ? Number(v).toLocaleString() : ""; };
  var _ft = (typeof ndChartTheme === "function") ? ndChartTheme() : null;
  var _sc = _fredScale();
  fredCharts[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels: labels, datasets: [{ label: label, data: values, borderColor: _ft ? _ft.accent : "rgba(212,160,23,0.9)", backgroundColor: "rgba(212,160,23,0.08)", fill: true, tension: 0.3, pointRadius: 0, pointHitRadius: 20, borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { display: false }, tooltip: _fredTooltip() }, scales: { x: { ticks: { color: _sc.text, maxTicksLimit: 8, font: { size: 10.5, weight: "500" }, padding: 4 }, grid: { display: false }, border: { display: false } }, y: { ticks: { color: _sc.text, callback: yCallback, font: { size: 10.5, weight: "500" }, padding: 4 }, grid: { color: _sc.grid, borderDash: [3, 3] }, border: { display: false } } } }
  });
}
function fredBarChart(canvasId, points, label, colorFn) {
  var ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === "undefined") return;
  var labels = (points || []).map(function(p) { return fredDateLabel(p.date); });
  var values = (points || []).map(function(p) { return p.value; });
  var colors = (colorFn && values) ? values.map(colorFn) : "rgba(212,160,23,0.6)";
  if (fredCharts[canvasId]) {
    fredCharts[canvasId].data.labels = labels;
    fredCharts[canvasId].data.datasets[0].data = values;
    fredCharts[canvasId].data.datasets[0].backgroundColor = colors;
    fredCharts[canvasId].update();
    return;
  }
  var _ft2 = (typeof ndChartTheme === "function") ? ndChartTheme() : null;
  var _sc2 = _fredScale();
  fredCharts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels: labels, datasets: [{ label: label, data: values, backgroundColor: colors, borderRadius: 4, borderSkipped: false }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { display: false }, tooltip: _fredTooltip() }, scales: { x: { ticks: { color: _sc2.text, maxTicksLimit: 8, font: { size: 10.5, weight: "500" }, padding: 4 }, grid: { display: false }, border: { display: false } }, y: { ticks: { color: _sc2.text, font: { size: 10.5, weight: "500" }, padding: 4 }, grid: { color: _sc2.grid, borderDash: [3, 3] }, border: { display: false } } } }
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
  if (!spendingPct.length && outlays.length && gdp.length) {
    var gdpMap = {};
    gdp.forEach(function(p) { if (p.value != null) gdpMap[fredDateLabel(p.date)] = p.value; });
    spendingPct = outlays.filter(function(p) { return p.value != null && gdpMap[fredDateLabel(p.date)]; }).map(function(p) {
      var d = fredDateLabel(p.date);
      return { date: p.date, value: (p.value / gdpMap[d]) * 100 };
    });
  }
  if (!interestPct.length && interest.length && gdp.length) {
    var gdpMap2 = {};
    gdp.forEach(function(p) { if (p.value != null) gdpMap2[fredDateLabel(p.date)] = p.value; });
    interestPct = interest.filter(function(p) { return p.value != null && gdpMap2[fredDateLabel(p.date)]; }).map(function(p) {
      var d = fredDateLabel(p.date);
      return { date: p.date, value: (p.value / gdpMap2[d]) * 100 };
    });
  }
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
    receipts.forEach(function(p) { allDates[fredDateLabel(p.date)] = true; });
    outlays.forEach(function(p) { allDates[fredDateLabel(p.date)] = true; });
    var dates = Object.keys(allDates).sort();
    var rVals = dates.map(function(d) { var p = receipts.find(function(x) { return fredDateLabel(x.date) === d; }); return p ? p.value : null; });
    var oVals = dates.map(function(d) { var p = outlays.find(function(x) { return fredDateLabel(x.date) === d; }); return p ? p.value : null; });
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
  var rawDates = cpi.map(function(p) { return p.date; });
  var labels = rawDates.map(fredDateLabel);
  var cpiV = cpi.map(function(p) { return p.value; });
  var coreV = rawDates.map(function(d) { var p = core.find(function(x) { return x.date === d; }); return p ? p.value : null; });
  var pceV = rawDates.map(function(d) { var p = pce.find(function(x) { return x.date === d; }); return p ? p.value : null; });
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
  if (!fed.length) {
    var dgs1mo = fredSeries(data, "DGS1MO");
    if (dgs1mo.length) fed = dgs1mo;
  }
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
      data: { labels: ycLabels, datasets: [{ label: "Current", data: currentRates, borderColor: "rgba(212,160,23,0.9)", backgroundColor: "rgba(212,160,23,0.1)", fill: true, tension: 0.2, pointRadius: 3, spanGaps: true }, { label: "1Y ago", data: pastRates, borderColor: "rgba(100,116,139,0.7)", borderDash: [4,2], fill: false, pointRadius: 2, spanGaps: true }] },
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
  var labels = hy.map(function(p) { return fredDateLabel(p.date); });
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
  var rawBeDates = be10.length ? be10.map(function(p) { return p.date; }) : be5.map(function(p) { return p.date; });
  var labels = rawBeDates.map(fredDateLabel);
  var be5V = rawBeDates.map(function(d) { var p = be5.find(function(x) { return x.date === d; }); return p ? p.value : null; });
  var be10V = rawBeDates.map(function(d) { var p = be10.find(function(x) { return x.date === d; }); return p ? p.value : null; });
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
  var labels = sahm.map(function(p) { return fredDateLabel(p.date); });
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
  if (!gdpGr.length) {
    var gdpRaw = fredSeries(data, "GDP");
    if (gdpRaw.length >= 2) {
      gdpGr = [];
      for (var i = 1; i < gdpRaw.length; i++) {
        var prev = gdpRaw[i - 1].value;
        var cur = gdpRaw[i].value;
        if (prev != null && cur != null && prev > 0) {
          gdpGr.push({ date: gdpRaw[i].date, value: (Math.pow(cur / prev, 4) - 1) * 100 });
        }
      }
    }
  }
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

  var _fwt = (typeof ndChartTheme === "function") ? ndChartTheme() : null;
  _fwChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors,
        borderRadius: 6,
        borderSkipped: false,
        maxBarThickness: 80
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: Object.assign(_fredTooltip(), {
          callbacks: {
            label: function(ctx) { return ctx.parsed.y.toFixed(1) + "%"; }
          }
        }),
        datalabels: false
      },
      scales: {
        x: {
          ticks: { color: _fwt ? _fwt.text : "#94a3b8", font: { size: 10.5, weight: "500" }, padding: 4 },
          grid: { display: false }, border: { display: false },
          title: { display: true, text: "Target Rate (bps)", color: _fwt ? _fwt.textMuted : "#64748b", font: { size: 10.5 } }
        },
        y: {
          min: 0, max: 110,
          ticks: { color: _fwt ? _fwt.text : "#64748b", callback: function(v) { return v <= 100 ? v + "%" : ""; }, stepSize: 20, font: { size: 10.5, weight: "500" }, padding: 4 },
          grid: { color: _fwt ? _fwt.grid : "rgba(148,163,184,0.08)", borderDash: [3, 3] },
          border: { display: false },
          title: { display: true, text: "Probability", color: _fwt ? _fwt.textMuted : "#64748b", font: { size: 10.5 } }
        }
      }
    },
    plugins: [{
      afterDatasetsDraw: function(chart) {
        var _ctx = chart.ctx;
        var _labelColor = _fwt ? _fwt.textBright : "#e2e8f0";
        chart.data.datasets[0].data.forEach(function(val, i) {
          if (val < 1) return;
          var meta = chart.getDatasetMeta(0).data[i];
          _ctx.save();
          _ctx.fillStyle = _labelColor;
          _ctx.font = "bold 10.5px sans-serif";
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
      + (d.label ? '<div class="pulse-item" style="min-width:120px;max-width:150px;"><span class="pulse-label">Valuation</span><span class="pulse-price" style="' + labelClass + 'font-size:0.82rem;">' + d.label + '</span></div>' : '');
  }
  var pts = d.history || [];
  if (!pts.length) return;
  fredCharts["cape-chart"] && fredCharts["cape-chart"].destroy();
  var ctx = document.getElementById("cape-chart");
  if (!ctx || typeof Chart === "undefined") return;
  var labels = pts.map(function(p) { return fredDateLabel(p.date); });
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
      + (d.label ? '<div class="pulse-item" style="min-width:120px;max-width:160px;"><span class="pulse-label">Valuation</span><span class="pulse-price" style="' + labelClass + 'font-size:0.82rem;">' + d.label + '</span></div>' : '');
  }
  var pts = d.history || [];
  if (!pts.length) return;
  fredCharts["buffett-chart"] && fredCharts["buffett-chart"].destroy();
  var ctx = document.getElementById("buffett-chart");
  if (!ctx || typeof Chart === "undefined") return;
  var labels = pts.map(function(p) { return fredDateLabel(p.date); });
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
  var labels = wui.map(function(p) { return fredDateLabel(p.date); });
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
  var seriesCount = Object.keys(data).length;
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
  NDDiag.track("fred", "ok", seriesCount + " series rendered");
}
var _fredObserver = null;
var _fredInited = false;
function loadFredData() {
  NDDiag.track("fred", "loading");
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
  var lt = ndIsLight();
  var thHead = lt ? "#475569" : "#94a3b8";
  var thEvent = lt ? "#1e293b" : "#e2e8f0";
  var thDay = lt ? "#334155" : "#e2e8f0";
  var thTime = lt ? "#64748b" : "#94a3b8";
  var thForecast = lt ? "#64748b" : "#94a3b8";
  var thPrev = lt ? "#94a3b8" : "#64748b";
  var thNoActual = lt ? "#94a3b8" : "#94a3b8";
  var borderHead = lt ? "rgba(0,0,0,0.08)" : "rgba(255,255,255,0.08)";
  var borderDay = lt ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.06)";
  var borderRow = lt ? "rgba(0,0,0,0.04)" : "rgba(255,255,255,0.03)";
  var impactColor = { high: "#ef4444", medium: "#f59e0b", low: lt ? "#94a3b8" : "#64748b" };
  var grouped = {};
  d.events.forEach(function(e) {
    if (!grouped[e.date]) grouped[e.date] = [];
    grouped[e.date].push(e);
  });
  var dates = Object.keys(grouped).sort();
  var html = '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">';
  html += '<thead><tr style="border-bottom:1px solid ' + borderHead + ';text-align:left;">';
  html += '<th style="padding:6px 8px;color:' + thHead + ';font-weight:600;width:32px;"></th>';
  html += '<th style="padding:6px 8px;color:' + thHead + ';font-weight:600;">Time</th>';
  html += '<th style="padding:6px 8px;color:' + thHead + ';font-weight:600;">Event</th>';
  html += '<th style="padding:6px 4px;color:' + thHead + ';font-weight:600;text-align:right;">Actual</th>';
  html += '<th style="padding:6px 4px;color:' + thHead + ';font-weight:600;text-align:right;">Forecast</th>';
  html += '<th style="padding:6px 4px;color:' + thHead + ';font-weight:600;text-align:right;">Previous</th>';
  html += '</tr></thead><tbody>';
  dates.forEach(function(dt) {
    var dayLabel = new Date(dt + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    var isToday = dt === today;
    html += '<tr><td colspan="6" style="padding:8px 8px 4px;font-weight:700;color:' + (isToday ? "var(--gold)" : thDay) + ';font-size:0.82rem;border-top:1px solid ' + borderDay + ';">' + dayLabel + (isToday ? " (Today)" : "") + '</td></tr>';
    grouped[dt].forEach(function(e) {
      var ic = impactColor[e.impact] || impactColor.low;
      var actualVal = e.actual || "-";
      var actualColor = thNoActual;
      if (e.actual && e.actual !== "-") {
        actualColor = "#22c55e";
        if (e.forecast && e.forecast !== "-") {
          var af = parseFloat(e.actual.replace(/[%KMB,]/g, ""));
          var ff = parseFloat(e.forecast.replace(/[%KMB,]/g, ""));
          if (!isNaN(af) && !isNaN(ff) && af !== ff) {
            var evLower = (e.event || "").toLowerCase();
            var higherIsBad = /inflat|cpi|pce price|core pce|ppi|jobless claim|unemploy|deficit|debt|delinquen|foreclosure|price index|import price|export price|cost|wage/.test(evLower);
            var beat = af > ff;
            if (higherIsBad) {
              actualColor = beat ? "#ef4444" : "#22c55e";
            } else {
              actualColor = beat ? "#22c55e" : "#ef4444";
            }
          }
        }
      }
      html += '<tr style="border-bottom:1px solid ' + borderRow + ';">';
      html += '<td style="padding:4px 8px;"><span style="display:inline-block;width:8px;height:8px;background:' + ic + ';border-radius:50%;"></span></td>';
      html += '<td style="padding:4px 8px;color:' + thTime + ';white-space:nowrap;">' + (e.time || "-") + '</td>';
      html += '<td style="padding:4px 8px;color:' + thEvent + ';">' + e.event + '</td>';
      html += '<td style="padding:4px 4px;text-align:right;color:' + actualColor + ';font-weight:' + (e.actual ? "600" : "400") + ';">' + actualVal + '</td>';
      html += '<td style="padding:4px 4px;text-align:right;color:' + thForecast + ';">' + (e.forecast || "-") + '</td>';
      html += '<td style="padding:4px 4px;text-align:right;color:' + thPrev + ';">' + (e.previous || "-") + '</td>';
      html += '</tr>';
    });
  });
  html += '</tbody></table>';
  body.innerHTML = html;
}
/* FRED_JS_END */
