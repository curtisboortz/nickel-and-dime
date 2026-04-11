/* Nickel&Dime — Widget registry for the configurable dashboard grid.
 *
 * Each widget has: name, category, default size, min size, and init/destroy
 * lifecycle hooks. init(el) receives the .grid-stack-item-content inner div.
 */

var WIDGET_REGISTRY = {};

(function() {
  "use strict";

  // ─── Summary widgets ─────────────────────────────────────────

  WIDGET_REGISTRY["allocation-donut"] = {
    name: "Portfolio Allocation",
    category: "Summary",
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
    init: function(el) {
      var card = document.querySelector('[data-widget="allocation-donut"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["allocation-table"] = {
    name: "Allocation vs Target",
    category: "Summary",
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 3,
    init: function(el) {
      var card = document.querySelector('[data-widget="allocation-table"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["monthly-investments"] = {
    name: "Monthly Investments",
    category: "Summary",
    defaultW: 6, defaultH: 8,
    minW: 4, minH: 4,
    init: function(el) {
      var card = document.querySelector('[data-widget="monthly-investments"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["watchlist"] = {
    name: "Watchlist & Alerts",
    category: "Summary",
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 3,
    init: function(el) {
      var card = document.querySelector('[data-widget="watchlist"]');
      if (card) el.appendChild(card);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["financial-goals"] = {
    name: "Financial Goals",
    category: "Summary",
    defaultW: 12, defaultH: 4,
    minW: 6, minH: 3,
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
    defaultW: 12, defaultH: 5,
    minW: 6, minH: 4,
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
    defaultW: 6, defaultH: 6,
    minW: 4, minH: 4,
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
    defaultW: 6, defaultH: 6,
    minW: 4, minH: 4,
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
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
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
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
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
    defaultW: 6, defaultH: 6,
    minW: 4, minH: 3,
    init: function(el) {
      var section = document.getElementById("insights-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["allocation-templates"] = {
    name: "Allocation Templates",
    category: "Portfolio",
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 3,
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
    defaultW: 12, defaultH: 6,
    minW: 6, minH: 4,
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
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
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
    defaultW: 12, defaultH: 5,
    minW: 6, minH: 3,
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
    defaultW: 12, defaultH: 7,
    minW: 6, minH: 5,
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
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
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
    defaultW: 6, defaultH: 6,
    minW: 4, minH: 4,
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
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
    init: function(el) {
      var section = document.getElementById("spending-chart-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["spending-trends"] = {
    name: "Spending Trends",
    category: "Budget",
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
    init: function(el) {
      var section = document.getElementById("spending-trends-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["debt-tracker"] = {
    name: "Debt Tracker",
    category: "Budget",
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 3,
    init: function(el) {
      var section = document.getElementById("debt-tracker-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["amortization"] = {
    name: "Loan Amortization",
    category: "Budget",
    defaultW: 12, defaultH: 8,
    minW: 6, minH: 5,
    init: function(el) {
      var section = document.getElementById("amortization-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["transaction-log"] = {
    name: "Transaction Log",
    category: "Budget",
    defaultW: 12, defaultH: 6,
    minW: 6, minH: 4,
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
    defaultW: 12, defaultH: 7,
    minW: 6, minH: 4,
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
    defaultW: 12, defaultH: 5,
    minW: 6, minH: 3,
    init: function(el) {
      var section = document.getElementById("crypto-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["physical-metals"] = {
    name: "Physical Metals",
    category: "Holdings",
    defaultW: 12, defaultH: 5,
    minW: 6, minH: 3,
    init: function(el) {
      var section = document.getElementById("metals-section");
      if (section) el.appendChild(section);
    },
    destroy: function(el) {}
  };

  WIDGET_REGISTRY["dividends-fees"] = {
    name: "Dividends & Fees",
    category: "Holdings",
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 4,
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
    defaultW: 6, defaultH: 5,
    minW: 4, minH: 3,
    init: function(el) {
      var section = document.getElementById("balances-section");
      if (section) el.appendChild(section);
      if (typeof loadBalances === "function") loadBalances();
    },
    destroy: function(el) {}
  };

})();
