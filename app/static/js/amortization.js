/* Nickel&Dime — Loan Amortization Calculator */

var _amortMode = "fixed";
var _amortChart = null;
var _amortSchedule = [];
var _amortPage = 0;
var _AMORT_PAGE_SIZE = 24;

/* ── Mode Switching ── */

function amortSetMode(mode) {
  _amortMode = mode;
  document.querySelectorAll(".amort-mode-btn").forEach(function(b) {
    b.classList.toggle("active", b.getAttribute("data-mode") === mode);
  });
  document.getElementById("amort-fixed-inputs").style.display = mode === "fixed" ? "" : "none";
  document.getElementById("amort-arm-inputs").style.display = mode === "arm" ? "" : "none";
  document.getElementById("amort-refi-inputs").style.display = mode === "refi" ? "" : "none";
  _amortClearOutput();
}

function _amortClearOutput() {
  var out = document.getElementById("amort-output");
  if (out) out.style.display = "none";
  if (_amortChart) { _amortChart.destroy(); _amortChart = null; }
  _amortSchedule = [];
  _amortPage = 0;
}

/* ── Main Entry Point ── */

function amortCalc() {
  _amortClearOutput();
  if (_amortMode === "fixed") _amortRunFixed();
  else if (_amortMode === "arm") _amortRunARM();
  else if (_amortMode === "refi") _amortRunRefi();
}

/* ── Fixed-Rate Calculator ── */

function _amortRunFixed() {
  var principal = _amortNum("amort-amount");
  var rate = _amortNum("amort-rate");
  var termYears = _amortNum("amort-term");
  var extra = _amortNum("amort-extra");
  if (!principal || !rate || !termYears) return _amortError("Please fill in loan amount, rate, and term.");

  var termMonths = Math.round(termYears * 12);
  var schedule = _calcFixed(principal, rate, termMonths, extra);
  _amortSchedule = schedule;

  var baseSchedule = extra > 0 ? _calcFixed(principal, rate, termMonths, 0) : null;
  _renderOutput(schedule, baseSchedule, "fixed");
}

function _calcFixed(principal, annualRate, termMonths, extraPayment) {
  var r = annualRate / 100 / 12;
  var schedule = [];
  var balance = principal;

  var basePayment;
  if (r === 0) {
    basePayment = principal / termMonths;
  } else {
    basePayment = principal * (r * Math.pow(1 + r, termMonths)) / (Math.pow(1 + r, termMonths) - 1);
  }

  var totalInterest = 0;
  var totalExtra = 0;

  for (var m = 1; m <= termMonths && balance > 0.01; m++) {
    var interestPmt = balance * r;
    var principalPmt = Math.min(basePayment - interestPmt, balance);
    var extraPmt = Math.min(extraPayment || 0, balance - principalPmt);
    balance -= (principalPmt + extraPmt);
    if (balance < 0) balance = 0;
    totalInterest += interestPmt;
    totalExtra += extraPmt;

    schedule.push({
      month: m,
      payment: Math.round((principalPmt + interestPmt + extraPmt) * 100) / 100,
      principal: Math.round(principalPmt * 100) / 100,
      interest: Math.round(interestPmt * 100) / 100,
      extra: Math.round(extraPmt * 100) / 100,
      balance: Math.round(balance * 100) / 100,
      rate: annualRate,
    });
  }

  schedule._summary = {
    monthlyPayment: Math.round(basePayment * 100) / 100,
    totalInterest: Math.round(totalInterest * 100) / 100,
    totalCost: Math.round((principal + totalInterest) * 100) / 100,
    totalExtra: Math.round(totalExtra * 100) / 100,
    actualMonths: schedule.length,
    originalMonths: termMonths,
  };

  return schedule;
}

/* ── ARM Calculator ── */

function _amortRunARM() {
  var principal = _amortNum("amort-arm-amount");
  var initialRate = _amortNum("amort-arm-rate");
  var termYears = _amortNum("amort-arm-term");
  var fixedYears = _amortNum("amort-arm-fixed-period");
  var adjInterval = _amortNum("amort-arm-adj-interval") || 12;
  var rateAdj = _amortNum("amort-arm-rate-adj");
  var rateCap = _amortNum("amort-arm-rate-cap");
  var extra = _amortNum("amort-arm-extra");
  if (!principal || !initialRate || !termYears || !fixedYears)
    return _amortError("Please fill in all required ARM fields.");

  var termMonths = Math.round(termYears * 12);
  var fixedMonths = Math.round(fixedYears * 12);
  var schedule = _calcARM(principal, initialRate, termMonths, fixedMonths, adjInterval, rateAdj, rateCap, extra);
  _amortSchedule = schedule;

  var baseSchedule = _calcFixed(principal, initialRate, termMonths, 0);
  _renderOutput(schedule, baseSchedule, "arm");
}

