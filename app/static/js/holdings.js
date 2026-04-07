/* Nickel&Dime - Holdings, crypto, metals tables */

var _holdingsLoaded = false;
var _bucketOptions = [];

function _buildBucketSelect(selected, isNew) {
  selected = _normalizeBucketClient(selected);
  var sel = '<select data-field="bucket" style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;appearance:auto;">';
  if (isNew || !selected) sel += '<option value="">Class</option>';
  _bucketOptions.forEach(function(b) {
    sel += '<option value="' + b + '"' + (b === selected ? ' selected' : '') + '>' + _bucketLabel(b) + '</option>';
  });
  if (selected && _bucketOptions.indexOf(selected) === -1) {
    sel += '<option value="' + selected + '" selected>' + selected + '</option>';
  }
  sel += '<option value="__custom__">+ Custom...</option>';
  sel += '</select>';
  return sel;
}

function _handleBucketCustom(selectEl) {
  if (selectEl.value === "__custom__") {
    var custom = prompt("Enter custom category name:");
    if (custom && custom.trim()) {
      var val = custom.trim();
      if (_bucketOptions.indexOf(val) === -1) _bucketOptions.push(val);
      var opt = document.createElement("option");
      opt.value = val; opt.textContent = val; opt.selected = true;
      selectEl.insertBefore(opt, selectEl.querySelector('option[value="__custom__"]'));
    } else {
      selectEl.value = "";
    }
  }
}

var _accountsData = null;

function loadHoldings() {
  if (_holdingsLoaded) return;
  _holdingsLoaded = true;
  NDDiag.track("holdings", "loading");

  var stockWrap = document.getElementById("holdings-table-wrap");
  var cryptoWrap = document.getElementById("crypto-tbody");

  fetch("/api/normalize-buckets", { method: "POST" }).catch(function() {});

  Promise.all([
    fetch("/api/holdings").then(function(r) {
      if (!r.ok) throw new Error("Holdings API returned " + r.status);
      return r.json();
    }),
    fetch("/api/buckets").then(function(r) { return r.json(); }).catch(function() { return { standard: [], custom: [] }; })
  ]).then(function(results) {
      var d = results[0];
      var bk = results[1];
      _bucketOptions = (bk.standard || []).concat(bk.custom || []);
      _accountsData = d.accounts || [];
      _holdingsCache = d.holdings || [];
      _renderAccountWidgets(stockWrap, _accountsData, d.grand_total || 0);
      _renderCryptoHoldings(cryptoWrap, d.crypto || []);
      _loadPhysicalMetals();
      if (_fxRate !== 1) convertDisplayCurrency(_fxRate, _fxSymbol);
      NDDiag.track("holdings", "ok", (d.holdings||[]).length + " stocks, " + (d.crypto||[]).length + " crypto");
    })
    .catch(function(e) {
      if (stockWrap) stockWrap.innerHTML = '<p class="hint" style="color:var(--danger);">Failed to load holdings.</p>';
      NDDiag.track("holdings", "error", e.message || String(e));
      _holdingsLoaded = false;
    });
}

var _sortPrefs = JSON.parse(localStorage.getItem("nd-sort-prefs") || "{}");
function _saveSortPrefs() { localStorage.setItem("nd-sort-prefs", JSON.stringify(_sortPrefs)); }

var _holdingsSortKey = _sortPrefs.hk || "ticker";
var _holdingsSortDir = _sortPrefs.hd || 1;
var _holdingsCache = null;
var _holdingsWrapRef = null;

function _sortHoldingsBy(key) {
  if (_holdingsSortKey === key) {
    _holdingsSortDir *= -1;
  } else {
    _holdingsSortKey = key;
    _holdingsSortDir = 1;
  }
  _sortPrefs.hk = _holdingsSortKey; _sortPrefs.hd = _holdingsSortDir; _saveSortPrefs();
  if (_accountsData && _holdingsWrapRef) {
    _renderAccountWidgets(_holdingsWrapRef, _accountsData, 0);
  } else if (_holdingsCache && _holdingsWrapRef) {
    _renderStockHoldings(_holdingsWrapRef, _holdingsCache);
  }
}

function _acctKey(g) {
  return (g.institution_name || "") + "|" + (g.account_name || "");
}

function _getCollapseState() {
  try { return JSON.parse(localStorage.getItem("nd-acct-collapse") || "{}"); } catch(e) { return {}; }
}

function _toggleAccountCollapse(key) {
  var state = _getCollapseState();
  state[key] = !state[key];
  localStorage.setItem("nd-acct-collapse", JSON.stringify(state));
  var body = document.getElementById("acct-body-" + key.replace(/[^a-zA-Z0-9]/g, "_"));
  if (body) body.style.display = state[key] ? "none" : "";
  var arrow = document.getElementById("acct-arrow-" + key.replace(/[^a-zA-Z0-9]/g, "_"));
  if (arrow) arrow.textContent = state[key] ? "\u25B6" : "\u25BC";
}

