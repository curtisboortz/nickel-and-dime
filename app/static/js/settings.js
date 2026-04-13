/* Nickel&Dime - Settings modal, integrations, category grouping */

/* ═══════════════════════════════════════════════
   Settings & Integrations (Coinbase)
   ═══════════════════════════════════════════════ */

function openSettingsModal() {
  var m = document.getElementById("settings-modal");
  if (!m) return;
  m.style.display = "flex";
  _loadIntegrationStatus();
  _loadPlaidAccounts();
  _loadBucketRollup();
  _loadCategoryColors();
  _loadReferralCode();
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
   Plaid Brokerage Connections
   ═══════════════════════════════════════════════ */

function _loadPlaidAccounts() {
  var list = document.getElementById("plaid-accounts-list");
  if (!list) return;
  fetch("/api/plaid/accounts").then(function(r) { return r.json(); }).then(function(d) {
    var accounts = d.accounts || [];
    if (accounts.length === 0) {
      list.innerHTML = '<p style="font-size:0.82rem;color:var(--text-muted);text-align:center;margin:4px 0;">No linked accounts yet.</p>';
      return;
    }
    var html = "";
    accounts.forEach(function(a) {
      var statusColor = a.status === "good" ? "#3fb950" : a.status === "login_required" ? "#d29922" : "var(--danger)";
      var statusLabel = a.status === "good" ? "Connected" : a.status === "login_required" ? "Re-auth needed" : "Error";
      var syncTime = a.last_synced_at ? new Date(a.last_synced_at).toLocaleString() : "Never";
      html += '<div style="padding:10px 12px;background:var(--bg-input);border-radius:var(--radius);display:flex;align-items:center;gap:10px;">';
      html += '<div style="flex:1;min-width:0;">';
      html += '<div style="font-size:0.88rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + _esc(a.institution_name || "Unknown") + '</div>';
      html += '<div style="font-size:0.72rem;color:var(--text-muted);">Last sync: ' + _esc(syncTime) + '</div>';
      html += '</div>';
      html += '<span style="padding:2px 8px;border-radius:10px;font-size:0.68rem;font-weight:600;background:rgba(' + (a.status === "good" ? "46,160,67,0.15" : a.status === "login_required" ? "210,153,34,0.15" : "248,81,73,0.15") + ');color:' + statusColor + ';">' + statusLabel + '</span>';
      html += '<button type="button" class="secondary" style="padding:4px 10px;font-size:0.72rem;white-space:nowrap;" onclick="syncPlaidItem(' + a.id + ', this)">Sync</button>';
      html += '<button type="button" style="padding:4px 10px;font-size:0.72rem;background:var(--danger);color:#fff;white-space:nowrap;" onclick="disconnectPlaidItem(' + a.id + ', \'' + _esc(a.institution_name || "") + '\')">Remove</button>';
      html += '</div>';
    });
    list.innerHTML = html;
  }).catch(function() {
    if (list) list.innerHTML = '<p style="font-size:0.82rem;color:var(--danger);text-align:center;">Failed to load accounts.</p>';
  });
}

function openPlaidLink() {
  var btn = document.getElementById("plaid-connect-btn");
  var msg = document.getElementById("plaid-status-msg");
  if (btn) { btn.disabled = true; btn.textContent = "Connecting..."; }
  if (msg) { msg.textContent = ""; }

  fetch("/api/plaid/link-token", { method: "POST" }).then(function(r) {
    if (!r.ok) throw new Error("Server returned " + r.status);
    return r.json();
  }).then(function(d) {
    if (d.error) {
      if (msg) { msg.textContent = d.error; msg.style.color = "var(--danger)"; }
      if (btn) { btn.disabled = false; btn.textContent = "+ Connect Account"; }
      return;
    }
    if (typeof Plaid === "undefined") {
      if (msg) { msg.textContent = "Plaid SDK not loaded. Please refresh and try again."; msg.style.color = "var(--danger)"; }
      if (btn) { btn.disabled = false; btn.textContent = "+ Connect Account"; }
      return;
    }
    var handler = Plaid.create({
      token: d.link_token,
      onSuccess: function(publicToken, metadata) {
        if (msg) { msg.textContent = "Linking account..."; msg.style.color = "var(--text-secondary)"; }
        fetch("/api/plaid/exchange-token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ public_token: publicToken, metadata: metadata })
        }).then(function(r) { return r.json(); }).then(function(result) {
          if (result.error) {
            if (msg) { msg.textContent = result.error; msg.style.color = "var(--danger)"; }
          } else {
            var inv = result.sync && result.sync.investments ? result.sync.investments : {};
            if (msg) { msg.textContent = "Linked " + _esc(result.institution || "account") + "; synced " + (inv.synced || 0) + " holdings"; msg.style.color = "var(--success)"; }
            _holdingsLoaded = false;
            if (typeof loadHoldings === "function") loadHoldings();
          }
          _loadPlaidAccounts();
          if (btn) { btn.disabled = false; btn.textContent = "+ Connect Account"; }
        }).catch(function() {
          if (msg) { msg.textContent = "Failed to link account."; msg.style.color = "var(--danger)"; }
          if (btn) { btn.disabled = false; btn.textContent = "+ Connect Account"; }
        });
      },
      onExit: function(err) {
        if (err && msg) { msg.textContent = "Connection cancelled."; msg.style.color = "var(--text-muted)"; }
        if (btn) { btn.disabled = false; btn.textContent = "+ Connect Account"; }
      },
    });
    handler.open();
  }).catch(function(e) {
    if (msg) { msg.textContent = "Failed to start connection: " + (e.message || "unknown error") + ". Try refreshing the page."; msg.style.color = "var(--danger)"; }
    if (btn) { btn.disabled = false; btn.textContent = "+ Connect Account"; }
  });
}

