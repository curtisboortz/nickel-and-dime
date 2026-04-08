/* Nickel&Dime - Pulse cards, sparklines, investment tracker */
/* ── Sparklines ── */
function renderSparkCanvas(canvasId, values) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || !values || values.length < 2) return;
  if (canvas.offsetWidth < 5 || canvas.offsetHeight < 5) return;
  var ctx = canvas.getContext("2d");
  var w = canvas.width = canvas.offsetWidth * 2;
  var h = canvas.height = canvas.offsetHeight * 2;
  ctx.scale(2, 2);
  var cw = canvas.offsetWidth, ch = canvas.offsetHeight;
  var mn = Math.min.apply(null, values), mx = Math.max.apply(null, values);
  var range = mx - mn || 1;
  var up = values[values.length-1] >= values[0];
  ctx.beginPath();
  ctx.strokeStyle = up ? "#34d399" : "#f87171";
  ctx.lineWidth = 1.5; ctx.lineJoin = "round";
  for (var i = 0; i < values.length; i++) {
    var x = (i / (values.length - 1)) * cw;
    var y = ch - ((values[i] - mn) / range) * (ch - 4) - 2;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.lineTo(cw, ch); ctx.lineTo(0, ch); ctx.closePath();
  var grad = ctx.createLinearGradient(0, 0, 0, ch);
  grad.addColorStop(0, up ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = grad; ctx.fill();
}
function loadAllSparklines() {
  // Dynamically build spark map from all pulse items with spark canvases
  var map = {};
  var cryptoSymbols = [];
  document.querySelectorAll(".pulse-spark").forEach(function(c) {
    var id = c.id;
    if (id) {
      var sym = id.substring(6); // remove "spark-"
      if (sym.match(/^[A-Z]{1,3}-F$/)) sym = sym.replace("-F", "=F");
      var parent = c.closest(".pulse-item");
      var ptype = parent && parent.dataset.pulseType ? parent.dataset.pulseType : "stock";
      map[sym] = id;
      if (ptype === "crypto") cryptoSymbols.push(sym);
    }
  });
  if (Object.keys(map).length === 0) return;
  var url = "/api/sparklines?symbols=" + encodeURIComponent(Object.keys(map).join(","));
  if (cryptoSymbols.length) url += "&crypto=" + encodeURIComponent(cryptoSymbols.join(","));
  fetch(url)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      for (var sym in map) {
        if (data[sym] && data[sym].length > 1) renderSparkCanvas(map[sym], data[sym]);
      }
    })
    .catch(function() {});
}

