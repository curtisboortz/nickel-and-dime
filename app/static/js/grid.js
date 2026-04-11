/* Nickel&Dime — Dashboard grid controller (gridstack.js).
 *
 * Manages the configurable widget grid on the Summary tab.
 * Loads layout from server, initializes widgets, saves on change.
 */

var _grid = null;
var _gridEditMode = false;
var _gridWidgetIds = [];

var DEFAULT_LAYOUT = [
  { id: "allocation-donut",    x: 0, y: 0,  w: 6, h: 12 },
  { id: "allocation-table",    x: 6, y: 0,  w: 6, h: 9  },
  { id: "monthly-investments", x: 0, y: 12, w: 6, h: 12 },
  { id: "watchlist",           x: 6, y: 9,  w: 6, h: 9  },
  { id: "financial-goals",     x: 6, y: 18, w: 6, h: 9  }
];

(function() {
  "use strict";

  var _saveTimer = null;

  function _debounceSave() {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(function() { saveDashboardLayout(); }, 800);
  }

  function _buildWidgetEl(widgetId, opts) {
    var reg = WIDGET_REGISTRY[widgetId];
    if (!reg) return null;

    var wrapper = document.createElement("div");
    wrapper.className = "grid-stack-item";
    wrapper.setAttribute("gs-id", widgetId);
    wrapper.setAttribute("gs-w", opts.w || reg.defaultW);
    wrapper.setAttribute("gs-h", opts.h || reg.defaultH);
    wrapper.setAttribute("gs-x", opts.x != null ? opts.x : "");
    wrapper.setAttribute("gs-y", opts.y != null ? opts.y : "");
    wrapper.setAttribute("gs-min-w", reg.minW || 3);
    wrapper.setAttribute("gs-min-h", reg.minH || 2);

    var content = document.createElement("div");
    content.className = "grid-stack-item-content";

    var header = document.createElement("div");
    header.className = "gs-widget-header";
    header.innerHTML = '<span class="gs-widget-drag" title="Drag to reorder">&#x2630;</span>' +
      '<span class="gs-widget-title">' + _esc(reg.name) + '</span>' +
      '<button class="gs-widget-remove" title="Remove widget" onclick="removeWidgetFromGrid(\'' +
      widgetId + '\')">&times;</button>';
    content.appendChild(header);

    var body = document.createElement("div");
    body.className = "gs-widget-body";
    content.appendChild(body);

    wrapper.appendChild(content);
    return { wrapper: wrapper, body: body };
  }

  window.initDashboardGrid = function() {
    var container = document.getElementById("dashboard-grid");
    if (!container || _grid) return;

    fetch("/api/dashboard-layout")
      .then(function(r) { return r.json(); })
      .then(function(d) {
        var layout = d.layout;
        if (!layout || !layout.length) layout = DEFAULT_LAYOUT;
        _bootGrid(container, layout);
      })
      .catch(function() {
        _bootGrid(container, DEFAULT_LAYOUT);
      });
  };

  function _bootGrid(container, layout) {
    _grid = GridStack.init({
      column: 12,
      cellHeight: 40,
      margin: 8,
      animate: true,
      float: false,
      draggable: { handle: ".gs-widget-drag" },
      resizable: { handles: "se,sw" },
      disableDrag: true,
      disableResize: true,
      columnOpts: {
        breakpoints: [
          { w: 768, c: 1 }
        ]
      }
    }, container);

    _gridWidgetIds = [];

    _grid.batchUpdate();
    for (var i = 0; i < layout.length; i++) {
      var item = layout[i];
      if (!WIDGET_REGISTRY[item.id]) continue;
      var built = _buildWidgetEl(item.id, item);
      if (!built) continue;
      _grid.addWidget(built.wrapper);
      _gridWidgetIds.push(item.id);
      try {
        WIDGET_REGISTRY[item.id].init(built.body);
      } catch (e) {
        built.body.innerHTML = '<div style="padding:16px;color:var(--text-muted);font-size:0.82rem;">Widget failed to load.</div>';
      }
    }
    _grid.commit();

    _grid.on("change", _debounceSave);

    _updateCatalogStates();
    _applyEditState();
  }

  window.saveDashboardLayout = function() {
    if (!_grid) return;
    var items = _grid.getGridItems();
    var layout = [];
    items.forEach(function(el) {
      var node = el.gridstackNode;
      if (!node) return;
      layout.push({
        id: node.id || el.getAttribute("gs-id"),
        x: node.x, y: node.y,
        w: node.w, h: node.h
      });
    });
    var csrf = document.querySelector('meta[name="csrf-token"]');
    fetch("/api/dashboard-layout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf ? csrf.content : ""
      },
      body: JSON.stringify({ layout: layout })
    }).catch(function() {});
  };

  window.addWidgetToGrid = function(widgetId) {
    if (!_grid || !WIDGET_REGISTRY[widgetId]) return;
    if (_gridWidgetIds.indexOf(widgetId) !== -1) return;

    var reg = WIDGET_REGISTRY[widgetId];
    var built = _buildWidgetEl(widgetId, {
      w: reg.defaultW, h: reg.defaultH
    });
    if (!built) return;

    _grid.addWidget(built.wrapper);
    _gridWidgetIds.push(widgetId);
    try {
      reg.init(built.body);
    } catch (e) {
      built.body.innerHTML = '<div style="padding:16px;color:var(--text-muted);">Widget failed to load.</div>';
    }
    saveDashboardLayout();
    _updateCatalogStates();
  };

  window.removeWidgetFromGrid = function(widgetId) {
    if (!_grid) return;
    var items = _grid.getGridItems();
    for (var i = 0; i < items.length; i++) {
      var gid = items[i].getAttribute("gs-id");
      if (gid === widgetId) {
        var reg = WIDGET_REGISTRY[widgetId];
        if (reg && reg.destroy) {
          var body = items[i].querySelector(".gs-widget-body");
          try { reg.destroy(body); } catch(e) {}
        }
        _grid.removeWidget(items[i]);
        var idx = _gridWidgetIds.indexOf(widgetId);
        if (idx !== -1) _gridWidgetIds.splice(idx, 1);
        saveDashboardLayout();
        _updateCatalogStates();
        return;
      }
    }
  };

  window.toggleGridEditMode = function() {
    _gridEditMode = !_gridEditMode;
    _applyEditState();
  };

  function _applyEditState() {
    if (!_grid) return;
    if (_gridEditMode) {
      _grid.enableMove(true);
      _grid.enableResize(true);
    } else {
      _grid.enableMove(false);
      _grid.enableResize(false);
    }
    var container = document.getElementById("dashboard-grid");
    if (container) {
      container.classList.toggle("gs-edit-mode", _gridEditMode);
    }
    var btn = document.getElementById("grid-edit-btn");
    if (btn) {
      btn.textContent = _gridEditMode ? "Done Editing" : "Edit Layout";
      btn.classList.toggle("active", _gridEditMode);
    }
    var resetBtn = document.getElementById("grid-reset-btn");
    if (resetBtn) resetBtn.style.display = _gridEditMode ? "" : "none";

    var headers = document.querySelectorAll(".gs-widget-header");
    headers.forEach(function(h) {
      h.style.display = _gridEditMode ? "" : "none";
    });
  }

  window.resetDashboardLayout = function() {
    if (!_grid) return;
    _grid.removeAll();
    _gridWidgetIds = [];
    _grid.batchUpdate();
    for (var i = 0; i < DEFAULT_LAYOUT.length; i++) {
      var item = DEFAULT_LAYOUT[i];
      if (!WIDGET_REGISTRY[item.id]) continue;
      var built = _buildWidgetEl(item.id, item);
      if (!built) continue;
      _grid.addWidget(built.wrapper);
      _gridWidgetIds.push(item.id);
      try { WIDGET_REGISTRY[item.id].init(built.body); } catch(e) {}
    }
    _grid.commit();
    saveDashboardLayout();
    _updateCatalogStates();
  };

  function _updateCatalogStates() {
    var items = document.querySelectorAll(".catalog-widget-item");
    items.forEach(function(el) {
      var wid = el.dataset.widgetId;
      var added = _gridWidgetIds.indexOf(wid) !== -1;
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
    if (_gridWidgetIds.indexOf(widgetId) !== -1) {
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
