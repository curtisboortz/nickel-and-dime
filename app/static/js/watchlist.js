/* Nickel&Dime - Watchlist & Price Alerts */

(function() {
  var _wlData = [];
  var _alertFormTicker = null;
  var _alertCheckCache = {};

  // ── Load watchlist ──

  function loadWatchlist() {
    fetch("/api/watchlist").then(function(r) { return r.json(); }).then(function(d) {
      _wlData = d.items || [];
      renderWatchlist();
      loadWatchlistSparklines();
    }).catch(function() {});
    loadAlertsList();
  }
  window.loadWatchlist = loadWatchlist;

  function renderWatchlist() {
    var tbody = document.getElementById("wl-tbody");
    var table = document.getElementById("wl-table");
    var empty = document.getElementById("wl-empty");
    if (!tbody) return;

    if (_wlData.length === 0) {
      table.style.display = "none";
      empty.style.display = "block";
      return;
    }
    table.style.display = "table";
    empty.style.display = "none";

    var html = "";
    for (var i = 0; i < _wlData.length; i++) {
      var item = _wlData[i];
      var priceStr = item.price != null
        ? "$" + Number(item.price).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})
        : "--";
      var chgPct = item.change_pct;
      var chgClass = chgPct > 0 ? "up" : chgPct < 0 ? "down" : "flat";
      var chgStr = chgPct != null ? (chgPct > 0 ? "+" : "") + chgPct.toFixed(2) + "%" : "--";
      var hasAlert = item.alerts && item.alerts.length > 0;

      html += '<tr data-wl-id="' + item.id + '" data-wl-ticker="' + item.ticker + '">';
      html += '<td><span class="wl-ticker">' + item.ticker + '</span>';
      if (item.label && item.label !== item.ticker) {
        html += '<span class="wl-label">' + item.label + '</span>';
      }
      if (item.alerts && item.alerts.length > 0) {
        html += '<div class="wl-alert-badges">';
        for (var a = 0; a < item.alerts.length; a++) {
          var al = item.alerts[a];
          var cls = al.triggered_at ? " triggered" : "";
          html += '<span class="wl-alert-badge' + cls + '">' + al.condition + ' $' + al.target_price + '</span>';
        }
        html += '</div>';
      }
      html += '</td>';
      html += '<td class="wl-price" data-wl-price="' + item.ticker + '">' + priceStr + '</td>';
      html += '<td class="wl-change ' + chgClass + '" data-wl-change="' + item.ticker + '">' + chgStr + '</td>';
      html += '<td class="wl-spark-cell"><canvas class="pulse-spark" id="wl-spark-' + item.id + '" width="60" height="24"></canvas></td>';
      html += '<td><div class="wl-actions">';
      html += '<button class="wl-btn' + (hasAlert ? " has-alert" : "") + '" onclick="wlShowAlertForm(\'' + item.ticker + '\')" title="Set alert">&#128276;</button>';
      html += '<button class="wl-btn remove" onclick="wlRemoveItem(' + item.id + ')" title="Remove">&times;</button>';
      html += '</div></td>';
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  // ── Sparklines for watchlist ──

  function loadWatchlistSparklines() {
    if (_wlData.length === 0) return;
    var tickers = _wlData.map(function(w) { return w.ticker; });
    var url = "/api/sparklines?symbols=" + encodeURIComponent(tickers.join(","));
    fetch(url).then(function(r) { return r.json(); }).then(function(data) {
      for (var i = 0; i < _wlData.length; i++) {
        var item = _wlData[i];
        var canvasId = "wl-spark-" + item.id;
        var values = data[item.ticker];
        if (values && values.length > 1 && typeof renderSparkCanvas === "function") {
          renderSparkCanvas(canvasId, values);
        }
      }
    }).catch(function() {});
  }

  // ── Update prices from live data ──

  function updateWatchlistPrices(liveData) {
    if (!liveData || _wlData.length === 0) return;
    for (var i = 0; i < _wlData.length; i++) {
      var item = _wlData[i];
      var priceEl = document.querySelector('[data-wl-price="' + item.ticker + '"]');
      var changeEl = document.querySelector('[data-wl-change="' + item.ticker + '"]');
      if (!priceEl) continue;

      var row = null;
      if (liveData._watchlist_prices) {
        row = liveData._watchlist_prices[item.ticker];
      }
      if (row && row.price != null) {
        item.price = row.price;
        item.change_pct = row.change_pct;
        priceEl.textContent = "$" + Number(row.price).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
        if (changeEl && row.change_pct != null) {
          var chgClass = row.change_pct > 0 ? "up" : row.change_pct < 0 ? "down" : "flat";
          changeEl.className = "wl-change " + chgClass;
          changeEl.textContent = (row.change_pct > 0 ? "+" : "") + row.change_pct.toFixed(2) + "%";
        }
      }
    }
    checkAndFireAlerts();
  }
  window.updateWatchlistPrices = updateWatchlistPrices;

  // ── Add item ──

  window.wlToggleAdd = function() {
    var form = document.getElementById("wl-add-form");
    form.style.display = form.style.display === "none" ? "flex" : "none";
    if (form.style.display === "flex") {
      document.getElementById("wl-add-ticker").value = "";
      document.getElementById("wl-add-label").value = "";
      document.getElementById("wl-add-ticker").focus();
    }
  };

  window.wlAddItem = function() {
    var tickerInput = document.getElementById("wl-add-ticker");
    var labelInput = document.getElementById("wl-add-label");
    var ticker = tickerInput.value.trim().toUpperCase();
    var label = labelInput.value.trim();
    if (!ticker) return;

    fetch("/api/watchlist", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ticker: ticker, label: label})
    }).then(function(r) {
      if (r.status === 400) return r.json().then(function(d) { throw d; });
      return r.json();
    }).then(function(d) {
      if (d.success) {
        tickerInput.value = "";
        labelInput.value = "";
        document.getElementById("wl-add-form").style.display = "none";
        loadWatchlist();
        fetch("/api/bg-refresh", {method: "POST"});
      } else {
        _wlToast(d.error || "Failed to add ticker.", true);
      }
    }).catch(function(e) {
      var msg = (e && e.error) || "Network error.";
      if (msg.toLowerCase().indexOf("csrf") !== -1) msg = "Session expired — please refresh the page.";
      _wlToast(msg, true);
    });
  };

  // Enter key to submit add form
  var _wlTickerInput = document.getElementById("wl-add-ticker");
  if (_wlTickerInput) {
    _wlTickerInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter") { e.preventDefault(); wlAddItem(); }
    });
  }

  // ── Remove item ──

  window.wlRemoveItem = function(id) {
    fetch("/api/watchlist/" + id, {method: "DELETE"}).then(function(r) { return r.json(); }).then(function(d) {
      if (d.success) loadWatchlist();
    }).catch(function() {});
  };

  // ── Alert form ──

  window.wlShowAlertForm = function(ticker) {
    _alertFormTicker = ticker;
    var form = document.getElementById("wl-alert-form");
    document.getElementById("wl-alert-form-ticker").textContent = ticker;
    document.getElementById("wl-alert-price").value = "";
    document.getElementById("wl-alert-cond").value = "above";
    form.style.display = "flex";
    document.getElementById("wl-alert-price").focus();
  };

  window.wlHideAlertForm = function() {
    document.getElementById("wl-alert-form").style.display = "none";
    _alertFormTicker = null;
  };

  window.wlSubmitAlert = function() {
    if (!_alertFormTicker) return;
    var condition = document.getElementById("wl-alert-cond").value;
    var price = document.getElementById("wl-alert-price").value;
    if (!price) return;

    fetch("/api/price-alerts", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ticker: _alertFormTicker, condition: condition, target_price: parseFloat(price)})
    }).then(ndCheckProResponse).then(function(r) {
      if (r.status === 400) return r.json().then(function(d) { throw d; });
      return r.json();
    }).then(function(d) {
      if (d.success) {
        wlHideAlertForm();
        _wlToast("Alert set: " + _alertFormTicker + " " + condition + " $" + price);
        loadWatchlist();
      } else {
        _wlToast(d.error || "Failed to set alert.", true);
      }
    }).catch(function(e) {
      var msg = (e && e.error) || "Network error.";
      if (msg.toLowerCase().indexOf("csrf") !== -1) msg = "Session expired — please refresh the page.";
      _wlToast(msg, true);
    });
  };

  // Enter key in alert price input
  var _alertPriceInput = document.getElementById("wl-alert-price");
  if (_alertPriceInput) {
    _alertPriceInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter") { e.preventDefault(); wlSubmitAlert(); }
    });
  }

  // ── Alerts list ──

  function loadAlertsList() {
    fetch("/api/price-alerts").then(ndCheckProResponse).then(function(r) { return r.json(); }).then(function(d) {
      var alerts = d.alerts || [];
      var section = document.getElementById("wl-alerts-section");
      var list = document.getElementById("wl-alerts-list");
      var active = alerts.filter(function(a) { return a.active; });
      if (active.length === 0) {
        section.style.display = "none";
        return;
      }
      section.style.display = "block";
      var html = "";
      for (var i = 0; i < active.length; i++) {
        var a = active[i];
        var curStr = a.current_price != null
          ? "$" + Number(a.current_price).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})
          : "--";
        html += '<div class="wl-alert-row">';
        html += '<span class="wl-alert-ticker">' + a.ticker + '</span>';
        html += '<span class="wl-alert-cond">' + a.condition + '</span>';
        html += '<span class="wl-alert-target">$' + a.target_price + '</span>';
        html += '<span class="wl-alert-current">now ' + curStr + '</span>';
        html += '<button class="wl-btn remove" onclick="wlDeleteAlert(' + a.id + ')" title="Remove">&times;</button>';
        html += '</div>';
      }
      list.innerHTML = html;
    }).catch(function() {});
  }

  window.wlDeleteAlert = function(id) {
    fetch("/api/price-alerts/" + id, {method: "DELETE"}).then(ndCheckProResponse).then(function(r) { return r.json(); }).then(function(d) {
      if (d.success) loadWatchlist();
    }).catch(function() {});
  };

  // ── Client-side alert checking ──

  function checkAndFireAlerts() {
    for (var i = 0; i < _wlData.length; i++) {
      var item = _wlData[i];
      if (!item.alerts || !item.price) continue;
      for (var j = 0; j < item.alerts.length; j++) {
        var a = item.alerts[j];
        if (a.triggered_at) continue;
        var cacheKey = a.id;
        if (_alertCheckCache[cacheKey]) continue;

        var fired = false;
        if (a.condition === "above" && item.price >= a.target_price) fired = true;
        if (a.condition === "below" && item.price <= a.target_price) fired = true;

        if (fired) {
          _alertCheckCache[cacheKey] = true;
          _wlToast(item.ticker + " is " + a.condition + " $" + a.target_price + " (now $" + item.price.toFixed(2) + ")");
          fetch("/api/price-alerts/" + a.id + "/trigger", {method: "POST"}).catch(function() {});
          a.triggered_at = new Date().toISOString();
        }
      }
    }
  }

  // ── Toast helper ──

  function _wlToast(msg, isError) {
    var div = document.createElement("div");
    div.className = "toast";
    if (isError) {
      div.style.background = "rgba(239,68,68,0.15)";
      div.style.color = "var(--danger)";
      div.style.borderColor = "rgba(239,68,68,0.3)";
    } else {
      div.style.background = "rgba(212,160,23,0.15)";
      div.style.color = "var(--accent-primary)";
      div.style.borderColor = "rgba(212,160,23,0.3)";
    }
    div.textContent = msg;
    document.body.appendChild(div);
    setTimeout(function() { div.remove(); }, 5000);
  }

  // ── Pulse Chart Modal integration ──

  var _pcmCurrentTicker = null;
  var _pcmCurrentLabel = null;

  var PCM_TICKER_MAP = {
    "gold": "GC=F", "silver": "SI=F", "au_ag": "AUAG-RATIO", "gold_oil": "GOLDOIL-RATIO",
    "dxy": "DX=F", "vix": "^VIX", "oil": "CL=F", "copper": "HG=F",
    "tnx_10y": "^TNX", "tnx_2y": "2YY=F", "btc": "BTC-USD", "spy": "SPY"
  };

  function _resolvePcmTicker(pulseId) {
    if (PCM_TICKER_MAP[pulseId]) return PCM_TICKER_MAP[pulseId];
    if (pulseId && pulseId.startsWith("custom-")) return pulseId;
    return pulseId;
  }

  function _updatePcmWatchlistBtn() {
    var btn = document.getElementById("pcm-wl-add");
    if (!btn || !_pcmCurrentTicker) return;
    var isOnWatchlist = _wlData.some(function(w) { return w.ticker === _pcmCurrentTicker; });
    if (isOnWatchlist) {
      btn.classList.add("active");
      btn.innerHTML = "&#9733; Watchlist";
    } else {
      btn.classList.remove("active");
      btn.innerHTML = "&#9734; Watchlist";
    }
  }

  // Detect when the pulse chart modal opens via class change on overlay
  var _pcmOverlay = document.getElementById("pcm-overlay");
  if (_pcmOverlay) {
    var _pcmObserver = new MutationObserver(function(mutations) {
      for (var i = 0; i < mutations.length; i++) {
        if (mutations[i].attributeName === "class") {
          if (_pcmOverlay.classList.contains("active")) {
            var titleEl = document.getElementById("pcm-title");
            var label = titleEl ? titleEl.textContent : "";
            _pcmCurrentLabel = label;
            // Reverse-lookup the ticker from the label or pulse items
            _pcmCurrentTicker = _findTickerFromPcm();
            _updatePcmWatchlistBtn();
            var alertFormInline = document.getElementById("pcm-alert-form-inline");
            if (alertFormInline) alertFormInline.style.display = "none";
          }
        }
      }
    });
    _pcmObserver.observe(_pcmOverlay, {attributes: true, attributeFilter: ["class"]});
  }

  function _findTickerFromPcm() {
    // Read the title from the modal, then resolve to a ticker
    var titleEl = document.getElementById("pcm-title");
    if (!titleEl) return null;
    var label = titleEl.textContent.trim();

    // Build reverse label-to-ticker map from pulse items
    var LABEL_MAP = {
      "Gold": "GC=F", "Silver": "SI=F", "S&P 500": "SPY", "Bitcoin": "BTC-USD",
      "10Y Yield": "^TNX", "2Y Yield": "2YY=F", "Au/Ag": "AUAG-RATIO",
      "Gold/Oil": "GOLDOIL-RATIO", "DXY": "DX=F", "VIX": "^VIX",
      "Oil": "CL=F", "Copper": "HG=F"
    };
    if (LABEL_MAP[label]) return LABEL_MAP[label];

    // Check custom pulse items
    var pulseItems = document.querySelectorAll(".pulse-item[data-pulse-id]");
    for (var i = 0; i < pulseItems.length; i++) {
      var lbl = pulseItems[i].querySelector(".pulse-label");
      if (lbl && lbl.textContent.trim() === label) {
        var pid = pulseItems[i].dataset.pulseId;
        return _resolvePcmTicker(pid);
      }
    }
    return label;
  }

  window.pcmAddToWatchlist = function() {
    if (!_pcmCurrentTicker) return;
    var isOnWatchlist = _wlData.some(function(w) { return w.ticker === _pcmCurrentTicker; });
    if (isOnWatchlist) {
      _wlToast(_pcmCurrentTicker + " is already on your watchlist.");
      return;
    }
    fetch("/api/watchlist", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ticker: _pcmCurrentTicker, label: _pcmCurrentLabel || _pcmCurrentTicker})
    }).then(function(r) {
      if (r.status === 400) return r.json().then(function(d) { throw d; });
      return r.json();
    }).then(function(d) {
      if (d.success) {
        _wlToast("Added " + _pcmCurrentTicker + " to watchlist.");
        loadWatchlist();
        _updatePcmWatchlistBtn();
      } else {
        _wlToast(d.error || "Failed to add.", true);
      }
    }).catch(function(e) {
      var msg = (e && e.error) || "Network error.";
      if (msg.toLowerCase().indexOf("csrf") !== -1) msg = "Session expired — please refresh the page.";
      _wlToast(msg, true);
    });
  };

  window.pcmShowAlertForm = function() {
    if (!_pcmCurrentTicker) return;
    var form = document.getElementById("pcm-alert-form-inline");
    document.getElementById("pcm-alert-ticker-label").textContent = _pcmCurrentLabel || _pcmCurrentTicker;
    document.getElementById("pcm-alert-price-input").value = "";
    document.getElementById("pcm-alert-cond-sel").value = "above";
    form.style.display = "flex";
    document.getElementById("pcm-alert-price-input").focus();
  };

  window.pcmSubmitAlert = function() {
    var condition = document.getElementById("pcm-alert-cond-sel").value;
    var price = document.getElementById("pcm-alert-price-input").value;
    var ticker = _pcmCurrentTicker;
    if (!ticker || !price) return;

    fetch("/api/price-alerts", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ticker: ticker, condition: condition, target_price: parseFloat(price)})
    }).then(ndCheckProResponse).then(function(r) {
      if (r.status === 400) return r.json().then(function(d) { throw d; });
      return r.json();
    }).then(function(d) {
      if (d.success) {
        document.getElementById("pcm-alert-form-inline").style.display = "none";
        _wlToast("Alert set: " + ticker + " " + condition + " $" + price);
        loadWatchlist();
      } else {
        _wlToast(d.error || "Failed to set alert.", true);
      }
    }).catch(function(e) {
      var msg = (e && e.error) || "Network error.";
      if (msg.toLowerCase().indexOf("csrf") !== -1) msg = "Session expired — please refresh the page.";
      _wlToast(msg, true);
    });
  };

  // Enter key in PCM alert input
  var _pcmAlertInput = document.getElementById("pcm-alert-price-input");
  if (_pcmAlertInput) {
    _pcmAlertInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter") { e.preventDefault(); pcmSubmitAlert(); }
    });
  }

  // ── Hook into live-data refresh cycle ──

  var _origApplyLive = window.applyLiveDataToDOM;
  if (typeof _origApplyLive === "function") {
    window.applyLiveDataToDOM = function(d) {
      _origApplyLive(d);
      updateWatchlistPrices(d);
    };
  }

  // ── Init ──

  loadWatchlist();
})();
