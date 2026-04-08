/* Nickel&Dime - Balances tab and bucket helpers */
/* ══════════════════════════════════════════════════════
   Balances Tab — fetch /api/balances, render editable table, save
   ══════════════════════════════════════════════════════ */
var _balancesLoaded = false;
var _balOpenMenu = null;

function _closeBalsMenu() {
  if (_balOpenMenu) { _balOpenMenu.remove(); _balOpenMenu = null; }
  document.removeEventListener("click", _closeBalsMenu);
}

function _openBalMenu(e, id, name, idx, total) {
  e.stopPropagation();
  _closeBalsMenu();
  var btn = e.currentTarget;
  var menu = document.createElement("div");
  menu.className = "bal-menu";
  var items = [];
  items.push('<button onclick="renameBalance(' + id + ',this)">Rename</button>');
  if (idx > 0) items.push('<button onclick="moveBalance(' + id + ',\'up\')">Move Up</button>');
  if (idx < total - 1) items.push('<button onclick="moveBalance(' + id + ',\'down\')">Move Down</button>');
  items.push('<button class="danger" onclick="deleteBalance(' + id + ')">Delete</button>');
  menu.innerHTML = items.join("");
  btn.parentElement.appendChild(menu);
  _balOpenMenu = menu;
  setTimeout(function() { document.addEventListener("click", _closeBalsMenu); }, 0);
}

var STANDARD_BUCKETS_FALLBACK = ["Alternatives","Art","Cash","Crypto","Equities","Fixed Income","Gold","International","Managed Blend","Real Assets","Real Estate","Retirement Blend","Silver"];

var _BUCKET_HINTS = {
  "Art": "Real Assets", "Gold": "Real Assets", "Silver": "Real Assets",
  "Real Estate": "Real Assets", "International": "Equities",
  "Managed Blend": "Equities", "Retirement Blend": "Equities",
  "Crypto": "Alternatives"
};

var _CLIENT_BUCKET_ALIASES = {
  "realassets": "Real Assets", "fixedincome": "Fixed Income",
  "managedblend": "Managed Blend", "retirementblend": "Retirement Blend",
  "realestate": "Real Estate"
};

function _normalizeBucketClient(name) {
  if (!name) return name;
  var key = name.toLowerCase().replace(/\s+/g, "");
  if (_CLIENT_BUCKET_ALIASES[key]) return _CLIENT_BUCKET_ALIASES[key];
  var fb = STANDARD_BUCKETS_FALLBACK;
  for (var i = 0; i < fb.length; i++) {
    if (fb[i].toLowerCase().replace(/\s+/g, "") === key) return fb[i];
  }
  return name;
}

function _bucketLabel(b) {
  var hint = _BUCKET_HINTS[b];
  return hint ? b + "  (" + hint + ")" : b;
}

function _buildBalBucketSelect(selected) {
  selected = _normalizeBucketClient(selected);
  var opts = _bucketOptions.length ? _bucketOptions : STANDARD_BUCKETS_FALLBACK;
  var s = '<select class="bal-bucket" style="padding:6px 8px;font-size:0.82rem;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);appearance:auto;min-width:100px;">';
  s += '<option value="">Category</option>';
  opts.forEach(function(b) { s += '<option value="' + b + '"' + (b === selected ? ' selected' : '') + '>' + _bucketLabel(b) + '</option>'; });
  if (selected && opts.indexOf(selected) === -1) s += '<option value="' + selected + '" selected>' + selected + '</option>';
  s += '<option value="__custom__">+ Custom...</option>';
  s += '</select>';
  return s;
}

function _smartDetectBucket(name) {
  var n = (name || "").toLowerCase();
  if (/check|saving|cash|money.?market|spaxx|fzfxx/i.test(n)) return "Cash";
  if (/ira|401k|403b|roth|retire|target.?date/i.test(n)) return "Retirement Blend";
  if (/crypto|bitcoin|coinbase|binance/i.test(n)) return "Crypto";
  if (/gold/i.test(n)) return "Gold";
  if (/silver/i.test(n)) return "Silver";
  if (/real.?estate|reit|property/i.test(n)) return "Real Estate";
  if (/bond|fixed|treasury|tips/i.test(n)) return "Fixed Income";
  if (/international|foreign|emerg/i.test(n)) return "International";
  if (/brokerage|stock|equity|etf|index|fund|fidelity|schwab|vanguard|robinhood/i.test(n)) return "Equities";
  return "";
}