/* ── Investment Tracker ── */
function updateProgressBar(input) {
  var key=input.dataset.key, target=parseFloat(input.dataset.target)||1, contributed=parseFloat(input.value)||0;
  var pct=Math.min((contributed/target)*100,100), diff=contributed-target;
  var bar=document.getElementById("progress-"+key);
  if(bar) { bar.style.width=pct+"%"; bar.className="mini-fill "+(pct<40?"low":pct<90?"mid":"done"); }
  var st=document.getElementById("status-"+key);
  if(st) {
    if(diff>=0) { st.textContent="+$"+diff.toFixed(0); st.className=diff>0?"surplus":"complete"; }
    else { st.textContent="-$"+Math.abs(diff).toFixed(0); st.className="shortage"; }
  }
  updateTotals();
}
function updateTotals() {
  var tc=0, tt=0;
  document.querySelectorAll(".contrib-input").forEach(function(i) { tc+=parseFloat(i.value)||0; tt+=parseFloat(i.dataset.target)||0; });
  var rem=tt-tc, pct=tt>0?Math.min((tc/tt)*100,100):0;
  var row=document.querySelector(".invest-table tfoot tr");
  if(row) {
    var cells=row.querySelectorAll("td");
    if(cells[2]) cells[2].innerHTML="<span class='mono' style='color:var(--accent-primary)'>$"+tc.toFixed(0)+"</span>";
    if(cells[3]) cells[3].innerHTML="<span class='mono' style='color:"+(rem>0?"var(--warning)":"var(--success)")+"'>$"+rem.toFixed(0)+" left</span>";
  }
  var pf=document.getElementById("total-progress-fill"); if(pf) pf.style.width=pct+"%";
  var pl=document.getElementById("total-progress-pct"); if(pl) pl.textContent=Math.round(pct)+"%";
}
function saveContributions() {
  var data={};
  document.querySelectorAll(".contrib-input").forEach(function(i) { data[i.dataset.key]=parseFloat(i.value)||0; });
  fetch("/api/save-contributions",{ method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data) })
  .then(function(r){ return r.json(); })
  .then(function(res){
    if(res.success) {
      var btn=document.querySelector("button[onclick*='saveContributions']");
      if(btn) { btn.textContent="Saved!"; }
      setTimeout(function() { ndSoftReload(); }, 600);
    }
  });
}
function newMonth() {
  if(!confirm("Start a new month? This resets all investment contributions to $0.")) return;
  fetch("/api/new-month",{method:"POST"}).then(function(r){return r.json();}).then(function(d){ if(d.success) ndSoftReload(); });
}
function newBudgetMonth() {
  if(!confirm("Start a new budget month? This updates both budget and investment months, and resets contributions.")) return;
  fetch("/api/new-budget-month",{method:"POST"}).then(function(r){return r.json();}).then(function(d){ if(d.success) ndSoftReload(); });
}
var saveTimeout;
function _autoSaveContributions() {
  var data={};
  document.querySelectorAll(".contrib-input").forEach(function(i) { data[i.dataset.key]=parseFloat(i.value)||0; });
  fetch("/api/save-contributions",{ method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data) });
}
document.querySelectorAll(".contrib-input").forEach(function(input) {
  input.addEventListener("input", function() { updateProgressBar(this); clearTimeout(saveTimeout); saveTimeout=setTimeout(_autoSaveContributions,1000); });
  input.addEventListener("change", function() { updateProgressBar(this); clearTimeout(saveTimeout); saveTimeout=setTimeout(_autoSaveContributions,500); });
});

