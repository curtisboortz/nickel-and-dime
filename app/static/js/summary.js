/* Nickel&Dime - Summary tab: allocation table, donut, monthly investments */
/* ── Summary Tab Data (allocation table + monthly investments) ── */
var _summaryDataLoaded = false;
function loadSummaryData() {
  if (_summaryDataLoaded) return;
  _summaryDataLoaded = true;
  NDDiag.track("summary", "loading");
  loadAllocationTable();
  loadMonthlyInvestments();
  if (window.BUCKETS_DATA && Object.keys(window.BUCKETS_DATA).length > 0) {
    if (typeof buildDonut === "function") buildDonut();
  }
}

function loadAllocationTable() {
  var tbody = document.getElementById("alloc-table-body");
  if (!tbody) return;
  fetch("/api/allocation-targets")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var rows = d.rows || [];
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted);">No allocation data yet. Add holdings to see your breakdown.</td></tr>';
        return;
      }
      var html = "";
      _allocData = rows;
      _renderAllocRows(rows);
    })
    .catch(function() {});
}

var _allocData = [];
var _allocSort = { col: null, asc: true };

function sortAllocTable(col) {
  if (_allocSort.col === col) {
    _allocSort.asc = !_allocSort.asc;
  } else {
    _allocSort.col = col;
    _allocSort.asc = col === "bucket";
  }
  var sorted = _allocData.slice().sort(function(a, b) {
    var va = a[col], vb = b[col];
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    if (va < vb) return _allocSort.asc ? -1 : 1;
    if (va > vb) return _allocSort.asc ? 1 : -1;
    return 0;
  });
  _renderAllocRows(sorted);
  document.querySelectorAll("#alloc-table-head th").forEach(function(th) {
    var arrow = th.querySelector(".sort-arrow");
    if (arrow) arrow.textContent = th.dataset.col === col ? (_allocSort.asc ? " \u25B2" : " \u25BC") : "";
  });
}

function _renderAllocRows(rows) {
  var tbody = document.getElementById("alloc-table-body");
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted);">No allocation data yet.</td></tr>';
    return;
  }
  var html = "";
  rows.forEach(function(r, idx) {
    var driftCls = r.drift > 1 ? "color:var(--success)" : r.drift < -1 ? "color:var(--danger)" : "color:var(--text-muted)";
    var driftStr = (r.drift > 0 ? "+" : "") + r.drift.toFixed(1) + "%";
    var hasChildren = r.children && r.children.length > 0;
    var toggleId = "alloc-expand-" + idx;
    var nameHtml = _esc(r.bucket);
    if (hasChildren) {
      nameHtml = '<span style="cursor:pointer;user-select:none;" onclick="document.querySelectorAll(\'.' + toggleId + '\').forEach(function(el){el.style.display=el.style.display===\'none\'?\'table-row\':\'none\';});var a=this.querySelector(\'.alloc-arrow\');if(a)a.textContent=a.textContent===\'\\u25B6\'?\'\\u25BC\':\'\\u25B6\';">'
        + '<span class="alloc-arrow" style="font-size:0.7rem;margin-right:4px;">&#9654;</span>' + _esc(r.bucket) + '</span>';
    }
    html += '<tr>';
    html += '<td style="padding:8px 6px;font-weight:' + (hasChildren ? '600' : '400') + ';">' + nameHtml + '</td>';
    html += '<td style="padding:8px 6px;font-family:var(--mono);">$' + r.value.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
    html += '<td style="padding:8px 6px;font-family:var(--mono);">' + r.pct.toFixed(1) + '%</td>';
    html += '<td style="padding:8px 6px;font-family:var(--mono);">' + r.target + '%</td>';
    html += '<td style="padding:8px 6px;font-family:var(--mono);' + driftCls + '">' + driftStr + '</td>';
    html += '</tr>';
    if (hasChildren) {
      r.children.forEach(function(c) {
        var cdCls = "";
        var cdStr = "";
        if (c.drift != null) {
          cdCls = c.drift > 1 ? "color:var(--success)" : c.drift < -1 ? "color:var(--danger)" : "color:var(--text-muted)";
          cdStr = (c.drift > 0 ? "+" : "") + c.drift.toFixed(1) + "%";
        }
        html += '<tr class="' + toggleId + '" style="display:none;">';
        html += '<td style="padding:4px 6px 4px 24px;font-size:0.8rem;color:var(--text-muted);">' + _esc(c.bucket) + '</td>';
        html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">$' + c.value.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
        html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">' + c.pct.toFixed(1) + '%</td>';
        html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">' + (c.target ? c.target + '%' : '') + '</td>';
        html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;' + cdCls + '">' + cdStr + '</td>';
        html += '</tr>';
      });
    }
  });
  tbody.innerHTML = html;
}

