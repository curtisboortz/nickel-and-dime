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
        html += '<tr class="' + toggleId + '" style="display:none;">';
        html += '<td style="padding:4px 6px 4px 24px;font-size:0.8rem;color:var(--text-muted);">' + _esc(c.bucket) + '</td>';
        html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">$' + c.value.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
        html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">' + c.pct.toFixed(1) + '%</td>';
        html += '<td style="padding:4px 6px;font-family:var(--mono);font-size:0.8rem;color:var(--text-muted);">' + (c.target ? c.target + '%' : '') + '</td>';
        html += '<td></td>';
        html += '</tr>';
      });
    }
  });
  tbody.innerHTML = html;
}

function loadMonthlyInvestments() {
  var tbody = document.getElementById("invest-table-body");
  var subtitle = document.getElementById("invest-subtitle");
  if (!tbody) return;
  fetch("/api/investments")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var cats = d.categories || [];
      var budget = d.monthly_budget || 0;
      var month = d.month || "";
      var monthLabel = month ? new Date(month + "-01").toLocaleDateString(undefined, {year:"numeric", month:"long"}) : "";
      if (subtitle) subtitle.textContent = monthLabel + " - Budget: $" + budget.toLocaleString(undefined, {maximumFractionDigits:0}) + " / $" + budget.toLocaleString(undefined, {maximumFractionDigits:0});

      if (cats.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted);">No investment categories set up for this month.</td></tr>';
        return;
      }

      var totalTarget = 0, totalContrib = 0;
      var html = "";
      cats.forEach(function(c) {
        var pct = budget > 0 ? Math.round((c.target / budget) * 100) : 0;
        var diff = c.contributed - c.target;
        var diffStr = (diff >= 0 ? "+" : "") + "$" + Math.abs(diff).toFixed(1);
        var diffCls = diff >= 0 ? "color:var(--success)" : "color:var(--warning)";
        var progressPct = c.target > 0 ? Math.min((c.contributed / c.target) * 100, 100) : 0;
        var barCls = progressPct < 40 ? "low" : progressPct < 90 ? "mid" : "done";
        totalTarget += c.target;
        totalContrib += c.contributed;
        html += '<tr>';
        html += '<td style="padding:8px 6px;"><strong>' + _esc(c.category) + '</strong> <span style="color:var(--text-muted);font-size:0.75rem;">(' + pct + '%)</span></td>';
        html += '<td style="padding:8px 6px;text-align:right;font-family:var(--mono);">$' + c.target.toLocaleString(undefined, {maximumFractionDigits:0}) + '</td>';
        html += '<td style="padding:8px 6px;text-align:right;"><input type="number" class="contrib-input num" data-id="' + c.id + '" data-target="' + c.target + '" value="' + c.contributed + '" style="width:80px;text-align:right;" onchange="updateInvestTotals()"></td>';
        html += '<td style="padding:8px 6px;text-align:right;font-family:var(--mono);' + diffCls + '">' + diffStr + '</td>';
        html += '<td style="padding:8px 6px;text-align:center;"><div class="progress-bar" style="width:80px;display:inline-block;"><div class="progress-fill mini-fill ' + barCls + '" style="width:' + progressPct + '%"></div></div></td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;

      var totalRem = totalTarget - totalContrib;
      var totalPct = totalTarget > 0 ? Math.min((totalContrib / totalTarget) * 100, 100) : 0;
      var itgt = document.getElementById("invest-total-target"); if (itgt) itgt.textContent = "$" + totalTarget.toLocaleString(undefined, {maximumFractionDigits:0});
      var icnt = document.getElementById("invest-total-contrib"); if (icnt) icnt.textContent = "$" + totalContrib.toLocaleString(undefined, {maximumFractionDigits:0});
      var istat = document.getElementById("invest-total-status"); if (istat) { istat.textContent = "$" + totalRem.toLocaleString(undefined, {maximumFractionDigits:0}) + " left"; istat.style.color = totalRem > 0 ? "var(--warning)" : "var(--success)"; }
      var pf = document.getElementById("total-progress-fill"); if (pf) pf.style.width = totalPct + "%";
      var pp = document.getElementById("total-progress-pct"); if (pp) pp.textContent = Math.round(totalPct) + "%";
    })
    .catch(function() {});
}

function updateInvestTotals() {
  var tc = 0, tt = 0;
  document.querySelectorAll(".contrib-input").forEach(function(i) { tc += parseFloat(i.value) || 0; tt += parseFloat(i.dataset.target) || 0; });
  var rem = tt - tc, pct = tt > 0 ? Math.min((tc / tt) * 100, 100) : 0;
  var itgt = document.getElementById("invest-total-target"); if (itgt) itgt.textContent = "$" + tt.toLocaleString(undefined, {maximumFractionDigits:0});
  var icnt = document.getElementById("invest-total-contrib"); if (icnt) icnt.textContent = "$" + tc.toLocaleString(undefined, {maximumFractionDigits:0});
  var istat = document.getElementById("invest-total-status"); if (istat) { istat.textContent = "$" + Math.abs(rem).toLocaleString(undefined, {maximumFractionDigits:0}) + (rem > 0 ? " left" : ""); istat.style.color = rem > 0 ? "var(--warning)" : "var(--success)"; }
  var pf = document.getElementById("total-progress-fill"); if (pf) pf.style.width = pct + "%";
  var pp = document.getElementById("total-progress-pct"); if (pp) pp.textContent = Math.round(pct) + "%";
}