/* ── Investment Quick-Log Chat ── */
var INVEST_ALIASES = {
  "gold etf": "gold_etf", "gold": "gold_etf", "gld": "gold_etf", "gldm": "gold_etf", "iau": "gold_etf",
  "gold savings": "gold_phys_save", "gold save": "gold_phys_save", "gold physical": "gold_phys_save", "physical gold": "gold_phys_save",
  "silver etf": "silver_etf", "silver": "silver_etf", "slv": "silver_etf", "pslv": "silver_etf",
  "silver savings": "silver_phys_save", "silver save": "silver_phys_save", "silver physical": "silver_phys_save", "physical silver": "silver_phys_save",
  "crypto": "crypto", "bitcoin": "crypto", "btc": "crypto", "eth": "crypto", "ethereum": "crypto", "coinbase": "crypto",
  "equities": "equities", "stocks": "equities", "stock": "equities", "spy": "equities", "voo": "equities",
  "xar": "equities", "fidelity": "equities", "etf": "equities", "index": "equities",
  "real assets": "real_assets", "real estate": "real_assets", "fundrise": "real_assets", "masterworks": "real_assets", "art": "real_assets",
  "cash": "cash", "cash reserve": "cash", "savings": "cash", "emergency": "cash",
  "stash": "equities", "stash personal": "equities", "stash smart": "equities",
  "stash retirement": "equities", "retirement": "equities", "401k": "equities", "ira": "equities",
  "acorns": "equities", "acorns invest": "equities", "acorns later": "equities",
};
var INVEST_NAMES = {
  "gold_etf": "Gold ETF", "gold_phys_save": "Gold Savings",
  "silver_etf": "Silver ETF", "silver_phys_save": "Silver Savings",
  "crypto": "Crypto", "equities": "Equities",
  "real_assets": "Real Assets", "cash": "Cash Reserve",
};
function matchCategory(text) {
  var t = text.toLowerCase().trim();
  // Exact match first
  if (INVEST_ALIASES[t]) return INVEST_ALIASES[t];
  // Partial match
  for (var alias in INVEST_ALIASES) {
    if (t.indexOf(alias) !== -1 || alias.indexOf(t) !== -1) return INVEST_ALIASES[alias];
  }
  // Fuzzy: check each word
  var words = t.split(/\s+/);
  for (var w = 0; w < words.length; w++) {
    if (INVEST_ALIASES[words[w]]) return INVEST_ALIASES[words[w]];
  }
  return null;
}
function processInvestChat() {
  var input = document.getElementById("invest-chat-input");
  var log = document.getElementById("chat-log");
  var raw = input.value.trim();
  if (!raw) return;

  // Split by comma for multiple entries
  var entries = raw.split(",");
  var results = [];
  var hasMetalEntry = false;
  var hasContribEntry = false;
  entries.forEach(function(entry) {
    entry = entry.trim();
    if (!entry) return;

    // ── Physical metals purchase detection ──
    // Patterns: "bought 5oz silver at $31", "bought 1oz gold for $2700",
    //           "added 10oz silver bar", "5oz gold at $2800"
    var metalMatch = entry.match(/(?:bought|added|purchased|buy)?\s*(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)\s+(?:of\s+)?(gold|silver)(?:\s+([\w\s]+?))?(?:\s+(?:at|for|@)\s+\$?\s*(\d+(?:\.\d{1,2})?))?/i);
    if (!metalMatch) {
      // Also try: "gold 5oz at $2800"
      metalMatch = entry.match(/(?:bought|added|purchased|buy)?\s*(gold|silver)\s+(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)(?:\s+([\w\s]+?))?(?:\s+(?:at|for|@)\s+\$?\s*(\d+(?:\.\d{1,2})?))?/i);
      if (metalMatch) {
        // Rearrange so [1]=qty, [2]=metal, [3]=form, [4]=price
        var _m = metalMatch;
        metalMatch = [_m[0], _m[2], _m[1], _m[3], _m[4]];
      }
    }
    if (metalMatch) {
      var mQty = parseFloat(metalMatch[1]);
      var mMetal = metalMatch[2].charAt(0).toUpperCase() + metalMatch[2].slice(1).toLowerCase();
      var mForm = (metalMatch[3] || "").trim();
      var mCost = metalMatch[4] ? parseFloat(metalMatch[4]) : 0;
      if (mQty <= 0) {
        results.push({ ok: false, msg: "Quantity must be > 0" });
        return;
      }
      // POST to physical metals API
      fetch("/api/physical-metals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metal: mMetal, form: mForm, qty_oz: mQty, cost_per_oz: mCost, date: "", note: "Logged via chat" })
      }).then(function(r) { return r.json(); }).then(function(d) {
        var div = document.createElement("div");
        if (d.ok) {
          var priceNote = mCost > 0 ? " at $" + mCost.toFixed(2) + "/oz" : "";
          div.className = "chat-msg ok";
          div.innerHTML = '<span class="chat-label">&#10003;</span>Logged ' + mQty + 'oz ' + mMetal + priceNote;
        } else {
          div.className = "chat-msg err";
          div.innerHTML = '<span class="chat-label">&#10007;</span>' + (d.error || "Error saving metal");
        }
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
      }).catch(function() {
        var div = document.createElement("div");
        div.className = "chat-msg err";
        div.innerHTML = '<span class="chat-label">&#10007;</span>Network error saving metal';
        log.appendChild(div);
      });
      hasMetalEntry = true;
      return;  // Don't process as contribution
    }

    // ── Normal contribution + holdings/balance processing ──
    // Extract dollar amount: $100, 100, etc.
    var amountMatch = entry.match(/\$?\s*(\d+(?:\.\d{1,2})?)/);
    if (!amountMatch) {
      results.push({ ok: false, msg: 'No amount found in "' + entry + '"' });
      return;
    }
    var amount = parseFloat(amountMatch[1]);
    // Remove the amount portion to get the category text
    var catText = entry.replace(amountMatch[0], "").replace(/^\s*to\s+/i, "").replace(/\s*to\s*$/i, "").trim();
    catText = catText.replace(/^to\s+/i, "").replace(/^add\s+/i, "").trim();
    if (!catText) {
      results.push({ ok: false, msg: 'No category found in "' + entry + '"' });
      return;
    }
    // Parse optional "in [account]" suffix: "100 to pslv in fidelity"
    var acctMatch = catText.match(/^(.+?)\s+(?:in|at|for)\s+(.+)$/i);
    var rawTarget = acctMatch ? acctMatch[1].trim() : catText;
    var acctHint = acctMatch ? acctMatch[2].trim() : "";

    // Try contribution category match
    var key = matchCategory(rawTarget);
    if (key) {
      var field = document.querySelector('.contrib-input[data-key="' + key + '"]');
      if (field) {
        var oldVal = parseFloat(field.value) || 0;
        var newVal = oldVal + amount;
        field.value = Math.round(newVal);
        updateProgressBar(field);
        hasContribEntry = true;
        results.push({ ok: true, msg: '+$' + amount.toFixed(0) + ' to ' + INVEST_NAMES[key] + ' (now $' + Math.round(newVal) + ')' });
      }
    }

    // Also try to update holdings/balances via quick-update API
    // (rawTarget could be a ticker like PSLV, or a balance account like Fundrise)
    fetch("/api/quick-update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: amount, target: rawTarget, account: acctHint })
    }).then(function(r) { return r.json(); }).then(function(d) {
      var div = document.createElement("div");
      if (d.ok && d.type === "holding") {
        div.className = "chat-msg ok";
        var sharesNote = d.shares_added ? ' (+' + d.shares_added + ' shares @ $' + d.price.toFixed(2) + ')' : '';
        var cashNote = d.cash_deducted ? ' | SPAXX: $' + d.old_cash.toLocaleString(undefined, {maximumFractionDigits:0}) + ' &rarr; $' + d.new_cash.toLocaleString(undefined, {maximumFractionDigits:0}) : '';
        div.innerHTML = '<span class="chat-label">&#10003;</span>' + d.ticker + (d.account ? ' (' + d.account + ')' : '') + ': $' + d.old_value.toLocaleString(undefined, {maximumFractionDigits:0}) + ' &rarr; $' + d.new_value.toLocaleString(undefined, {maximumFractionDigits:0}) + sharesNote + cashNote;
        log.appendChild(div);
      } else if (d.ok && d.type === "balance") {
        div.className = "chat-msg ok";
        div.innerHTML = '<span class="chat-label">&#10003;</span>' + d.name + ': $' + d.old_value.toLocaleString(undefined, {maximumFractionDigits:0}) + ' &rarr; $' + d.new_value.toLocaleString(undefined, {maximumFractionDigits:0});
        log.appendChild(div);
      } else if (!key) {
        // Only show error if we also failed the contribution match
        div.className = "chat-msg err";
        div.innerHTML = '<span class="chat-label">&#10007;</span>No match for "' + rawTarget + '" in contributions, holdings, or balances';
        log.appendChild(div);
      }
      log.scrollTop = log.scrollHeight;
    }).catch(function() {});
  });

  // Render results in chat log
  results.forEach(function(r) {
    var div = document.createElement("div");
    div.className = "chat-msg " + (r.ok ? "ok" : "err");
    div.innerHTML = '<span class="chat-label">' + (r.ok ? "&#10003;" : "&#10007;") + '</span>' + r.msg;
    log.appendChild(div);
  });
  log.scrollTop = log.scrollHeight;

  // Clear input and auto-save contributions if any
  input.value = "";
  if (hasContribEntry && results.some(function(r) { return r.ok; })) {
    clearTimeout(saveTimeout);
    // Save contributions then reload to reflect updated totals
    var cdata={};
    document.querySelectorAll(".contrib-input").forEach(function(i) { cdata[i.dataset.key]=parseFloat(i.value)||0; });
    fetch("/api/save-contributions",{ method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(cdata) })
    .then(function() { setTimeout(function() { ndSoftReload(); }, 800); });
    updateTotals();
  }
}
// Allow Enter key to submit
var _investInput = document.getElementById("invest-chat-input");
if (_investInput) _investInput.addEventListener("keydown", function(e) {
  if (e.key === "Enter") { e.preventDefault(); processInvestChat(); }
});

