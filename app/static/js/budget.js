/* Nickel&Dime - Budget, transactions, spending, auto-refresh, command palette */
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
  var fxR = (typeof _fxRate !== "undefined") ? _fxRate : 1;
  var fxS = (typeof _fxSymbol !== "undefined") ? _fxSymbol : "$";
  var nw = document.getElementById("net-worth-counter");
  if (nw && typeof d.total === "number") {
    nw.dataset.target = d.total;
    var _nwConverted = d.total * fxR;
    if (typeof ndCountUp === "function" && nw.dataset.ndCurrent) {
      ndCountUp(nw, _nwConverted, { prefix: fxS, decimals: 2, duration: 700 });
    } else {
      nw.dataset.ndCurrent = _nwConverted;
      nw.textContent = fxS + _nwConverted.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    }
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
    var dc = d.daily_change * fxR;
    var sign = dc >= 0 ? "+" : "";
    heroChange.textContent = sign + fxS + Math.abs(dc).toLocaleString(undefined, {maximumFractionDigits:0}) + " (" + sign + d.daily_change_pct.toFixed(1) + "%)";
    heroChange.className = "hero-change " + (dc >= 0 ? "pos" : "neg");
    heroChange.dataset.fxUsd = sign + "$" + Math.abs(d.daily_change).toLocaleString(undefined, {maximumFractionDigits:0}) + " (" + sign + d.daily_change_pct.toFixed(1) + "%)";
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
    var canAnimate = typeof ndCountUp === "function" && el.dataset.ndCurrent;
    if (entry.fmt === "dollar0") {
      if (canAnimate) ndCountUp(el, v, { prefix: "$", decimals: 0, duration: 500 });
      else { el.dataset.ndCurrent = v; el.textContent = "$" + v.toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0}); }
    } else if (entry.fmt === "dollar2") {
      if (canAnimate) ndCountUp(el, v, { prefix: "$", decimals: 2, duration: 500 });
      else { el.dataset.ndCurrent = v; el.textContent = "$" + v.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}); }
    } else if (entry.fmt === "nodollar2") {
      if (canAnimate) ndCountUp(el, v, { prefix: "", decimals: 2, duration: 500 });
      else { el.dataset.ndCurrent = v; el.textContent = v.toFixed(2); }
    } else if (entry.fmt === "pct") {
      el.textContent = v.toFixed(2) + "%";
    } else if (entry.fmt === "raw2") {
      el.textContent = v.toFixed(2);
    } else if (entry.fmt === "raw1") {
      el.textContent = v.toFixed(1);
    }
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

