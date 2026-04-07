/* Nickel&Dime — Tab switching with lazy-load support */

(function() {
  var _tabLoaded = {};
  _tabLoaded[window.ACTIVE_TAB || "summary"] = true;
  _tabLoaded["economics"] = false;

  function _injectTabContent(tabEl, html) {
    tabEl.innerHTML = html;
    var scripts = tabEl.querySelectorAll("script");
    scripts.forEach(function(oldScript) {
      var ns = document.createElement("script");
      ns.textContent = oldScript.textContent;
      document.head.appendChild(ns);
      oldScript.remove();
    });
  }

  function _safe(fn, label) {
    try { fn(); } catch(e) {
      console.error("[TabInit] " + (label||"unknown") + " error:", e);
      if (typeof NDDiag !== "undefined") NDDiag.track(label||"unknown", "error", e.message || String(e));
    }
  }

  function _postTabInit(t) {
    if (t === "summary") {
      _safe(function() { if (typeof loadSummaryData === "function") loadSummaryData(); }, "loadSummaryData");
      setTimeout(function() { _safe(function() { if (typeof loadAllSparklines === "function") loadAllSparklines(); }, "loadAllSparklines"); }, 200);
    }
    if (t === "economics") _safe(function() { if (typeof loadFredData === "function") loadFredData(); }, "loadFredData");
    if (t === "history") {
      _safe(function() { if (typeof buildProjectionChart === "function") buildProjectionChart(); }, "buildProjectionChart");
      _safe(function() { if (typeof runMonteCarlo === "function") runMonteCarlo(); }, "runMonteCarlo");
      _safe(function() { if (typeof buildDrawdownChart === "function") buildDrawdownChart(); }, "buildDrawdownChart");
      _safe(function() { if (typeof buildPerfAttribution === "function") buildPerfAttribution(); }, "buildPerfAttribution");
      _safe(function() { if (typeof loadSentimentGauges === "function") loadSentimentGauges(); }, "loadSentimentGauges");
      _safe(function() { if (typeof loadTLH === "function") loadTLH(); }, "loadTLH");
    }
    if (t === "budget") _safe(function() { if (typeof _initBudgetListeners === "function") _initBudgetListeners(); }, "_initBudgetListeners");
    if (t === "technical") _safe(function() { if (typeof initTechnicalTab === "function") initTechnicalTab(); }, "initTechnicalTab");
    if (t === "balances") _safe(function() { if (typeof loadBalances === "function") loadBalances(); }, "loadBalances");
    if (t === "holdings") _safe(function() { if (typeof loadHoldings === "function") loadHoldings(); }, "loadHoldings");
  }

  function _animateCards(container) {
    if (!container) return;
    var cards = container.querySelectorAll(".card, .hero-row, .pulse-bar, .summary-grid, .income-bar");
    cards.forEach(function(c) { c.classList.remove("card-enter"); });
    requestAnimationFrame(function() {
      cards.forEach(function(c) { c.classList.add("card-enter"); });
    });
  }

  function _doTabSwitch(t) {
    document.querySelectorAll(".tab").forEach(function(d) { d.classList.remove("active"); });
    document.querySelectorAll(".nav-item, .mob-item").forEach(function(l) { l.classList.remove("active"); });
    var el = document.getElementById("tab-" + t);
    if (el) el.classList.add("active");
    document.querySelectorAll('[data-tab="' + t + '"]').forEach(function(l) { l.classList.add("active"); });

    if (!_tabLoaded[t] && el && el.querySelector("[data-lazy-tab]")) {
      fetch("/api/tab-content/" + t)
        .then(function(r) { return r.text(); })
        .then(function(html) {
          _injectTabContent(el, html);
          _tabLoaded[t] = true;
          _postTabInit(t);
          _animateCards(el);
        })
        .catch(function() {
          el.innerHTML = '<div style="text-align:center;padding:60px;color:var(--danger);">Failed to load tab. <button onclick="showTab(\'' + t + '\')" style="color:var(--accent-primary);text-decoration:underline;background:none;border:none;cursor:pointer;">Retry</button></div>';
        });
    } else {
      _postTabInit(t);
      _animateCards(el);
    }

    var url = "/dashboard" + (t === "summary" ? "" : "/" + t);
    if (window.location.pathname !== url) history.pushState({tab:t}, "", url);
  }

  window.showTab = function(t) {
    if (document.startViewTransition) {
      document.startViewTransition(function() { _doTabSwitch(t); });
    } else {
      _doTabSwitch(t);
    }
  };

  window.addEventListener("popstate", function(e) {
    if (e.state && e.state.tab) showTab(e.state.tab);
  });

  document.querySelectorAll(".nav-item, .mob-item").forEach(function(a) {
    a.addEventListener("click", function(e) {
      e.preventDefault();
      var tab = this.getAttribute("data-tab");
      if (tab) showTab(tab);
    });
  });

  /* Keyboard shortcut: Cmd/Ctrl+K for command palette */
  document.addEventListener("keydown", function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      var overlay = document.getElementById("cmd-overlay");
      if (overlay) {
        overlay.classList.toggle("open");
        if (overlay.classList.contains("open")) {
          var input = document.getElementById("cmd-input");
          if (input) { input.value = ""; input.focus(); }
        }
      }
    }
    if (e.key === "Escape") {
      var overlay = document.getElementById("cmd-overlay");
      if (overlay) overlay.classList.remove("open");
    }
  });

  /* Initialize active tab on page load -- defer so all scripts are parsed first */
  var tabMap = {
    "balances":"balances","budget":"budget","holdings":"holdings",
    "import":"import","history":"history","economics":"economics",
    "charts":"history","technical":"technical","ai":"ai"
  };
  var pathParts = window.location.pathname.split("/").filter(Boolean);
  var pathTab = pathParts.length > 1 ? pathParts[pathParts.length - 1] : null;
  var tab = tabMap[pathTab] || new URLSearchParams(window.location.search).get("tab") || window.ACTIVE_TAB || "summary";
  setTimeout(function() { showTab(tab); }, 0);
})();