var _investCurrentMonth = "";
var _investAvailableMonths = [];
var _investIsCurrent = false;
var _investDriftSuggestions = {};
var _investRebalanceMonths = 12;

var _BUCKET_GROUPS = {
  "Equities": ["Equities", "International", "Managed Blend", "Retirement Blend"],
  "Real Assets": ["Real Assets", "Gold", "Silver", "Real Estate", "Art"],
  "Alternatives": ["Alternatives", "Crypto", "Private Equity", "Venture Capital"],
  "Fixed Income": ["Fixed Income"],
  "Cash": ["Cash"],
  "Commodities": ["Commodities"],
};

function _bucketDropdownHtml(selected) {
  var html = '<option value="">-- Select bucket --</option>';
  Object.keys(_BUCKET_GROUPS).forEach(function(parent) {
    html += '<optgroup label="' + _esc(parent) + '">';
    _BUCKET_GROUPS[parent].forEach(function(b) {
      html += '<option value="' + _esc(b) + '"' + (b === selected ? ' selected' : '') + '>' + _esc(b) + '</option>';
    });
    html += '</optgroup>';
  });
  return html;
}

function loadMonthlyInvestments(month) {
  var tbody = document.getElementById("invest-table-body");
  var subtitle = document.getElementById("invest-subtitle");
  if (!tbody) return;
  var _cb = "_t=" + Date.now();
  var url = "/api/investments?" + _cb;
  if (month) url += "&month=" + encodeURIComponent(month);

  console.log("[ND:invest] loadMonthlyInvestments fetching", url);
  var investPromise = fetch(url).then(function(r) { return r.json(); });
  var driftPromise = fetch("/api/drift-targets?" + _cb).then(function(r) { return r.json(); }).catch(function() { return { suggestions: [] }; });

  Promise.all([investPromise, driftPromise]).then(function(results) {
    var d = results[0];
    var drift = results[1];
    var cats = d.categories || [];
    var budget = d.monthly_budget || 0;
    console.log("[ND:invest] loaded", cats.length, "cats, budget=$" + budget, "urgency=" + (drift.urgency || 0), "rebal=" + (d.rebalance_months || "?"), "targets:", cats.map(function(c) { return c.category + "=$" + c.target; }).join(", "));
    _investCurrentMonth = d.month || "";
    _investAvailableMonths = d.available_months || [];
    _investIsCurrent = d.is_current !== false;
    _investRebalanceMonths = d.rebalance_months || 12;

    _investDriftSuggestions = {};
    (drift.suggestions || []).forEach(function(s) {
      _investDriftSuggestions[s.bucket] = s;
    });
    var _urgency = drift.urgency || 0;

    var monthLabel = _investCurrentMonth ? new Date(_investCurrentMonth + "-15").toLocaleDateString(undefined, {year:"numeric", month:"long"}) : "";
    if (subtitle) subtitle.textContent = monthLabel + " \u2022 Budget: $" + budget.toLocaleString(undefined, {maximumFractionDigits:0});
    _updateInvestNav();

    var rebalCtrl = document.getElementById("invest-rebalance-ctrl");
    if (rebalCtrl) {
      if (_investIsCurrent) {
        rebalCtrl.style.display = "";
        var sel = document.getElementById("rebalance-months-sel");
        if (sel) sel.value = String(_investRebalanceMonths);
        var poolHint = document.getElementById("invest-pool-hint");
        if (poolHint) {
          if (_urgency > 0) {
            var pctRebal = Math.round(_urgency * 100);
            poolHint.textContent = pctRebal + "% toward rebalancing \u00B7 " + (100 - pctRebal) + "% maintaining targets";
            poolHint.style.display = "";
          } else {
            poolHint.style.display = "none";
          }
        }
      } else {
        rebalCtrl.style.display = "none";
      }
    }


    if (cats.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted);">No investment categories set up for this month.</td></tr>';
      _updateInvestFooter(0, 0, budget);
      return;
    }

    var totalTarget = 0, totalContrib = 0;
    var html = "";
    cats.forEach(function(c, idx) {
      var pct = budget > 0 ? Math.round((c.target / budget) * 100) : 0;
      var diff = c.contributed - c.target;
      var diffStr = (diff >= 0 ? "+" : "") + "$" + Math.abs(diff).toFixed(0);
      var diffCls = diff >= 0 ? "color:var(--success)" : "color:var(--warning)";
      var progressPct = c.target > 0 ? Math.min((c.contributed / c.target) * 100, 100) : 0;
      var barCls = progressPct < 40 ? "low" : progressPct < 90 ? "mid" : "done";
      totalTarget += c.target;
      totalContrib += c.contributed;

      var driftTag = "";
      if (c.bucket && _investDriftSuggestions[c.bucket]) {
        var sg = _investDriftSuggestions[c.bucket];
        var driftColor = sg.drift < 0 ? "var(--danger)" : sg.drift > 0 ? "var(--success)" : "var(--text-muted)";
        var driftLabel = sg.drift < 0 ? sg.drift.toFixed(1) + "%" : "+" + sg.drift.toFixed(1) + "%";
        driftTag = ' <span style="font-size:0.62rem;color:' + driftColor + ';">' + driftLabel + '</span>';
      }

      var detailId = "invest-detail-" + idx;
      html += '<tr class="invest-summary-row" data-bucket="' + _esc(c.bucket || "") + '" style="cursor:pointer;" onclick="toggleInvestDetail(\'' + detailId + '\',this)">';
      html += '<td style="padding:8px 6px;"><span class="invest-chevron" style="display:inline-block;font-size:0.6rem;margin-right:4px;transition:transform .2s;color:var(--text-muted);">&#9654;</span><strong>' + _esc(c.category) + '</strong>' + driftTag + ' <span style="color:var(--text-muted);font-size:0.72rem;">(' + pct + '%)</span></td>';
      html += '<td style="padding:8px 6px;text-align:right;font-family:var(--mono);">$' + c.target.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
      html += '<td style="padding:8px 6px;text-align:right;" onclick="event.stopPropagation()"><input type="number" class="contrib-input num" data-id="' + c.id + '" data-target="' + c.target + '" value="' + c.contributed + '" style="width:80px;text-align:right;" onchange="updateInvestTotals()"></td>';
      html += '<td style="padding:8px 6px;text-align:right;font-family:var(--mono);' + diffCls + '">' + diffStr + '</td>';
      html += '<td style="padding:8px 6px;text-align:center;"><div class="progress-bar" style="width:80px;display:inline-block;"><div class="progress-fill mini-fill ' + barCls + '" style="width:' + progressPct + '%"></div></div></td>';
      html += '</tr>';

      var detailContent = "";
      if (_investIsCurrent) {
        detailContent += '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;">';
        detailContent += '<label style="font-size:0.72rem;color:var(--text-muted);">Asset class:</label>';
        detailContent += '<select class="bucket-select" data-id="' + c.id + '" onclick="event.stopPropagation()" onchange="event.stopPropagation();saveInvestBucket(this)" style="font-size:0.72rem;padding:2px 6px;border-radius:4px;background:var(--bg-input);color:var(--text-primary);border:1px solid var(--border-subtle);max-width:140px;">' + _bucketDropdownHtml(c.bucket || "") + '</select>';
        detailContent += '<button type="button" class="secondary" style="padding:2px 8px;font-size:0.68rem;margin-left:auto;color:var(--danger);border-color:var(--danger);" onclick="event.stopPropagation();deleteInvestCategory(' + c.id + ')">Delete</button>';
        detailContent += '</div>';
      } else if (c.bucket) {
        detailContent += '<span style="font-size:0.72rem;color:var(--text-muted);">Asset class: ' + _esc(c.bucket) + '</span>';
      }

      html += '<tr id="' + detailId + '" class="invest-detail-row" style="display:none;" data-bucket="' + _esc(c.bucket || "") + '">';
      html += '<td colspan="5" style="padding:4px 6px 10px 24px;border-top:none;">' + detailContent + '</td>';
      html += '</tr>';
    });
    tbody.innerHTML = html;
    _updateInvestFooter(totalTarget, totalContrib, budget);
    console.log("[ND:invest] render complete, totalTarget=$" + totalTarget);
  }).catch(function(err) { console.error("[ND:invest] loadMonthlyInvestments error:", err); });
}