/* ── Pulse Card Drag & Drop + Add/Remove ── */
(function() {
  var bar = document.getElementById("pulse-bar");
  if (!bar) return;
  var pulseDragSrc = null;

  function setupPulseDrag() {
    bar.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {
      item.addEventListener("dragstart", function(e) {
        pulseDragSrc = item;
        item.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", item.dataset.pulseId);
      });
      item.addEventListener("dragend", function() {
        item.classList.remove("dragging");
        bar.querySelectorAll(".drag-over").forEach(function(el) { el.classList.remove("drag-over"); });
        pulseDragSrc = null;
      });
      item.addEventListener("dragover", function(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (item !== pulseDragSrc && !item.classList.contains("pulse-add")) item.classList.add("drag-over");
      });
      item.addEventListener("dragleave", function() { item.classList.remove("drag-over"); });
      item.addEventListener("drop", function(e) {
        e.preventDefault();
        item.classList.remove("drag-over");
        if (!pulseDragSrc || pulseDragSrc === item || item.classList.contains("pulse-add")) return;
        // Insert before or after based on position
        var rect = item.getBoundingClientRect();
        var midX = rect.left + rect.width / 2;
        if (e.clientX < midX) {
          bar.insertBefore(pulseDragSrc, item);
        } else {
          bar.insertBefore(pulseDragSrc, item.nextSibling);
        }
        savePulseOrder();
      });
    });
  }

  function savePulseOrder() {
    var order = [];
    bar.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {
      order.push(item.dataset.pulseId);
    });
    fetch("/api/pulse-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order: order })
    });
  }

  setupPulseDrag();
  window._setupPulseDrag = setupPulseDrag;
})();