function _calcARM(principal, initialRate, termMonths, fixedMonths, adjInterval, rateAdj, rateCap, extraPayment) {
  var schedule = [];
  var balance = principal;
  var currentRate = initialRate;
  var totalInterest = 0;
  var totalExtra = 0;
  var remainingMonths = termMonths;

  for (var m = 1; m <= termMonths && balance > 0.01; m++) {
    if (m > fixedMonths && (m - fixedMonths - 1) % adjInterval === 0 && m !== fixedMonths + 1 || m === fixedMonths + 1) {
      if (m > fixedMonths) {
        currentRate = Math.min(currentRate + rateAdj, rateCap || 999);
      }
    }

    var r = currentRate / 100 / 12;
    remainingMonths = termMonths - m + 1;

    var basePayment;
    if (r === 0) {
      basePayment = balance / remainingMonths;
    } else {
      basePayment = balance * (r * Math.pow(1 + r, remainingMonths)) / (Math.pow(1 + r, remainingMonths) - 1);
    }

    var interestPmt = balance * r;
    var principalPmt = Math.min(basePayment - interestPmt, balance);
    var extraPmt = Math.min(extraPayment || 0, balance - principalPmt);
    balance -= (principalPmt + extraPmt);
    if (balance < 0) balance = 0;
    totalInterest += interestPmt;
    totalExtra += extraPmt;

    schedule.push({
      month: m,
      payment: Math.round((principalPmt + interestPmt + extraPmt) * 100) / 100,
      principal: Math.round(principalPmt * 100) / 100,
      interest: Math.round(interestPmt * 100) / 100,
      extra: Math.round(extraPmt * 100) / 100,
      balance: Math.round(balance * 100) / 100,
      rate: Math.round(currentRate * 1000) / 1000,
    });
  }

  schedule._summary = {
    monthlyPayment: schedule.length > 0 ? schedule[0].payment - (schedule[0].extra || 0) : 0,
    totalInterest: Math.round(totalInterest * 100) / 100,
    totalCost: Math.round((principal + totalInterest) * 100) / 100,
    totalExtra: Math.round(totalExtra * 100) / 100,
    actualMonths: schedule.length,
    originalMonths: termMonths,
    initialRate: initialRate,
    maxRate: schedule.length > 0 ? Math.max.apply(null, schedule.map(function(s) { return s.rate; })) : initialRate,
  };

  return schedule;
}

/* ── Refinance Comparison ── */

function _amortRunRefi() {
  var curBalance = _amortNum("amort-refi-balance");
  var curRate = _amortNum("amort-refi-cur-rate");
  var curRemainYears = _amortNum("amort-refi-cur-remain");
  var newRate = _amortNum("amort-refi-new-rate");
  var newTermYears = _amortNum("amort-refi-new-term");
  var closingCosts = _amortNum("amort-refi-closing") || 0;
  if (!curBalance || !curRate || !curRemainYears || !newRate || !newTermYears)
    return _amortError("Please fill in all refinance fields.");

  var curMonths = Math.round(curRemainYears * 12);
  var newMonths = Math.round(newTermYears * 12);

  var curSchedule = _calcFixed(curBalance, curRate, curMonths, 0);
  var newSchedule = _calcFixed(curBalance, newRate, newMonths, 0);

  var curTotal = curSchedule._summary.totalCost;
  var newTotal = newSchedule._summary.totalCost + closingCosts;
  var monthlySavings = curSchedule._summary.monthlyPayment - newSchedule._summary.monthlyPayment;

  var breakEvenMonth = 0;
  if (monthlySavings > 0 && closingCosts > 0) {
    breakEvenMonth = Math.ceil(closingCosts / monthlySavings);
  }

  var refiResult = {
    current: curSchedule._summary,
    new: newSchedule._summary,
    closingCosts: closingCosts,
    monthlySavings: Math.round(monthlySavings * 100) / 100,
    totalSavings: Math.round((curTotal - newTotal) * 100) / 100,
    breakEvenMonth: breakEvenMonth,
    curSchedule: curSchedule,
    newSchedule: newSchedule,
  };

  _renderRefiOutput(refiResult);
}

/* ── Render Output (Fixed & ARM) ── */

