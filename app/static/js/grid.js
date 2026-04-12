/* Nickel&Dime — Dashboard grid controller (gridstack.js).
 *
 * 8-column square-cell grid.  cellHeight = containerWidth / 8 so every
 * cell is a perfect square (~120 px on a typical 960 px container).
 *
 * Size presets live in widgets.js (_WIDE / _TALL).
 * Widgets flagged expandable:true auto-grow by 2 rows when content overflows.
 */

var _grid = null;
var _gridEditMode = false;
var _gridWidgetIds = [];

var DEFAULT_LAYOUT = [
  { id: "allocation-donut",    x: 0, y: 0, w: 4, h: 4 },
  { id: "allocation-table",    x: 4, y: 0, w: 4, h: 4 },
  { id: "monthly-investments", x: 0, y: 4, w: 4, h: 8 },
  { id: "watchlist",           x: 4, y: 4, w: 4, h: 4 },
  { id: "financial-goals",     x: 4, y: 8, w: 4, h: 4 }
];

(function() {
  "use strict";

  var _saveTimer = null;
  var COLS = 8;
  var MARGIN = 4;

  function _calcCellH(container) {
    var w = container.offsetWidth;
    return Math.round((w - (COLS - 1) * MARGIN) / COLS);
  }

  function _debounceSave() {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(function() { saveDashboardLayout(); }, 800);
  }

  function _returnToStaging(gridItem) {
    var staging = document.getElementById("widget-staging");
    if (!staging) return;
    var body = gridItem.querySelector(".gs-widget-body");
    if (!body) return;
    while (body.firstChild) {
      staging.appendChild(body.firstChild);
    }
  }

  function _returnAllToStaging() {
    if (!_grid) return;
    var items = _grid.getGridItems();
    for (var i = 0; i < items.length; i++) {
      _returnToStaging(items[i]);
    }
  }

  function _activeSizeIdx(widgetId, w, h) {
    var reg = WIDGET_REGISTRY[widgetId];
    if (!reg || !reg.sizes) return -1;
    for (var i = 0; i < reg.sizes.length; i++) {
      if (reg.sizes[i].w === w && reg.sizes[i].h === h) return i;
    }
    return -1;
  }

  function _applySizeClass(el, widgetId, w, h) {
    el.classList.remove("gs-size-s", "gs-size-m", "gs-size-l");
    var idx = _activeSizeIdx(widgetId, w, h);
    var reg = WIDGET_REGISTRY[widgetId];
    if (idx >= 0 && reg && reg.sizes[idx]) {
      el.classList.add("gs-size-" + reg.sizes[idx].label.toLowerCase());
    } else {
      el.classList.add("gs-size-m");
    }
  }

  function _buildSizeBtns(widgetId, currentW, currentH) {
    var reg = WIDGET_REGISTRY[widgetId];
    if (!reg || !reg.sizes) return "";
    var html = '<div class="gs-size-btns">';
    for (var i = 0; i < reg.sizes.length; i++) {
      var s = reg.sizes[i];
      var active = (s.w === currentW && s.h === currentH) ? " active" : "";
      html += '<button class="gs-size-btn' + active + '" ' +
        'onclick="setWidgetSize(\'' + widgetId + '\',' + i + ')" ' +
        'title="' + s.w + '\u00d7' + s.h + '">' + s.label + '</button>';
    }
    html += '</div>';
    return html;
  }

  function _buildWidgetEl(widgetId, opts) {
    var reg = WIDGET_REGISTRY[widgetId];
    if (!reg) return null;

    var sizeIdx = reg.defaultSize || 0;
    var w = opts.w || reg.sizes[sizeIdx].w;
    var h = opts.h || reg.sizes[sizeIdx].h;

    var wrapper = document.createElement("div");
    wrapper.className = "grid-stack-item";
    wrapper.setAttribute("gs-id", widgetId);
    wrapper.setAttribute("gs-w", w);
    wrapper.setAttribute("gs-h", h);
    wrapper.setAttribute("gs-x", opts.x != null ? opts.x : "");
    wrapper.setAttribute("gs-y", opts.y != null ? opts.y : "");

    if (reg.expandable) wrapper.classList.add("gs-expandable");

    var content = document.createElement("div");
    content.className = "grid-stack-item-content";

    var header = document.createElement("div");
    header.className = "gs-widget-header";
    header.innerHTML = '<span class="gs-widget-drag" title="Drag to reorder">&#x2630;</span>' +
      '<span class="gs-widget-title">' + _esc(reg.name) + '</span>' +
      _buildSizeBtns(widgetId, w, h) +
      '<button class="gs-widget-remove" title="Remove widget" onclick="removeWidgetFromGrid(\'' +
      widgetId + '\')">&times;</button>';
    content.appendChild(header);

    var body = document.createElement("div");
    body.className = "gs-widget-body";
    content.appendChild(body);

    wrapper.appendChild(content);
    _applySizeClass(wrapper, widgetId, w, h);
    return { wrapper: wrapper, body: body };
  }

  /* ── 2-block expansion for expandable widgets ── */

  function _expandIfNeeded(wrapper, body, widgetId) {
    var reg = WIDGET_REGISTRY[widgetId];
    if (!reg || !reg.expandable) return;
    setTimeout(function() {
      var contentH = body.scrollHeight;
      var visibleH = body.clientHeight;
      if (contentH > visibleH + 10) {
        var node = wrapper.gridstackNode;
        if (!node) return;
        var cellH = _grid.getCellHeight();
        if (!cellH || cellH <= 0) return;
        var needed = Math.ceil(contentH / cellH);
        var extra = needed - node.h;
        if (extra > 0) {
          extra = Math.ceil(extra / 2) * 2;
          _grid.update(wrapper, { h: node.h + extra });
        }
      }
    }, 300);
  }

  /* ── Grid boot ── */

  window.initDashboardGrid = function() {
    var container = document.getElementById("dashboard-grid");
    if (!container || _grid) return;

    fetch("/api/dashboard-layout")
      .then(function(r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function(d) {
        var layout = d.layout;
        if (!layout || !layout.length) {
          layout = DEFAULT_LAYOUT;
        }
        _bootGrid(container, layout);
      })
      .catch(function(e) {
        console.warn("Dashboard layout load failed, using defaults:", e);
        _bootGrid(container, DEFAULT_LAYOUT);
      });
  };

  function _bootGrid(container, layout) {
    var cellH = _calcCellH(container);

    _grid = GridStack.init({
      column: COLS,
      cellHeight: cellH,
      margin: MARGIN,
      animate: true,
      float: false,
      draggable: { handle: ".gs-widget-drag" },
      resizable: { handles: "" },
      disableDrag: true,
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
      _expandIfNeeded(built.wrapper, built.body, item.id);
    }
    _grid.commit();

    _grid.on("change", _debounceSave);

    window.addEventListener("resize", _onResize);

    _updateCatalogStates();
    _applyEditState();
  }

  var _resizeTimer = null;
  function _onResize() {
    if (_resizeTimer) clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(function() {
      if (!_grid) return;
      var container = document.getElementById("dashboard-grid");
      if (!container) return;
      _grid.cellHeight(_calcCellH(container));
    }, 150);
  }

  window.saveDashboardLayout = function() {
    if (!_grid) return;
    var items = _grid.getGridItems();
    var layout = [];
    items.forEach(function(el) {
      var node = el.gridstackNode;
      var gid = el.getAttribute("gs-id");
      if (!gid) return;
      layout.push({
        id: gid,
        x: node ? node.x : 0,
        y: node ? node.y : 0,
        w: node ? node.w : parseInt(el.getAttribute("gs-w")) || 4,
        h: node ? node.h : parseInt(el.getAttribute("gs-h")) || 4
      });
    });
    if (!layout.length) return;
    var csrf = document.querySelector('meta[name="csrf-token"]');
    fetch("/api/dashboard-layout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf ? csrf.content : ""
      },
      body: JSON.stringify({ layout: layout })
    }).then(function(r) {
      if (!r.ok) console.warn("Dashboard layout save failed:", r.status);
    }).catch(function(e) {
      console.warn("Dashboard layout save error:", e);
    });
  };

  window.setWidgetSize = function(widgetId, sizeIdx) {
    if (!_grid) return;
    var reg = WIDGET_REGISTRY[widgetId];
    if (!reg || !reg.sizes || !reg.sizes[sizeIdx]) return;

    var size = reg.sizes[sizeIdx];
    var items = _grid.getGridItems();
    for (var i = 0; i < items.length; i++) {
      if (items[i].getAttribute("gs-id") === widgetId) {
        _grid.update(items[i], { w: size.w, h: size.h });
        _applySizeClass(items[i], widgetId, size.w, size.h);
        var btns = items[i].querySelectorAll(".gs-size-btn");
        for (var j = 0; j < btns.length; j++) {
          btns[j].classList.toggle("active", j === sizeIdx);
        }
        var body = items[i].querySelector(".gs-widget-body");
        if (body) _expandIfNeeded(items[i], body, widgetId);
        _debounceSave();
        return;
      }
    }
  };

  window.addWidgetToGrid = function(widgetId) {
    if (!_grid || !WIDGET_REGISTRY[widgetId]) return;
    if (_gridWidgetIds.indexOf(widgetId) !== -1) return;

    var reg = WIDGET_REGISTRY[widgetId];
    var sizeIdx = reg.defaultSize || 0;
    var built = _buildWidgetEl(widgetId, {
      w: reg.sizes[sizeIdx].w,
      h: reg.sizes[sizeIdx].h
    });
    if (!built) return;

    _grid.addWidget(built.wrapper);
    _gridWidgetIds.push(widgetId);
    try {
      reg.init(built.body);
    } catch (e) {
      built.body.innerHTML = '<div style="padding:16px;color:var(--text-muted);">Widget failed to load.</div>';
    }
    _expandIfNeeded(built.wrapper, built.body, widgetId);
    saveDashboardLayout();
    _updateCatalogStates();
  };

  window.removeWidgetFromGrid = function(widgetId) {
    if (!_grid) return;
    var items = _grid.getGridItems();
    for (var i = 0; i < items.length; i++) {
      var gid = items[i].getAttribute("gs-id");
      if (gid === widgetId) {
        _returnToStaging(items[i]);
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
    } else {
      _grid.enableMove(false);
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
    _returnAllToStaging();
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
      _expandIfNeeded(built.wrapper, built.body, item.id);
    }
    _grid.commit();
    saveDashboardLayout();
    _updateCatalogStates();
    _applyEditState();
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