function showAddPulseCard() {
  var modal = document.getElementById("pulse-add-modal");
  modal.style.display = "flex";
  document.getElementById("pulse-add-ticker").value = "";
  document.getElementById("pulse-add-label").value = "";
  document.getElementById("pulse-add-ticker").focus();
}
function hideAddPulseCard() {
  document.getElementById("pulse-add-modal").style.display = "none";
}
function addPulseCard() {
  var ticker = document.getElementById("pulse-add-ticker").value.trim().toUpperCase();
  var label = document.getElementById("pulse-add-label").value.trim();
  if (!ticker) return alert("Please enter a ticker symbol.");
  fetch("/api/pulse-cards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: ticker, label: label })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.success) {
      hideAddPulseCard();
      var displayLabel = label || ticker;
      var cardId = "custom-" + d.id;
      var bar = document.getElementById("pulse-bar");
      var addBtn = document.getElementById("pulse-add-btn");
      var div = document.createElement("div");
      div.className = "pulse-item";
      div.draggable = true;
      div.setAttribute("data-pulse-id", cardId);
      div.setAttribute("data-pulse-type", "stock");
      div.innerHTML =
        '<button class="pulse-remove" onclick="event.stopPropagation();removePulseCard(\'' + d.id + '\')" title="Remove">&times;</button>' +
        '<span class="pulse-label">' + displayLabel + '</span>' +
        '<span class="pulse-price" data-pulse-price="' + cardId + '">--</span>' +
        '<canvas class="pulse-spark" id="spark-' + cardId + '" width="60" height="24"></canvas>';
      if (addBtn) bar.insertBefore(div, addBtn);
      else bar.appendChild(div);
      setTimeout(loadAllSparklines, 300);
    } else {
      alert(d.error || "Failed to add ticker.");
    }
  });
}
function removePulseCard(id) {
  if (!confirm("Remove this card from the pulse bar?")) return;
  var el = document.querySelector('[data-pulse-id="' + id + '"]')
    || document.querySelector('[data-pulse-id="custom-' + id + '"]');
  if (el) { el.style.opacity = "0"; el.style.transition = "opacity 0.2s"; }
  fetch("/api/pulse-cards/" + encodeURIComponent(id), { method: "DELETE" })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (d.success && el) el.remove(); });
}
function setPulseSize(size) {
  var bar = document.getElementById("pulse-bar");
  if (!bar) return;
  bar.className = "pulse-bar size-" + size;
  document.querySelectorAll(".pulse-size-btn").forEach(function(b) {
    b.classList.toggle("active", b.getAttribute("data-size") === size);
  });
  localStorage.setItem("nd-pulse-size", size);
  fetch("/api/pulse-size", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ size: size })
  }).catch(function() {});
  setTimeout(loadAllSparklines, 200);
}

function restoreAllPulseCards() {
  if (!confirm("Restore all hidden pulse cards?")) return;
  fetch("/api/pulse-cards/restore-all", { method: "POST" })
    .then(function(r) { return r.json(); })
    .then(function(d) { if (d.success) ndSoftReload(); });
}