function loadBalances() {
  if (_balancesLoaded) return;
  _balancesLoaded = true;
  NDDiag.track("balances", "loading");
  var wrap = document.getElementById("balances-table-wrap");
  if (!wrap) return;

  var bucketsP = _bucketOptions.length
    ? Promise.resolve()
    : fetch("/api/buckets").then(function(r) { return r.json(); }).then(function(bk) {
        _bucketOptions = (bk.standard || []).concat(bk.custom || []);
      }).catch(function() {});

  bucketsP.then(function() {
    return fetch("/api/balances").then(function(r) { return r.json(); });
  }).then(function(d) {
      var accts = d.accounts || [];
      var html = "";
      if (accts.length > 0) {
        html += '<table style="width:100%;border-collapse:collapse;">';
        html += '<thead><tr>';
        html += '<th style="width:28px;padding:10px 0;"></th>';
        html += '<th style="text-align:left;padding:10px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600;">Account</th>';
        html += '<th style="text-align:left;padding:10px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600;">Category</th>';
        html += '<th style="text-align:right;padding:10px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--text-muted);font-weight:600;">Value ($)</th>';
        html += '</tr></thead><tbody>';
        accts.forEach(function(a, idx) {
          var currentBucket = (a.allocations && a.allocations.asset_class) || "";
          var isPlaid = (a.source || "manual") !== "manual";
          html += '<tr class="bal-row" data-acct-id="' + a.id + '">';
          if (isPlaid) {
            html += '<td style="width:28px;padding:10px 0;border-bottom:1px solid var(--border-subtle);text-align:center;" title="Synced via Plaid"><svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:none;stroke:var(--text-muted);stroke-width:2;vertical-align:middle;"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg></td>';
            html += '<td class="bal-name-cell" data-acct-id="' + a.id + '" style="padding:14px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.92rem;font-weight:500;">' + (a.name || "Account") + ' <span style="font-size:0.62rem;background:rgba(99,102,241,0.15);color:#a5b4fc;padding:2px 5px;border-radius:3px;margin-left:4px;">Synced</span></td>';
            html += '<td style="padding:10px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.82rem;color:var(--text-muted);">' + _bucketLabel(currentBucket) + '</td>';
            html += '<td style="text-align:right;padding:14px 10px;border-bottom:1px solid var(--border-subtle);font-family:var(--mono);font-size:0.92rem;font-weight:500;color:var(--text-primary);">$' + (a.value || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</td>';
          } else {
            html += '<td style="width:28px;padding:10px 0;border-bottom:1px solid var(--border-subtle);position:relative;">';
            html += '<button class="bal-kebab" onclick="_openBalMenu(event,' + a.id + ',\'' + (a.name || "").replace(/'/g, "\\'") + '\',' + idx + ',' + accts.length + ')" title="Options">&#8942;</button>';
            html += '</td>';
            html += '<td class="bal-name-cell" data-acct-id="' + a.id + '" style="padding:14px 10px;border-bottom:1px solid var(--border-subtle);font-size:0.92rem;font-weight:500;">' + (a.name || "Account") + '</td>';
            html += '<td style="padding:10px 10px;border-bottom:1px solid var(--border-subtle);">' + _buildBalBucketSelect(currentBucket) + '</td>';
            html += '<td style="text-align:right;padding:14px 10px;border-bottom:1px solid var(--border-subtle);font-family:var(--mono);font-size:0.92rem;font-weight:500;">';
            html += '<input type="text" inputmode="decimal" class="bal-input" data-acct-id="' + a.id + '" value="' + (a.value || 0) + '" style="width:140px;text-align:right;padding:6px 10px;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);font-family:var(--mono);font-size:0.92rem;">';
            html += '</td>';
          }
          html += '</tr>';
        });
        html += '</tbody></table>';
      } else {
        html += '<p class="hint" style="margin-bottom:14px;">No accounts yet. Add one below to start tracking your balances.</p>';
      }
      html += '<div style="display:flex;gap:8px;align-items:end;margin-top:16px;flex-wrap:wrap;">';
      html += '<input type="text" id="new-acct-name" placeholder="Account name (e.g. Fidelity IRA)" style="flex:1;min-width:160px;padding:8px 12px;font-size:0.88rem;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);">';
      html += '<div id="new-acct-bucket-wrap" style="min-width:120px;">' + _buildBalBucketSelect("") + '</div>';
      html += '<input type="text" inputmode="decimal" id="new-acct-value" placeholder="Balance" style="width:120px;padding:8px 12px;font-size:0.88rem;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);text-align:right;">';
      html += '<button onclick="addBalance()" style="padding:8px 16px;font-size:0.85rem;background:var(--accent-primary);color:#fff;border:none;border-radius:6px;cursor:pointer;white-space:nowrap;">+ Add Account</button>';
      html += '</div>';
      wrap.innerHTML = html;

      wrap.querySelectorAll("select.bal-bucket").forEach(function(sel) {
        sel.addEventListener("change", function() { _handleBucketCustom(this); });
      });

      var nameInput = document.getElementById("new-acct-name");
      if (nameInput) {
        nameInput.addEventListener("blur", function() {
          var detected = _smartDetectBucket(this.value);
          if (detected) {
            var bucketSel = document.querySelector("#new-acct-bucket-wrap select.bal-bucket");
            if (bucketSel && !bucketSel.value) bucketSel.value = detected;
          }
        });
      }

      NDDiag.track("balances", "ok", accts.length + " accounts");
    })
    .catch(function(e) {
      wrap.innerHTML = '<p class="hint" style="color:var(--danger);">Failed to load accounts.</p>';
      NDDiag.track("balances", "error", e.message || String(e));
      _balancesLoaded = false;
    });
}

function addBalance() {
  var name = document.getElementById("new-acct-name");
  var value = document.getElementById("new-acct-value");
  var bucketSel = document.querySelector("#new-acct-bucket-wrap select.bal-bucket");
  if (!name || !name.value.trim()) { if (name) name.focus(); return; }
  var alloc = {};
  if (bucketSel && bucketSel.value && bucketSel.value !== "__custom__") alloc.asset_class = bucketSel.value;
  fetch("/api/balances", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_account: { name: name.value.trim(), value: parseFloat(value && value.value || 0), allocations: alloc } })
  }).then(function() {
    _balancesLoaded = false;
    loadBalances();
  });
}