function _buildAccountLogo(g) {
  if (g.logo_base64) {
    return '<img src="data:image/png;base64,' + g.logo_base64 + '" style="width:28px;height:28px;border-radius:6px;object-fit:contain;background:#fff;">';
  }
  var name = g.institution_name || g.account_name || "?";
  var initials = name.split(/\s+/).map(function(w) { return w[0]; }).join("").substring(0, 2).toUpperCase();
  var color = g.primary_color || "#6366f1";
  return '<div style="width:28px;height:28px;border-radius:6px;background:' + color + ';display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.7rem;color:#fff;">' + initials + '</div>';
}

function _renderAccountWidgets(wrap, accounts, grandTotal) {
  if (!wrap) return;
  _holdingsWrapRef = wrap;

  var fmtMoney = function(v) { return v ? "$" + v.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : ""; };
  var collapseState = _getCollapseState();

  if (!accounts || accounts.length === 0) {
    wrap.innerHTML = '<p class="hint">No holdings yet. Add your first holding below.</p>' + _buildAddRow("");
    return;
  }

  var html = "";
  var allGrandDayPL = 0, allGrandCost = 0, allGrandPL = 0, allGrandTotal = 0;

  accounts.forEach(function(g, gi) {
    var key = _acctKey(g);
    var safeKey = key.replace(/[^a-zA-Z0-9]/g, "_");
    var collapsed = collapseState[key] || false;

    var title = g.institution_name ? (g.institution_name + " \u2013 " + g.account_name) : g.account_name;
    var sourceBadge = g.source === "plaid" ? '<span style="font-size:0.65rem;background:rgba(99,102,241,0.15);color:#a5b4fc;padding:2px 6px;border-radius:4px;margin-left:8px;">Plaid</span>' : '';
    var countBadge = '<span style="font-size:0.72rem;color:var(--text-muted);margin-left:8px;">' + g.holdings.length + ' holding' + (g.holdings.length !== 1 ? 's' : '') + '</span>';

    html += '<div style="border:1px solid var(--border-subtle);border-radius:8px;margin-bottom:12px;overflow:hidden;">';
    html += '<div onclick="_toggleAccountCollapse(\'' + key.replace(/'/g, "\\'") + '\')" style="display:flex;align-items:center;gap:10px;padding:12px 16px;background:var(--surface-raised);cursor:pointer;user-select:none;">';
    html += '<span id="acct-arrow-' + safeKey + '" style="font-size:0.7rem;color:var(--text-muted);width:12px;">' + (collapsed ? "\u25B6" : "\u25BC") + '</span>';
    html += _buildAccountLogo(g);
    html += '<div style="flex:1;min-width:0;">';
    html += '<span style="font-weight:600;font-size:0.92rem;">' + title + '</span>' + sourceBadge + countBadge;
    html += '</div>';
    html += '<span style="font-family:var(--mono);font-weight:600;font-size:0.95rem;color:#58a6ff;">' + fmtMoney(g.subtotal) + '</span>';
    html += '</div>';

    html += '<div id="acct-body-' + safeKey + '"' + (collapsed ? ' style="display:none;"' : '') + '>';
    html += _buildAccountTable(g.holdings, g.account_name);
    html += '</div>';
    html += '</div>';

    allGrandTotal += g.subtotal;
  });

  html += _buildAddRow("");

  var gTotals = _computeGrandTotals(accounts);
  var gdColor = gTotals.dayPL >= 0 ? "var(--success)" : "var(--danger)";
  var gdSign = gTotals.dayPL >= 0 ? "+" : "";
  var gpColor = gTotals.pl >= 0 ? "var(--success)" : "var(--danger)";
  var gpSign = gTotals.pl >= 0 ? "+" : "";
  var gpPct = gTotals.cost > 0 ? (gTotals.pl / gTotals.cost) * 100 : 0;
  var gdPct = (allGrandTotal - gTotals.dayPL) > 0 ? (gTotals.dayPL / (allGrandTotal - gTotals.dayPL)) * 100 : 0;

  html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;border-top:2px solid var(--border-subtle);margin-top:8px;font-weight:700;">';
  html += '<span style="font-size:0.95rem;">Holdings Total</span>';
  html += '<div style="display:flex;gap:16px;align-items:center;">';
  html += '<span style="font-family:var(--mono);color:' + gdColor + ';font-size:0.82rem;">' + gdSign + '$' + Math.abs(gTotals.dayPL).toLocaleString(undefined,{maximumFractionDigits:0}) + ' (' + gdSign + gdPct.toFixed(2) + '%)</span>';
  html += '<span style="font-family:var(--mono);color:' + gpColor + ';font-size:0.82rem;">' + gpSign + '$' + Math.abs(gTotals.pl).toLocaleString(undefined,{maximumFractionDigits:0}) + (gTotals.cost > 0 ? ' (' + gpSign + gpPct.toFixed(1) + '%)' : '') + '</span>';
  html += '<span style="font-family:var(--mono);color:#58a6ff;font-size:1.05rem;">' + fmtMoney(allGrandTotal) + '</span>';
  html += '</div></div>';

  wrap.innerHTML = html;

  wrap.querySelectorAll('select[data-field="bucket"]').forEach(function(sel) {
    sel.addEventListener("change", function() { _handleBucketCustom(this); });
  });
}

function _computeGrandTotals(accounts) {
  var dayPL = 0, cost = 0, pl = 0;
  accounts.forEach(function(g) {
    g.holdings.forEach(function(h) {
      if (h.price && h.prev_close && h.shares) {
        dayPL += (h.price - h.prev_close) * h.shares;
      }
      var ct = (h.cost_basis && h.shares) ? h.cost_basis * h.shares : 0;
      if (ct > 0 && (h.total || 0) > 0) {
        cost += ct;
        pl += (h.total - ct);
      }
    });
  });
  return { dayPL: dayPL, cost: cost, pl: pl };
}

function _buildAccountTable(holdings, acctName) {
  var fmtMoney = function(v) { return v ? "$" + v.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : ""; };
  var inputStyle = 'style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;"';

  var sorted = holdings.slice().sort(function(a, b) {
    var aCash = (a.bucket || "").toLowerCase() === "cash" ? 1 : 0;
    var bCash = (b.bucket || "").toLowerCase() === "cash" ? 1 : 0;
    if (aCash !== bCash) return bCash - aCash;
    var k = _holdingsSortKey;
    var va, vb;
    if (k === "account" || k === "ticker" || k === "bucket" || k === "notes") {
      va = (a[k] || "").toLowerCase(); vb = (b[k] || "").toLowerCase();
      return va < vb ? -_holdingsSortDir : va > vb ? _holdingsSortDir : 0;
    }
    if (k === "pl_dollar" || k === "pl_pct") {
      var aCost = (a.cost_basis && a.shares) ? a.cost_basis * a.shares : 0;
      var bCost = (b.cost_basis && b.shares) ? b.cost_basis * b.shares : 0;
      va = aCost > 0 ? (a.total || 0) - aCost : -Infinity;
      vb = bCost > 0 ? (b.total || 0) - bCost : -Infinity;
      if (k === "pl_pct") { va = aCost > 0 ? va/aCost : -Infinity; vb = bCost > 0 ? vb/bCost : -Infinity; }
    } else if (k === "day_dollar" || k === "day_pct") {
      va = (a.price && a.prev_close && a.shares) ? (a.price - a.prev_close) * a.shares : -Infinity;
      vb = (b.price && b.prev_close && b.shares) ? (b.price - b.prev_close) * b.shares : -Infinity;
      if (k === "day_pct") {
        va = (a.price && a.prev_close) ? (a.price - a.prev_close) / a.prev_close : -Infinity;
        vb = (b.price && b.prev_close) ? (b.price - b.prev_close) / b.prev_close : -Infinity;
      }
    } else { va = a[k] || 0; vb = b[k] || 0; }
    return (va - vb) * _holdingsSortDir;
  });

  var html = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.82rem;">';
  html += '<thead><tr style="border-bottom:1px solid var(--border-subtle);">';
  html += '<th style="padding:6px;text-align:left;cursor:pointer;" onclick="_sortHoldingsBy(\'ticker\')">Ticker</th>';
  html += '<th style="padding:6px;text-align:left;cursor:pointer;" onclick="_sortHoldingsBy(\'bucket\')">Class</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'shares\')">Qty</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'cost_basis\')">Cost</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'price\')">Price</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'total\')">Total</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'day_dollar\')">Day $</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'day_pct\')">Day %</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'pl_dollar\')">Total $</th>';
  html += '<th style="padding:6px;text-align:right;cursor:pointer;" onclick="_sortHoldingsBy(\'pl_pct\')">Total %</th>';
  html += '<th style="padding:6px;">Notes</th><th style="width:28px;"></th>';
  html += '</tr></thead><tbody>';

  sorted.forEach(function(h) {
    var priceStr = h.price ? fmtMoney(h.price) : "";
    var computedTotal = (h.price && h.shares) ? h.price * h.shares : 0;
    var isOvr = h.value_override != null && h.value_override > 0;
    var totalVal = isOvr ? h.value_override : (computedTotal ? computedTotal.toFixed(2) : "");
    var totalColor = isOvr ? "color:var(--warning);" : "";
    var qtyStr = (h.shares !== null && h.shares !== undefined) ? h.shares : "";
    var muted = '<span style="color:var(--text-muted);">--</span>';
    var isCash = (h.bucket || "").toLowerCase() === "cash";

    var dayDH = muted, dayPH = isCash ? "" : muted;
    if (h.price && h.prev_close && h.shares) {
      var dd = (h.price - h.prev_close) * h.shares;
      var dp = h.prev_close > 0 ? ((h.price - h.prev_close) / h.prev_close) * 100 : 0;
      var dc = dd >= 0 ? "var(--success)" : "var(--danger)";
      var ds = dd >= 0 ? "+" : "";
      dayDH = isCash ? "" : '<span style="color:' + dc + ';font-family:var(--mono);white-space:nowrap;">' + ds + "$" + Math.abs(dd).toLocaleString(undefined,{maximumFractionDigits:0}) + '</span>';
      dayPH = isCash ? "" : '<span style="color:' + dc + ';font-family:var(--mono);white-space:nowrap;">' + ds + dp.toFixed(2) + '%</span>';
    }

    var ct = (h.cost_basis && h.shares) ? h.cost_basis * h.shares : 0;
    var cv = h.total || 0;
    var plDH = isCash ? "" : muted, plPH = isCash ? "" : muted;
    if (!isCash && ct > 0 && cv > 0) {
      var pld = cv - ct; var plp = (pld / ct) * 100;
      var plc = pld >= 0 ? "var(--success)" : "var(--danger)";
      var pls = pld >= 0 ? "+" : "";
      plDH = '<span style="color:' + plc + ';font-family:var(--mono);white-space:nowrap;">' + pls + '$' + Math.abs(pld).toLocaleString(undefined,{maximumFractionDigits:0}) + '</span>';
      plPH = '<span style="color:' + plc + ';font-family:var(--mono);white-space:nowrap;">' + pls + plp.toFixed(1) + '%</span>';
    }

    var noteVal = (h.notes || "").replace(/"/g, "&quot;");
    var isLinked = h.source === "plaid";
    var totalDisplay = totalVal ? fmtMoney(parseFloat(totalVal)) : "";
    var rCell = 'style="padding:6px;text-align:right;font-family:var(--mono);white-space:nowrap;"';

    if (isLinked) {
      html += '<tr data-hid="' + h.id + '" data-source="plaid">';
      html += '<td style="padding:6px;font-weight:600;">' + (h.ticker || "") + '<input type="hidden" data-field="ticker" value="' + (h.ticker || "") + '"><input type="hidden" data-field="account" value="' + (h.account || acctName || "") + '"></td>';
      html += '<td style="padding:4px 4px;">' + _buildBucketSelect(h.bucket || "", false) + '</td>';
      html += '<td ' + rCell + '>' + qtyStr + '</td>';
      html += '<td ' + rCell + '>' + (h.cost_basis ? fmtMoney(h.cost_basis) : "") + '</td>';
      html += '<td ' + rCell + ' style="padding:6px;text-align:right;color:var(--text-muted);font-family:var(--mono);white-space:nowrap;">' + priceStr + '</td>';
      html += '<td style="padding:6px;text-align:right;font-family:var(--mono);font-weight:600;white-space:nowrap;">' + totalDisplay + '</td>';
      html += '<td style="padding:6px;text-align:right;">' + dayDH + '</td>';
      html += '<td style="padding:6px;text-align:right;">' + dayPH + '</td>';
      html += '<td style="padding:6px;text-align:right;">' + plDH + '</td>';
      html += '<td style="padding:6px;text-align:right;">' + plPH + '</td>';
      html += '<td style="padding:6px;color:var(--text-muted);font-size:0.82rem;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + noteVal + '">' + (h.notes || "") + '</td>';
      html += '<td style="padding:4px;text-align:center;" title="Synced via Plaid"><span style="font-size:0.7rem;color:var(--text-muted);">&#128274;</span></td>';
      html += '</tr>';
    } else {
      html += '<tr data-hid="' + h.id + '" data-computed="' + computedTotal.toFixed(2) + '">';
      html += '<td style="padding:4px 6px;"><input type="text" data-field="ticker" value="' + (h.ticker || "") + '" ' + inputStyle + '><input type="hidden" data-field="account" value="' + (h.account || acctName || "") + '"></td>';
      html += '<td style="padding:4px 4px;">' + _buildBucketSelect(h.bucket || "", false) + '</td>';
      html += '<td style="padding:4px 4px;"><input type="text" data-field="shares" value="' + qtyStr + '" class="num" ' + inputStyle + '></td>';
      html += '<td style="padding:4px 4px;"><input type="text" inputmode="decimal" data-field="cost_basis" value="' + (h.cost_basis || "") + '" class="num" ' + inputStyle + '></td>';
      html += '<td style="padding:6px;text-align:right;color:var(--text-muted);font-family:var(--mono);white-space:nowrap;">' + priceStr + '</td>';
      html += '<td style="padding:4px 4px;"><input type="text" data-field="total_edit" value="' + totalVal + '" class="num" style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;' + totalColor + 'padding:5px 8px;font-size:0.82rem;width:100%;font-family:var(--mono);font-weight:600;"></td>';
      html += '<td style="padding:6px;text-align:right;">' + dayDH + '</td>';
      html += '<td style="padding:6px;text-align:right;">' + dayPH + '</td>';
      html += '<td style="padding:6px;text-align:right;">' + plDH + '</td>';
      html += '<td style="padding:6px;text-align:right;">' + plPH + '</td>';
      html += '<td style="padding:4px 4px;"><input type="text" data-field="notes" value="' + noteVal + '" title="' + noteVal + '" style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;text-overflow:ellipsis;"></td>';
      html += '<td style="padding:4px;text-align:center;"><button type="button" onclick="deleteHolding(' + h.id + ')" title="Delete" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;" onmouseover="this.style.color=\'var(--danger)\'" onmouseout="this.style.color=\'var(--text-muted)\'">&times;</button></td>';
      html += '</tr>';
    }
  });

  html += '</tbody></table></div>';
  return html;
}

function _buildAddRow(acctName) {
  var inputStyle = 'style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;"';
  var html = '<div style="overflow-x:auto;margin-top:8px;"><table style="width:100%;border-collapse:collapse;font-size:0.82rem;"><tbody>';
  html += '<tr>';
  html += '<td style="padding:4px;"><input type="text" data-field="account" placeholder="Account" value="' + (acctName || "") + '" ' + inputStyle + '></td>';
  html += '<td style="padding:4px;"><input type="text" data-field="ticker" placeholder="Ticker" style="text-transform:uppercase;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;"></td>';
  html += '<td style="padding:4px;">' + _buildBucketSelect("", true) + '</td>';
  html += '<td style="padding:4px;"><input type="text" data-field="shares" placeholder="Qty" class="num" ' + inputStyle + '></td>';
  html += '<td style="padding:4px;"><input type="text" inputmode="decimal" data-field="cost_basis" placeholder="Cost" class="num" ' + inputStyle + '></td>';
  html += '<td></td>';
  html += '<td style="padding:4px;"><input type="text" data-field="total_edit" placeholder="Total" class="num" ' + inputStyle + '></td>';
  html += '<td colspan="5"><input type="text" data-field="notes" placeholder="Notes" ' + inputStyle + '></td>';
  html += '</tr>';
  html += '</tbody></table></div>';
  return html;
}

function _renderStockHoldings(wrap, holdings) {
  _holdingsCache = holdings;
  _holdingsWrapRef = wrap;
  if (_accountsData) {
    _renderAccountWidgets(wrap, _accountsData, 0);
  }
}

function _fmtCryptoQty(qty) {
  var n = parseFloat(qty);
  if (isNaN(n)) return qty;
  if (n >= 1) return n.toLocaleString(undefined, {maximumFractionDigits: 4});
  if (n >= 0.001) return n.toFixed(6);
  return n.toFixed(6);
}

var _cryptoSortKey = _sortPrefs.ck || "symbol";
var _cryptoSortDir = _sortPrefs.cd || 1;
var _cryptoCache = null;
var _cryptoWrapRef = null;

function _sortCryptoBy(key) {
  if (_cryptoSortKey === key) { _cryptoSortDir *= -1; } else { _cryptoSortKey = key; _cryptoSortDir = 1; }
  _sortPrefs.ck = _cryptoSortKey; _sortPrefs.cd = _cryptoSortDir; _saveSortPrefs();
  if (_cryptoCache && _cryptoWrapRef) _renderCryptoHoldings(_cryptoWrapRef, _cryptoCache);
}

function deleteCrypto(id) {
  if (!confirm("Remove this crypto holding?")) return;
  fetch("/api/crypto/" + id, { method: "DELETE" })
    .then(function() { _holdingsLoaded = false; loadHoldings(); });
}

function showAddCryptoForm() {
  var wrap = document.getElementById("crypto-add-form");
  if (!wrap) return;
  if (wrap.style.display === "flex") { wrap.style.display = "none"; return; }
  wrap.style.display = "flex";
  var inp = wrap.querySelector("#crypto-add-symbol");
  if (inp) inp.focus();
}

function submitAddCrypto() {
  var symbol = (document.getElementById("crypto-add-symbol").value || "").trim().toUpperCase();
  var qty = parseFloat(document.getElementById("crypto-add-qty").value) || 0;
  var cbVal = document.getElementById("crypto-add-cb").value;
  var costBasis = cbVal ? parseFloat(cbVal) : null;
  if (!symbol) { alert("Enter a symbol (e.g. BTC, ETH, SOL)"); return; }
  if (qty <= 0) { alert("Quantity must be greater than 0"); return; }
  var btn = document.getElementById("crypto-add-btn");
  if (btn) btn.disabled = true;
  fetch("/api/crypto", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol: symbol, quantity: qty, cost_basis: costBasis })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) { alert(d.error); return; }
    document.getElementById("crypto-add-symbol").value = "";
    document.getElementById("crypto-add-qty").value = "";
    document.getElementById("crypto-add-cb").value = "";
    document.getElementById("crypto-add-form").style.display = "none";
    _holdingsLoaded = false;
    loadHoldings();
  }).catch(function(e) { alert("Failed to add crypto: " + e.message); })
    .finally(function() { if (btn) btn.disabled = false; });
}