/* ── Pulse Chart Modal ── */
(function() {
  var PCM_SYMBOL_MAP = {
    "gold": "GC=F", "silver": "SI=F", "au_ag": "AUAG-RATIO", "gold_oil": "GOLDOIL-RATIO",
    "dxy": "DX=F", "vix": "^VIX", "oil": "CL=F", "copper": "HG=F",
    "tnx_10y": "^TNX", "tnx_2y": "2YY=F", "btc": "BTC", "spy": "SPY"
  };
  var pcmChart = null;
  var pcmPollId = null;
  var pcmState = { symbol: "", label: "", type: "stock", period: "1d", interval: "1m", chartType: "line" };

  function pcmResolveSymbol(pulseId, pulseType) {
    if (PCM_SYMBOL_MAP[pulseId]) return { sym: PCM_SYMBOL_MAP[pulseId], type: pulseId === "btc" ? "crypto" : "stock" };
    if (pulseId.startsWith("custom-")) {
      return { sym: pulseId, type: pulseType || "stock" };
    }
    return { sym: pulseId, type: pulseType || "stock" };
  }

  function openPulseChart(pulseId, label, pulseType) {
    var resolved = pcmResolveSymbol(pulseId, pulseType);
    pcmState.symbol = resolved.sym;
    pcmState.type = resolved.type;
    pcmState.label = label;
    pcmState.period = "1d";
    pcmState.interval = "1m";
    pcmState.chartType = "line";
    document.getElementById("pcm-title").textContent = label;
    document.getElementById("pcm-price").textContent = "";
    document.getElementById("pcm-type-toggle").textContent = "Candlestick";
    var pills = document.querySelectorAll(".pcm-pill");
    pills.forEach(function(p) { p.classList.remove("active"); });
    if (pills.length > 0) pills[0].classList.add("active");
    document.getElementById("pcm-overlay").classList.add("active");
    document.body.style.overflow = "hidden";
    loadPulseChart();
    startPcmPoll();
  }
  window.openPulseChart = openPulseChart;

  function closePulseChart() {
    document.getElementById("pcm-overlay").classList.remove("active");
    document.body.style.overflow = "";
    stopPcmPoll();
    if (pcmChart) { pcmChart.destroy(); pcmChart = null; }
  }
  window.closePulseChart = closePulseChart;

  function togglePcmChartType() {
    var btn = document.getElementById("pcm-type-toggle");
    if (pcmState.chartType === "line") {
      pcmState.chartType = "candlestick";
      btn.textContent = "Line";
    } else {
      pcmState.chartType = "line";
      btn.textContent = "Candlestick";
    }
    loadPulseChart();
  }
  window.togglePcmChartType = togglePcmChartType;

  function startPcmPoll() {
    stopPcmPoll();
    if (pcmState.period === "1d") {
      pcmPollId = setInterval(function() {
        if (document.getElementById("pcm-overlay").classList.contains("active")) loadPulseChart(true);
        else stopPcmPoll();
      }, 60000);
    }
  }

  function stopPcmPoll() {
    if (pcmPollId) { clearInterval(pcmPollId); pcmPollId = null; }
  }

  function loadPulseChart(silent) {
    var spinner = document.getElementById("pcm-spinner");
    if (!silent) spinner.classList.add("show");
    var url = "/api/historical?symbol=" + encodeURIComponent(pcmState.symbol)
      + "&period=" + pcmState.period
      + "&interval=" + pcmState.interval
      + "&type=" + pcmState.type;
    fetch(url).then(function(r) { return r.json(); }).then(function(resp) {
      spinner.classList.remove("show");
      var proxyEl = document.getElementById("pcm-proxy");
      if (proxyEl) { proxyEl.style.display = "none"; proxyEl.textContent = ""; }
      if (resp.error || !resp.data || resp.data.length === 0) {
        if (pcmChart) { pcmChart.destroy(); pcmChart = null; }
        document.getElementById("pcm-price").textContent = "(no data)";
        return;
      }
      var d = resp.data;
      var lastPrice = d[d.length - 1].c;
      var firstPrice = d[0].o || d[0].c;
      var chg = lastPrice - firstPrice;
      var chgPct = firstPrice ? ((chg / firstPrice) * 100) : 0;
      var sign = chg >= 0 ? "+" : "";
      var noDollar = ["AUAG-RATIO","GOLDOIL-RATIO","^VIX","^TNX","2YY=F","10Y2Y-SPREAD","DX=F"].indexOf(pcmState.symbol) >= 0;
      var prefix = noDollar ? "" : "$";
      document.getElementById("pcm-price").textContent = prefix + lastPrice.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})
        + "  " + sign + chg.toFixed(2) + " (" + sign + chgPct.toFixed(2) + "%)";
      document.getElementById("pcm-price").style.color = chg >= 0 ? "var(--accent-green, #22c55e)" : "var(--danger, #ef4444)";
      if (resp.proxy && proxyEl) {
        proxyEl.textContent = "via " + resp.proxy;
        proxyEl.style.display = "inline";
      }
      try {
        renderPcmChart(d);
        var meta = pcmChart && pcmChart.getDatasetMeta(0);
        var hasVisible = meta && meta.data && meta.data.length > 0 &&
          meta.data.some(function(pt) { return isFinite(pt.x) && isFinite(pt.y); });
        if (!hasVisible) {
          pcmState.chartType = pcmState.chartType === "line" ? "candlestick" : "line";
          var btn = document.querySelector("#pcm-overlay .pcm-toggle-chart");
          if (btn) btn.textContent = pcmState.chartType === "line" ? "Candlestick" : "Line";
          renderPcmChart(d);
        }
      } catch(_e) {
        pcmState.chartType = pcmState.chartType === "line" ? "candlestick" : "line";
        var btn2 = document.querySelector("#pcm-overlay .pcm-toggle-chart");
        if (btn2) btn2.textContent = pcmState.chartType === "line" ? "Candlestick" : "Line";
        try { renderPcmChart(d); } catch(_e2) { /* both types failed */ }
      }
    }).catch(function() {
      spinner.classList.remove("show");
    });
  }

  function renderPcmChart(data) {
    var canvas = document.getElementById("pcm-canvas");
    if (pcmChart) { pcmChart.destroy(); pcmChart = null; }
    var isIntraday = pcmState.interval && ["1m","2m","5m","15m","30m","60m","1h"].indexOf(pcmState.interval) >= 0;
    var timeUnit = "day";
    if (isIntraday) timeUnit = "minute";
    else if (["1wk"].indexOf(pcmState.interval) >= 0) timeUnit = "week";
    else if (["1mo"].indexOf(pcmState.interval) >= 0) timeUnit = "month";

    if (pcmState.chartType === "candlestick") {
      var candles = data.map(function(p) {
        return { x: new Date(p.date).getTime(), o: p.o, h: p.h, l: p.l, c: p.c };
      });
      var candleXScale = isIntraday
        ? { type: "timeseries", time: { unit: timeUnit }, grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 10 } }
        : { type: "time", time: { unit: timeUnit, tooltipFormat: "MMM d, yyyy" }, grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 10 } };
      pcmChart = new Chart(canvas.getContext("2d"), {
        type: "candlestick",
        data: { datasets: [{
          label: pcmState.label,
          data: candles,
          backgroundColors: { up: "rgba(34,197,94,1)", down: "rgba(239,68,68,1)", unchanged: "rgba(100,116,139,1)" },
          borderColors: { up: "rgba(34,197,94,1)", down: "rgba(239,68,68,1)", unchanged: "rgba(100,116,139,1)" }
        }] },
        options: {
          responsive: true, maintainAspectRatio: false,
          scales: {
            x: candleXScale,
            y: { position: "right", grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)" } }
          },
          plugins: {
            legend: { display: false },
            tooltip: { yAlign: "bottom", caretPadding: 8, backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0", borderColor: "rgba(99,102,241,0.4)", borderWidth: 1 }
          }
        }
      });
    } else {
      var closes = data.map(function(p) { return p.c; });
      var first = closes[0]; var last = closes[closes.length - 1];
      var lineColor = last >= first ? "rgba(34,197,94,0.9)" : "rgba(239,68,68,0.9)";
      var fillColor = last >= first ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)";

      // Intraday: even spacing (no gaps for closed hours), show simplified tick labels
      // Daily+: proportional time axis so weekends/holidays show proper gaps
      var xScale, chartData;
      if (isIntraday) {
        // Format labels: show date at session boundaries, time otherwise
        var tickLabels = data.map(function(p, i) {
          var dt = new Date(p.date);
          var prev = i > 0 ? new Date(data[i-1].date) : null;
          if (!prev || dt.toDateString() !== prev.toDateString()) {
            return dt.toLocaleDateString(undefined, {month:"short", day:"numeric"});
          }
          return "";
        });
        xScale = { type: "category", labels: tickLabels,
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 8, autoSkip: true, maxRotation: 0 }
        };
        chartData = { labels: tickLabels, datasets: [{
          label: pcmState.label, data: closes,
          borderColor: lineColor, backgroundColor: fillColor,
          borderWidth: 2, pointRadius: 0, pointHitRadius: 8,
          fill: true, tension: 0.15
        }] };
      } else {
        var pointData = data.map(function(p) { return { x: new Date(p.date).getTime(), y: p.c }; });
        xScale = { type: "time", time: { unit: timeUnit, tooltipFormat: "MMM d, yyyy" },
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.5)", maxTicksLimit: 8 }
        };
        chartData = { datasets: [{
          label: pcmState.label, data: pointData,
          borderColor: lineColor, backgroundColor: fillColor,
          borderWidth: 2, pointRadius: 0, pointHitRadius: 8,
          fill: true, tension: 0.15
        }] };
      }

      pcmChart = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: chartData,
        options: {
          responsive: true, maintainAspectRatio: false,
          interaction: { mode: "nearest", axis: "x", intersect: false },
          scales: {
            x: xScale,
            y: { position: "right", grid: { color: "rgba(255,255,255,0.04)" }, ticks: { color: "rgba(255,255,255,0.5)" } }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              yAlign: "bottom", caretPadding: 8,
              backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0",
              borderColor: "rgba(99,102,241,0.4)", borderWidth: 1,
              callbacks: {
                title: function(items) {
                  var idx = items[0] ? items[0].dataIndex : 0;
                  var p = data[idx];
                  if (!p) return "";
                  var dt = new Date(p.date);
                  return isIntraday ? dt.toLocaleString(undefined, {month:"short", day:"numeric", hour:"numeric", minute:"2-digit"}) : p.date;
                },
                label: function(ctx) {
                  var noDollar = ["AUAG-RATIO","GOLDOIL-RATIO","^VIX","^TNX","2YY=F","10Y2Y-SPREAD","DX=F"].indexOf(pcmState.symbol) >= 0;
                  var prefix = noDollar ? "" : "$";
                  var val = isIntraday ? ctx.raw : ctx.raw.y;
                  return pcmState.label + ": " + prefix + Number(val).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                }
              }
            },
            crosshair: false
          }
        }
      });
    }
  }

  // Timescale pill click handlers
  document.getElementById("pcm-controls").addEventListener("click", function(e) {
    var pill = e.target.closest(".pcm-pill");
    if (!pill) return;
    document.querySelectorAll(".pcm-pill").forEach(function(p) { p.classList.remove("active"); });
    pill.classList.add("active");
    pcmState.period = pill.dataset.pcmP;
    pcmState.interval = pill.dataset.pcmI;
    stopPcmPoll();
    loadPulseChart();
    startPcmPoll();
  });

  // Attach click handlers to all pulse items (guard against drag)
  var pcmDragHappened = false;
  document.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {
    item.addEventListener("dragstart", function() { pcmDragHappened = true; });
    item.addEventListener("click", function(e) {
      if (e.target.closest(".pulse-remove")) return;
      if (pcmDragHappened) { pcmDragHappened = false; return; }
      var pid = item.dataset.pulseId;
      var label = item.querySelector(".pulse-label") ? item.querySelector(".pulse-label").textContent : pid;
      var ptype = item.dataset.pulseType || "stock";
      openPulseChart(pid, label, ptype);
    });
    item.style.cursor = "pointer";
  });

  // Close on Escape key
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape" && document.getElementById("pcm-overlay").classList.contains("active")) {
      closePulseChart();
    }
  });
})();

/* ── Init on load ── */
buildDonut();
if (PRICE_HISTORY_DATA.length > 0) buildHistoryChart("total");
(function() {
  var savedSize = localStorage.getItem("nd-pulse-size") || "compact";
  var bar = document.getElementById("pulse-bar");
  if (bar) bar.className = "pulse-bar size-" + savedSize;
  document.querySelectorAll(".pulse-size-btn").forEach(function(b) {
    b.classList.toggle("active", b.getAttribute("data-size") === savedSize);
  });
})();
setTimeout(loadAllSparklines, 300);
var toast = document.getElementById("toast-msg");
if (toast) setTimeout(function() { toast.style.display="none"; }, 4000);
