/* Nickel&Dime - Settings modal, integrations, category grouping */

/* ═══════════════════════════════════════════════
   Settings & Integrations (Coinbase)
   ═══════════════════════════════════════════════ */

function openSettingsModal() {
  var m = document.getElementById("settings-modal");
  if (!m) return;
  m.style.display = "flex";
  _loadIntegrationStatus();
  _loadBucketRollup();
}

function closeSettingsModal() {
  var m = document.getElementById("settings-modal");
  if (m) m.style.display = "none";
}

function _loadIntegrationStatus() {
  var badge = document.getElementById("cb-status-badge");
  var connPanel = document.getElementById("cb-connected-panel");
  var setupPanel = document.getElementById("cb-setup-panel");
  fetch("/api/settings/integrations").then(function(r) { return r.json(); }).then(function(d) {
    if (d.coinbase && d.coinbase.connected) {
      if (badge) { badge.textContent = "Connected"; badge.style.background = "rgba(46,160,67,0.15)"; badge.style.color = "#3fb950"; }
      if (connPanel) connPanel.style.display = "block";
      if (setupPanel) setupPanel.style.display = "none";
      var hint = document.getElementById("cb-key-hint");
      if (hint && d.coinbase.key_hint) hint.textContent = d.coinbase.key_hint;
    } else {
      if (badge) { badge.textContent = "Not connected"; badge.style.background = "var(--bg-input)"; badge.style.color = "var(--text-muted)"; }
      if (connPanel) connPanel.style.display = "none";
      if (setupPanel) setupPanel.style.display = "block";
    }
  }).catch(function() {
    if (badge) { badge.textContent = "Error"; badge.style.color = "var(--danger)"; }
  });
}

function saveCoinbaseKeys() {
  var keyName = document.getElementById("cb-key-name");
  var privKey = document.getElementById("cb-private-key");
  var btn = document.getElementById("cb-save-btn");
  if (!keyName || !keyName.value.trim() || !privKey || !privKey.value.trim()) {
    alert("Please enter both the API Key Name and Private Key.");
    return;
  }
  if (btn) { btn.disabled = true; btn.textContent = "Connecting..."; }
  fetch("/api/settings/coinbase-keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      key_name: keyName.value.trim(),
      private_key: privKey.value.trim()
    })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      alert(d.error);
      if (btn) { btn.disabled = false; btn.textContent = "Connect & Sync"; }
      return;
    }
    keyName.value = "";
    privKey.value = "";
    syncCoinbaseNow(true);
    _loadIntegrationStatus();
  }).catch(function() {
    alert("Failed to save keys. Please try again.");
    if (btn) { btn.disabled = false; btn.textContent = "Connect & Sync"; }
  });
}

function syncCoinbaseNow(isInitial) {
  var btn = document.getElementById("cb-sync-btn");
  var status = document.getElementById("cb-sync-status");
  if (btn) { btn.disabled = true; btn.textContent = "Syncing..."; }
  if (status) { status.textContent = "Fetching balances from Coinbase..."; status.style.color = "var(--text-secondary)"; }
  fetch("/api/coinbase-sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      if (status) { status.textContent = d.error; status.style.color = "var(--danger)"; }
    } else {
      var msg = "Synced " + d.synced + " asset" + (d.synced !== 1 ? "s" : "");
      if (d.removed > 0) msg += ", removed " + d.removed;
      if (status) { status.textContent = msg; status.style.color = "var(--success)"; }
      _holdingsLoaded = false;
      if (typeof loadHoldings === "function") loadHoldings();
    }
    if (btn) { btn.disabled = false; btn.textContent = "Sync Now"; }
    if (isInitial) {
      var saveBtn = document.getElementById("cb-save-btn");
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Connect & Sync"; }
    }
  }).catch(function() {
    if (status) { status.textContent = "Sync failed. Please try again."; status.style.color = "var(--danger)"; }
    if (btn) { btn.disabled = false; btn.textContent = "Sync Now"; }
  });
}