function deleteBalance(id) {
  _closeBalsMenu();
  if (!confirm("Remove this account?")) return;
  fetch("/api/balances/" + id, { method: "DELETE" })
    .then(function() { _balancesLoaded = false; loadBalances(); });
}

function renameBalance(id) {
  _closeBalsMenu();
  var cell = document.querySelector('.bal-name-cell[data-acct-id="' + id + '"]');
  if (!cell) return;
  var current = cell.textContent.trim();
  var input = document.createElement("input");
  input.type = "text";
  input.value = current;
  input.className = "bal-rename-input";
  input.style.cssText = "width:100%;padding:6px 10px;font-size:0.92rem;font-weight:500;background:var(--bg-input);border:1px solid var(--accent-primary);border-radius:6px;color:var(--text-primary);";
  cell.textContent = "";
  cell.appendChild(input);
  input.focus();
  input.select();
  function commit() {
    var newName = input.value.trim();
    if (!newName || newName === current) { cell.textContent = current; return; }
    cell.textContent = newName;
    fetch("/api/balances/rename", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id, name: newName })
    });
  }
  input.addEventListener("blur", commit);
  input.addEventListener("keydown", function(e) {
    if (e.key === "Enter") { e.preventDefault(); input.blur(); }
    if (e.key === "Escape") { cell.textContent = current; }
  });
}

function moveBalance(id, direction) {
  _closeBalsMenu();
  var rows = document.querySelectorAll(".bal-row");
  var order = [];
  rows.forEach(function(r) { order.push(parseInt(r.getAttribute("data-acct-id"))); });
  var idx = order.indexOf(id);
  if (idx < 0) return;
  var swapIdx = direction === "up" ? idx - 1 : idx + 1;
  if (swapIdx < 0 || swapIdx >= order.length) return;
  var tmp = order[idx];
  order[idx] = order[swapIdx];
  order[swapIdx] = tmp;
  fetch("/api/balances/reorder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order: order })
  }).then(function() { _balancesLoaded = false; loadBalances(); });
}

function saveAllBalances() {
  var rows = document.querySelectorAll(".bal-row");
  var accounts = [];
  rows.forEach(function(tr) {
    var id = parseInt(tr.getAttribute("data-acct-id"));
    var inp = tr.querySelector(".bal-input");
    var sel = tr.querySelector("select.bal-bucket");
    var val = inp ? parseFloat(inp.value) || 0 : 0;
    var bucket = sel ? sel.value : "";
    var item = { id: id, value: val };
    if (bucket && bucket !== "__custom__") item.asset_class = bucket;
    accounts.push(item);
  });
  fetch("/api/balances", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accounts: accounts })
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.success) {
        var btn = document.querySelector('#tab-balances .success');
        if (btn) { btn.textContent = "Saved!"; setTimeout(function(){ btn.textContent = "Save Balances"; }, 2000); }
      }
    });
}
