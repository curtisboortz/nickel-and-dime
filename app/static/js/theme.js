/* Nickel&Dime — Theme management (light/dark) */

(function() {
  var saved = localStorage.getItem("theme");
  if (saved === "light") document.documentElement.classList.add("light");

  window.toggleTheme = function() {
    var isLight = document.documentElement.classList.toggle("light");
    localStorage.setItem("theme", isLight ? "light" : "dark");

    var icon = document.getElementById("theme-icon");
    if (icon) {
      icon.innerHTML = isLight
        ? '<path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z"/>'
        : '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
    }

    if (typeof Chart !== "undefined") {
      Chart.helpers.each(Chart.instances, function(chart) {
        if (chart && chart.options) {
          var txtColor = isLight ? "#4a4a5a" : "#94a3b8";
          var gridColor = isLight ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.06)";
          if (chart.options.scales) {
            Object.values(chart.options.scales).forEach(function(axis) {
              if (axis.ticks) axis.ticks.color = txtColor;
              if (axis.grid) axis.grid.color = gridColor;
            });
          }
          if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
            chart.options.plugins.legend.labels.color = txtColor;
          }
          chart.update("none");
        }
      });
    }
  };

  if (saved === "light") window.toggleTheme();
})();
