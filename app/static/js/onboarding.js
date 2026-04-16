/* Nickel&Dime - Onboarding wizard state machine.
 *
 * Drives the 10-step wizard rendered by _onboarding_wizard.html.
 * Collects answers, previews the recommended allocation with a live
 * Chart.js donut, fetches classic portfolio templates from the server,
 * and POSTs final answers to /api/onboarding.
 */
(function() {
  "use strict";

  var STEPS = [
    "welcome",
    "experience",
    "time_horizon",
    "interests",
    "philosophy",
    "risk",
    "allocation",
    "contribution",
    "populate",
    "done"
  ];

  // N&D-native presets (simple 5-bucket rollup)
  var ND_PRESETS = {
    conservative: {
      label: "Conservative",
      author: "Nickel&Dime",
      desc: "Capital preservation, low drawdowns.",
      alloc: { "Equities": 30, "Real Assets": 10, "Alternatives": 5, "Cash": 15, "Fixed Income": 40 }
    },
    balanced: {
      label: "Balanced",
      author: "Nickel&Dime",
      desc: "Steady mix of growth and safety.",
      alloc: { "Equities": 55, "Real Assets": 15, "Alternatives": 5, "Cash": 5, "Fixed Income": 20 }
    },
    aggressive: {
      label: "Aggressive",
      author: "Nickel&Dime",
      desc: "Growth-first, tolerates big swings.",
      alloc: { "Equities": 75, "Real Assets": 15, "Alternatives": 5, "Cash": 0, "Fixed Income": 5 }
    }
  };

  // Classic templates -- populated at runtime via /api/templates
  var CLASSIC_TEMPLATES = {};

  // Full palette, covers both N&D and classic buckets
  var BUCKET_COLORS = {
    "Equities":      "#f5c842",
    "International": "#fbbf24",
    "Real Assets":   "#34d399",
    "Real Estate":   "#10b981",
    "Gold":          "#eab308",
    "Silver":        "#d1d5db",
    "Alternatives":  "#a78bfa",
    "Crypto":        "#f97316",
    "Cash":          "#60a5fa",
    "Fixed Income":  "#94a3b8",
    "Commodities":   "#fb923c",
    "Art":           "#ec4899"
  };
  function colorFor(bucket) {
    return BUCKET_COLORS[bucket] || "#9ca3af";
  }

  var state = {
    stepIdx: 0,
    answers: {
      experience: "",
      time_horizon: "",
      interests: [],
      philosophy: "",
      risk: "",
      allocation_preset: "",
      custom_allocation: null,
      monthly_contribution: null,
      frequency: "monthly"
    },
    allocMode: "single",
    donutChart: null,
    templatesLoaded: false
  };

  var overlay = document.getElementById("nd-wiz-overlay");
  if (!overlay) return;
  var progressBar = document.getElementById("nd-wiz-progress-bar");
  var stepIndicator = document.getElementById("nd-wiz-step-indicator");

  /* ── Preset helpers ── */
  function getPreset(key) {
    if (!key) return null;
    if (ND_PRESETS[key]) return ND_PRESETS[key];
    if (key.indexOf("classic:") === 0) {
      var id = key.slice("classic:".length);
      return CLASSIC_TEMPLATES[id] || null;
    }
    return null;
  }

  /* ── Recommendation logic (mirrors Python side) ── */
  function recommendPreset() {
    var r = (state.answers.risk || "").toLowerCase();
    var philo = (state.answers.philosophy || "").toLowerCase();
    var horizon = (state.answers.time_horizon || "").toLowerCase();
    var interests = state.answers.interests || [];

    if (r === "custom") return "custom";

    if (philo === "income" || horizon === "retired") return "classic:income-focus";
    if (philo === "defensive" && r === "conservative") return "classic:permanent";
    if (philo === "defensive") return "classic:all-weather";
    if (philo === "active") return "classic:macro-investor";
    if (philo === "passive" && r === "aggressive" && horizon === "long") return "classic:boglehead-3";
    if (philo === "passive" && r === "balanced") return "classic:60-40";
    if (interests.indexOf("metals") !== -1 && (r === "balanced" || r === "aggressive")) {
      return "classic:golden-butterfly";
    }
    if (ND_PRESETS[r]) return r;
    return "balanced";
  }

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

    updateStepValidity();
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
    else if (name === "time_horizon") valid = !!state.answers.time_horizon;
    else if (name === "interests") valid = (state.answers.interests || []).length > 0;
    else if (name === "philosophy") valid = !!state.answers.philosophy;
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

  /* ── Templates fetch ── */
  function ensureTemplatesLoaded() {
    if (state.templatesLoaded) return Promise.resolve();
    return fetch("/api/templates", { credentials: "same-origin" })
      .then(function(r) { return r.ok ? r.json() : { templates: [] }; })
      .then(function(data) {
        var list = (data && data.templates) || [];
        // list view omits allocations; fetch each one to get the full payload
        return Promise.all(list.map(function(t) {
          return fetch("/api/templates/" + encodeURIComponent(t.id), { credentials: "same-origin" })
            .then(function(r) { return r.ok ? r.json() : null; })
            .catch(function() { return null; });
        }));
      })
      .then(function(detailed) {
        (detailed || []).forEach(function(entry) {
          if (!entry) return;
          var tpl = entry.template || entry;
          if (!tpl || !tpl.id) return;
          CLASSIC_TEMPLATES[tpl.id] = {
            id: tpl.id,
            label: tpl.name,
            author: tpl.author,
            desc: tpl.description,
            alloc: tpl.allocations || {}
          };
        });
        state.templatesLoaded = true;
      })
      .catch(function() {
        state.templatesLoaded = true;
      });
  }

  /* ── Allocation step rendering ── */
  function renderAllocationStep() {
    ensureTemplatesLoaded().then(function() {
      var recommended = recommendPreset();
      if (recommended === "custom") {
        state.answers.allocation_preset = "skip";
        setAllocMode("skip");
        return;
      }
      // If recommendation is a classic template that failed to load, fall back.
      if (recommended.indexOf("classic:") === 0 && !getPreset(recommended)) {
        recommended = mapRiskToNDPreset();
      }
      if (!state.answers.allocation_preset || state.answers.allocation_preset === "skip") {
        state.answers.allocation_preset = recommended;
      }
      setAllocMode(state.allocMode);
      drawRecommendedDonut(state.answers.allocation_preset);
    });
  }

  function mapRiskToNDPreset() {
    var r = (state.answers.risk || "").toLowerCase();
    return ND_PRESETS[r] ? r : "balanced";
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
    var ndGrid = document.getElementById("nd-wiz-preset-grid-nd");
    var classicGrid = document.getElementById("nd-wiz-preset-grid-classic");
    if (ndGrid) {
      ndGrid.innerHTML = "";
      Object.keys(ND_PRESETS).forEach(function(key) {
        ndGrid.appendChild(buildPresetCard(key, ND_PRESETS[key]));
      });
    }
    if (classicGrid) {
      classicGrid.innerHTML = "";
      Object.keys(CLASSIC_TEMPLATES).forEach(function(id) {
        var key = "classic:" + id;
        classicGrid.appendChild(buildPresetCard(key, CLASSIC_TEMPLATES[id]));
      });
      if (!Object.keys(CLASSIC_TEMPLATES).length) {
        classicGrid.innerHTML = '<div style="grid-column:1/-1;color:var(--text-muted);font-size:0.8rem;">Classic templates couldn\'t load.</div>';
      }
    }
  }

  function buildPresetCard(key, p) {
    var card = document.createElement("div");
    card.className = "nd-wiz-preset" + (state.answers.allocation_preset === key ? " selected" : "");
    card.dataset.preset = key;

    var total = Object.keys(p.alloc).reduce(function(s, b) { return s + (p.alloc[b] || 0); }, 0) || 1;
    var miniBars = Object.keys(p.alloc).map(function(b) {
      return '<span style="flex:' + (p.alloc[b] / total) + ';background:' + colorFor(b) + ';"></span>';
    }).join("");

    var rows = Object.keys(p.alloc).map(function(b) {
      return '<div><span>' + escapeHtml(b) + '</span><span>' + p.alloc[b] + '%</span></div>';
    }).join("");

    var author = p.author ? '<div class="nd-wiz-preset-author">' + escapeHtml(p.author) + '</div>' : "";

    card.innerHTML =
      '<h4>' + escapeHtml(p.label) + '</h4>' +
      author +
      (p.desc ? '<div class="nd-wiz-preset-desc">' + escapeHtml(p.desc) + '</div>' : '<div class="nd-wiz-preset-desc"></div>') +
      '<div class="nd-wiz-preset-mini">' + miniBars + '</div>' +
      '<div class="nd-wiz-preset-rows">' + rows + '</div>';

    card.addEventListener("click", function() {
      state.answers.allocation_preset = key;
      document.querySelectorAll("#nd-wiz-alloc-compare .nd-wiz-preset").forEach(function(el) {
        el.classList.remove("selected");
      });
      card.classList.add("selected");
    });
    return card;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function drawRecommendedDonut(presetKey) {
    var preset = getPreset(presetKey);
    if (!preset) return;
    var nameEl = document.getElementById("nd-wiz-donut-name");
    if (nameEl) nameEl.textContent = preset.label;
    var authorEl = document.getElementById("nd-wiz-alloc-author");
    if (authorEl) authorEl.textContent = preset.author ? "By " + preset.author : "";

    var legend = document.getElementById("nd-wiz-alloc-legend");
    if (legend) {
      legend.innerHTML = Object.keys(preset.alloc).map(function(b) {
        return '<div class="row">' +
          '<span class="label"><span class="swatch" style="background:' + colorFor(b) + ';"></span>' + escapeHtml(b) + '</span>' +
          '<span>' + preset.alloc[b] + '%</span>' +
          '</div>';
      }).join("");
    }

    var canvas = document.getElementById("nd-wiz-donut");
    if (!canvas || typeof Chart === "undefined") return;
    var labels = Object.keys(preset.alloc);
    var data = labels.map(function(b) { return preset.alloc[b]; });
    var colors = labels.map(function(b) { return colorFor(b); });

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

  /* ── Populate step: persist + navigate to relevant tab ── */
  overlay.addEventListener("click", function(e) {
    var btn = e.target.closest("[data-populate-go]");
    if (!btn) return;
    var dest = btn.dataset.populateGo;
    btn.disabled = true;
    var orig = btn.textContent;
    btn.textContent = "Saving...";
    submitAnswers().finally(function() {
      var target = "/dashboard";
      if (dest === "import") target = "/dashboard/import";
      else if (dest === "balances") target = "/dashboard/balances";
      else if (dest === "plaid") target = "/dashboard?open=plaid";
      else if (dest === "upgrade") target = "/billing/pricing";
      window.location.href = target;
      // safety fallback
      setTimeout(function() { btn.disabled = false; btn.textContent = orig; }, 2000);
    });
  });

  /* ── Summary + finish ── */
  function renderSummary() {
    var parts = [];
    var ans = state.answers;
    if (ans.experience) parts.push("<div><strong>Experience:</strong> " + cap(ans.experience) + "</div>");
    if (ans.time_horizon) parts.push("<div><strong>Time horizon:</strong> " + horizonLabel(ans.time_horizon) + "</div>");
    if ((ans.interests || []).length) {
      parts.push("<div><strong>Tracking:</strong> " + ans.interests.map(interestLabel).join(", ") + "</div>");
    }
    if (ans.philosophy) parts.push("<div><strong>Style:</strong> " + philoLabel(ans.philosophy) + "</div>");

    var preset = getPreset(ans.allocation_preset);
    if (preset && ans.allocation_preset !== "skip") {
      parts.push("<div><strong>Allocation:</strong> " + escapeHtml(preset.label) + "</div>");
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
  function horizonLabel(h) {
    return ({
      short: "Under 5 years", medium: "5 to 15 years",
      long: "15+ years", retired: "Retired / drawing"
    })[h] || h;
  }
  function philoLabel(p) {
    return ({
      passive: "Simple & passive", active: "Active & macro-aware",
      defensive: "Defensive & all-weather", income: "Income-focused",
      unsure: "Exploring"
    })[p] || p;
  }

  function submitAnswers() {
    var csrf = document.querySelector('meta[name="csrf-token"]');
    return fetch("/api/onboarding", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf ? csrf.content : ""
      },
      body: JSON.stringify(state.answers)
    }).then(function(r) { return r.json().catch(function() { return {}; }); });
  }

  var finishBtn = document.getElementById("nd-wiz-finish");
  if (finishBtn) finishBtn.addEventListener("click", function() {
    finishBtn.disabled = true;
    finishBtn.textContent = "Setting up...";
    submitAnswers()
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