function syncPlaidItem(itemId, btnEl) {
  if (btnEl) { btnEl.disabled = true; btnEl.textContent = "Syncing..."; }
  var msg = document.getElementById("plaid-status-msg");
  fetch("/api/plaid/sync/" + itemId, { method: "POST" }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      if (msg) { msg.textContent = d.error; msg.style.color = "var(--danger)"; }
    } else {
      var inv = d.sync && d.sync.investments ? d.sync.investments : {};
      var txn = d.sync && d.sync.transactions ? d.sync.transactions : {};
      if (msg) { msg.textContent = "Synced " + (inv.synced || 0) + " holdings, " + (txn.added || 0) + " transactions"; msg.style.color = "var(--success)"; }
      _holdingsLoaded = false;
      if (typeof loadHoldings === "function") loadHoldings();
    }
    _loadPlaidAccounts();
    if (btnEl) { btnEl.disabled = false; btnEl.textContent = "Sync"; }
  }).catch(function() {
    if (msg) { msg.textContent = "Sync failed."; msg.style.color = "var(--danger)"; }
    if (btnEl) { btnEl.disabled = false; btnEl.textContent = "Sync"; }
  });
}

function disconnectPlaidItem(itemId, name) {
  if (!confirm("Disconnect " + (name || "this account") + "? All synced holdings and transactions from this institution will be removed.")) return;
  var msg = document.getElementById("plaid-status-msg");
  fetch("/api/plaid/accounts/" + itemId, { method: "DELETE" }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.error) {
      if (msg) { msg.textContent = d.error; msg.style.color = "var(--danger)"; }
    } else {
      if (msg) { msg.textContent = "Account disconnected."; msg.style.color = "var(--text-muted)"; }
      _holdingsLoaded = false;
      if (typeof loadHoldings === "function") loadHoldings();
    }
    _loadPlaidAccounts();
  }).catch(function() {
    if (msg) { msg.textContent = "Disconnect failed."; msg.style.color = "var(--danger)"; }
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

/* ═══════════════════════════════════════════════
   Category Colors
   ═══════════════════════════════════════════════ */

var _colorCategories = ["Equities","International","Fixed Income","Cash","Alternatives","Crypto","Real Assets","Gold","Silver","Real Estate","Art","Managed Blend","Retirement Blend"];

function _loadCategoryColors() {
  var wrap = document.getElementById("category-color-rows");
  if (!wrap) return;
  fetch("/api/settings/category-colors").then(function(r) { return r.json(); }).then(function(d) {
    var custom = d.colors || {};
    Object.keys(custom).forEach(function(k) { window.ND_CATEGORY_COLORS[k] = custom[k]; });
    var html = "";
    _colorCategories.forEach(function(cat) {
      var current = ndCategoryColor(cat);
      var defColor = ndDefaultCategoryColor(cat);
      var isCustom = custom[cat] ? true : false;
      html += '<div style="display:flex;align-items:center;gap:10px;padding:5px 0;">';
      html += '<input type="color" data-cat="' + cat + '" value="' + current + '" style="width:28px;height:28px;border:1px solid var(--border-subtle);border-radius:4px;background:none;cursor:pointer;padding:0;">';
      html += '<span style="flex:1;font-size:0.82rem;color:var(--text-primary);">' + cat + '</span>';
      if (isCustom) {
        html += '<button type="button" onclick="_resetCategoryColor(\'' + cat + '\',\'' + defColor + '\')" style="font-size:0.7rem;color:var(--text-muted);background:none;border:none;cursor:pointer;text-decoration:underline;">reset</button>';
      }
      html += '</div>';
    });
    wrap.innerHTML = html;
  }).catch(function() {});
}

function _resetCategoryColor(cat, defColor) {
  var input = document.querySelector('#category-color-rows input[data-cat="' + cat + '"]');
  if (input) input.value = defColor;
  window.ND_CATEGORY_COLORS[cat] = undefined;
}

function saveCategoryColors() {
  var btn = document.getElementById("save-colors-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Saving..."; }
  var inputs = document.querySelectorAll("#category-color-rows input[type=color]");
  var colors = {};
  inputs.forEach(function(inp) {
    var cat = inp.getAttribute("data-cat");
    var val = inp.value;
    var def = ndDefaultCategoryColor(cat);
    if (val && val !== def) colors[cat] = val;
  });
  fetch("/api/settings/category-colors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ colors: colors })
  }).then(function(r) { return r.json(); }).then(function() {
    window.ND_CATEGORY_COLORS = colors;
    if (btn) { btn.disabled = false; btn.textContent = "Saved!"; setTimeout(function() { btn.textContent = "Save Colors"; }, 1500); }
    if (typeof buildDonut === "function") buildDonut();
    if (typeof buildPerfAttribution === "function") { window.PERF_DATA = {}; buildPerfAttribution(); }
  }).catch(function() {
    if (btn) { btn.disabled = false; btn.textContent = "Save Colors"; }
    alert("Failed to save colors.");
  });
}

function resetAllCategoryColors() {
  if (!confirm("Reset all category colors to defaults?")) return;
  var inputs = document.querySelectorAll("#category-color-rows input[type=color]");
  inputs.forEach(function(inp) {
    var cat = inp.getAttribute("data-cat");
    inp.value = ndDefaultCategoryColor(cat);
  });
  window.ND_CATEGORY_COLORS = {};
  saveCategoryColors();
}

/* ── Referral Program ── */
function _loadReferralCode() {
  fetch("/api/referral/stats")
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var el = document.getElementById("referral-code-display");
      if (el) el.value = d.code || "N/A";
      var cnt = document.getElementById("referral-count");
      if (cnt) cnt.textContent = d.total_referrals || 0;
      var cred = document.getElementById("referral-credits");
      if (cred) cred.textContent = d.credits_earned || 0;
    })
    .catch(function() {});
}