function _updateInvestFooter(totalTarget, totalContrib, budget) {
  var displayBudget = budget || totalTarget;
  var totalRem = displayBudget - totalContrib;
  var totalPct = displayBudget > 0 ? Math.min((totalContrib / displayBudget) * 100, 100) : 0;
  var itgt = document.getElementById("invest-total-target"); if (itgt) itgt.textContent = "$" + displayBudget.toLocaleString(undefined, {maximumFractionDigits:0});
  var icnt = document.getElementById("invest-total-contrib"); if (icnt) icnt.textContent = "$" + totalContrib.toLocaleString(undefined, {maximumFractionDigits:0});
  var istat = document.getElementById("invest-total-status"); if (istat) { istat.textContent = "$" + Math.abs(totalRem).toLocaleString(undefined, {maximumFractionDigits:0}) + (totalRem > 0 ? " left" : ""); istat.style.color = totalRem > 0 ? "var(--warning)" : "var(--success)"; }
  var pf = document.getElementById("total-progress-fill"); if (pf) pf.style.width = totalPct + "%";
  var pp = document.getElementById("total-progress-pct"); if (pp) pp.textContent = Math.round(totalPct) + "%";
}

function updateInvestTotals() {
  var tc = 0, tt = 0;
  document.querySelectorAll(".contrib-input").forEach(function(i) { tc += parseFloat(i.value) || 0; tt += parseFloat(i.dataset.target) || 0; });
  _updateInvestFooter(tt, tc, 0);
}