function editCrypto(id) {
  var row = document.querySelector('.crypto-row[data-cid="' + id + '"]');
  if (!row) return;
  var cells = row.querySelectorAll("td");
  var sym = cells[0].textContent.trim();
  var oldQty = cells[1].textContent.trim().replace(/,/g, "");
  var newQty = prompt("Edit quantity for " + sym + ":", oldQty);
  if (newQty === null) return;
  var q = parseFloat(newQty);
  if (isNaN(q) || q < 0) { alert("Invalid quantity"); return; }
  fetch("/api/crypto/" + id, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantity: q })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) { alert(d.error); return; }
    _holdingsLoaded = false;
    loadHoldings();
  });
}

function _renderCryptoHoldings(wrap, crypto) {
  if (!wrap) return;
  _cryptoCache = crypto;
  _cryptoWrapRef = wrap;
  var countEl = document.getElementById("crypto-count");
  var subEl = document.getElementById("crypto-subtitle");
  var headerTotal = document.getElementById("crypto-header-total");
  if (countEl) countEl.textContent = crypto.length;
  var hasCb = crypto.some(function(c) { return c.source === "coinbase"; });
  if (subEl) subEl.textContent = hasCb ? "Synced from Coinbase - " + crypto.length + " assets" : crypto.length + " assets";

  if (crypto.length === 0) {
    wrap.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted);">No crypto holdings yet. Add manually or connect Coinbase in Settings.</td></tr>';
    return;
  }

  var totalVal = 0;
  crypto.forEach(function(c) { totalVal += (c.value || 0); });

  var sorted = crypto.slice().sort(function(a, b) {
    var k = _cryptoSortKey;
    if (k === "symbol") {
      var va = (a.symbol || "").toLowerCase(), vb = (b.symbol || "").toLowerCase();
      return va < vb ? -_cryptoSortDir : va > vb ? _cryptoSortDir : 0;
    }
    if (k === "pct") {
      return ((a.value || 0) - (b.value || 0)) * _cryptoSortDir;
    }
    return ((a[k] || 0) - (b[k] || 0)) * _cryptoSortDir;
  });

  var arrow = function(key) {
    if (_cryptoSortKey !== key) return ' <span style="opacity:0.3;">&#8597;</span>';
    return _cryptoSortDir === 1 ? ' &#9650;' : ' &#9660;';
  };
  var thL = 'style="padding:8px 10px;cursor:pointer;user-select:none;white-space:nowrap;text-align:left;"';
  var thR = 'style="padding:8px 10px;cursor:pointer;user-select:none;white-space:nowrap;text-align:right;"';
  var thead = document.getElementById("crypto-thead");
  if (thead) {
    thead.innerHTML = '<tr style="border-bottom:1px solid var(--border-subtle);">' +
      '<th ' + thL + ' onclick="_sortCryptoBy(\'symbol\')">Symbol' + arrow("symbol") + '</th>' +
      '<th ' + thR + ' onclick="_sortCryptoBy(\'quantity\')">Qty' + arrow("quantity") + '</th>' +
      '<th ' + thR + ' onclick="_sortCryptoBy(\'price\')">Price' + arrow("price") + '</th>' +
      '<th ' + thR + ' onclick="_sortCryptoBy(\'value\')">Value' + arrow("value") + '</th>' +
      '<th ' + thR + ' onclick="_sortCryptoBy(\'pct\')">%' + arrow("pct") + '</th>' +
      '<th style="width:32px;"></th></tr>';
  }

  var rows = "";
  sorted.forEach(function(c) {
    var val = c.value || 0;
    var priceStr = c.price ? fxFmt(c.price) : "-";
    var valStr = val ? fxFmt(val) : "-";
    var pctStr = totalVal > 0 ? ((val / totalVal) * 100).toFixed(1) + "%" : "";
    rows += '<tr class="crypto-row" data-cid="' + c.id + '" data-cgid="' + (c.coingecko_id || "") + '">';
    rows += '<td style="padding:8px 10px;font-weight:600;">' + c.symbol + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + _fmtCryptoQty(c.quantity) + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);color:var(--text-muted);">' + priceStr + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + valStr + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;color:var(--text-muted);">' + pctStr + '</td>';
    var isManual = (c.source || "manual") === "manual";
    rows += '<td style="padding:8px 4px;text-align:center;white-space:nowrap;">';
    if (isManual) {
      rows += '<button type="button" onclick="editCrypto(' + c.id + ')" title="Edit" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:0.85rem;padding:2px 5px;" onmouseover="this.style.color=\'var(--accent-primary)\'" onmouseout="this.style.color=\'var(--text-muted)\'">&#9998;</button>';
    }
    rows += '<button type="button" onclick="deleteCrypto(' + c.id + ')" title="Delete" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;padding:2px 5px;" onmouseover="this.style.color=\'var(--danger)\'" onmouseout="this.style.color=\'var(--text-muted)\'">&times;</button>';
    rows += '</td></tr>';
  });

  rows += '<tr style="font-weight:600;border-top:2px solid var(--border-subtle);">';
  rows += '<td style="padding:8px 10px;" colspan="3">Total</td>';
  rows += '<td style="padding:8px 10px;text-align:right;color:#58a6ff;font-family:var(--mono);">' + fxFmt(totalVal) + '</td>';
  rows += '<td style="padding:8px 10px;text-align:right;">100%</td>';
  rows += '<td></td>';
  rows += '</tr>';

  wrap.innerHTML = rows;
  if (headerTotal) headerTotal.textContent = fxFmt(totalVal);
}