function disconnectCoinbase() {
  if (!confirm("Disconnect Coinbase? Your crypto holdings data will remain, but auto-sync will stop.")) return;
  fetch("/api/settings/coinbase-keys", { method: "DELETE" }).then(function() {
    _loadIntegrationStatus();
    var status = document.getElementById("cb-sync-status");
    if (status) status.textContent = "";
  });
}

/* ═══════════════════════════════════════════════
   Category Grouping (bucket rollup settings)
   ═══════════════════════════════════════════════ */

var _rollupDefaults = {};
var _rollupOverrides = {};
var _rollupSubcats = ["Managed Blend","Retirement Blend","International","Real Estate","Art","Gold","Silver","Crypto"];
var _rollupParentOptions = ["Equities","Real Assets","Alternatives","Cash","Fixed Income"];

function _loadBucketRollup() {
  var wrap = document.getElementById("bucket-rollup-rows");
  if (!wrap) return;
  fetch("/api/settings/bucket-rollup").then(function(r) { return r.json(); }).then(function(d) {
    _rollupDefaults = d.defaults || {};
    _rollupOverrides = d.overrides || {};
    var effective = d.effective || {};
    var html = "";
    _rollupSubcats.forEach(function(child) {
      var defaultParent = _rollupDefaults[child] || "Standalone";
      var currentParent = effective[child] || null;
      var isOverridden = child in _rollupOverrides;
      html += '<div style="display:flex;align-items:center;gap:10px;padding:6px 0;">';
      html += '<span style="font-size:0.85rem;min-width:120px;color:var(--text-primary);">' + child + '</span>';
      html += '<select data-child="' + child + '" class="rollup-sel" style="flex:1;padding:5px 8px;font-size:0.82rem;background:var(--bg-input);border:1px solid var(--border-subtle);border-radius:6px;color:var(--text-primary);appearance:auto;">';
      _rollupParentOptions.forEach(function(p) {
        var sel = (currentParent === p) ? " selected" : "";
        var isDefault = (p === defaultParent);
        html += '<option value="' + p + '"' + sel + '>' + p + (isDefault ? " (default)" : "") + '</option>';
      });
      var standaloneSelected = !currentParent ? " selected" : "";
      html += '<option value="__standalone__"' + standaloneSelected + '>Standalone</option>';
      html += '</select>';
      html += '</div>';
    });
    wrap.innerHTML = html;
  }).catch(function() {
    if (wrap) wrap.innerHTML = '<p style="font-size:0.82rem;color:var(--text-muted);">Could not load category settings.</p>';
  });
}

function saveBucketRollup() {
  var selects = document.querySelectorAll(".rollup-sel");
  var overrides = {};
  selects.forEach(function(sel) {
    var child = sel.getAttribute("data-child");
    var val = sel.value;
    var defaultParent = _rollupDefaults[child] || null;
    if (val === "__standalone__") {
      if (defaultParent) overrides[child] = null;
    } else if (val !== defaultParent) {
      overrides[child] = val;
    }
  });
  var btn = document.getElementById("rollup-save-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Saving..."; }
  fetch("/api/settings/bucket-rollup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ overrides: overrides })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (btn) { btn.disabled = false; btn.textContent = "Saved!"; setTimeout(function() { btn.textContent = "Save Grouping"; }, 1500); }
    _rollupOverrides = overrides;
    _summaryDataLoaded = false;
    _holdingsLoaded = false;
    _allocData = null;
    if (typeof loadSummaryData === "function") loadSummaryData();
  }).catch(function() {
    if (btn) { btn.disabled = false; btn.textContent = "Save Grouping"; }
    alert("Failed to save category grouping.");
  });
}

(function _autoInitTab() {
  var tab = window.ACTIVE_TAB;
  if (tab === "holdings" && !_holdingsLoaded) {
    loadHoldings();
  } else if (tab === "balances" && typeof loadBalances === "function") {
    loadBalances();
  }
})();