function saveContributionsAPI() {
  var categories = [];
  document.querySelectorAll(".contrib-input").forEach(function(i) {
    categories.push({ id: parseInt(i.dataset.id), contributed: parseFloat(i.value) || 0 });
  });
  fetch("/api/investments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ month: _investCurrentMonth, categories: categories })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      var btn = document.querySelector("button[onclick*='saveContributions']");
      if (btn) { btn.textContent = "Saved!"; setTimeout(function() { btn.textContent = "Save Changes"; }, 2000); }
    }
  });
}

function toggleInvestDetail(detailId, summaryRow) {
  var detail = document.getElementById(detailId);
  if (!detail) return;
  var chevron = summaryRow.querySelector(".invest-chevron");
  if (detail.style.display === "none") {
    detail.style.display = "";
    if (chevron) chevron.style.transform = "rotate(90deg)";
  } else {
    detail.style.display = "none";
    if (chevron) chevron.style.transform = "";
  }
}

function deleteInvestCategory(id) {
  if (!confirm("Remove this category?")) return;
  fetch("/api/investments/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: id })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) loadMonthlyInvestments(_investCurrentMonth);
  });
}

function saveInvestBucket(sel) {
  var id = parseInt(sel.dataset.id);
  var bucket = sel.value;
  fetch("/api/investments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ month: _investCurrentMonth, categories: [{ id: id, bucket: bucket }] })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) loadMonthlyInvestments(_investCurrentMonth);
  });
}


function changeRebalanceMonths() {
  var sel = document.getElementById("rebalance-months-sel");
  if (!sel) return;
  var months = parseInt(sel.value) || 12;
  console.log("[ND:recalc] changeRebalanceMonths to", months);
  sel.disabled = true;
  fetch("/api/rebalance-months", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ months: months })
  }).then(function(r) { return r.json(); }).then(function(d) {
    sel.disabled = false;
    console.log("[ND:recalc] rebalance-months save result:", JSON.stringify(d));
    if (d && d.success) {
      _applyAndReload();
    } else {
      console.log("[ND:recalc] save failed, just reloading");
      loadMonthlyInvestments(_investCurrentMonth);
    }
  }).catch(function(err) { sel.disabled = false; console.error("[ND:recalc] changeRebalanceMonths error:", err); });
}

function _applyAndReload() {
  console.log("[ND:recalc] _applyAndReload starting, fetching /api/drift-targets");
  fetch("/api/drift-targets?_t=" + Date.now()).then(function(r) {
    console.log("[ND:recalc] drift-targets response status:", r.status);
    return r.json();
  }).then(function(drift) {
    console.log("[ND:recalc] drift-targets data:", JSON.stringify(drift).substring(0, 300));
    var sug = {};
    (drift.suggestions || []).forEach(function(s) { sug[s.bucket] = s; });
    console.log("[ND:recalc] suggestion buckets:", Object.keys(sug));

    var bucketCounts = {};
    document.querySelectorAll(".invest-summary-row").forEach(function(row) {
      var b = row.dataset.bucket;
      if (b) bucketCounts[b] = (bucketCounts[b] || 0) + 1;
    });
    console.log("[ND:recalc] bucketCounts from DOM:", JSON.stringify(bucketCounts));

    if (!Object.keys(bucketCounts).length) {
      console.log("[ND:recalc] no buckets in DOM, just reloading");
      loadMonthlyInvestments(_investCurrentMonth);
      return;
    }

    var categories = [];
    document.querySelectorAll(".contrib-input").forEach(function(i) {
      var id = parseInt(i.dataset.id);
      var row = i.closest("tr");
      var bucket = row ? (row.dataset.bucket || "") : "";
      var entry = { id: id, contributed: parseFloat(i.value) || 0 };
      if (bucket && sug[bucket]) {
        var count = bucketCounts[bucket] || 1;
        entry.target = Math.round(sug[bucket].suggested / count);
        console.log("[ND:recalc] category id=" + id + " bucket=" + bucket + " -> target=" + entry.target + " (suggested=" + sug[bucket].suggested + " / " + count + ")");
      } else {
        console.log("[ND:recalc] category id=" + id + " bucket='" + bucket + "' -> NO match in suggestions");
      }
      categories.push(entry);
    });

    console.log("[ND:recalc] POSTing", categories.length, "categories to /api/investments");
    fetch("/api/investments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month: _investCurrentMonth, categories: categories })
    }).then(function(r) {
      console.log("[ND:recalc] POST response status:", r.status);
      return r.json();
    }).then(function(d) {
      console.log("[ND:recalc] POST result:", JSON.stringify(d));
      var ctrl = document.getElementById("invest-rebalance-ctrl");
      if (ctrl) {
        ctrl.style.transition = "box-shadow .3s";
        ctrl.style.boxShadow = "0 0 0 2px var(--success)";
        setTimeout(function() { ctrl.style.boxShadow = ""; }, 1200);
      }
      loadMonthlyInvestments(_investCurrentMonth);
    });
  }).catch(function(err) {
    console.error("[ND:recalc] error in _applyAndReload:", err);
    loadMonthlyInvestments(_investCurrentMonth);
  });
}

