/* Nickel&Dime — Dashboard widget visibility controller.
 *
 * No grid library.  Widgets live in the original two-column CSS flow at
 * their natural height.  This file manages which widgets are visible,
 * persists that list to the server, and powers the widget catalog.
 */

var _activeWidgetIds = [];

var DEFAULT_WIDGETS = [
  "allocation-donut",
  "allocation-table",
  "monthly-investments",
  "watchlist",
  "financial-goals"
];

(function() {
  "use strict";

  /* ── Show / hide helpers ── */

  function _showWidget(id) {
    var el = document.querySelector('[data-widget="' + id + '"]');
    if (el) el.style.display = "";
    var reg = WIDGET_REGISTRY[id];
    if (reg && reg.init) {
      try { reg.init(el); } catch (e) {}
    }
  }

  function _hideWidget(id) {
    var el = document.querySelector('[data-widget="' + id + '"]');
    if (el) el.style.display = "none";
  }

  function _applyVisibility(ids) {
    _activeWidgetIds = ids.slice();
    document.querySelectorAll('[data-widget]').forEach(function(el) {
      el.style.display = "none";
    });
    for (var i = 0; i < ids.length; i++) {
      _showWidget(ids[i]);
    }
  }

  /* ── Init ── */

  window.initDashboardGrid = function() {
    fetch("/api/dashboard-layout")
      .then(function(r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function(d) {
        var layout = d.layout;
        if (!layout || !layout.length) {
          layout = DEFAULT_WIDGETS;
        }
        var ids = _normalizeLayout(layout);
        _applyVisibility(ids);
      })
      .catch(function() {
        _applyVisibility(DEFAULT_WIDGETS);
      });
  };

  function _normalizeLayout(layout) {
    if (!layout || !layout.length) return DEFAULT_WIDGETS;
    if (typeof layout[0] === "string") return layout;
    return layout.map(function(item) { return item.id || item; });
  }

  /* ── Save ── */

  window.saveDashboardLayout = function() {
    var csrf = document.querySelector('meta[name="csrf-token"]');
    fetch("/api/dashboard-layout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf ? csrf.content : ""
      },
      body: JSON.stringify({ layout: _activeWidgetIds })
    }).catch(function(e) {
      console.warn("Dashboard layout save error:", e);
    });
  };

  /* ── Add / Remove ── */

  window.addWidgetToGrid = function(widgetId) {
    if (_activeWidgetIds.indexOf(widgetId) !== -1) return;
    _activeWidgetIds.push(widgetId);
    _showWidget(widgetId);
    saveDashboardLayout();
    _updateCatalogStates();
  };

  window.removeWidgetFromGrid = function(widgetId) {
    var idx = _activeWidgetIds.indexOf(widgetId);
    if (idx === -1) return;
    _activeWidgetIds.splice(idx, 1);
    _hideWidget(widgetId);
    saveDashboardLayout();
    _updateCatalogStates();
  };

  window.resetDashboardLayout = function() {
    _applyVisibility(DEFAULT_WIDGETS);
    saveDashboardLayout();
    _updateCatalogStates();
  };

  /* ── Catalog ── */

  function _updateCatalogStates() {
    var items = document.querySelectorAll(".catalog-widget-item");
    items.forEach(function(el) {
      var wid = el.dataset.widgetId;
      var added = _activeWidgetIds.indexOf(wid) !== -1;
      el.classList.toggle("added", added);
      var btn = el.querySelector(".catalog-add-btn");
      if (btn) btn.textContent = added ? "\u2713 Added" : "+ Add";
    });
  }
  window._updateCatalogStates = _updateCatalogStates;

  window.openWidgetCatalog = function() {
    var overlay = document.getElementById("widget-catalog-overlay");
    if (!overlay) return;
    var body = document.getElementById("catalog-body");
    if (body && !body.children.length) _buildCatalog(body);
    _updateCatalogStates();
    overlay.style.display = "flex";
  };

  window.closeWidgetCatalog = function() {
    var overlay = document.getElementById("widget-catalog-overlay");
    if (overlay) overlay.style.display = "none";
  };

  function _buildCatalog(body) {
    var categories = {};
    var order = ["Summary", "Portfolio", "Economics", "Budget", "Holdings", "Balances"];
    for (var wid in WIDGET_REGISTRY) {
      var reg = WIDGET_REGISTRY[wid];
      var cat = reg.category || "Other";
      if (!categories[cat]) categories[cat] = [];
      categories[cat].push({ id: wid, name: reg.name });
    }
    var html = "";
    for (var i = 0; i < order.length; i++) {
      var cat = order[i];
      var widgets = categories[cat];
      if (!widgets || !widgets.length) continue;
      html += '<div class="catalog-category">';
      html += '<div class="catalog-category-title">' + _esc(cat) + '</div>';
      for (var j = 0; j < widgets.length; j++) {
        var w = widgets[j];
        html += '<div class="catalog-widget-item" data-widget-id="' + w.id + '">';
        html += '<span class="catalog-widget-name">' + _esc(w.name) + '</span>';
        html += '<button class="catalog-add-btn" onclick="toggleCatalogWidget(\'' + w.id + '\')">+ Add</button>';
        html += '</div>';
      }
      html += '</div>';
    }
    body.innerHTML = html;
  }

  window.toggleCatalogWidget = function(widgetId) {
    if (_activeWidgetIds.indexOf(widgetId) !== -1) {
      removeWidgetFromGrid(widgetId);
    } else {
      addWidgetToGrid(widgetId);
    }
  };

  function _esc(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

})();
