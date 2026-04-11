/* Nickel&Dime — Widget registry for the configurable dashboard grid.
 *
 * Each widget has: name, category, size presets (S/M/L), default size index,
 * and init/destroy lifecycle hooks.
 * init(el) receives the .gs-widget-body inner div.
 */

var WIDGET_REGISTRY = {};

(function() {
  "use strict";

  var _COMPACT = [
    { label: "S", w: 6, h: 6 },
    { label: "M", w: 6, h: 9 },
    { label: "L", w: 12, h: 9 }
  ];
  var _CHART = [
    { label: "S", w: 6, h: 9 },
    { label: "M", w: 6, h: 12 },
    { label: "L", w: 12, h: 12 }
  ];
  var _LARGE = [
    { label: "S", w: 6, h: 12 },
    { label: "M", w: 12, h: 12 },
    { label: "L", w: 12, h: 16 }
  ];

  // ─── Summary widgets ─────────────────────────────────────────

  WIDGET_REGISTRY["allocation-donut"] = {
    name: "Portfolio Allocation",
    category: "Summary",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var card = document.querySelector('[data-widget="allocation-donut"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["allocation-table"] = {
    name: "Allocation vs Target",
    category: "Summary",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var card = document.querySelector('[data-widget="allocation-table"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["monthly-investments"] = {
    name: "Monthly Investments",
    category: "Summary",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var card = document.querySelector('[data-widget="monthly-investments"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["watchlist"] = {
    name: "Watchlist & Alerts",
    category: "Summary",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var card = document.querySelector('[data-widget="watchlist"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["financial-goals"] = {
    name: "Financial Goals",
    category: "Summary",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var card = document.getElementById("goals-card");
      if (!card) {
        var staging = document.getElementById("widget-staging");
        if (staging) {
          var cards = staging.querySelectorAll(".card");
          for (var i = 0; i < cards.length; i++) {
            if (cards[i].querySelector("#goals-container")) {
              card = cards[i];
              break;
            }
          }
        }
      }
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  // ─── Portfolio widgets ────────────────────────────────────────

  WIDGET_REGISTRY["sentiment-gauges"] = {
    name: "Market Sentiment",
    category: "Portfolio",
    sizes: _LARGE, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("sentiment-section");
      if (section) el.appendChild(section);
      if (typeof loadSentimentGauges === "function") loadSentimentGauges();
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["projected-growth"] = {
    name: "Projected Growth",
    category: "Portfolio",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("projection-section");
      if (section) el.appendChild(section);
      setTimeout(function() {
        if (typeof buildProjectionChart === "function") buildProjectionChart();
      }, 100);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["monte-carlo"] = {
    name: "Monte Carlo Simulation",
    category: "Portfolio",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("monte-carlo-section");
      if (section) el.appendChild(section);
      setTimeout(function() {
        if (typeof runMonteCarlo === "function") runMonteCarlo();
      }, 100);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["drawdown"] = {
    name: "Drawdown Analysis",
    category: "Portfolio",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("drawdown-section");
      if (section) el.appendChild(section);
      setTimeout(function() {
        if (typeof buildDrawdownChart === "function") buildDrawdownChart();
      }, 100);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["perf-attribution"] = {
    name: "Performance Attribution",
    category: "Portfolio",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("perf-attribution-section");
      if (section) el.appendChild(section);
      setTimeout(function() {
        if (typeof buildPerfAttribution === "function") buildPerfAttribution();
      }, 100);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["portfolio-insights"] = {
    name: "Portfolio Insights",
    category: "Portfolio",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("insights-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["allocation-templates"] = {
    name: "Allocation Templates",
    category: "Portfolio",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("templates-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  // ─── Economics widgets ────────────────────────────────────────

  WIDGET_REGISTRY["economic-calendar"] = {
    name: "Economic Calendar",
    category: "Economics",
    sizes: _LARGE, defaultSize: 1,
    init: function(el) {
      _ensureEconLoaded();
      var section = document.getElementById("fred-section-econcal");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["fedwatch"] = {
    name: "FedWatch Tool",
    category: "Economics",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      _ensureEconLoaded();
      var section = document.getElementById("fred-section-fedwatch");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["cape-buffett"] = {
    name: "CAPE & Buffett Indicator",
    category: "Economics",
    sizes: _LARGE, defaultSize: 1,
    init: function(el) {
      _ensureEconLoaded();
      var cape = document.getElementById("fred-section-cape");
      var buff = document.getElementById("fred-section-buffett");
      if (cape) el.appendChild(cape);
      if (buff) el.appendChild(buff);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["macro-charts"] = {
    name: "Macro Charts",
    category: "Economics",
    sizes: _LARGE, defaultSize: 2,
    init: function(el) {
      _ensureEconLoaded();
      var section = document.getElementById("fred-section-debt");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["world-uncertainty"] = {
    name: "World Uncertainty Index",
    category: "Economics",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      _ensureEconLoaded();
      var section = document.getElementById("fred-section-wui");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  var _econLoadPromise = null;
  function _ensureEconLoaded() {
    if (document.getElementById("fred-section-econcal")) return;
    if (_econLoadPromise) return;
    var tab = document.getElementById("tab-economics");
    if (!tab) return;
    _econLoadPromise = fetch("/api/tab-content/economics")
      .then(function(r) { return r.text(); })
      .then(function(html) {
        var tmp = document.createElement("div");
        tmp.innerHTML = html;
        while (tmp.firstChild) tab.appendChild(tmp.firstChild);
        if (typeof loadFredData === "function") loadFredData();
      })
      .catch(function() {});
  }

  // ─── Budget widgets ───────────────────────────────────────────

  WIDGET_REGISTRY["monthly-budget"] = {
    name: "Monthly Budget",
    category: "Budget",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("budget-section");
      if (section) el.appendChild(section);
      if (typeof _initBudgetListeners === "function") _initBudgetListeners();
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["spending-chart"] = {
    name: "Spending vs Budget",
    category: "Budget",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("spending-chart-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["spending-trends"] = {
    name: "Spending Trends",
    category: "Budget",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("spending-trends-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["debt-tracker"] = {
    name: "Debt Tracker",
    category: "Budget",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("debt-tracker-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["amortization"] = {
    name: "Loan Amortization",
    category: "Budget",
    sizes: _LARGE, defaultSize: 2,
    init: function(el) {
      var section = document.getElementById("amortization-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["transaction-log"] = {
    name: "Transaction Log",
    category: "Budget",
    sizes: _LARGE, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("transaction-log-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  // ─── Holdings widgets ─────────────────────────────────────────

  WIDGET_REGISTRY["brokerage-holdings"] = {
    name: "Brokerage Holdings",
    category: "Holdings",
    sizes: _LARGE, defaultSize: 2,
    init: function(el) {
      var section = document.getElementById("holdings-section");
      if (section) el.appendChild(section);
      if (typeof loadHoldings === "function") loadHoldings();
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["crypto-holdings"] = {
    name: "Crypto Holdings",
    category: "Holdings",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("crypto-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["physical-metals"] = {
    name: "Physical Metals",
    category: "Holdings",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("metals-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["dividends-fees"] = {
    name: "Dividends & Fees",
    category: "Holdings",
    sizes: _CHART, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("dividends-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  // ─── Balances widget ──────────────────────────────────────────

  WIDGET_REGISTRY["account-balances"] = {
    name: "Account Balances",
    category: "Balances",
    sizes: _COMPACT, defaultSize: 1,
    init: function(el) {
      var section = document.getElementById("balances-section");
      if (section) el.appendChild(section);
      if (typeof loadBalances === "function") loadBalances();
    },
    destroy: function(el) {}
  };

})();
