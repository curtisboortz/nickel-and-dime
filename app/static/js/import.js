/* Nickel&Dime — Brokerage Import Module */

var _importPreviewData = [];

function handleImportDrop(event) {
  var files = event.dataTransfer.files;
  if (files.length > 0) handleImportFile(files[0]);
}

function handleImportFile(file) {
  if (!file) return;

  var preview = document.getElementById("import-preview");
  var result = document.getElementById("import-result");
  var dropzone = document.getElementById("import-dropzone");

  result.style.display = "none";
  preview.style.display = "none";

  // Show loading state on dropzone
  dropzone.innerHTML =
    '<div class="loading-spinner" style="margin:0 auto;"></div>' +
    '<p style="margin-top:12px;font-size:0.85rem;color:var(--text-muted);">Analyzing ' +
    file.name + '&hellip;</p>';

  var formData = new FormData();
  formData.append("file", file);

  fetch("/api/import/preview", {
    method: "POST",
    body: formData,
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      // Restore dropzone
      dropzone.innerHTML =
        '<svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:8px;">' +
        '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>' +
        '</svg>' +
        '<p style="font-size:0.9rem;font-weight:600;margin-bottom:4px;">Drop your CSV here or click to browse</p>' +
        '<p style="font-size:0.78rem;color:var(--text-muted);">Positions export from any supported brokerage</p>' +
        '<input type="file" id="import-file-input" accept=".csv,.tsv,.txt" style="display:none" onchange="handleImportFile(this.files[0])">';
      dropzone.onclick = function () {
        document.getElementById("import-file-input").click();
      };

      if (data.error) {
        result.style.display = "block";
        result.style.background = "rgba(239,68,68,0.1)";
        result.style.border = "1px solid rgba(239,68,68,0.2)";
        result.innerHTML =
          '<p style="color:var(--danger);font-weight:600;">' + data.error + "</p>";
        return;
      }

      _importPreviewData = data.holdings || [];
      _renderImportPreview(data);
    })
    .catch(function (err) {
      dropzone.innerHTML =
        '<p style="color:var(--danger);">Upload failed. Please try again.</p>';
    });
}

function _renderImportPreview(data) {
  var preview = document.getElementById("import-preview");
  var brokerage = document.getElementById("import-brokerage");
  var count = document.getElementById("import-count");
  var tbody = document.getElementById("import-table-body");
  var warnings = document.getElementById("import-warnings");

  brokerage.textContent = data.brokerage;
  count.textContent = data.holdings.length + " holdings found";

  // Show warnings/errors
  var warningLines = [];
  if (data.errors && data.errors.length > 0) {
    warningLines = warningLines.concat(data.errors);
  }
  if (data.skipped && data.skipped.length > 5) {
    warningLines.push(data.skipped.length + " rows skipped (cash positions, totals, etc.)");
  }
  if (warningLines.length > 0) {
    warnings.style.display = "block";
    warnings.innerHTML = warningLines
      .map(function (w) { return "<div>" + w + "</div>"; })
      .join("");
  } else {
    warnings.style.display = "none";
  }

  // Render table rows
  var html = "";
  for (var i = 0; i < data.holdings.length; i++) {
    var h = data.holdings[i];
    var typeLabel = h.asset_type === "crypto" ? "Crypto" :
                    h.asset_type === "mutual_fund" ? "Fund" : "Stock/ETF";
    var typeColor = h.asset_type === "crypto" ? "var(--accent-primary)" :
                    h.asset_type === "mutual_fund" ? "#8b5cf6" : "var(--text-secondary)";
    var dupBadge = h.is_duplicate
      ? '<span style="font-size:0.7rem;padding:2px 6px;background:rgba(234,179,8,0.15);color:#eab308;border-radius:4px;">Existing</span>'
      : '<span style="font-size:0.7rem;padding:2px 6px;background:rgba(52,211,153,0.15);color:var(--accent-primary);border-radius:4px;">New</span>';

    html +=
      '<tr style="border-bottom:1px solid var(--border);">' +
      '<td style="padding:8px 12px;"><input type="checkbox" class="import-row-cb" data-idx="' + i + '" checked></td>' +
      '<td style="padding:8px 12px;font-weight:600;">' + h.ticker + "</td>" +
      '<td style="padding:8px 12px;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
        (h.description || "") + "</td>" +
      '<td style="padding:8px 12px;text-align:right;">' +
        (h.shares != null ? Number(h.shares).toLocaleString(undefined, {maximumFractionDigits: 4}) : "—") + "</td>" +
      '<td style="padding:8px 12px;">' + (h.account || "") + "</td>" +
      '<td style="padding:8px 12px;"><span style="font-size:0.75rem;color:' + typeColor + ';">' + typeLabel + "</span></td>" +
      '<td style="padding:8px 12px;text-align:center;">' + dupBadge + "</td>" +
      "</tr>";
  }
  tbody.innerHTML = html;

  preview.style.display = "block";
}

function toggleImportSelectAll(checked) {
  var boxes = document.querySelectorAll(".import-row-cb");
  for (var i = 0; i < boxes.length; i++) {
    boxes[i].checked = checked;
  }
}

function commitImport() {
  var boxes = document.querySelectorAll(".import-row-cb");
  var selected = [];
  for (var i = 0; i < boxes.length; i++) {
    if (boxes[i].checked) {
      var idx = parseInt(boxes[i].getAttribute("data-idx"), 10);
      if (_importPreviewData[idx]) selected.push(_importPreviewData[idx]);
    }
  }

  if (selected.length === 0) {
    alert("No holdings selected.");
    return;
  }

  var mode = document.getElementById("import-mode").value;
  var result = document.getElementById("import-result");

  fetch("/api/import/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holdings: selected, mode: mode }),
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        result.style.display = "block";
        result.style.background = "rgba(239,68,68,0.1)";
        result.style.border = "1px solid rgba(239,68,68,0.2)";
        result.innerHTML =
          '<p style="color:var(--danger);font-weight:600;">' + data.error + "</p>";
        return;
      }

      var parts = [];
      if (data.imported > 0) parts.push(data.imported + " imported");
      if (data.updated > 0) parts.push(data.updated + " updated");
      if (data.skipped > 0) parts.push(data.skipped + " skipped");

      result.style.display = "block";
      result.style.background = "rgba(52,211,153,0.1)";
      result.style.border = "1px solid rgba(52,211,153,0.2)";
      result.innerHTML =
        '<p style="color:var(--success);font-weight:600;">Import complete: ' +
        parts.join(", ") + "</p>" +
        '<p style="color:var(--text-muted);font-size:0.82rem;margin-top:4px;">Switch to the Holdings tab to view your imported positions.</p>';

      document.getElementById("import-preview").style.display = "none";
    })
    .catch(function () {
      result.style.display = "block";
      result.style.background = "rgba(239,68,68,0.1)";
      result.style.border = "1px solid rgba(239,68,68,0.2)";
      result.innerHTML =
        '<p style="color:var(--danger);font-weight:600;">Import failed. Please try again.</p>';
    });
}