/* Theme is managed by theme.js -- toggleTheme() is defined there */

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
var TRANSFER_CATS = ["Transfer"];
var _budgetDataLoaded = false;
function _initBudgetListeners() {
  if (_budgetDataLoaded) return;
  _budgetDataLoaded = true;
  fetch("/api/budget-data")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      TRANSACTIONS = d.transactions || [];
      BUDGET_LIMITS = d.budget_limits || {};
      BUDGET_CATS = d.budget_cats || [];
      TRANSFER_CATS = d.transfer_categories || ["Transfer"];
      var incomeInput = document.getElementById("budget-income-input");
      if (incomeInput && d.budget && d.budget.monthly_income) {
        incomeInput.value = d.budget.monthly_income;
      }
      var wrap = document.getElementById("budget-categories-wrap");
      if (wrap && d.budget && d.budget.categories) {
        _renderBudgetCategories(d.budget.categories);
      }
      renderTxns();
      renderSpendingBreakdown();
      buildSpendingChart();
    })
    .catch(function() { _budgetDataLoaded = false; });
}
function _renderBudgetCategories(categories) {
  var wrap = document.getElementById("budget-categories-wrap");
  if (!wrap) return;
  if (!categories || categories.length === 0) {
    wrap.innerHTML = '<p class="hint" style="padding:12px 0;">No budget categories configured yet. Save to create defaults.</p>';
    return;
  }
  var html = '<div style="display:flex;flex-direction:column;gap:8px;margin-top:12px;">';
  categories.forEach(function(c, i) {
    html += '<div style="display:flex;align-items:center;gap:8px;">';
    html += '<input type="text" class="budget-cat-name" data-idx="' + i + '" value="' + (c.name || "") + '" style="flex:1;font-size:0.85rem;" placeholder="Category name">';
    html += '<span class="hint" style="font-size:0.78rem;white-space:nowrap;">$</span>';
    html += '<input type="number" class="budget-cat-limit num" data-idx="' + i + '" value="' + (c.limit || 0) + '" style="width:100px;font-size:0.85rem;" min="0" placeholder="Limit">';
    html += '<button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;color:var(--danger);" onclick="this.parentElement.remove()">x</button>';
    html += '</div>';
  });
  html += '</div>';
  html += '<button type="button" class="secondary" style="margin-top:8px;padding:4px 12px;font-size:0.75rem;" onclick="_addBudgetCategory()">+ Add Category</button>';
  wrap.innerHTML = html;
}
function _addBudgetCategory() {
  var wrap = document.getElementById("budget-categories-wrap");
  if (!wrap) return;
  var container = wrap.querySelector("div");
  if (!container) return;
  var idx = container.children.length;
  var row = document.createElement("div");
  row.style.cssText = "display:flex;align-items:center;gap:8px;";
  row.innerHTML = '<input type="text" class="budget-cat-name" data-idx="' + idx + '" value="" style="flex:1;font-size:0.85rem;" placeholder="Category name">'
    + '<span class="hint" style="font-size:0.78rem;white-space:nowrap;">$</span>'
    + '<input type="number" class="budget-cat-limit num" data-idx="' + idx + '" value="0" style="width:100px;font-size:0.85rem;" min="0" placeholder="Limit">'
    + '<button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;color:var(--danger);" onclick="this.parentElement.remove()">x</button>';
  container.appendChild(row);
  row.querySelector("input").focus();
}
function saveBudget() {
  var btn = document.querySelector('[onclick="saveBudget()"]');
  var incomeInput = document.getElementById("budget-income-input");
  var income = parseFloat(incomeInput ? incomeInput.value : 0) || 0;
  var names = document.querySelectorAll(".budget-cat-name");
  var limits = document.querySelectorAll(".budget-cat-limit");
  var categories = [];
  names.forEach(function(n, i) {
    var name = n.value.trim();
    if (!name) return;
    var limit = parseFloat(limits[i] ? limits[i].value : 0) || 0;
    categories.push({ name: name, limit: limit });
  });
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Saving...";
  }
  fetch("/api/budget-data", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ monthly_income: income, categories: categories })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    if (d.success) {
      if (btn) {
        btn.textContent = "Saved";
        btn.style.background = "var(--success)";
        setTimeout(function() {
          btn.textContent = "Save Budget";
          btn.style.background = "";
          btn.disabled = false;
        }, 2000);
      }
      _budgetDataLoaded = false;
      _initBudgetListeners();
    } else {
      if (btn) {
        btn.textContent = "Error — try again";
        btn.style.background = "var(--danger)";
        setTimeout(function() {
          btn.textContent = "Save Budget";
          btn.style.background = "";
          btn.disabled = false;
        }, 2500);
      }
    }
  })
  .catch(function() {
    if (btn) {
      btn.textContent = "Error — try again";
      btn.style.background = "var(--danger)";
      setTimeout(function() {
        btn.textContent = "Save Budget";
        btn.style.background = "";
        btn.disabled = false;
      }, 2500);
    }
  });
}
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
    var isXfer = t.is_transfer || TRANSFER_CATS.indexOf(t.category) !== -1;
    var catLabel = t.category + (isXfer ? ' <span style="font-size:0.68rem;color:var(--text-muted);font-style:italic;">(excluded)</span>' : '');
    return "<tr><td class='mono'>"+t.date+"</td><td>"+catLabel+"</td><td class='mono'>$"+parseFloat(t.amount).toFixed(2)+"</td><td class='hint'>"+( t.note||"")+"</td></tr>";
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

  var byExpenseCat = {};
  var incomeTxns = [];
  var transferTxns = [];
  var totalExpenses = 0;
  var totalIncome = 0;
  var totalTransfers = 0;
  monthTxns.forEach(function(t) {
    var amt = parseFloat(t.amount) || 0;
    var cat = t.category || "Other";
    var isIncome = amt < 0 || t.type === "income" || cat === "Income";
    var isTransfer = !isIncome && (t.is_transfer || TRANSFER_CATS.indexOf(cat) !== -1);
    if (isIncome) {
      incomeTxns.push(t);
      totalIncome += Math.abs(amt);
    } else if (isTransfer) {
      transferTxns.push(t);
      totalTransfers += Math.abs(amt);
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

  // ── Transfers section (excluded from spending) ──
  if (transferTxns.length > 0) {
    var transferSorted = transferTxns.slice().sort(function(a,b) { return b.date.localeCompare(a.date); });
    var expenseCats = BUDGET_CATS.filter(function(c) { return TRANSFER_CATS.indexOf(c) === -1 && c !== "Income"; });
    if (expenseCats.indexOf("Other") === -1) expenseCats.push("Other");
    html += '<div class="spend-row">';
    html += '  <div class="spend-header" style="background:rgba(148,163,184,0.06);">';
    html += '    <span class="spend-chevron">&#9654;</span>';
    html += '    <span class="spend-cat" style="color:var(--text-muted);">';
    html += '      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:4px;"><path d="M7 16l-4-4 4-4"/><path d="M17 8l4 4-4 4"/><line x1="3" y1="12" x2="21" y2="12"/></svg>';
    html += '      Transfers (not counted as spending)';
    html += '    </span>';
    html += '    <div class="spend-amounts">';
    html += '      <span style="color:var(--text-muted);font-family:var(--mono);font-size:0.82rem;">$' + totalTransfers.toLocaleString(undefined, {minimumFractionDigits:2}) + '</span>';
    html += '      <span class="spend-budget">' + transferTxns.length + ' transaction' + (transferTxns.length > 1 ? 's' : '') + '</span>';
    html += '    </div>';
    html += '    <div style="flex:0 0 120px;"></div>';
    html += '  </div>';
    html += '  <div class="spend-details">';
    html += '    <table><thead><tr><th>Date</th><th>Description</th><th style="text-align:right">Amount</th><th style="text-align:right;width:140px;">Recategorize</th></tr></thead><tbody>';
    transferSorted.forEach(function(t) {
      var desc = t.description || t.note || "\u2014";
      var amt = Math.abs(parseFloat(t.amount));
      var opts = '<option value="">Transfer</option>';
      expenseCats.forEach(function(c) {
        opts += '<option value="' + c + '">' + c + '</option>';
      });
      html += '<tr><td class="mono">' + t.date + '</td><td>' + desc + '</td>';
      html += '<td class="mono" style="text-align:right">$' + amt.toFixed(2) + '</td>';
      html += '<td style="text-align:right"><select class="transfer-recat" data-txn-id="' + t.id + '" style="padding:3px 6px;font-size:0.75rem;background:var(--card-bg);color:var(--text-primary);border:1px solid var(--border-subtle);border-radius:4px;">' + opts + '</select></td>';
      html += '</tr>';
    });
    html += '    </tbody></table>';
    html += '    <p class="hint" style="padding:6px 0 0;font-size:0.72rem;">Not all transfers are internal. If a transfer is actually an expense (rent via Venmo, etc.), recategorize it above.</p>';
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

  // ── Summary: Income / Expenses / Transfers / Net Cash Flow ──
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
  if (totalTransfers > 0) {
    html += '<div style="display:flex;justify-content:space-between;width:100%;color:var(--text-muted);font-size:0.82rem;">';
    html += '  <span>Transfers (excluded)</span>';
    html += '  <span class="mono">$' + totalTransfers.toLocaleString(undefined, {minimumFractionDigits:2}) + '</span>';
    html += '</div>';
  }
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
  // Transfer recategorization
  container.querySelectorAll(".transfer-recat").forEach(function(sel) {
    sel.addEventListener("change", function() {
      var newCat = this.value;
      var txnId = this.dataset.txnId;
      if (!newCat || !txnId) return;
      fetch("/api/transactions/" + txnId, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: newCat })
      })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.success) {
          for (var i = 0; i < TRANSACTIONS.length; i++) {
            if (TRANSACTIONS[i].id == txnId) {
              TRANSACTIONS[i].category = newCat;
              TRANSACTIONS[i].is_transfer = false;
              break;
            }
          }
          renderSpendingBreakdown();
          buildSpendingChart();
        }
      });
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
        ndSoftReload();
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
        ndSoftReload();
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
  var months = {};
  TRANSACTIONS.forEach(function(t) {
    var cat = t.category || "Other";
    if (t.is_transfer || TRANSFER_CATS.indexOf(cat) !== -1) return;
    var m = t.date ? t.date.substring(0,7) : "unknown";
    if (!months[m]) months[m] = {};
    months[m][cat] = (months[m][cat]||0) + (parseFloat(t.amount)||0);
  });
  var labels = Object.keys(months).sort().slice(-6);
  var cats = BUDGET_CATS.length ? BUDGET_CATS.filter(function(c) { return TRANSFER_CATS.indexOf(c) === -1; }) : [];
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
