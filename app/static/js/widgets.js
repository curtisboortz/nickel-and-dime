/* Nickel&Dime — Widget registry for the dashboard.
 *
 * Each widget: name, category, init(el), destroy(el).
 * Summary widgets are already in the DOM and just need to be shown.
 * Non-summary widgets move their content into a generated card in #widget-staging.
 */

var WIDGET_REGISTRY = {};

(function() {
  "use strict";

  function _noop() {}

  /* Summary widgets init receives the existing card element; nothing to move. */

  WIDGET_REGISTRY["allocation-donut"] = {
    name: "Portfolio Allocation",
    category: "Summary",
    init: _noop, destroy: _noop
  };

  WIDGET_REGISTRY["allocation-table"] = {
    name: "Allocation vs Target",
    category: "Summary",
    init: _noop, destroy: _noop
  };

  WIDGET_REGISTRY["monthly-investments"] = {
    name: "Monthly Investments",
    category: "Summary",
    init: _noop, destroy: _noop
  };

  WIDGET_REGISTRY["watchlist"] = {
    name: "Watchlist & Alerts",
    category: "Summary",
    init: _noop, destroy: _noop
  };

  WIDGET_REGISTRY["financial-goals"] = {
    name: "Financial Goals",
    category: "Summary",
    init: _noop, destroy: _noop
  };

  // ─── Portfolio widgets ────────────────────────────────────────

  WIDGET_REGISTRY["sentiment-gauges"] = {
    name: "Market Sentiment",
    category: "Portfolio",
    init: function(el) {
      var section = document.getElementById("sentiment-section");
      if (section) _ensureCard("sentiment-gauges", "Market Sentiment").appendChild(section);
      if (typeof loadSentimentGauges === "function") loadSentimentGauges();
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["projected-growth"] = {
    name: "Projected Growth",
    category: "Portfolio",
    init: function() {
      var section = document.getElementById("projection-section");
      if (section) _ensureCard("projected-growth", "Projected Growth").appendChild(section);
      setTimeout(function() {
        if (typeof buildProjectionChart === "function") buildProjectionChart();
      }, 100);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["monte-carlo"] = {
    name: "Monte Carlo Simulation",
    category: "Portfolio",
    init: function() {
      var section = document.getElementById("monte-carlo-section");
      if (section) _ensureCard("monte-carlo", "Monte Carlo Simulation").appendChild(section);
      setTimeout(function() {
        if (typeof runMonteCarlo === "function") runMonteCarlo();
      }, 100);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["drawdown"] = {
    name: "Drawdown Analysis",
    category: "Portfolio",
    init: function() {
      var section = document.getElementById("drawdown-section");
      if (section) _ensureCard("drawdown", "Drawdown Analysis").appendChild(section);
      setTimeout(function() {
        if (typeof buildDrawdownChart === "function") buildDrawdownChart();
      }, 100);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["perf-attribution"] = {
    name: "Performance Attribution",
    category: "Portfolio",
    init: function() {
      var section = document.getElementById("perf-attribution-section");
      if (section) _ensureCard("perf-attribution", "Performance Attribution").appendChild(section);
      setTimeout(function() {
        if (typeof buildPerfAttribution === "function") buildPerfAttribution();
      }, 100);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["portfolio-insights"] = {
    name: "Portfolio Insights",
    category: "Portfolio",
    init: function() {
      var section = document.getElementById("insights-section");
      if (section) _ensureCard("portfolio-insights", "Portfolio Insights").appendChild(section);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["allocation-templates"] = {
    name: "Allocation Templates",
    category: "Portfolio",
    init: function() {
      var section = document.getElementById("templates-section");
      if (section) _ensureCard("allocation-templates", "Allocation Templates").appendChild(section);
    },
    destroy: _noop
  };

  // ─── Economics widgets ────────────────────────────────────────

  WIDGET_REGISTRY["economic-calendar"] = {
    name: "Economic Calendar",
    category: "Economics",
    init: function() {
      _ensureEconLoaded().then(function() {
        var section = document.getElementById("fred-section-econcal");
        if (section) _ensureCard("economic-calendar", "Economic Calendar").appendChild(section);
      });
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["fedwatch"] = {
    name: "FedWatch Tool",
    category: "Economics",
    init: function() {
      _ensureEconLoaded().then(function() {
        var section = document.getElementById("fred-section-fedwatch");
        if (section) _ensureCard("fedwatch", "FedWatch Tool").appendChild(section);
      });
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["cape-buffett"] = {
    name: "CAPE & Buffett Indicator",
    category: "Economics",
    init: function() {
      _ensureEconLoaded().then(function() {
        var cape = document.getElementById("fred-section-cape");
        var buff = document.getElementById("fred-section-buffett");
        var card = _ensureCard("cape-buffett", "CAPE & Buffett Indicator");
        if (cape) card.appendChild(cape);
        if (buff) card.appendChild(buff);
      });
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["macro-charts"] = {
    name: "Macro Charts",
    category: "Economics",
    init: function() {
      _ensureEconLoaded().then(function() {
        var section = document.getElementById("fred-section-debt");
        if (section) _ensureCard("macro-charts", "Macro Charts").appendChild(section);
      });
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["world-uncertainty"] = {
    name: "World Uncertainty Index",
    category: "Economics",
    init: function() {
      _ensureEconLoaded().then(function() {
        var section = document.getElementById("fred-section-wui");
        if (section) _ensureCard("world-uncertainty", "World Uncertainty Index").appendChild(section);
      });
    },
    destroy: _noop
  };

  var _econLoadPromise = null;
  function _ensureEconLoaded() {
    if (document.getElementById("fred-section-econcal")) return Promise.resolve();
    if (_econLoadPromise) return _econLoadPromise;
    var tab = document.getElementById("tab-economics");
    if (!tab) return Promise.resolve();
    _econLoadPromise = fetch("/api/tab-content/economics")
      .then(function(r) { return r.text(); })
      .then(function(html) {
        var tmp = document.createElement("div");
        tmp.innerHTML = html;
        while (tmp.firstChild) tab.appendChild(tmp.firstChild);
        if (typeof loadFredData === "function") loadFredData();
      })
      .catch(function() {});
    return _econLoadPromise;
  }

  // ─── Budget widgets ───────────────────────────────────────────

  WIDGET_REGISTRY["monthly-budget"] = {
    name: "Monthly Budget",
    category: "Budget",
    init: function() {
      var section = document.getElementById("budget-section");
      if (section) _ensureCard("monthly-budget", "Monthly Budget").appendChild(section);
      if (typeof _initBudgetListeners === "function") _initBudgetListeners();
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["spending-chart"] = {
    name: "Spending vs Budget",
    category: "Budget",
    init: function() {
      var section = document.getElementById("spending-chart-section");
      if (section) _ensureCard("spending-chart", "Spending vs Budget").appendChild(section);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["spending-trends"] = {
    name: "Spending Trends",
    category: "Budget",
    init: function() {
      var section = document.getElementById("spending-trends-section");
      if (section) _ensureCard("spending-trends", "Spending Trends").appendChild(section);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["debt-tracker"] = {
    name: "Debt Tracker",
    category: "Budget",
    init: function() {
      var section = document.getElementById("debt-tracker-section");
      if (section) _ensureCard("debt-tracker", "Debt Tracker").appendChild(section);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["amortization"] = {
    name: "Loan Amortization",
    category: "Budget",
    init: function() {
      var section = document.getElementById("amortization-section");
      if (section) _ensureCard("amortization", "Loan Amortization").appendChild(section);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["transaction-log"] = {
    name: "Transaction Log",
    category: "Budget",
    init: function() {
      var section = document.getElementById("transaction-log-section");
      if (section) _ensureCard("transaction-log", "Transaction Log").appendChild(section);
    },
    destroy: _noop
  };

  // ─── Holdings widgets ─────────────────────────────────────────

  WIDGET_REGISTRY["brokerage-holdings"] = {
    name: "Brokerage Holdings",
    category: "Holdings",
    init: function() {
      var section = document.getElementById("holdings-section");
      if (section) _ensureCard("brokerage-holdings", "Brokerage Holdings").appendChild(section);
      if (typeof loadHoldings === "function") loadHoldings();
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["crypto-holdings"] = {
    name: "Crypto Holdings",
    category: "Holdings",
    init: function() {
      var section = document.getElementById("crypto-section");
      if (section) _ensureCard("crypto-holdings", "Crypto Holdings").appendChild(section);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["physical-metals"] = {
    name: "Physical Metals",
    category: "Holdings",
    init: function() {
      var section = document.getElementById("metals-section");
      if (section) _ensureCard("physical-metals", "Physical Metals").appendChild(section);
    },
    destroy: _noop
  };

  WIDGET_REGISTRY["dividends-fees"] = {
    name: "Dividends & Fees",
    category: "Holdings",
    init: function() {
      var section = document.getElementById("dividends-section");
      if (section) _ensureCard("dividends-fees", "Dividends & Fees").appendChild(section);
    },
    destroy: _noop
  };

  // ─── Balances widget ──────────────────────────────────────────

  WIDGET_REGISTRY["account-balances"] = {
    name: "Account Balances",
    category: "Balances",
    init: function() {
      var section = document.getElementById("balances-section");
      if (section) _ensureCard("account-balances", "Account Balances").appendChild(section);
      if (typeof loadBalances === "function") loadBalances();
    },
    destroy: _noop
  };

  /* ── Helper: create a card wrapper for non-summary widgets ── */

  function _ensureCard(widgetId, title) {
    var existing = document.querySelector('[data-widget="' + widgetId + '"]');
    if (existing) return existing;

    var card = document.createElement("div");
    card.className = "card widget-card";
    card.setAttribute("data-widget", widgetId);
    card.setAttribute("draggable", "true");
    card.innerHTML = '<div class="card-title">' +
      '<span class="drag-handle" title="Drag to reorder">&#x2630;</span> ' +
      _esc(title) + '</div>';

    var staging = document.getElementById("widget-staging");
    if (staging) {
      var rightCol = document.getElementById("widget-col-right");
      if (rightCol) {
        rightCol.appendChild(card);
      } else {
        staging.appendChild(card);
      }
    }
    return card;
  }

  function _esc(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

})();