function saveContributionsAPI() {
  var categories = [];
  document.querySelectorAll(".contrib-input").forEach(function(i) {
    categories.push({ id: parseInt(i.dataset.id), contributed: parseFloat(i.value) || 0 });
  });
  fetch("/api/investments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categories: categories })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      var btn = document.querySelector("button[onclick*='saveContributions']");
      if (btn) { btn.textContent = "Saved!"; setTimeout(function() { btn.textContent = "Save Changes"; }, 2000); }
    }
  });
}

function newMonthAPI() {
  var now = new Date();
  var month = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  if (!confirm("Start investment tracking for " + month + "? Targets will carry over, contributions reset to $0.")) return;
  fetch("/api/investments/new-month", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ month: month })
  }).then(function(r) { return r.json(); }).then(function() {
    _summaryDataLoaded = false;
    loadMonthlyInvestments();
  });
}

/* ── Add Investment Category ── */
function showAddCategoryForm() {
  var form = document.getElementById("add-category-form");
  if (form) form.style.display = form.style.display === "none" ? "block" : "none";
}
function addInvestCategory() {
  var name = document.getElementById("new-cat-name").value.trim();
  var target = parseFloat(document.getElementById("new-cat-target").value) || 0;
  if (!name) { alert("Enter a category name."); return; }
  fetch("/api/investments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ categories: [{ category: name, target: target, contributed: 0 }] })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      document.getElementById("new-cat-name").value = "";
      document.getElementById("new-cat-target").value = "";
      document.getElementById("add-category-form").style.display = "none";
      _summaryDataLoaded = false;
      loadMonthlyInvestments();
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
        if (hasChildren) {
          html += '<td style="padding:8px 6px;font-family:var(--mono);color:var(--text-muted);font-size:0.8rem;" title="Set targets on sub-categories below">' + r.target + '% (sum)</td>';
        } else {
          html += '<td style="padding:8px 6px;"><input type="number" class="target-input num" data-bucket="' + r.bucket + '" value="' + r.target + '" style="width:60px;text-align:right;" min="0" max="100">%</td>';
        }
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
            html += '<td style="padding:4px 6px;"><input type="number" class="target-input num" data-bucket="' + c.bucket + '" value="' + (c.target || 0) + '" style="width:60px;text-align:right;font-size:0.8rem;" min="0" max="100">%</td>';
            html += '<td></td>';
            html += '</tr>';
          });
        }
      });
      html += '<tr><td colspan="5" style="padding:10px 6px;text-align:right;"><button type="button" onclick="saveAllocationTargets()" style="padding:6px 16px;font-size:0.8rem;">Save Targets</button></td></tr>';
      tbody.innerHTML = html;
    });
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
  var inputs = document.querySelectorAll(".target-input");
  if (inputs.length === 0) return;
  var tactical = {};
  inputs.forEach(function(i) {
    var val = parseFloat(i.value);
    if (!isNaN(val) && val > 0) {
      tactical[i.dataset.bucket] = { target: val, min: 0, max: 100 };
    }
  });
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
var _donutColorMap = {
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
  "Retirement Blend": "#86efac"
};
var _donutFallback = ["#ef4444","#f97316","#84cc16","#06b6d4","#e879f9","#fb923c","#a3e635"];

function _donutColor(label) {
  return _donutColorMap[label] || _donutFallback[Math.abs(_hashStr(label)) % _donutFallback.length];
}
function _hashStr(s) { var h = 0; for (var i = 0; i < s.length; i++) h = ((h << 5) - h) + s.charCodeAt(i); return h; }

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
    html += '<span style="font-family:var(--mono);color:var(--text-muted);font-size:0.72rem;white-space:nowrap;">' + pct + '%</span>';
    html += '<span style="font-family:var(--mono);color:var(--text-primary);font-size:0.78rem;white-space:nowrap;">$' + val.toLocaleString(undefined, {maximumFractionDigits: 0}) + '</span>';
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
        html += '<span style="font-family:var(--mono);color:var(--text-muted);font-size:0.68rem;white-space:nowrap;">' + cpct + '%</span>';
        html += '<span style="font-family:var(--mono);color:var(--text-muted);font-size:0.7rem;white-space:nowrap;">$' + cv.toLocaleString(undefined, {maximumFractionDigits: 0}) + '</span>';
        html += '</div>';
      });
      html += '</div>';
    }
    html += '</div>';
  });
  legend.innerHTML = html;
}

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
  var ctx = document.getElementById("allocation-donut");
  if (!ctx || typeof Chart === "undefined") return;
  if (_donutChart) { try { _donutChart.destroy(); } catch(e) {} }

  var centerVal = document.getElementById("donut-center-value");
  if (centerVal) centerVal.textContent = "$" + total.toLocaleString(undefined, {maximumFractionDigits: 0});

  _donutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: "rgba(9,9,11,0.8)",
        hoverBorderWidth: 3,
        hoverBorderColor: "#fff",
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      layout: { padding: 4 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(9,9,11,0.95)",
          titleColor: "#f1f5f9", bodyColor: "#cbd5e1",
          borderColor: "rgba(255,255,255,0.08)", borderWidth: 1,
          padding: 14, cornerRadius: 10,
          titleFont: { size: 13, weight: "600" },
          bodyFont: { size: 12 },
          callbacks: {
            title: function(items) { return items[0].label; },
            label: function(c) {
              var pct = total > 0 ? ((c.raw / total) * 100).toFixed(1) : "0";
              return "$" + c.raw.toLocaleString(undefined, {maximumFractionDigits: 0}) + "  ·  " + pct + "%";
            }
          }
        }
      }
    }
  });

  _buildDonutLegend(parentData, detailData, total);
  NDDiag.track("donut", "ok", labels.length + " parent + " + Object.keys(detailData).length + " detail slices");
}