function _renderOutput(schedule, baseSchedule, mode) {
  var out = document.getElementById("amort-output");
  out.style.display = "";

  var s = schedule._summary;
  var summaryEl = document.getElementById("amort-summary");
  var payoffLabel = Math.floor(s.actualMonths / 12) + "y " + (s.actualMonths % 12) + "m";
  var html = "";
  html += _amortStatCard("Monthly Payment", _amortFmt(s.monthlyPayment));
  html += _amortStatCard("Total Interest", _amortFmt(s.totalInterest));
  html += _amortStatCard("Total Cost", _amortFmt(s.totalCost));
  html += _amortStatCard("Payoff", payoffLabel);

  if (s.totalExtra > 0 && baseSchedule) {
    var bs = baseSchedule._summary;
    var savedInterest = bs.totalInterest - s.totalInterest;
    var savedMonths = bs.actualMonths - s.actualMonths;
    html += _amortStatCard("Interest Saved", _amortFmt(savedInterest), "success");
    html += _amortStatCard("Months Saved", savedMonths + " months", "success");
  }

  if (mode === "arm" && s.maxRate) {
    html += _amortStatCard("Initial Rate", s.initialRate + "%");
    html += _amortStatCard("Max Rate Hit", s.maxRate + "%");
  }

  summaryEl.innerHTML = html;

  _renderAmortChart(schedule);
  _amortPage = 0;
  _renderAmortTable(schedule);
}

function _renderRefiOutput(result) {
  var out = document.getElementById("amort-output");
  out.style.display = "";

  var summaryEl = document.getElementById("amort-summary");
  var html = "";
  html += _amortStatCard("Current Payment", _amortFmt(result.current.monthlyPayment));
  html += _amortStatCard("New Payment", _amortFmt(result.new.monthlyPayment));
  html += _amortStatCard("Monthly Savings", _amortFmt(result.monthlySavings), result.monthlySavings > 0 ? "success" : "danger");
  html += _amortStatCard("Total Savings", _amortFmt(result.totalSavings), result.totalSavings > 0 ? "success" : "danger");
  html += _amortStatCard("Closing Costs", _amortFmt(result.closingCosts));
  html += _amortStatCard("Break-Even", result.breakEvenMonth > 0 ? result.breakEvenMonth + " months" : "Immediate");
  html += _amortStatCard("Current Total Interest", _amortFmt(result.current.totalInterest));
  html += _amortStatCard("New Total Interest", _amortFmt(result.new.totalInterest));
  summaryEl.innerHTML = html;

  _renderRefiChart(result);

  _amortSchedule = result.newSchedule;
  _amortPage = 0;
  _renderAmortTable(result.newSchedule);
}

/* ── Chart ── */

function _renderAmortChart(schedule) {
  var canvas = document.getElementById("amort-chart");
  if (!canvas || typeof Chart === "undefined") return;
  if (_amortChart) { _amortChart.destroy(); _amortChart = null; }

  var labels = [];
  var principalData = [];
  var interestData = [];
  var step = schedule.length > 120 ? 3 : 1;

  for (var i = 0; i < schedule.length; i += step) {
    var row = schedule[i];
    labels.push(row.month);
    principalData.push(row.principal);
    interestData.push(row.interest);
  }

  _amortChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Principal",
          data: principalData,
          backgroundColor: "rgba(52,211,153,0.7)",
          borderRadius: 1,
          order: 2,
        },
        {
          label: "Interest",
          data: interestData,
          backgroundColor: "rgba(212,160,23,0.7)",
          borderRadius: 1,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return ctx.dataset.label + ": $" + ctx.parsed.y.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          title: { display: true, text: "Month", color: "#64748b", font: { size: 11 } },
          ticks: { color: "#64748b", maxTicksLimit: 15 },
          grid: { color: "rgba(255,255,255,0.03)" },
        },
        y: {
          stacked: true,
          title: { display: true, text: "Payment ($)", color: "#64748b", font: { size: 11 } },
          ticks: {
            color: "#64748b",
            callback: function(v) { return "$" + v.toLocaleString(); },
          },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
      },
    },
  });
}