var _metalsSortKey = _sortPrefs.mk || "metal";
var _metalsSortDir = _sortPrefs.md || 1;
var _metalsCache = null;

function _sortMetalsBy(key) {
  if (_metalsSortKey === key) { _metalsSortDir *= -1; } else { _metalsSortKey = key; _metalsSortDir = 1; }
  _sortPrefs.mk = _metalsSortKey; _sortPrefs.md = _metalsSortDir; _saveSortPrefs();
  if (_metalsCache) _renderMetals(_metalsCache);
}

var _metalsSpot = {};
function _loadPhysicalMetals() {
  var tbody = document.getElementById("metals-tbody");
  if (!tbody) return;
  fetch("/api/physical-metals")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      _metalsCache = d.metals || [];
      _metalsSpot = d.spot || {};
      _renderMetals(_metalsCache);
    });
}

function _renderMetals(metals) {
  var tbody = document.getElementById("metals-tbody");
  if (!tbody) return;

  if (metals.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:20px;color:var(--text-muted);">No physical metals yet. Click "+ Add Purchase" to start.</td></tr>';
    return;
  }

  var goldSpot = (_metalsSpot.gold && _metalsSpot.gold.price) || (window._lastLiveData && window._lastLiveData.gold ? window._lastLiveData.gold : 0);
  var silverSpot = (_metalsSpot.silver && _metalsSpot.silver.price) || (window._lastLiveData && window._lastLiveData.silver ? window._lastLiveData.silver : 0);
  var goldChg = (_metalsSpot.gold && _metalsSpot.gold.change_pct) || null;
  var silverChg = (_metalsSpot.silver && _metalsSpot.silver.change_pct) || null;

  var spotEl = document.getElementById("metals-spot-info");
  if (spotEl) {
    var parts = [];
    if (goldSpot) {
      var gc = goldChg != null ? (' <span style="color:' + (goldChg >= 0 ? 'var(--success)' : 'var(--danger)') + ';">(' + (goldChg >= 0 ? '+' : '') + goldChg.toFixed(2) + '%)</span>') : '';
      parts.push('Gold: ' + fxFmt(goldSpot) + '/oz' + gc);
    }
    if (silverSpot) {
      var sc = silverChg != null ? (' <span style="color:' + (silverChg >= 0 ? 'var(--success)' : 'var(--danger)') + ';">(' + (silverChg >= 0 ? '+' : '') + silverChg.toFixed(2) + '%)</span>') : '';
      parts.push('Silver: ' + fxFmt(silverSpot) + '/oz' + sc);
    }
    if (parts.length) spotEl.innerHTML = parts.join(' &nbsp;&middot;&nbsp; ');
  }

  var enriched = metals.map(function(m) {
    var oz = parseFloat(m.oz) || 0;
    var cost = parseFloat(m.purchase_price) || 0;
    var isGold = m.metal && m.metal.toLowerCase() === "gold";
    var spot = isGold ? goldSpot : silverSpot;
    var val = oz * spot;
    var totalItemCost = oz * cost;
    return { raw: m, oz: oz, cost: cost, isGold: isGold, spot: spot, val: val, totalCost: totalItemCost, gl: val - totalItemCost };
  });

  enriched.sort(function(a, b) {
    var k = _metalsSortKey;
    if (k === "metal" || k === "form" || k === "date") {
      var va = (k === "date" ? (a.raw.date || "") : (a.raw[k] || "")).toLowerCase();
      var vb = (k === "date" ? (b.raw.date || "") : (b.raw[k] || "")).toLowerCase();
      return va < vb ? -_metalsSortDir : va > vb ? _metalsSortDir : 0;
    }
    var na = k === "oz" ? a.oz : k === "cost" ? a.cost : k === "spot" ? a.spot : k === "val" ? a.val : a.gl;
    var nb = k === "oz" ? b.oz : k === "cost" ? b.cost : k === "spot" ? b.spot : k === "val" ? b.val : b.gl;
    return (na - nb) * _metalsSortDir;
  });

  var arrow = function(key) {
    if (_metalsSortKey !== key) return ' <span style="opacity:0.3;">&#8597;</span>';
    return _metalsSortDir === 1 ? ' &#9650;' : ' &#9660;';
  };
  var mthL = 'style="padding:8px 6px;cursor:pointer;user-select:none;white-space:nowrap;text-align:left;"';
  var mthR = 'style="padding:8px 6px;cursor:pointer;user-select:none;white-space:nowrap;text-align:right;"';
  var thead = document.getElementById("metals-thead");
  if (thead) {
    thead.innerHTML = '<tr>' +
      '<th ' + mthL + ' onclick="_sortMetalsBy(\'metal\')">Metal' + arrow("metal") + '</th>' +
      '<th ' + mthL + ' onclick="_sortMetalsBy(\'form\')">Form' + arrow("form") + '</th>' +
      '<th ' + mthR + ' onclick="_sortMetalsBy(\'oz\')">Qty (oz)' + arrow("oz") + '</th>' +
      '<th ' + mthR + ' onclick="_sortMetalsBy(\'cost\')">Cost/oz' + arrow("cost") + '</th>' +
      '<th ' + mthR + ' onclick="_sortMetalsBy(\'spot\')">Spot' + arrow("spot") + '</th>' +
      '<th ' + mthR + ' onclick="_sortMetalsBy(\'val\')">Value' + arrow("val") + '</th>' +
      '<th ' + mthR + ' onclick="_sortMetalsBy(\'gl\')">G/L' + arrow("gl") + '</th>' +
      '<th ' + mthL + ' onclick="_sortMetalsBy(\'date\')">Date' + arrow("date") + '</th>' +
      '<th></th></tr>';
  }

  var totalAu = 0, totalAg = 0, totalVal = 0, totalCost = 0;
  var html = "";
  enriched.forEach(function(e) {
    var m = e.raw;
    if (e.isGold) totalAu += e.oz; else totalAg += e.oz;
    totalVal += e.val;
    totalCost += e.totalCost;
    var glColor = e.gl >= 0 ? "var(--success)" : "var(--danger)";
    var glSign = e.gl >= 0 ? "" : "-";
    var noteText = (m.note || m.description || "").replace(/"/g, "&quot;");
    var rowTitle = noteText ? ' title="' + noteText + '" style="cursor:help;"' : '';
    html += '<tr' + rowTitle + '>';
    var noteHint = noteText ? '<span style="display:block;font-size:0.72rem;color:var(--text-muted);font-weight:400;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:help;" title="' + noteText + '" onclick="if(this.style.whiteSpace===\'normal\'){this.style.whiteSpace=\'nowrap\';this.style.maxWidth=\'120px\';}else{this.style.whiteSpace=\'normal\';this.style.maxWidth=\'320px\';}">' + noteText + '</span>' : '';
    html += '<td style="padding:8px 6px;text-transform:capitalize;font-weight:500;">' + (m.metal || "") + noteHint + '</td>';
    html += '<td style="padding:8px 6px;">' + (m.form || "") + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;" class="mono">' + e.oz + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;" class="mono">$' + e.cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;" class="mono metal-spot-cell" data-metal-spot="' + (e.isGold ? 'gold' : 'silver') + '" data-metal-qty="' + e.oz + '" data-metal-cost="' + e.cost + '">$' + e.spot.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;" class="mono">$' + e.val.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;color:' + glColor + ';" class="mono">' + glSign + '$' + Math.abs(e.gl).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
    html += '<td style="padding:8px 6px;color:var(--text-muted);font-size:0.82rem;">' + (m.date || "") + '</td>';
    html += '<td style="padding:8px 4px;text-align:center;"><button onclick="deleteMetal(' + m.id + ')" title="Delete" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;padding:2px 6px;border-radius:4px;" onmouseover="this.style.color=\'var(--danger)\'" onmouseout="this.style.color=\'var(--text-muted)\'">&times;</button></td>';
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
  if (!_holdingsLoaded) { alert("Holdings haven't finished loading yet."); return; }
  var allRows = wrap.querySelectorAll("tbody tr");
  var holdings = [];
  allRows.forEach(function(tr) {
    if (tr.style && tr.style.fontWeight) return;
    if (tr.querySelector("td[colspan]")) return;
    var hid = tr.getAttribute("data-hid");
    var computed = parseFloat(tr.getAttribute("data-computed")) || 0;
    var fields = {};
    tr.querySelectorAll("input[data-field], select[data-field]").forEach(function(inp) {
      fields[inp.getAttribute("data-field")] = inp.value;
    });
    if (!fields.ticker || !fields.ticker.trim()) return;
    var enteredTotal = fields.total_edit ? parseFloat(fields.total_edit) || null : null;
    var vo = null;
    if (enteredTotal && computed > 0 && Math.abs(enteredTotal - computed) > 0.01) {
      vo = enteredTotal;
    } else if (enteredTotal && !computed) {
      vo = enteredTotal;
    }
    var row = {
      ticker: fields.ticker.trim().toUpperCase(),
      shares: fields.shares ? parseFloat(fields.shares) || null : null,
      bucket: fields.bucket || "",
      account: fields.account || "",
      value_override: vo,
      cost_basis: fields.cost_basis ? parseFloat(fields.cost_basis) || null : null,
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

function deleteHolding(holdingId) {
  if (!confirm("Delete this holding?")) return;
  fetch("/api/holdings/" + holdingId, {
    method: "DELETE"
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