function investNavMonth(dir) {
  if (!_investCurrentMonth) return;
  var parts = _investCurrentMonth.split("-");
  var y = parseInt(parts[0]), m = parseInt(parts[1]);
  m += dir;
  if (m < 1) { m = 12; y--; }
  if (m > 12) { m = 1; y++; }
  var target = y + "-" + String(m).padStart(2, "0");
  var now = new Date();
  var currentMonth = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  if (target > currentMonth) return;
  var oneYearAgo = (now.getFullYear() - 1) + "-" + String(now.getMonth() + 1).padStart(2, "0");
  if (target < oneYearAgo) return;
  loadMonthlyInvestments(target);
}

function _updateInvestNav() {
  var prevBtn = document.getElementById("invest-prev-btn");
  var nextBtn = document.getElementById("invest-next-btn");
  if (!prevBtn || !nextBtn || !_investCurrentMonth) return;
  var now = new Date();
  var currentMonth = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  var oneYearAgo = (now.getFullYear() - 1) + "-" + String(now.getMonth() + 1).padStart(2, "0");
  var parts = _investCurrentMonth.split("-");
  var y = parseInt(parts[0]), m = parseInt(parts[1]);
  var prevM = m - 1 < 1 ? 12 : m - 1;
  var prevY = m - 1 < 1 ? y - 1 : y;
  var prevMonth = prevY + "-" + String(prevM).padStart(2, "0");
  prevBtn.disabled = prevMonth < oneYearAgo;
  nextBtn.disabled = _investCurrentMonth >= currentMonth;
}

/* ── Add Investment Category ── */
function showAddCategoryForm() {
  var form = document.getElementById("add-category-form");
  if (!form) return;
  if (form.style.display === "none") {
    form.style.display = "block";
    var sel = document.getElementById("new-cat-bucket");
    if (sel && !sel.dataset.loaded) {
      sel.innerHTML = _bucketDropdownHtml("");
      sel.dataset.loaded = "1";
    }
  } else {
    form.style.display = "none";
  }
}
function addInvestCategory() {
  var name = document.getElementById("new-cat-name").value.trim();
  var target = parseFloat(document.getElementById("new-cat-target").value) || 0;
  var bucketSel = document.getElementById("new-cat-bucket");
  var bucket = bucketSel ? bucketSel.value : "";
  if (!name) { alert("Enter a category name."); return; }
  if (!bucket) { alert("Select an asset class bucket."); return; }
  fetch("/api/investments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ month: _investCurrentMonth, categories: [{ category: name, bucket: bucket, target: target, contributed: 0 }] })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      document.getElementById("new-cat-name").value = "";
      document.getElementById("new-cat-target").value = "";
      if (bucketSel) bucketSel.value = "";
      document.getElementById("add-category-form").style.display = "none";
      _summaryDataLoaded = false;
      loadMonthlyInvestments(_investCurrentMonth);
    }
  });
}