function _renderRefiChart(result) {
  var canvas = document.getElementById("amort-chart");
  if (!canvas || typeof Chart === "undefined") return;
  if (_amortChart) { _amortChart.destroy(); _amortChart = null; }

  var maxMonths = Math.max(result.curSchedule.length, result.newSchedule.length);
  var labels = [];
  var curCumulative = [];
  var newCumulative = [];
  var curSum = 0;
  var newSum = result.closingCosts;

  for (var m = 0; m < maxMonths; m++) {
    labels.push(m + 1);
    if (m < result.curSchedule.length) curSum += result.curSchedule[m].payment;
    if (m < result.newSchedule.length) newSum += result.newSchedule[m].payment;
    curCumulative.push(Math.round(curSum));
    newCumulative.push(Math.round(newSum));
  }

  _amortChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Current Loan",
          data: curCumulative,
          borderColor: "#f87171",
          backgroundColor: "rgba(248,113,113,0.1)",
          fill: false,
          tension: 0.3,
          pointRadius: 0,
        },
        {
          label: "Refinanced Loan",
          data: newCumulative,
          borderColor: "#34d399",
          backgroundColor: "rgba(52,211,153,0.1)",
          fill: false,
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return ctx.dataset.label + ": $" + ctx.parsed.y.toLocaleString();
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Month", color: "#64748b", font: { size: 11 } },
          ticks: { color: "#64748b", maxTicksLimit: 15 },
          grid: { color: "rgba(255,255,255,0.03)" },
        },
        y: {
          title: { display: true, text: "Cumulative Cost ($)", color: "#64748b", font: { size: 11 } },
          ticks: {
            color: "#64748b",
            callback: function(v) { return "$" + v.toLocaleString(); },
          },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
      },
    },
  });
}

/* ── Schedule Table ── */

function _renderAmortTable(schedule) {
  var tbody = document.getElementById("amort-schedule-tbody");
  if (!tbody) return;
  var start = _amortPage * _AMORT_PAGE_SIZE;
  var end = Math.min(start + _AMORT_PAGE_SIZE, schedule.length);
  var hasRate = _amortMode === "arm";
  var html = "";

  for (var i = start; i < end; i++) {
    var row = schedule[i];
    html += "<tr>";
    html += "<td>" + row.month + "</td>";
    html += '<td class="mono" style="text-align:right">' + _amortFmt(row.payment) + "</td>";
    html += '<td class="mono" style="text-align:right">' + _amortFmt(row.principal) + "</td>";
    html += '<td class="mono" style="text-align:right">' + _amortFmt(row.interest) + "</td>";
    if (row.extra > 0) {
      html += '<td class="mono" style="text-align:right;color:var(--success)">' + _amortFmt(row.extra) + "</td>";
    } else {
      html += '<td class="mono" style="text-align:right;color:var(--text-muted)">—</td>';
    }
    if (hasRate) {
      html += '<td class="mono" style="text-align:right">' + row.rate + "%</td>";
    }
    html += '<td class="mono" style="text-align:right">' + _amortFmt(row.balance) + "</td>";
    html += "</tr>";
  }

  tbody.innerHTML = html;

  var rateHeader = document.getElementById("amort-rate-th");
  if (rateHeader) rateHeader.style.display = hasRate ? "" : "none";

  var info = document.getElementById("amort-page-info");
  if (info) {
    var totalPages = Math.ceil(schedule.length / _AMORT_PAGE_SIZE);
    info.textContent = "Page " + (_amortPage + 1) + " of " + totalPages + " (" + schedule.length + " payments)";
  }

  var prevBtn = document.getElementById("amort-prev-btn");
  var nextBtn = document.getElementById("amort-next-btn");
  if (prevBtn) prevBtn.disabled = _amortPage === 0;
  if (nextBtn) nextBtn.disabled = end >= schedule.length;
}

function amortPagePrev() {
  if (_amortPage > 0) { _amortPage--; _renderAmortTable(_amortSchedule); }
}

function amortPageNext() {
  if ((_amortPage + 1) * _AMORT_PAGE_SIZE < _amortSchedule.length) { _amortPage++; _renderAmortTable(_amortSchedule); }
}

/* ── Helpers ── */

function _amortNum(id) {
  var el = document.getElementById(id);
  if (!el) return 0;
  var v = parseFloat(el.value);
  return isNaN(v) ? 0 : v;
}

function _amortFmt(v) {
  if (typeof fxFmt === "function") return fxFmt(v, 2);
  return "$" + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function _amortStatCard(label, value, color) {
  var c = color === "success" ? "var(--success)" : color === "danger" ? "var(--danger)" : "var(--text-primary)";
  return '<div class="amort-stat">' +
    '<div class="amort-stat-label">' + label + "</div>" +
    '<div class="amort-stat-value" style="color:' + c + '">' + value + "</div>" +
    "</div>";
}

function _amortError(msg) {
  var out = document.getElementById("amort-output");
  if (out) {
    out.style.display = "";
    document.getElementById("amort-summary").innerHTML =
      '<div style="grid-column:1/-1;color:var(--danger);font-size:0.85rem;">' + _esc(msg) + "</div>";
  }
}
