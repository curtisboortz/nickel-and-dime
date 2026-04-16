/* Nickel&Dime - Onboarding wizard state machine.
 *
 * Drives the wizard modal rendered by _onboarding_wizard.html.
 * Collects answers across 7 steps, previews the recommended allocation
 * with a live Chart.js donut, and POSTs final answers to /api/onboarding.
 */
(function() {
  "use strict";

  var STEPS = ["welcome", "experience", "interests", "risk", "allocation", "contribution", "done"];
  var PRESETS = {
    conservative: { label: "Conservative", desc: "Capital preservation, low drawdowns.",
      alloc: { "Equities": 30, "Real Assets": 10, "Alternatives": 5, "Cash": 15, "Fixed Income": 40 } },
    balanced:     { label: "Balanced",     desc: "Steady mix of growth and safety.",
      alloc: { "Equities": 55, "Real Assets": 15, "Alternatives": 5, "Cash": 5,  "Fixed Income": 20 } },
    aggressive:   { label: "Aggressive",   desc: "Growth-first, tolerates big swings.",
      alloc: { "Equities": 75, "Real Assets": 15, "Alternatives": 5, "Cash": 0,  "Fixed Income": 5 } },
    metals_heavy: { label: "Metals-Heavy", desc: "N&D-signature hard-asset tilt.",
      alloc: { "Equities": 50, "Real Assets": 30, "Alternatives": 5, "Cash": 10, "Fixed Income": 5 } }
  };
  var BUCKET_COLORS = {
    "Equities":     "#f5c842",
    "Real Assets":  "#34d399",
    "Alternatives": "#a78bfa",
    "Cash":         "#60a5fa",
    "Fixed Income": "#94a3b8"
  };

  var state = {
    stepIdx: 0,
    answers: {
      experience: "",
      interests: [],
      risk: "",
      allocation_preset: "",
      custom_allocation: null,
      monthly_contribution: null,
      frequency: "monthly"
    },
    allocMode: "single",
    donutChart: null
  };

  var overlay = document.getElementById("nd-wiz-overlay");
  if (!overlay) return;
  var progressBar = document.getElementById("nd-wiz-progress-bar");
  var stepIndicator = document.getElementById("nd-wiz-step-indicator");

  /* ── Step navigation ── */
  function showStep(idx) {
    if (idx < 0) idx = 0;
    if (idx >= STEPS.length) idx = STEPS.length - 1;
    state.stepIdx = idx;
    var name = STEPS[idx];
    overlay.querySelectorAll(".nd-wiz-step").forEach(function(el) {
      el.hidden = (el.dataset.step !== name);
    });
    var pct = Math.round(((idx + 1) / STEPS.length) * 100);
    if (progressBar) progressBar.style.width = pct + "%";
    if (stepIndicator) stepIndicator.textContent = "Step " + (idx + 1) + " of " + STEPS.length;

    if (name === "allocation") renderAllocationStep();
    if (name === "done") renderSummary();
  }

  function nextStep()  { showStep(state.stepIdx + 1); }
  function prevStep()  { showStep(state.stepIdx - 1); }

  /* ── Card selection (single + multi) ── */
  overlay.querySelectorAll('[data-wiz-select]').forEach(function(grp) {
    var mode = grp.dataset.wizSelect;
    var field = grp.dataset.wizField;
    grp.querySelectorAll(".nd-wiz-card").forEach(function(card) {
      card.addEventListener("click", function() {
        var val = card.dataset.wizValue;
        if (mode === "single") {
          grp.querySelectorAll(".nd-wiz-card").forEach(function(c) { c.classList.remove("selected"); });
          card.classList.add("selected");
          state.answers[field] = val;
        } else {
          card.classList.toggle("selected");
          var list = Array.prototype.slice.call(grp.querySelectorAll(".nd-wiz-card.selected"))
            .map(function(c) { return c.dataset.wizValue; });
          state.answers[field] = list;
        }
        updateStepValidity();
      });
    });
  });

  function updateStepValidity() {
    var name = STEPS[state.stepIdx];
    var step = overlay.querySelector('.nd-wiz-step[data-step="' + name + '"]');
    if (!step) return;
    var nextBtn = step.querySelector('[data-wiz-action="next"].nd-wiz-btn-primary');
    if (!nextBtn) return;
    var valid = true;
    if (name === "experience") valid = !!state.answers.experience;
    else if (name === "interests") valid = (state.answers.interests || []).length > 0;
    else if (name === "risk") valid = !!state.answers.risk;
    nextBtn.disabled = !valid;
  }

  /* ── Action dispatcher ── */
  overlay.addEventListener("click", function(e) {
    var btn = e.target.closest("[data-wiz-action]");
    if (!btn) return;
    var action = btn.dataset.wizAction;
    if (action === "next") nextStep();
    else if (action === "back") prevStep();
    else if (action === "skip") skipWizard();
  });

  /* ── Close / skip ── */
  function skipWizard() {
    var csrf = document.querySelector('meta[name="csrf-token"]');
    fetch("/api/settings/onboarding-complete", {
      method: "POST",
      headers: { "X-CSRFToken": csrf ? csrf.content : "" }
    }).catch(function() {}).finally(function() {
      overlay.remove();
    });
  }
  var closeBtn = document.getElementById("nd-wiz-close");
  if (closeBtn) closeBtn.addEventListener("click", function() {
    if (confirm("Skip setup? You can configure everything from Settings later.")) skipWizard();
  });

  /* ── Allocation step rendering ── */
  function recommendPreset() {
    var r = (state.answers.risk || "").toLowerCase();
    var interests = state.answers.interests || [];
    if (r === "custom") return "custom";
    if (interests.indexOf("metals") !== -1 && (r === "balanced" || r === "aggressive")) return "metals_heavy";
    if (PRESETS[r]) return r;
    return "balanced";
  }

  function renderAllocationStep() {
    var recommended = recommendPreset();
    if (recommended === "custom") {
      state.answers.allocation_preset = "skip";
      setAllocMode("skip");
      return;
    }
    if (!state.answers.allocation_preset || state.answers.allocation_preset === "skip") {
      state.answers.allocation_preset = recommended;
    }
    setAllocMode(state.allocMode);
    drawRecommendedDonut(state.answers.allocation_preset);
  }

  function setAllocMode(mode) {
    state.allocMode = (mode === "compare" ? "compare" : "single");
    var single = document.getElementById("nd-wiz-alloc-single");
    var compare = document.getElementById("nd-wiz-alloc-compare");
    var toggleBtn = document.getElementById("nd-wiz-alloc-toggle");
    var title = document.getElementById("nd-wiz-alloc-title");
    var sub = document.getElementById("nd-wiz-alloc-sub");
    var acceptBtn = document.getElementById("nd-wiz-alloc-accept");

    if (mode === "skip") {
      // User chose custom risk -> skip donut, just let them continue
      single.hidden = true;
      compare.hidden = true;
      toggleBtn.hidden = true;
      title.textContent = "You'll set your own targets";
      sub.textContent = "No problem. You can define your allocation in Settings once you're in.";
      acceptBtn.textContent = "Continue";
      return;
    }
    acceptBtn.textContent = "Accept";
    toggleBtn.hidden = false;

    if (state.allocMode === "compare") {
      single.hidden = true;
      compare.hidden = false;
      toggleBtn.textContent = "Back to recommended";
      title.textContent = "Pick a template";
      sub.textContent = "Tap one to preview. You can always tweak later.";
      renderPresetGrid();
    } else {
      single.hidden = false;
      compare.hidden = true;
      toggleBtn.textContent = "See other templates";
      title.textContent = "Your recommended mix";
      sub.textContent = "Based on your answers. You can tweak anytime.";
    }
  }

  var allocToggle = document.getElementById("nd-wiz-alloc-toggle");
  if (allocToggle) allocToggle.addEventListener("click", function() {
    setAllocMode(state.allocMode === "single" ? "compare" : "single");
    if (state.allocMode === "single") drawRecommendedDonut(state.answers.allocation_preset);
  });

  var allocSkip = document.getElementById("nd-wiz-alloc-skip");
  if (allocSkip) allocSkip.addEventListener("click", function() {
    state.answers.allocation_preset = "skip";
    setAllocMode("skip");
  });

  function renderPresetGrid() {
    var grid = document.getElementById("nd-wiz-preset-grid");
    if (!grid) return;
    grid.innerHTML = "";
    Object.keys(PRESETS).forEach(function(key) {
      var p = PRESETS[key];
      var card = document.createElement("div");
      card.className = "nd-wiz-preset" + (state.answers.allocation_preset === key ? " selected" : "");
      card.dataset.preset = key;

      var miniBars = Object.keys(p.alloc).map(function(b) {
        return '<span style="flex:' + p.alloc[b] + ';background:' + BUCKET_COLORS[b] + ';"></span>';
      }).join("");

      var rows = Object.keys(p.alloc).map(function(b) {
        return '<div><span>' + b + '</span><span>' + p.alloc[b] + '%</span></div>';
      }).join("");

      card.innerHTML =
        '<h4>' + p.label + '</h4>' +
        '<div class="nd-wiz-preset-desc">' + p.desc + '</div>' +
        '<div class="nd-wiz-preset-mini">' + miniBars + '</div>' +
        '<div class="nd-wiz-preset-rows">' + rows + '</div>';

      card.addEventListener("click", function() {
        state.answers.allocation_preset = key;
        grid.querySelectorAll(".nd-wiz-preset").forEach(function(el) { el.classList.remove("selected"); });
        card.classList.add("selected");
      });
      grid.appendChild(card);
    });
  }

  function drawRecommendedDonut(presetKey) {
    var preset = PRESETS[presetKey];
    if (!preset) return;
    var nameEl = document.getElementById("nd-wiz-donut-name");
    if (nameEl) nameEl.textContent = preset.label;

    var legend = document.getElementById("nd-wiz-alloc-legend");
    if (legend) {
      legend.innerHTML = Object.keys(preset.alloc).map(function(b) {
        return '<div class="row">' +
          '<span class="label"><span class="swatch" style="background:' + BUCKET_COLORS[b] + ';"></span>' + b + '</span>' +
          '<span>' + preset.alloc[b] + '%</span>' +
          '</div>';
      }).join("");
    }

    var canvas = document.getElementById("nd-wiz-donut");
    if (!canvas || typeof Chart === "undefined") return;
    var labels = Object.keys(preset.alloc);
    var data = labels.map(function(b) { return preset.alloc[b]; });
    var colors = labels.map(function(b) { return BUCKET_COLORS[b]; });

    if (state.donutChart) {
      state.donutChart.data.labels = labels;
      state.donutChart.data.datasets[0].data = data;
      state.donutChart.data.datasets[0].backgroundColor = colors;
      state.donutChart.update("none");
      return;
    }
    state.donutChart = new Chart(canvas.getContext("2d"), {
      type: "doughnut",
      data: { labels: labels, datasets: [{
        data: data, backgroundColor: colors,
        borderWidth: 2, borderColor: "rgba(9,9,11,0.6)", spacing: 1
      }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(c) { return " " + c.label + ": " + c.raw + "%"; }
            }
          }
        }
      }
    });
  }

  /* ── Contribution step inputs ── */
  var contribInput = document.getElementById("nd-wiz-contrib");
  var freqSelect = document.getElementById("nd-wiz-frequency");
  if (contribInput) contribInput.addEventListener("input", function() {
    var v = parseFloat(contribInput.value);
    state.answers.monthly_contribution = (isFinite(v) && v > 0) ? v : null;
  });
  if (freqSelect) freqSelect.addEventListener("change", function() {
    state.answers.frequency = freqSelect.value;
  });

  /* ── Summary + finish ── */
  function renderSummary() {
    var parts = [];
    var ans = state.answers;
    if (ans.experience) parts.push("<div><strong>Experience:</strong> " + cap(ans.experience) + "</div>");
    if ((ans.interests || []).length) {
      parts.push("<div><strong>Tracking:</strong> " + ans.interests.map(interestLabel).join(", ") + "</div>");
    }
    if (ans.allocation_preset && ans.allocation_preset !== "skip" && PRESETS[ans.allocation_preset]) {
      parts.push("<div><strong>Allocation:</strong> " + PRESETS[ans.allocation_preset].label + "</div>");
    } else if (ans.allocation_preset === "skip") {
      parts.push("<div><strong>Allocation:</strong> you'll set this later</div>");
    }
    if (ans.monthly_contribution && ans.monthly_contribution > 0) {
      parts.push("<div><strong>Monthly investing:</strong> $" + Math.round(ans.monthly_contribution).toLocaleString() + " " + ans.frequency + "</div>");
    }

    var interestPulses = {
      crypto: "ETH", metals: "Silver + Gold/Silver ratio",
      bonds: "2Y Yield", commodities: "Copper", real_estate: "REITs"
    };
    var added = (ans.interests || [])
      .map(function(i) { return interestPulses[i]; })
      .filter(Boolean);
    if (added.length) {
      parts.push("<div><strong>Pulse cards added:</strong> " + added.join(", ") + "</div>");
    }

    parts.push('<div class="nd-wiz-summary-hint">Everything here is editable from Settings &rarr; Dashboard.</div>');

    var el = document.getElementById("nd-wiz-summary");
    if (el) el.innerHTML = parts.join("");
  }

  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function interestLabel(i) {
    return ({
      equities: "Equities", crypto: "Crypto", metals: "Metals",
      real_estate: "Real Estate", bonds: "Bonds",
      commodities: "Commodities", alternatives: "Alternatives"
    })[i] || i;
  }

  var finishBtn = document.getElementById("nd-wiz-finish");
  if (finishBtn) finishBtn.addEventListener("click", function() {
    finishBtn.disabled = true;
    finishBtn.textContent = "Setting up...";
    var csrf = document.querySelector('meta[name="csrf-token"]');
    fetch("/api/onboarding", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf ? csrf.content : ""
      },
      body: JSON.stringify(state.answers)
    })
      .then(function(r) { return r.json().catch(function() { return {}; }); })
      .then(function(d) {
        if (d && d.ok) {
          window.location.reload();
        } else {
          finishBtn.disabled = false;
          finishBtn.textContent = "Go to my dashboard";
          alert((d && d.error) || "Couldn't save your setup. Try again.");
        }
      })
      .catch(function() {
        finishBtn.disabled = false;
        finishBtn.textContent = "Go to my dashboard";
        alert("Network error. Try again.");
      });
  });

  /* ── Init ── */
  showStep(0);
})();