/* ── Edit Allocation Targets ── */
var _editingTargets = false;
function toggleEditTargets() {
  if (_editingTargets) {
    cancelEditTargets();
  } else {
    _editingTargets = true;
    var btn = document.getElementById("edit-targets-btn");
    btn.textContent = "Cancel";
    loadAllocationTableEditable();
  }
}
function cancelEditTargets() {
  _editingTargets = false;
  var btn = document.getElementById("edit-targets-btn");
  btn.textContent = "Edit Targets";
  loadAllocationTable();
}
function loadAllocationTableEditable() {
  var tbody = document.getElementById("alloc-table-body");
  if (!tbody) return;
  fetch("/api/allocation-targets")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var rows = d.rows || [];
      var html = "";
      rows.forEach(function(r) {
        var hasChildren = r.children && r.children.length > 0;
        html += '<tr>';
        html += '<td style="padding:8px 6px;font-weight:' + (hasChildren ? '600' : '400') + ';">' + _esc(r.bucket) + '</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">$' + r.value.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
        html += '<td style="padding:8px 6px;font-family:var(--mono);">' + r.pct.toFixed(1) + '%</td>';
        html += '<td style="padding:8px 6px;"><input type="number" class="target-input num" data-bucket="' + r.bucket + '" data-level="parent" value="' + r.target + '" style="width:60px;text-align:right;" min="0" max="100">%</td>';
        html += '<td style="padding:8px 6px;">';
        if (r.value === 0 && r.target === 0) {
          html += '<button type="button" onclick="_deleteAllocTarget(\'' + _esc(r.bucket).replace(/'/g, "\\'") + '\')" title="Remove row" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:0.9rem;" onmouseover="this.style.color=\'var(--danger)\'" onmouseout="this.style.color=\'var(--text-muted)\'">&times;</button>';
        }
        html += '</td>';
        html += '</tr>';
        if (hasChildren) {
          r.children.forEach(function(c) {
            html += '<tr>';
            html += '<td style="padding:4px 6px 4px 24px;font-size:0.8rem;color:var(--text-muted);">' + _esc(c.bucket) + '</td>';
            html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">$' + c.value.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
            html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">' + c.pct.toFixed(1) + '%</td>';
            html += '<td style="padding:4px 6px;"><input type="number" class="target-input num" data-bucket="' + c.bucket + '" data-level="child" value="' + (c.target || 0) + '" style="width:60px;text-align:right;font-size:0.8rem;" min="0" max="100">%</td>';
            html += '<td></td>';
            html += '</tr>';
          });
        }
      });
      html += '<tr id="alloc-total-row"><td colspan="3" style="padding:10px 6px;text-align:right;font-weight:600;">Total</td>';
      html += '<td style="padding:10px 6px;font-family:var(--mono);font-weight:600;" id="alloc-total-cell">0%</td><td></td></tr>';
      html += '<tr id="alloc-remainder-row" style="display:none;"><td colspan="5" style="padding:4px 6px;text-align:center;font-size:0.78rem;color:var(--accent-primary);" id="alloc-remainder-msg"></td></tr>';
      html += '<tr><td colspan="5" style="padding:10px 6px;text-align:right;"><button type="button" id="save-targets-btn" onclick="saveAllocationTargets()" style="padding:6px 16px;font-size:0.8rem;">Save Targets</button> <button type="button" class="secondary" onclick="cancelEditTargets()" style="padding:6px 16px;font-size:0.8rem;margin-left:6px;">Cancel</button></td></tr>';
      tbody.innerHTML = html;
      _attachTargetListeners();
      _updateAllocTotal();
    });
}
function _attachTargetListeners() {
  document.querySelectorAll('.target-input[data-level="parent"]').forEach(function(inp) {
    inp.addEventListener("input", _updateAllocTotal);
  });
}
function _updateAllocTotal() {
  var inputs = document.querySelectorAll('.target-input[data-level="parent"]');
  var sum = 0;
  inputs.forEach(function(i) {
    var v = parseFloat(i.value);
    if (!isNaN(v)) sum += v;
  });
  sum = Math.round(sum * 10) / 10;
  var cell = document.getElementById("alloc-total-cell");
  var msg = document.getElementById("alloc-remainder-msg");
  var msgRow = document.getElementById("alloc-remainder-row");
  var btn = document.getElementById("save-targets-btn");
  if (cell) {
    cell.textContent = sum + "%";
    cell.style.color = sum > 100 ? "var(--danger)" : sum === 100 ? "var(--success, #22c55e)" : "var(--text-primary)";
  }
  if (msg && msgRow) {
    if (sum < 100) {
      var rem = Math.round((100 - sum) * 10) / 10;
      msg.textContent = "Remaining " + rem + "% will be allocated to Cash on save";
      msg.style.color = "var(--accent-primary)";
      msgRow.style.display = "";
    } else if (sum > 100) {
      msg.textContent = "Total exceeds 100%. Reduce targets before saving.";
      msg.style.color = "var(--danger)";
      msgRow.style.display = "";
    } else {
      msgRow.style.display = "none";
    }
  }
  if (btn) {
    btn.disabled = sum > 100;
    btn.style.opacity = sum > 100 ? "0.5" : "1";
  }
}
function _deleteAllocTarget(bucket) {
  if (!confirm("Remove \"" + bucket + "\" from allocation targets?")) return;
  fetch("/api/allocation-targets/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bucket: bucket })
  }).then(function(r) { return r.json(); }).then(function() {
    if (_editingTargets) loadAllocationTableEditable();
    else { _allocData = []; loadAllocationTable(); }
  });
}
function saveAllocationTargets() {
  var parentInputs = document.querySelectorAll('.target-input[data-level="parent"]');
  var childInputs = document.querySelectorAll('.target-input[data-level="child"]');
  var parentSum = 0;
  parentInputs.forEach(function(i) {
    var v = parseFloat(i.value);
    if (!isNaN(v)) parentSum += v;
  });
  parentSum = Math.round(parentSum * 10) / 10;
  if (parentSum > 100) {
    alert("Targets total " + parentSum + "%; must be 100% or less.");
    return;
  }
  var tactical = {};
  parentInputs.forEach(function(i) {
    var val = parseFloat(i.value);
    if (!isNaN(val) && val > 0) {
      tactical[i.dataset.bucket] = { target: val, min: 0, max: 100 };
    }
  });
  childInputs.forEach(function(i) {
    var val = parseFloat(i.value);
    if (!isNaN(val) && val > 0) {
      tactical[i.dataset.bucket] = { target: val, min: 0, max: 100 };
    }
  });
  if (parentSum < 100) {
    var nonCashSum = 0;
    parentInputs.forEach(function(i) {
      if (i.dataset.bucket !== "Cash") {
        var v = parseFloat(i.value);
        if (!isNaN(v)) nonCashSum += v;
      }
    });
    nonCashSum = Math.round(nonCashSum * 10) / 10;
    tactical["Cash"] = { target: Math.round((100 - nonCashSum) * 10) / 10, min: 0, max: 100 };
  }
  if (Object.keys(tactical).length === 0) {
    alert("No targets to save. Enter at least one target percentage.");
    return;
  }
  fetch("/api/allocation-targets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ targets: { tactical: tactical } })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      _editingTargets = false;
      var btn = document.getElementById("edit-targets-btn");
      btn.textContent = "Edit Targets";
      _allocData = [];
      _summaryDataLoaded = false;
      loadAllocationTable();
    }
  });
}