function copyReferralCode() {
  var el = document.getElementById("referral-code-display");
  if (!el || !el.value) return;
  navigator.clipboard.writeText(el.value).then(function() {
    var btn = document.getElementById("referral-copy-btn");
    if (btn) {
      btn.textContent = "Copied!";
      setTimeout(function() { btn.textContent = "Copy"; }, 2000);
    }
  });
}

function redeemReferral() {
  var input = document.getElementById("referral-redeem-input");
  var msg = document.getElementById("referral-msg");
  if (!input || !input.value.trim()) return;
  fetch("/api/referral/redeem", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: input.value.trim() }),
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (msg) {
        msg.textContent = d.message || d.error || "";
        msg.style.color = d.success
          ? "var(--success)" : "var(--danger)";
      }
      if (d.success) { input.value = ""; _loadReferralCode(); }
    })
    .catch(function() {
      if (msg) {
        msg.textContent = "Network error";
        msg.style.color = "var(--danger)";
      }
    });
}

/* ── Digest preferences ── */
(function _initDigestUI() {
  var freq = document.getElementById("digest-frequency");
  var dayGrp = document.getElementById("digest-day-group");
  if (!freq || !dayGrp) return;
  function toggle() { dayGrp.style.display = freq.value === "weekly" ? "" : "none"; }
  freq.addEventListener("change", toggle);
  toggle();
})();

function sendTestDigest() {
  var btn = document.getElementById("test-digest-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Sending..."; }
  fetch("/api/settings/digest/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var t = document.createElement("div");
      t.className = "toast";
      t.textContent = d.ok ? (d.message || "Test digest sent!") : (d.error || "Failed to send");
      document.body.appendChild(t);
      setTimeout(function() { t.remove(); }, 4000);
    })
    .catch(function() {})
    .finally(function() {
      if (btn) { btn.disabled = false; btn.textContent = "Send Test"; }
    });
}

function saveDigestPrefs() {
  var enabled = document.getElementById("digest-enabled");
  var freq = document.getElementById("digest-frequency");
  var day = document.getElementById("digest-day");
  if (!enabled) return;
  fetch("/api/settings/digest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      enabled: enabled.checked,
      frequency: freq ? freq.value : "weekly",
      day: day ? day.value : "monday"
    })
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) {
        var t = document.createElement("div");
        t.className = "toast";
        t.textContent = "Digest preferences saved";
        document.body.appendChild(t);
        setTimeout(function() { t.remove(); }, 3000);
      }
    })
    .catch(function() {});
}

(function _autoInitTab() {
  var tab = window.ACTIVE_TAB;
  if (tab === "holdings" && !_holdingsLoaded) {
    loadHoldings();
  } else if (tab === "balances" && typeof loadBalances === "function") {
    loadBalances();
  }
})();

