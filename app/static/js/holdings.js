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

function loadHoldings() {
  if (_holdingsLoaded) return;
  _holdingsLoaded = true;
  NDDiag.track("holdings", "loading");

  var stockWrap = document.getElementById("holdings-table-wrap");
  var cryptoWrap = document.getElementById("crypto-tbody");

  fetch("/api/normalize-buckets", { method: "POST" }).catch(function() {});

  Promise.all([
    fetch("/api/holdings").then(function(r) { return r.json(); }),
    fetch("/api/buckets").then(function(r) { return r.json(); }).catch(function() { return { standard: [], custom: [] }; })
  ]).then(function(results) {
      var d = results[0];
      var bk = results[1];
      _bucketOptions = (bk.standard || []).concat(bk.custom || []);
      _renderStockHoldings(stockWrap, d.holdings || []);
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
  if (_holdingsCache && _holdingsWrapRef) {
    _renderStockHoldings(_holdingsWrapRef, _holdingsCache);
  }
}

function _renderStockHoldings(wrap, holdings) {
  if (!wrap) return;
  _holdingsCache = holdings;
  _holdingsWrapRef = wrap;
  var fmtMoney = function(v) { return v ? "$" + v.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : ""; };
  var inputStyle = 'style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;"';

  var sorted = holdings.slice().sort(function(a, b) {
    var aCash = (a.bucket || "").toLowerCase() === "cash" ? 1 : 0;
    var bCash = (b.bucket || "").toLowerCase() === "cash" ? 1 : 0;
    if (aCash !== bCash) return bCash - aCash;

    var k = _holdingsSortKey;
    var va, vb;
    if (k === "account" || k === "ticker" || k === "bucket" || k === "notes") {
      va = (a[k] || "").toLowerCase();
      vb = (b[k] || "").toLowerCase();
      return va < vb ? -_holdingsSortDir : va > vb ? _holdingsSortDir : 0;
    }
    if (k === "pl_dollar" || k === "pl_pct") {
      var aCost = (a.cost_basis && a.shares) ? a.cost_basis * a.shares : 0;
      var bCost = (b.cost_basis && b.shares) ? b.cost_basis * b.shares : 0;
      if (k === "pl_dollar") {
        va = aCost > 0 ? (a.total || 0) - aCost : -Infinity;
        vb = bCost > 0 ? (b.total || 0) - bCost : -Infinity;
      } else {
        va = aCost > 0 ? ((a.total || 0) - aCost) / aCost : -Infinity;
        vb = bCost > 0 ? ((b.total || 0) - bCost) / bCost : -Infinity;
      }
    } else if (k === "day_dollar" || k === "day_pct") {
      va = (a.price && a.prev_close && a.shares) ? (a.price - a.prev_close) * a.shares : -Infinity;
      vb = (b.price && b.prev_close && b.shares) ? (b.price - b.prev_close) * b.shares : -Infinity;
      if (k === "day_pct") {
        va = (a.price && a.prev_close) ? (a.price - a.prev_close) / a.prev_close : -Infinity;
        vb = (b.price && b.prev_close) ? (b.price - b.prev_close) / b.prev_close : -Infinity;
      }
    } else {
      va = a[k] || 0;
      vb = b[k] || 0;
    }
    return (va - vb) * _holdingsSortDir;
  });

  var arrow = function(key) {
    if (_holdingsSortKey !== key) return ' <span style="opacity:0.3;">&#8597;</span>';
    return _holdingsSortDir === 1 ? ' &#9650;' : ' &#9660;';
  };
  var hthL = 'style="padding:8px 6px;cursor:pointer;user-select:none;white-space:nowrap;text-align:left;"';
  var hthR = 'style="padding:8px 6px;cursor:pointer;user-select:none;white-space:nowrap;text-align:right;"';

  var html = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.82rem;">';
  html += '<thead><tr style="border-bottom:1px solid var(--border-subtle);">';
  html += '<th ' + hthL + ' onclick="_sortHoldingsBy(\'account\')">Account' + arrow("account") + '</th>';
  html += '<th ' + hthL + ' onclick="_sortHoldingsBy(\'ticker\')">Ticker' + arrow("ticker") + '</th>';
  html += '<th ' + hthL + ' onclick="_sortHoldingsBy(\'bucket\')">Class' + arrow("bucket") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'shares\')">Qty' + arrow("shares") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'cost_basis\')">Cost/Share' + arrow("cost_basis") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'price\')">Price' + arrow("price") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'total\')">Total' + arrow("total") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'day_dollar\')">Day $' + arrow("day_dollar") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'day_pct\')">Day %' + arrow("day_pct") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'pl_dollar\')">Total $' + arrow("pl_dollar") + '</th>';
  html += '<th ' + hthR + ' onclick="_sortHoldingsBy(\'pl_pct\')">Total %' + arrow("pl_pct") + '</th>';
  html += '<th style="padding:8px 6px;">Notes</th>';
  html += '<th style="padding:8px 4px;width:32px;"></th>';
  html += '</tr></thead><tbody>';

  var grandTotal = 0;
  var grandCost = 0;
  var grandPL = 0;
  var grandDayPL = 0;
  sorted.forEach(function(h) {
    grandTotal += (h.total || 0);
    var priceStr = h.price ? fmtMoney(h.price) : "";
    var computedTotal = (h.price && h.shares) ? h.price * h.shares : 0;
    var isOverridden = h.value_override != null && h.value_override > 0;
    var totalInputVal = isOverridden ? h.value_override : (computedTotal ? computedTotal.toFixed(2) : "");
    var totalColor = isOverridden ? "color:var(--warning);" : "";
    var qtyStr = (h.shares !== null && h.shares !== undefined) ? h.shares : "";

    var muted = '<span style="color:var(--text-muted);">--</span>';
    var isCash = (h.bucket || "").toLowerCase() === "cash";
    var dayDollarHtml = muted, dayPctHtml = isCash ? '' : muted;
    if (h.price && h.prev_close && h.shares) {
      var dayDollar = (h.price - h.prev_close) * h.shares;
      var dayPct = (h.prev_close > 0) ? ((h.price - h.prev_close) / h.prev_close) * 100 : 0;
      grandDayPL += dayDollar;
      var dayColor = dayDollar >= 0 ? "var(--success)" : "var(--danger)";
      var daySign = dayDollar >= 0 ? "+" : "";
      dayDollarHtml = isCash ? '' : '<span style="color:' + dayColor + ';font-family:var(--mono);white-space:nowrap;">' + daySign + '$' + Math.abs(dayDollar).toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0}) + '</span>';
      dayPctHtml = isCash ? '' : '<span style="color:' + dayColor + ';font-family:var(--mono);white-space:nowrap;">' + daySign + dayPct.toFixed(2) + '%</span>';
    }

    var costTotal = (h.cost_basis && h.shares) ? h.cost_basis * h.shares : 0;
    var currentVal = h.total || 0;
    var plDollarHtml = isCash ? '' : muted, plPctHtml = isCash ? '' : muted;
    if (!isCash && costTotal > 0 && currentVal > 0) {
      var plDollar = currentVal - costTotal;
      var plPct = (plDollar / costTotal) * 100;
      grandCost += costTotal;
      grandPL += plDollar;
      var plColor = plDollar >= 0 ? "var(--success)" : "var(--danger)";
      var plSign = plDollar >= 0 ? "+" : "";
      plDollarHtml = '<span style="color:' + plColor + ';font-family:var(--mono);white-space:nowrap;">' + plSign + '$' + Math.abs(plDollar).toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0}) + '</span>';
      plPctHtml = '<span style="color:' + plColor + ';font-family:var(--mono);white-space:nowrap;">' + plSign + plPct.toFixed(1) + '%</span>';
    }
    html += '<tr data-hid="' + h.id + '" data-computed="' + computedTotal.toFixed(2) + '">';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="account" value="' + (h.account || "") + '" ' + inputStyle + '></td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="ticker" value="' + (h.ticker || "") + '" ' + inputStyle + '></td>';
    html += '<td style="padding:4px 4px;">' + _buildBucketSelect(h.bucket || "", false) + '</td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="shares" value="' + qtyStr + '" class="num" ' + inputStyle + '></td>';
    html += '<td style="padding:4px 4px;"><input type="text" inputmode="decimal" data-field="cost_basis" value="' + (h.cost_basis || "") + '" class="num" ' + inputStyle + '></td>';
    html += '<td style="padding:8px 6px;text-align:right;color:var(--text-muted);font-family:var(--mono);white-space:nowrap;">' + priceStr + '</td>';
    html += '<td style="padding:4px 4px;"><input type="text" data-field="total_edit" value="' + totalInputVal + '" class="num" style="background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;' + totalColor + 'padding:5px 8px;font-size:0.82rem;width:100%;font-family:var(--mono);font-weight:600;"></td>';
    html += '<td style="padding:8px 6px;text-align:right;">' + dayDollarHtml + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;">' + dayPctHtml + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;">' + plDollarHtml + '</td>';
    html += '<td style="padding:8px 6px;text-align:right;">' + plPctHtml + '</td>';
    var noteVal = (h.notes || "").replace(/"/g, "&quot;");
    html += '<td style="padding:4px 4px;position:relative;"><input type="text" data-field="notes" value="' + noteVal + '" title="' + noteVal + '" ' + inputStyle.replace('width:100%', 'width:100%;text-overflow:ellipsis') + ' onfocus="this.style.position=\'absolute\';this.style.zIndex=\'10\';this.style.width=\'320px\';this.style.minWidth=\'320px\';" onblur="this.style.position=\'\';this.style.zIndex=\'\';this.style.width=\'100%\';this.style.minWidth=\'\';" ></td>';
    html += '<td style="padding:4px 4px;text-align:center;"><button type="button" onclick="deleteHolding(' + h.id + ')" title="Delete" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;padding:2px 6px;border-radius:4px;" onmouseover="this.style.color=\'var(--danger)\'" onmouseout="this.style.color=\'var(--text-muted)\'">&times;</button></td>';
    html += '</tr>';
  });

  html += '<tr>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="account" placeholder="Account" ' + inputStyle + '></td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="ticker" placeholder="Ticker" style="text-transform:uppercase;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:4px;color:var(--text-primary);padding:5px 8px;font-size:0.82rem;width:100%;"></td>';
  html += '<td style="padding:4px 4px;">' + _buildBucketSelect("", true) + '</td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="shares" placeholder="Qty" class="num" ' + inputStyle + '></td>';
  html += '<td style="padding:4px 4px;"><input type="text" inputmode="decimal" data-field="cost_basis" placeholder="Cost/Share" class="num" ' + inputStyle + '></td>';
  html += '<td></td>';
  html += '<td style="padding:4px 4px;"><input type="text" data-field="total_edit" placeholder="Total" class="num" ' + inputStyle + '></td>';
  html += '<td></td><td></td><td></td><td></td>';
  html += '<td style="padding:4px 4px;position:relative;"><input type="text" data-field="notes" placeholder="Notes" ' + inputStyle.replace('width:100%', 'width:100%;text-overflow:ellipsis') + ' onfocus="this.style.position=\'absolute\';this.style.zIndex=\'10\';this.style.width=\'320px\';this.style.minWidth=\'320px\';" onblur="this.style.position=\'\';this.style.zIndex=\'\';this.style.width=\'100%\';this.style.minWidth=\'\';" ></td>';
  html += '<td></td>';
  html += '</tr>';

  var grandDayColor = grandDayPL >= 0 ? "var(--success)" : "var(--danger)";
  var grandDaySign = grandDayPL >= 0 ? "+" : "";

  var grandPLColor = grandPL >= 0 ? "var(--success)" : "var(--danger)";
  var grandPLSign = grandPL >= 0 ? "+" : "";
  var grandPLPct = grandCost > 0 ? (grandPL / grandCost) * 100 : 0;

  html += '<tr style="font-weight:600;border-top:2px solid var(--border-subtle);">';
  html += '<td colspan="5" style="padding:8px 6px;">Holdings Total</td>';
  html += '<td></td>';
  var grandPrevTotal = grandTotal - grandDayPL;
  var grandDayPct = grandPrevTotal > 0 ? (grandDayPL / grandPrevTotal) * 100 : 0;

  html += '<td style="padding:8px 6px;text-align:right;color:#58a6ff;font-family:var(--mono);">' + fmtMoney(grandTotal) + '</td>';
  html += '<td style="padding:8px 6px;text-align:right;"><span style="color:' + grandDayColor + ';font-family:var(--mono);">' + grandDaySign + '$' + Math.abs(grandDayPL).toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0}) + '</span></td>';
  html += '<td style="padding:8px 6px;text-align:right;"><span style="color:' + grandDayColor + ';font-family:var(--mono);">' + grandDaySign + grandDayPct.toFixed(2) + '%</span></td>';
  html += '<td style="padding:8px 6px;text-align:right;"><span style="color:' + grandPLColor + ';font-family:var(--mono);">' + grandPLSign + '$' + Math.abs(grandPL).toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:0}) + '</span></td>';
  html += '<td style="padding:8px 6px;text-align:right;">' + (grandCost > 0 ? '<span style="color:' + grandPLColor + ';font-family:var(--mono);">' + grandPLSign + grandPLPct.toFixed(1) + '%</span>' : '') + '</td>';
  html += '<td colspan="2"></td>';
  html += '</tr>';

  html += '</tbody></table></div>';
  wrap.innerHTML = html;

  wrap.querySelectorAll('select[data-field="bucket"]').forEach(function(sel) {
    sel.addEventListener("change", function() { _handleBucketCustom(this); });
  });
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
    wrap.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-muted);">No crypto holdings. Connect Coinbase in Settings (gear icon) to auto-sync.</td></tr>';
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
    var priceStr = c.price ? "$" + c.price.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : "-";
    var valStr = val ? "$" + val.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) : "-";
    var pctStr = totalVal > 0 ? ((val / totalVal) * 100).toFixed(1) + "%" : "";
    rows += '<tr class="crypto-row" data-cid="' + c.id + '" data-cgid="' + (c.coingecko_id || "") + '">';
    rows += '<td style="padding:8px 10px;font-weight:600;">' + c.symbol + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + _fmtCryptoQty(c.quantity) + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);color:var(--text-muted);">' + priceStr + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;font-family:var(--mono);">' + valStr + '</td>';
    rows += '<td style="padding:8px 10px;text-align:right;color:var(--text-muted);">' + pctStr + '</td>';
    rows += '<td style="padding:8px 4px;text-align:center;"><button type="button" onclick="deleteCrypto(' + c.id + ')" title="Delete" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1rem;padding:2px 6px;border-radius:4px;" onmouseover="this.style.color=\'var(--danger)\'" onmouseout="this.style.color=\'var(--text-muted)\'">&times;</button></td>';
    rows += '</tr>';
  });

  rows += '<tr style="font-weight:600;border-top:2px solid var(--border-subtle);">';
  rows += '<td style="padding:8px 10px;" colspan="3">Total</td>';
  rows += '<td style="padding:8px 10px;text-align:right;color:#58a6ff;font-family:var(--mono);">$' + totalVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
  rows += '<td style="padding:8px 10px;text-align:right;">100%</td>';
  rows += '<td></td>';
  rows += '</tr>';

  wrap.innerHTML = rows;
  if (headerTotal) headerTotal.textContent = "$" + totalVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
}

var _metalsSortKey = _sortPrefs.mk || "metal";
var _metalsSortDir = _sortPrefs.md || 1;
var _metalsCache = null;

function _sortMetalsBy(key) {
  if (_metalsSortKey === key) { _metalsSortDir *= -1; } else { _metalsSortKey = key; _metalsSortDir = 1; }
  _sortPrefs.mk = _metalsSortKey; _sortPrefs.md = _metalsSortDir; _saveSortPrefs();
  if (_metalsCache) _renderMetals(_metalsCache);
}

function _loadPhysicalMetals() {
  var tbody = document.getElementById("metals-tbody");
  if (!tbody) return;
  fetch("/api/physical-metals")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      _metalsCache = d.metals || [];
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

  var goldSpot = window._lastLiveData && window._lastLiveData.gold ? window._lastLiveData.gold : 0;
  var silverSpot = window._lastLiveData && window._lastLiveData.silver ? window._lastLiveData.silver : 0;

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