/* ── Allocation Donut ── */
var _donutChart = null;
function _donutColor(label) {
  return ndCategoryColor(label);
}

function _getDonutCollapseState() {
  try { return JSON.parse(localStorage.getItem("nd-donut-collapse") || "{}"); } catch(e) { return {}; }
}

function _toggleDonutCategory(pk) {
  var state = _getDonutCollapseState();
  state[pk] = !state[pk];
  localStorage.setItem("nd-donut-collapse", JSON.stringify(state));
  var safeId = "donut-children-" + pk.replace(/[^a-zA-Z0-9]/g, "_");
  var el = document.getElementById(safeId);
  if (el) el.style.display = state[pk] ? "none" : "";
  var arrow = document.getElementById("donut-arrow-" + pk.replace(/[^a-zA-Z0-9]/g, "_"));
  if (arrow) arrow.textContent = state[pk] ? "\u25B6" : "\u25BC";
}

function _buildDonutLegend(parentData, detailData, total) {
  var legend = document.getElementById("donut-legend");
  if (!legend) return;

  var childrenMap = window.BUCKETS_CHILDREN || {};
  var collapseState = _getDonutCollapseState();
  var parentKeys = Object.keys(parentData).filter(function(k) { return parentData[k] > 0; });
  var sorted = parentKeys.slice().sort(function(a, b) { return (parentData[b] || 0) - (parentData[a] || 0); });

  var html = "";
  sorted.forEach(function(pk) {
    var val = parentData[pk] || 0;
    var pct = total > 0 ? ((val / total) * 100).toFixed(1) : "0.0";
    var color = _donutColor(pk);
    var children = childrenMap[pk];
    var hasChildren = children && Object.keys(children).length > 0;
    var safeId = pk.replace(/[^a-zA-Z0-9]/g, "_");
    var collapsed = collapseState[pk] || false;

    html += '<div style="margin-bottom:6px;">';
    html += '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;' + (hasChildren ? 'cursor:pointer;' : '') + '"' + (hasChildren ? ' onclick="_toggleDonutCategory(\'' + pk.replace(/'/g, "\\'") + '\')"' : '') + '>';
    if (hasChildren) {
      html += '<span id="donut-arrow-' + safeId + '" style="font-size:0.55rem;color:var(--text-muted);width:8px;flex-shrink:0;">' + (collapsed ? "\u25B6" : "\u25BC") + '</span>';
    } else {
      html += '<span style="width:8px;flex-shrink:0;"></span>';
    }
    html += '<span style="width:10px;height:10px;border-radius:50%;background:' + color + ';flex-shrink:0;"></span>';
    html += '<span style="flex:1;font-weight:600;color:var(--text-primary);font-size:0.82rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + pk + '</span>';
    html += '<span style="font-family:var(--mono);color:var(--text-muted);font-size:0.72rem;white-space:nowrap;min-width:38px;text-align:right;">' + pct + '%</span>';
    html += '<span style="font-family:var(--mono);color:var(--text-primary);font-size:0.78rem;white-space:nowrap;min-width:60px;text-align:right;">$' + val.toLocaleString(undefined, {maximumFractionDigits: 0}) + '</span>';
    html += '</div>';

    if (hasChildren) {
      var childKeys = Object.keys(children).sort(function(a, b) { return (children[b] || 0) - (children[a] || 0); });
      html += '<div id="donut-children-' + safeId + '"' + (collapsed ? ' style="display:none;"' : '') + '>';
      childKeys.forEach(function(ck) {
        var cv = children[ck] || 0;
        var cpct = total > 0 ? ((cv / total) * 100).toFixed(1) : "0.0";
        html += '<div style="display:flex;align-items:center;gap:8px;padding:2px 0 2px 26px;">';
        html += '<span style="width:6px;height:6px;border-radius:50%;background:' + color + ';opacity:0.45;flex-shrink:0;"></span>';
        html += '<span style="flex:1;color:var(--text-muted);font-size:0.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + ck + '</span>';
        html += '<span style="font-family:var(--mono);color:var(--text-muted);font-size:0.68rem;white-space:nowrap;min-width:38px;text-align:right;">' + cpct + '%</span>';
        html += '<span style="font-family:var(--mono);color:var(--text-muted);font-size:0.7rem;white-space:nowrap;min-width:60px;text-align:right;">$' + cv.toLocaleString(undefined, {maximumFractionDigits: 0}) + '</span>';
        html += '</div>';
      });
      html += '</div>';
    }
    html += '</div>';
  });
  legend.innerHTML = html;
}

var _lastDonutHash = "";
function buildDonut() {
  NDDiag.track("donut", "loading");
  var parentData = window.BUCKETS_DATA;
  var detailData = window.BUCKETS_DETAIL || parentData;
  if (!parentData || typeof parentData !== "object") { NDDiag.track("donut", "warn", "no BUCKETS_DATA"); return; }

  var labels = Object.keys(parentData).filter(function(k) { return parentData[k] > 0; });
  var values = labels.map(function(k) { return parentData[k]; });
  var colors = labels.map(function(l) { return _donutColor(l); });
  var total = values.reduce(function(a, b) { return a + b; }, 0);

  if (labels.length === 0) { NDDiag.track("donut", "warn", "empty buckets"); return; }

  var newHash = labels.join("|") + ":" + values.map(function(v) { return Math.round(v); }).join(",");
  var dataChanged = (newHash !== _lastDonutHash);
  _lastDonutHash = newHash;

  var centerVal = document.getElementById("donut-center-value");
  if (centerVal) {
    if (typeof ndCountUp === "function" && centerVal.dataset.ndCurrent) {
      ndCountUp(centerVal, total, { prefix: "$", decimals: 0, duration: 500, tickClass: false });
    } else {
      centerVal.textContent = "$" + total.toLocaleString(undefined, {maximumFractionDigits: 0});
      centerVal.dataset.ndCurrent = total;
    }
  }

  if (!dataChanged && _donutChart) {
    _buildDonutLegend(parentData, detailData, total);
    return;
  }

  var ctx = document.getElementById("allocation-donut");
  if (!ctx || typeof Chart === "undefined") return;

  if (_donutChart) {
    _donutChart.data.labels = labels;
    _donutChart.data.datasets[0].data = values;
    _donutChart.data.datasets[0].backgroundColor = colors;
    _donutChart.options.plugins.tooltip.callbacks.label = function(c) {
      var pct = total > 0 ? ((c.raw / total) * 100).toFixed(1) : "0";
      return "$" + c.raw.toLocaleString(undefined, {maximumFractionDigits: 0}) + "  ·  " + pct + "%";
    };
    _donutChart.update("none");
    _buildDonutLegend(parentData, detailData, total);
    NDDiag.track("donut", "ok", labels.length + " parent (update)");
    return;
  }

  var _t = ndChartTheme();
  _donutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderWidth: 2.5,
        borderColor: _t.donutBorder,
        hoverBorderWidth: 0,
        hoverOffset: 8,
        spacing: 1,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "70%",
      layout: { padding: 6 },
      animation: { animateRotate: true, animateScale: false, duration: 600, easing: "easeOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: Object.assign(ndTooltipOpts(_t), {
          callbacks: {
            title: function(items) { return items[0].label; },
            label: function(c) {
              var pct = total > 0 ? ((c.raw / total) * 100).toFixed(1) : "0";
              return " $" + c.raw.toLocaleString(undefined, {maximumFractionDigits: 0}) + "  \u00b7  " + pct + "%";
            }
          }
        })
      }
    }
  });

  _buildDonutLegend(parentData, detailData, total);
  NDDiag.track("donut", "ok", labels.length + " parent + " + Object.keys(detailData).length + " detail slices");
}

