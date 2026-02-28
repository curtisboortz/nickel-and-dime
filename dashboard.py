"""Dashboard rendering: data preparation + full HTML template for Nickel&Dime."""

import json
from datetime import datetime
from urllib.parse import quote


def append_history_log(base, action: str, details: str = "") -> None:
    from finance_manager import append_history_log as _log
    _log(base, action, details)


def render_economics_fragment_html() -> str:
    """Return the inner HTML for the Economics tab (lazily loaded on first visit)."""
    return """  <div class="card">
    <div class="card-title">US Economics &amp; Fiscal Data</div>
    <p class="hint" style="margin-bottom:12px;">Data from FRED (Federal Reserve Economic Data). Set <code>FRED_API_KEY</code> in .env or api_keys.fred_api_key in config for live data.</p>
    <div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-bottom:16px;">
      <button type="button" class="secondary" id="fred-refresh-btn">Refresh FRED Data</button>
      <span class="label" style="margin:0;">Horizon</span>
      <select id="fred-horizon" style="padding:6px 10px;font-size:0.85rem;">
        <option value="1y">1 year (fast)</option>
        <option value="5y">5 years</option>
        <option value="max">Max (~50y)</option>
      </select>
    </div>
    <div id="fred-load-status" class="hint" style="margin-bottom:12px;"></div>

    <!-- National Debt & Fiscal Policy -->
    <div id="fred-section-debt" class="card" style="margin-top:16px;padding:16px;">
      <div class="card-title" style="margin-bottom:12px;">National Debt &amp; Fiscal Policy</div>
      <div id="fred-debt-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(320px, 1fr));gap:16px;">
        <div><div class="card-title" style="font-size:0.9rem;">Federal Debt (Total Public)</div><div style="position:relative;height:200px;"><canvas id="fred-chart-debt"></canvas></div></div>
        <div><div class="card-title" style="font-size:0.9rem;">Debt to GDP Ratio</div><div style="position:relative;height:200px;"><canvas id="fred-chart-debt-gdp"></canvas></div></div>
        <div><div class="card-title" style="font-size:0.9rem;">Federal Surplus or Deficit (Annual)</div><div style="position:relative;height:200px;"><canvas id="fred-chart-deficit"></canvas></div></div>
        <div><div class="card-title" style="font-size:0.9rem;">Interest Payments</div><div style="position:relative;height:200px;"><canvas id="fred-chart-interest"></canvas></div></div>
        <div><div class="card-title" style="font-size:0.9rem;">Revenue vs Expenditures</div><div style="position:relative;height:200px;"><canvas id="fred-chart-revenue-spending"></canvas></div></div>
      </div>
      <div class="card-title" style="font-size:0.9rem;margin-top:20px;margin-bottom:8px;">Fiscal Ratios (% of GDP)</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:16px;">
        <div><div class="card-title" style="font-size:0.85rem;">Deficit as % of GDP</div><div style="position:relative;height:200px;"><canvas id="fred-chart-deficit-pct"></canvas></div></div>
        <div><div class="card-title" style="font-size:0.85rem;">Government Spending as % of GDP</div><div style="position:relative;height:200px;"><canvas id="fred-chart-spending-pct"></canvas></div></div>
        <div><div class="card-title" style="font-size:0.85rem;">Interest Expense as % of GDP</div><div style="position:relative;height:200px;"><canvas id="fred-chart-interest-pct"></canvas></div></div>
      </div>
      <p class="hint" style="margin-top:12px;">Debt and deficit ratios show fiscal sustainability. Interest % of GDP reflects debt-service burden &mdash; rising fast = concern.</p>
    </div>

    <!-- Inflation -->
    <div id="fred-section-inflation" class="card" style="margin-top:16px;padding:16px;">
      <div class="card-title" style="margin-bottom:12px;">Inflation (CPI, Core CPI, PCE)</div>
      <div id="fred-inflation-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="position:relative;height:220px;"><canvas id="fred-chart-inflation"></canvas></div>
      <p class="hint" style="margin-top:8px;">CPI-U = headline inflation. Core CPI excludes food &amp; energy (less volatile). PCE is the Fed&#39;s preferred measure.</p>
    </div>

    <!-- Monetary Policy -->
    <div id="fred-section-monetary" class="card" style="margin-top:16px;padding:16px;">
      <div class="card-title" style="margin-bottom:12px;">Monetary Policy (Fed Funds Rate, M2, Yield Curve)</div>
      <div id="fred-monetary-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:16px;">
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-fedfunds"></canvas></div></div>
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-m2"></canvas></div></div>
      </div>
      <div class="card-title" style="font-size:0.9rem;margin-top:16px;">Treasury Yield Curve (current vs 1Y ago)</div>
      <div style="position:relative;height:220px;margin-top:8px;"><canvas id="fred-chart-yield-curve"></canvas></div>
      <p class="hint" style="margin-top:8px;">Inverted curve (short rates &gt; long) often precedes recessions. Fed Funds drives short-term rates; M2 shows liquidity.</p>
    </div>

    <!-- Credit Stress -->
    <div id="fred-section-credit" class="card" style="margin-top:16px;padding:16px;">
      <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;">
        <div class="card-title" style="margin:0;">Credit Stress (High Yield Spreads)</div>
        <select class="fred-period-select" data-section="credit" style="padding:4px 8px;font-size:0.8rem;">
          <option value="1y">1 year</option>
          <option value="5y">5 years</option>
          <option value="max">Max (~15y)</option>
        </select>
      </div>
      <div id="fred-credit-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="position:relative;height:220px;"><canvas id="fred-chart-hy-spread"></canvas></div>
      <p class="hint" style="margin-top:8px;">Spread between high-yield corporate bonds and Treasuries. Widening = financial stress. Above 5% = recession risk.</p>
    </div>

    <!-- Real Yields & Inflation Expectations -->
    <div id="fred-section-realyields" class="card" style="margin-top:16px;padding:16px;">
      <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;">
        <div class="card-title" style="margin:0;">Real Yields &amp; Inflation Expectations</div>
        <select class="fred-period-select" data-section="realyields" style="padding:4px 8px;font-size:0.8rem;">
          <option value="1y">1 year</option>
          <option value="5y">5 years</option>
          <option value="max">Max (~15y)</option>
        </select>
      </div>
      <div id="fred-realyield-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:16px;">
        <div><div class="card-title" style="font-size:0.9rem;">10Y Real Yield (TIPS)</div><div style="position:relative;height:200px;"><canvas id="fred-chart-real-yield"></canvas></div></div>
        <div><div class="card-title" style="font-size:0.9rem;">Breakeven Inflation (5Y &amp; 10Y)</div><div style="position:relative;height:200px;"><canvas id="fred-chart-breakeven"></canvas></div></div>
      </div>
      <p class="hint" style="margin-top:8px;">Negative real yields are bullish for gold/crypto. Breakevens show what the bond market expects for inflation.</p>
    </div>

    <!-- Fed Balance Sheet & Liquidity -->
    <div id="fred-section-fedbs" class="card" style="margin-top:16px;padding:16px;">
      <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;">
        <div class="card-title" style="margin:0;">Fed Balance Sheet</div>
        <select class="fred-period-select" data-section="fedbs" style="padding:4px 8px;font-size:0.8rem;">
          <option value="1y">1 year</option>
          <option value="5y">5 years</option>
          <option value="max">Max (~15y)</option>
        </select>
      </div>
      <div id="fred-fedbs-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="position:relative;height:220px;"><canvas id="fred-chart-fedbs"></canvas></div>
      <p class="hint" style="margin-top:8px;">Total Fed assets. Expanding = QE (liquidity injection, bullish). Contracting = QT (liquidity drain, headwind).</p>
    </div>

    <!-- Sahm Rule Recession Indicator -->
    <div id="fred-section-sahm" class="card" style="margin-top:16px;padding:16px;">
      <div class="card-title" style="margin-bottom:12px;">Sahm Rule Recession Indicator</div>
      <div id="fred-sahm-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="position:relative;height:220px;"><canvas id="fred-chart-sahm"></canvas></div>
      <p class="hint" style="margin-top:8px;">Crosses 0.50 = recession signal. Based on 3-month moving average of unemployment rate vs 12-month low.</p>
    </div>

    <!-- Labor Market -->
    <div id="fred-section-labor" class="card" style="margin-top:16px;padding:16px;">
      <div class="card-title" style="margin-bottom:12px;">Labor Market (Unemployment, Jobless Claims)</div>
      <div id="fred-labor-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:16px;">
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-unemployment"></canvas></div></div>
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-claims"></canvas></div></div>
      </div>
      <p class="hint" style="margin-top:8px;">Unemployment rate (U-3) and weekly jobless claims. Rising claims can lead unemployment by weeks &mdash; early warning of slowdown.</p>
    </div>

    <!-- Growth & Sentiment -->
    <div id="fred-section-growth" class="card" style="margin-top:16px;padding:16px;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
        <div class="card-title" style="margin:0;">Growth &amp; Sentiment (Real GDP Growth, Consumer Sentiment)</div>
        <select class="fred-period-select" data-section="growth" style="padding:4px 8px;font-size:0.8rem;">
          <option value="1y">1 year</option>
          <option value="5y">5 years</option>
          <option value="max">Max</option>
        </select>
      </div>
      <div id="fred-growth-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:16px;">
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-gdp-growth"></canvas></div></div>
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-sentiment"></canvas></div></div>
      </div>
      <p class="hint" style="margin-top:8px;">Quarterly GDP growth (real, annualized) and U. of Michigan consumer sentiment. Sentiment can lead or confirm economic turns.</p>
    </div>

    <!-- Housing -->
    <div id="fred-section-housing" class="card" style="margin-top:16px;padding:16px;">
      <div class="card-title" style="margin-bottom:12px;">Housing (Case-Shiller Home Price Index, 30Y Mortgage Rate)</div>
      <div id="fred-housing-stats" class="pulse-bar" style="flex-wrap:wrap;gap:12px;margin-bottom:16px;"></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:16px;">
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-housing"></canvas></div></div>
        <div><div style="position:relative;height:200px;"><canvas id="fred-chart-mortgage"></canvas></div></div>
      </div>
      <p class="hint" style="margin-top:8px;">Case-Shiller tracks home prices nationally. Mortgage rates drive affordability &mdash; spiking rates often cool housing and economy.</p>
    </div>
  </div>"""


def render_dashboard(data: dict, saved: str = "", active_tab: str = "summary", demo_mode: bool = False) -> str:
    """Build single-page dashboard with Summary, Balances, Budget, Holdings."""
    holdings = data.get("holdings", [])
    buckets = data.get("buckets", {})
    total = data.get("total", 0)
    metals_prices = data.get("metals_prices", {})
    config = data.get("config", {})
    targets = config.get("targets", {}).get("tactical", {})
    gold_price = metals_prices.get("GOLD") or 0
    silver_price = metals_prices.get("SILVER") or 0
    treasury_yields = data.get("treasury_yields", {})
    gold_silver_ratio = data.get("gold_silver_ratio")
    price_history = data.get("price_history", [])
    tnx_10y = treasury_yields.get("tnx_10y")
    tnx_2y = treasury_yields.get("tnx_2y")
    tnx_10y_s = f"{tnx_10y:.2f}%" if tnx_10y is not None else "—"
    tnx_2y_s = f"{tnx_2y:.2f}%" if tnx_2y is not None else "—"
    gs_ratio_s = f"{gold_silver_ratio:.2f}" if gold_silver_ratio is not None else "—"

    from finance_manager import get_next_buys
    next_buys = get_next_buys(config, 0)

    alloc_rows = ""
    for bucket, value in buckets.items():
        pct = 100 * value / total if total > 0 else 0
        tgt = targets.get(bucket, {}).get("target", 0)
        drift = pct - tgt
        dc = "over" if drift > 5 else ("under" if drift < -5 else "ok")
        alloc_rows += f'<tr><td>{bucket}</td><td>${value:,.0f}</td><td>{pct:.1f}%</td><td>{tgt}%</td><td class="{dc}">{drift:+.1f}%</td></tr>'

    # Balances section (blended_accounts)
    blended = config.get("blended_accounts", [])
    balance_rows = "".join(
        f'<tr><td>{b.get("name", "")}</td><td style="text-align:right"><input type="text" name="bal_{b.get("name", "").replace(" ", "_")}" value="{b.get("value", 0):,.2f}" class="num"></td></tr>'
        for b in blended
    )

    # Budget section
    budget = config.get("budget", {})
    monthly_income = budget.get("monthly_income", 0)
    categories = budget.get("categories", [])
    total_expenses = sum(float(c.get("limit", 0) or 0) for c in categories)
    remaining = float(monthly_income or 0) - total_expenses
    budget_rows = "".join(
        f'<tr><td>{c.get("name", "")}</td><td><input type="text" name="cat_{i}" value="{c.get("limit", 0)}" class="num"></td></tr>'
        for i, c in enumerate(categories)
    )
    budget_totals_row = (
        '<tr style="font-weight:600;border-top:1px solid #30363d">'
        f'<td>Total expenses</td><td style="text-align:right">${total_expenses:,.2f}</td></tr>'
        f'<tr style="font-weight:700;border-top:2px solid #30363d">'
        f'<td>Remaining (income − expenses)</td><td style="text-align:right;color:{"#3fb950" if remaining >= 0 else "#f85149"}">${remaining:,.2f}</td></tr>'
    )

    # Debt section
    debts = config.get("debts", [])
    total_debt = sum(float(d.get("balance", 0) or 0) for d in debts)
    total_debt_payments = sum(float(d.get("monthly_payment", 0) or 0) for d in debts)
    net_worth = total - total_debt

    debt_rows_html = ""
    for di, d in enumerate(debts):
        d_name = d.get("name", "")
        d_balance = float(d.get("balance", 0) or 0)
        d_payment = float(d.get("monthly_payment", 0) or 0)
        d_months = int(d_balance / d_payment) if d_payment > 0 else 0
        d_months_label = f"{d_months} mo" if d_months > 0 else "—"
        debt_rows_html += (
            f'<tr>'
            f'<td><input type="text" name="debt_name_{di}" value="{d_name}" style="width:100%;border:none;background:transparent;color:var(--text-primary);font-size:0.85rem;"></td>'
            f'<td><input type="text" name="debt_bal_{di}" value="{d_balance:,.2f}" class="num"></td>'
            f'<td><input type="text" name="debt_pmt_{di}" value="{d_payment:,.2f}" class="num"></td>'
            f'<td class="mono hint" style="text-align:center;">{d_months_label}</td>'
            f'<td><button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;color:var(--danger);" onclick="removeDebt({di})">x</button></td>'
            f'</tr>'
        )

    # Holdings section: config holdings with live Price and Total from computed data
    cfg_holdings = config.get("holdings", [])
    stock_prices = data.get("stock_prices", {}) or {}
    crypto_prices = data.get("crypto_prices", {}) or {}
    # Computed holdings match config order (first len(cfg_holdings) entries)
    holding_rows = ""
    holdings_total = 0.0
    for i, h in enumerate(cfg_holdings):
        ticker = h.get("ticker", "")
        qty = h.get("qty")
        vo = h.get("value_override")
        qty_s = f'{qty}' if qty is not None else ''
        vo_s = f'{vo}' if vo is not None else ''
        val = holdings[i]["value"] if i < len(holdings) else 0
        holdings_total += val
        price = stock_prices.get(ticker) or crypto_prices.get(ticker)
        if price is None and qty and val:
            price = val / float(qty)
        price_s = f"${price:,.2f}" if price is not None else "—"
        val_s = f"${val:,.2f}" if val else "—"
        holding_rows += f'<tr><td><input type="text" name="h_account" value="{h.get("account", "")}"></td><td><input type="text" name="h_ticker" value="{ticker}"></td><td><input type="text" name="h_asset_class" value="{h.get("asset_class", "")}"></td><td><input type="text" name="h_qty" value="{qty_s}" class="num"></td><td style="text-align:right;color:#8b949e">{price_s}</td><td style="text-align:right;color:#e6edf3">{val_s}</td><td><input type="text" name="h_value_override" value="{vo_s}" class="num"></td><td><input type="text" name="h_notes" value="{h.get("notes", "")}"></td></tr>'
    # One blank row for add
    holding_rows += '<tr><td><input type="text" name="h_account" placeholder="Account"></td><td><input type="text" name="h_ticker" placeholder="Ticker"></td><td><input type="text" name="h_asset_class" placeholder="Asset class"></td><td><input type="text" name="h_qty" class="num" placeholder="Qty"></td><td></td><td></td><td><input type="text" name="h_value_override" class="num" placeholder="Value override"></td><td><input type="text" name="h_notes" placeholder="Notes"></td></tr>'
    totals_row = f'<tr style="font-weight:600;border-top:2px solid #30363d"><td colspan="4">Holdings total (should match CSV)</td><td></td><td style="text-align:right;color:#58a6ff">${holdings_total:,.2f}</td><td colspan="2"></td></tr>'

    # Physical metals table rows
    phys_metals = config.get("physical_metals", [])
    metals_rows_html = ""
    metals_gold_oz = 0.0
    metals_silver_oz = 0.0
    metals_total_cost = 0.0
    metals_total_value = 0.0
    for mi, m in enumerate(phys_metals):
        m_metal = m.get("metal", "Gold")
        m_form = m.get("form", "")
        m_qty = float(m.get("qty_oz", 0))
        m_cost = float(m.get("cost_per_oz", 0))
        m_date = m.get("date", "")
        m_note = m.get("note", "")
        m_spot = gold_price if m_metal.lower() == "gold" else silver_price
        m_cur_val = m_qty * m_spot
        m_cost_basis = m_qty * m_cost if m_cost > 0 else 0
        m_gl = m_cur_val - m_cost_basis if m_cost > 0 else 0
        m_gl_cls = "color:var(--success)" if m_gl >= 0 else "color:var(--danger)"
        m_gl_s = f"${m_gl:+,.2f}" if m_cost > 0 else "—"
        if m_metal.lower() == "gold":
            metals_gold_oz += m_qty
        else:
            metals_silver_oz += m_qty
        metals_total_cost += m_cost_basis
        metals_total_value += m_cur_val
        cost_td = f'<td class="mono" style="text-align:right">${m_cost:,.2f}</td>' if m_cost > 0 else '<td class="hint" style="text-align:right">—</td>'
        metals_rows_html += (
            f'<tr>'
            f'<td>{m_metal}</td>'
            f'<td>{m_form}</td>'
            f'<td class="mono" style="text-align:right">{m_qty:.4g}</td>'
            f'{cost_td}'
            f'<td class="mono metal-spot-cell" style="text-align:right" data-metal-spot="{m_metal.lower()}" data-metal-qty="{m_qty}" data-metal-cost="{m_cost}">${m_spot:,.2f}</td>'
            f'<td class="mono" style="text-align:right">${m_cur_val:,.2f}</td>'
            f'<td class="mono" style="text-align:right;{m_gl_cls}">{m_gl_s}</td>'
            f'<td class="hint">{m_date}</td>'
            f'<td><button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;color:var(--danger);" onclick="deleteMetalRow({mi})">x</button></td>'
            f'</tr>'
        )
    metals_total_gl = metals_total_value - metals_total_cost
    metals_gl_cls = "color:var(--success)" if metals_total_gl >= 0 else "color:var(--danger)"
    metals_totals_row = (
        f'<tr style="font-weight:600;border-top:2px solid #30363d">'
        f'<td colspan="2">Totals</td>'
        f'<td class="mono" style="text-align:right">Au {metals_gold_oz:.4g} / Ag {metals_silver_oz:.4g}</td>'
        f'<td class="mono" style="text-align:right">${metals_total_cost:,.2f}</td>'
        f'<td></td>'
        f'<td class="mono" style="text-align:right;color:#58a6ff">${metals_total_value:,.2f}</td>'
        f'<td class="mono" style="text-align:right;{metals_gl_cls}">${metals_total_gl:+,.2f}</td>'
        f'<td colspan="2"></td>'
        f'</tr>'
    )

    # Price history rows (newest first)
    history_rows = ""
    for e in reversed(price_history[-100:]):  # show last 100
        d = e.get("date", "")
        t = e.get("total")
        g = e.get("gold")
        s = e.get("silver")
        r = e.get("gold_silver_ratio")
        y10 = e.get("tnx_10y")
        y2 = e.get("tnx_2y")
        t_s = f"${t:,.0f}" if t is not None else "—"
        g_s = f"${g:,.0f}" if g is not None else "—"
        s_s = f"${s:,.1f}" if s is not None else "—"
        r_s = f"{r:.2f}" if r is not None else "—"
        y10_s = f"{y10:.2f}%" if y10 is not None else "—"
        y2_s = f"{y2:.2f}%" if y2 is not None else "—"
        history_rows += f'<tr><td>{d}</td><td>{t_s}</td><td>{g_s}</td><td>{s_s}</td><td>{r_s}</td><td>{y10_s}</td><td>{y2_s}</td></tr>'
    if not history_rows:
        history_rows = '<tr><td colspan="7" style="color:#8b949e">No history yet. Click Refresh prices to log a snapshot.</td></tr>'

    # JSON for chart (escape for script tag)
    history_for_chart = list(price_history)  # all daily OHLC entries for chart
    history_json = json.dumps(history_for_chart).replace("</", "<\\/")

    # Monthly investment tracker - calculate targets from percentages
    monthly_inv = config.get("monthly_investments", {})
    current_month = monthly_inv.get("month", datetime.now().strftime("%Y-%m"))
    budget_month = budget.get("month", datetime.now().strftime("%Y-%m"))
    allocation_pcts = monthly_inv.get("allocation_percentages", {})
    contributions = monthly_inv.get("contributions", {})
    
    # Get savings budget to calculate investment targets
    savings_budget = next((c.get("limit", 0) for c in budget.get("categories", []) 
                          if "Savings" in c.get("name", "") or "Investment" in c.get("name", "")), 0)
    
    # Investment categories with display names
    inv_categories = [
        ("gold_etf", "Gold ETF"),
        ("gold_phys_save", "Gold Savings"),
        ("silver_etf", "Silver ETF"),
        ("silver_phys_save", "Silver Savings"),
        ("crypto", "Crypto"),
        ("equities", "Equities"),
        ("real_assets", "Real Assets"),
        ("cash", "Cash Reserve"),
    ]
    
    # Calculate monthly investment targets from percentages
    inv_targets = {k: int(savings_budget * allocation_pcts.get(k, 0) / 100) for k, _ in inv_categories}
    
    total_target = sum(inv_targets.get(k, 0) for k, _ in inv_categories)
    total_contributed = sum(contributions.get(k, 0) for k, _ in inv_categories)
    total_remaining = total_target - total_contributed
    progress_pct = int(total_contributed / total_target * 100) if total_target > 0 else 0
    
    # Build investment rows HTML
    investment_rows_html = ""
    for key, name in inv_categories:
        alloc_pct = allocation_pcts.get(key, 0)
        target = inv_targets.get(key, 0)
        contributed = contributions.get(key, 0)
        remaining = target - contributed
        fill_pct = int(contributed / target * 100) if target > 0 else 0
        
        if remaining > 0:
            status_class = "shortage"
            status_text = f"-${remaining:,}"
        elif remaining < 0:
            status_class = "surplus"
            status_text = f"+${abs(remaining):,}"
        else:
            status_class = "complete"
            status_text = "Complete"
        
        investment_rows_html += f'''<tr>
          <td><strong>{name}</strong> <span style="color:var(--text-muted);font-size:0.8rem;">({alloc_pct}%)</span></td>
          <td style="text-align:right">${target:,}</td>
          <td style="text-align:right"><input type="number" class="contrib-input" data-key="{key}" data-target="{target}" value="{contributed}" min="0" step="1"></td>
          <td style="text-align:right" class="{status_class}" id="status-{key}">{status_text}</td>
          <td style="width:140px"><div class="mini-progress"><div class="mini-fill {'low' if fill_pct < 40 else 'mid' if fill_pct < 90 else 'done'}" id="progress-{key}" style="width:{min(fill_pct, 100)}%"></div></div></td>
        </tr>'''

    # Data for donut chart (allocation)
    buckets_json = json.dumps(buckets).replace("</", "<\\/")
    targets_json = json.dumps({b: targets.get(b, {}).get("target", 0) for b in buckets}).replace("</", "<\\/")

    # Daily change calculation - compare to 24 hours ago (yesterday's date), not last entry
    yesterday_str = (datetime.now() - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    prev_total = None
    # Find the most recent snapshot from yesterday (or earlier if none from yesterday)
    for entry in reversed(price_history):
        entry_date = entry.get("date", "")[:10]
        if entry_date <= yesterday_str:
            prev_total = entry.get("total")
            break
    if prev_total is None and len(price_history) >= 2:
        prev_total = price_history[0]["total"]  # fallback to oldest entry
    if prev_total is None:
        prev_total = total
    daily_change = total - prev_total if prev_total else 0
    daily_change_pct = (daily_change / prev_total * 100) if prev_total else 0

    # Crypto prices for market pulse
    btc_price = crypto_prices.get("BTC", 0)
    eth_price = crypto_prices.get("ETH", 0)
    spy_price = stock_prices.get("SPY", 0)
    dxy_price = stock_prices.get("DX-Y.NYB", 0)
    vix_price = stock_prices.get("^VIX", 0)
    oil_price = stock_prices.get("CL=F", 0)
    copper_price = stock_prices.get("HG=F", 0)

    # ── Market Pulse Cards (built-in + custom) ──
    default_pulse_cards = [
        {"id": "gold", "label": "Gold", "value": gold_price, "fmt": "dollar0", "color": "gold", "spark": "GC=F"},
        {"id": "silver", "label": "Silver", "value": silver_price, "fmt": "dollar2", "color": "silver", "spark": "SI=F"},
        {"id": "au_ag", "label": "Au/Ag Ratio", "value": gs_ratio_s, "fmt": "raw"},
        {"id": "dxy", "label": "DXY", "value": dxy_price, "fmt": "dollar2_nodollar", "spark": "DX-Y.NYB"},
        {"id": "vix", "label": "VIX", "value": vix_price, "fmt": "dollar2_nodollar", "spark": "^VIX"},
        {"id": "oil", "label": "Oil", "value": oil_price, "fmt": "dollar2", "spark": "CL=F"},
        {"id": "copper", "label": "Copper", "value": copper_price, "fmt": "dollar2", "spark": "HG=F"},
        {"id": "tnx_10y", "label": "10Y Yield", "value": tnx_10y_s, "fmt": "raw"},
        {"id": "tnx_2y", "label": "2Y Yield", "value": tnx_2y_s, "fmt": "raw"},
        {"id": "btc", "label": "BTC", "value": btc_price, "fmt": "dollar0", "spark": "BTC-USD"},
        {"id": "spy", "label": "SPY", "value": spy_price, "fmt": "dollar2", "spark": "SPY"},
    ]
    # Custom pulse cards from config
    custom_pulse = config.get("custom_pulse_cards", [])
    for cp in custom_pulse:
        ticker = cp.get("ticker", "").upper()
        label = cp.get("label", ticker)
        ptype = cp.get("type", "stock")
        src = crypto_prices if ptype == "crypto" else stock_prices
        price = src.get(ticker) or 0
        default_pulse_cards.append({
            "id": f"custom-{ticker}",
            "label": label,
            "value": price,
            "fmt": "dollar2",
            "spark": ticker,
            "custom": True,
            "ticker": ticker,
            "ptype": ptype,
        })

    # Filter out hidden cards
    hidden_cards = config.get("hidden_pulse_cards", [])
    visible_cards = [c for c in default_pulse_cards if c["id"] not in hidden_cards]
    hidden_count = len(default_pulse_cards) - len(visible_cards)

    # Pulse card order from config
    pulse_order = config.get("pulse_card_order", [])
    if pulse_order:
        ordered = []
        for pid in pulse_order:
            for card in visible_cards:
                if card["id"] == pid:
                    ordered.append(card)
                    break
        # Add any cards not in the saved order (new defaults)
        for card in visible_cards:
            if card not in ordered:
                ordered.append(card)
        pulse_cards = ordered
    else:
        pulse_cards = visible_cards

    # Build pulse HTML
    pulse_html = ""
    for pc in pulse_cards:
        pid = pc["id"]
        label = pc["label"]
        fmt = pc["fmt"]
        val = pc["value"]
        color_class = f' {pc["color"]}' if pc.get("color") else ""
        spark_id = pc.get("spark", "")

        if not isinstance(val, (int, float)) or val == 0:
            val_s = "—"
        elif fmt == "dollar0":
            val_s = f"${val:,.0f}"
        elif fmt == "dollar1":
            val_s = f"${val:,.1f}"
        elif fmt == "dollar2":
            val_s = f"${val:,.2f}"
        elif fmt == "dollar2_nodollar":
            val_s = f"{val:,.2f}"
        else:
            val_s = str(val)

        remove_btn = f'<button type="button" class="pulse-remove" onclick="removePulseCard(\'{pid}\')" title="Remove">&times;</button>'
        spark_canvas = f'<canvas class="pulse-spark" id="spark-{spark_id.replace("=", "-")}"></canvas>' if spark_id else ""
        data_type = f' data-pulse-type="{pc.get("ptype", "stock")}"' if pc.get("custom") else ""

        pulse_html += f'''<div class="pulse-item" draggable="true" data-pulse-id="{pid}"{data_type}>
      {remove_btn}
      <span class="pulse-label">{label}</span>
      <span class="pulse-price{color_class}" data-pulse-price="{pid}">{val_s}</span>
      {spark_canvas}
    </div>'''

    pulse_cards_json = json.dumps([{"id": c["id"], "label": c.get("label"), "spark": c.get("spark", "")} for c in pulse_cards]).replace("</", "<\\/")
    custom_pulse_json = json.dumps(custom_pulse).replace("</", "<\\/")

    # Auto-refresh settings (pre-compute for template)
    auto_refresh_cfg = config.get("auto_refresh", {})
    auto_enabled = auto_refresh_cfg.get("enabled", True)
    auto_interval = auto_refresh_cfg.get("interval_minutes", 15)
    auto_dot_class = "on" if auto_enabled else "off"
    auto_checked = "checked" if auto_enabled else ""
    auto_sel_5 = "selected" if auto_interval == 5 else ""
    auto_sel_10 = "selected" if auto_interval == 10 else ""
    auto_sel_15 = "selected" if auto_interval == 15 else ""
    auto_sel_30 = "selected" if auto_interval == 30 else ""
    auto_sel_60 = "selected" if auto_interval == 60 else ""
    auto_sel_120 = "selected" if auto_interval == 120 else ""
    auto_sel_240 = "selected" if auto_interval == 240 else ""

    # Widget order (pre-compute for template)
    widget_order = config.get("widget_order", {})
    widget_order_json = json.dumps(widget_order).replace("</", "<\\/")

    # Phase 2: Rebalancing recommendations
    # Only compare controllable buckets against targets. Exclude uncontrollable managed/retirement accounts.
    rebal_rows_html = ""
    if total > 0:
        for bucket, value in buckets.items():
            tgt_data = targets.get(bucket, {})
            tgt = tgt_data.get("target", 0)
            if tgt == 0:
                continue  # skip buckets with no target
            pct = 100 * value / total
            drift = pct - tgt
            tgt_min = tgt_data.get("min", tgt)
            tgt_max = tgt_data.get("max", tgt)
            # Only flag if outside the min/max range (not just > 2% drift)
            if pct < tgt_min or pct > tgt_max:
                target_value = total * tgt / 100
                diff_val = target_value - value
                action = "Buy" if diff_val > 0 else "Trim"
                drift_class = "shortage" if diff_val > 0 else "surplus"
                rebal_rows_html += f'<tr><td>{bucket}</td><td class="mono">{pct:.1f}%</td><td class="mono">{tgt}% ({tgt_min}-{tgt_max})</td><td class="mono {drift_class}">{drift:+.1f}%</td><td class="mono">${abs(diff_val):,.0f}</td><td class="{drift_class}">{action}</td></tr>'

    # Phase 2: Transaction data for budget
    transactions = config.get("transactions", [])
    transactions_json = json.dumps(transactions).replace("</", "<\\/")

    # Recurring transactions
    recurring = config.get("recurring_transactions", [])
    recurring_json = json.dumps(recurring).replace("</", "<\\/")
    recurring_rows_html = ""
    for i, rt in enumerate(recurring):
        recurring_rows_html += f'<tr><td>{rt.get("name","")}</td><td class="mono">${rt.get("amount",0):,.2f}</td><td>{rt.get("category","Other")}</td><td>{rt.get("frequency","monthly")}</td><td><button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;" onclick="deleteRecurring({i})">x</button></td></tr>'

    # Dividend/fee tracking
    dividends = config.get("dividends", [])
    dividends_json = json.dumps(dividends[-100:]).replace("</", "<\\/")
    div_rows_html = ""
    for d in reversed(dividends[-30:]):
        dtype = d.get("type", "dividend")
        color = "var(--success)" if dtype == "dividend" else "var(--danger)"
        sign = "+" if dtype == "dividend" else "-"
        div_rows_html += f'<tr><td class="mono">{d.get("date","")}</td><td>{d.get("ticker","")}</td><td style="color:{color}" class="mono">{sign}${d.get("amount",0):,.2f}</td><td>{dtype.title()}</td><td class="hint">{d.get("note","")}</td></tr>'

    # Phase 2: Monthly spending history (last 6 months)
    spending_history = config.get("spending_history", {})
    spending_json = json.dumps(spending_history).replace("</", "<\\/")

    # Phase 3: Price alerts
    price_alerts = config.get("price_alerts", [])
    alerts_json = json.dumps(price_alerts).replace("</", "<\\/")

    # Phase 3: Projected growth data
    monthly_contribution = total_target  # from investment tracker
    projection_data = {"current": total, "monthly_contrib": monthly_contribution}
    projection_json = json.dumps(projection_data).replace("</", "<\\/")

    # Phase 3: Tax-loss harvesting - find unrealized losses
    tlh_rows_html = ""
    for i, h in enumerate(cfg_holdings):
        ticker = h.get("ticker", "")
        qty = h.get("qty") or 0
        vo = h.get("value_override") or 0
        live_price = stock_prices.get(ticker) or crypto_prices.get(ticker)
        if live_price and qty and vo:
            cost_basis_per = vo / qty if qty else 0
            unrealized = (live_price - cost_basis_per) * qty
            if unrealized < -50:  # Only show losses > $50
                tlh_rows_html += f'<tr><td>{ticker}</td><td class="mono">{qty:.3f}</td><td class="mono">${cost_basis_per:,.2f}</td><td class="mono">${live_price:,.2f}</td><td class="mono danger">${unrealized:,.0f}</td></tr>'

    # Pre-build conditional HTML blocks (can't nest f-strings)
    # Rebalancing card removed (redundant with Allocation vs Target table)

    tlh_card_html = f"""<div class="card">
    <div class="card-title">Tax-Loss Harvesting Opportunities</div>
    <p class="hint" style="margin-bottom:10px;">Holdings with unrealized losses &gt; $50 (based on import value vs live price)</p>
    <table>
      <thead><tr><th>Ticker</th><th>Qty</th><th>Cost Basis</th><th>Current</th><th>Unrealized P&amp;L</th></tr></thead>
      <tbody>{tlh_rows_html}</tbody>
    </table>
  </div>""" if tlh_rows_html else ""

    txn_cat_options = "".join(f'<option value="{c.get("name","")}">{c.get("name","")}</option>' for c in categories)
    txn_date_val = datetime.now().strftime("%Y-%m-%d")

    # Pre-computed JS data
    holdings_tickers_json = json.dumps([h.get("ticker","") for h in cfg_holdings]).replace("</","<\\/")
    budget_cats_json = json.dumps([c.get("name","") for c in categories]).replace("</","<\\/")
    budget_limits_json = json.dumps({c.get("name",""): float(c.get("limit",0) or 0) for c in categories}).replace("</","<\\/")
    num_holdings = len(cfg_holdings)

    # ── AI Insights: generate natural language summary ──
    # ── Goal Tracking data ──
    goals = config.get("financial_goals", [])
    goals_json = json.dumps(goals).replace("</", "<\\/")
    goals_html = ""
    for gi, g in enumerate(goals):
        g_name = g.get("name", "Goal")
        g_target = g.get("target", 0)
        g_current = g.get("current", 0)
        g_pct = int(g_current / g_target * 100) if g_target > 0 else 0
        g_color = "done" if g_pct >= 100 else ("mid" if g_pct >= 40 else "low")
        g_remaining = max(g_target - g_current, 0)
        goals_html += f'''<div class="goal-card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <strong>{g_name}</strong>
            <button type="button" class="secondary" style="padding:2px 8px;font-size:0.65rem;" onclick="deleteGoal({gi})">x</button>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:4px;">
            <span class="mono">${g_current:,.0f}</span>
            <span class="hint">of ${g_target:,.0f}</span>
          </div>
          <div class="mini-progress"><div class="mini-fill {g_color}" style="width:{min(g_pct, 100)}%"></div></div>
          <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:0.75rem;">
            <span class="hint">{g_pct}%</span>
            <span class="hint">${g_remaining:,.0f} to go</span>
          </div>
        </div>'''

    # ── Performance Attribution data ──
    perf_data = []
    if len(price_history) >= 2:
        first_snap = price_history[0]
        last_snap = price_history[-1]
        first_total = first_snap.get("total", 0)
        if first_total > 0:
            overall_return = ((total - first_total) / first_total) * 100
        else:
            overall_return = 0
    else:
        overall_return = 0
    perf_json = json.dumps({"buckets": {b: round(v, 2) for b, v in buckets.items()}, "total": round(total, 2), "overall_return": round(overall_return, 2)}).replace("</", "<\\/")

    saved_msg = f'<div class="toast" id="toast-msg">{saved}. Changes logged to Excel History.</div>' if saved else ""

    change_sign = "+" if daily_change >= 0 else ""
    change_color = "pos" if daily_change >= 0 else "neg"

    demo_banner = ""
    if demo_mode:
        demo_banner = ('<div style="position:fixed;top:0;left:0;right:0;z-index:10000;background:linear-gradient(90deg,#d4a017,#f0c040);'
                       'color:#09090b;text-align:center;padding:8px 16px;font-size:0.85rem;font-weight:600;letter-spacing:0.02em;">'
                       'Live Demo &mdash; sample data shown. Write operations disabled. '
                       '<a href="https://github.com/curtisboortz/nickel-and-dime" target="_blank" '
                       'style="color:#09090b;text-decoration:underline;margin-left:8px;">View on GitHub</a>'
                       '</div><style>.sidebar{top:36px !important;height:calc(100vh - 36px) !important;}'
                       '.main-content{padding-top:36px !important;}</style>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nickel&amp;Dime</title>
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#09090b">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.1/dist/chartjs-adapter-luxon.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-financial@0.2.1/dist/chartjs-chart-financial.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg-primary: #09090b;
  --bg-secondary: #111114;
  --bg-card: #161619;
  --bg-card-hover: #1c1c20;
  --bg-input: #1a1a1f;
  --border-subtle: rgba(255,255,255,0.06);
  --border-accent: rgba(212,160,23,0.3);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent-primary: #d4a017;
  --accent-secondary: #f5c842;
  --accent-glow: rgba(212,160,23,0.15);
  --success: #34d399;
  --success-glow: rgba(52,211,153,0.15);
  --danger: #f87171;
  --warning: #fbbf24;
  --gold: #fbbf24;
  --silver: #cbd5e1;
  --sidebar-w: 72px;
  --radius: 12px;
  --mono: 'JetBrains Mono', monospace;
}}
*{{ box-sizing:border-box; margin:0; padding:0; }}
html {{ scroll-behavior:smooth; }}
body {{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
  background:var(--bg-primary);
  color:var(--text-primary);
  min-height:100vh;
  line-height:1.6;
  -webkit-font-smoothing:antialiased;
  display:flex;
}}
/* ── Sidebar ── */
.sidebar {{
  position:fixed; left:0; top:0; bottom:0;
  width:var(--sidebar-w);
  background:var(--bg-secondary);
  border-right:1px solid var(--border-subtle);
  display:flex; flex-direction:column; align-items:center;
  padding:20px 0; z-index:100;
  transition:width 0.2s ease;
}}
.sidebar-logo {{
  width:40px; height:40px;
  border-radius:10px;
  margin-bottom:32px;
  flex-shrink:0;
  overflow:hidden;
}}
.sidebar-logo img {{
  width:100%; height:100%; object-fit:cover;
  border-radius:10px;
}}
.sidebar-nav {{
  display:flex; flex-direction:column; gap:4px;
  flex:1; width:100%; padding:0 12px;
}}
.nav-item {{
  display:flex; align-items:center; justify-content:center;
  width:48px; height:48px; margin:0 auto;
  border-radius:12px; border:none; background:none;
  color:var(--text-muted); cursor:pointer;
  transition:all 0.2s ease; text-decoration:none;
  position:relative;
}}
.nav-item svg {{ width:22px; height:22px; stroke:currentColor; fill:none; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }}
.nav-item:hover {{ color:var(--text-secondary); background:rgba(255,255,255,0.04); }}
.nav-item.active {{
  color:var(--accent-primary);
  background:var(--accent-glow);
}}
.nav-item.active::before {{
  content:''; position:absolute; left:-12px; top:50%; transform:translateY(-50%);
  width:3px; height:24px; border-radius:0 3px 3px 0;
  background:var(--accent-primary);
}}
.nav-item .tooltip {{
  position:absolute; left:calc(100% + 12px); top:50%; transform:translateY(-50%);
  background:#1e1e24; color:var(--text-primary); font-size:0.8rem; font-weight:500;
  padding:6px 12px; border-radius:8px; white-space:nowrap;
  pointer-events:none; opacity:0; transition:opacity 0.15s ease;
  border:1px solid var(--border-subtle);
  box-shadow:0 4px 12px rgba(0,0,0,0.4);
}}
.nav-item:hover .tooltip {{ opacity:1; }}
.sidebar-bottom {{
  padding:0 12px; width:100%;
  display:flex; flex-direction:column; align-items:center; gap:8px;
}}
.refresh-btn {{
  width:48px; height:48px; border-radius:12px;
  background:linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
  border:none; cursor:pointer; color:#09090b;
  display:flex; align-items:center; justify-content:center;
  transition:all 0.2s ease;
  box-shadow:0 2px 8px var(--accent-glow);
}}
.refresh-btn svg {{ width:20px; height:20px; stroke:currentColor; fill:none; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }}
.refresh-btn:hover {{ transform:translateY(-1px); box-shadow:0 4px 16px var(--accent-glow); }}
/* ── Auto-refresh Indicator ── */
.auto-refresh-indicator {{
  display:flex; align-items:center; gap:5px; cursor:pointer;
  padding:4px 8px; border-radius:6px;
  transition:background 0.15s;
  position:relative;
}}
.auto-refresh-indicator:hover {{ background:rgba(255,255,255,0.05); }}
.auto-dot {{
  width:7px; height:7px; border-radius:50%;
  transition:background 0.3s;
}}
.auto-dot.on {{ background:#34d399; box-shadow:0 0 6px rgba(52,211,153,0.5); }}
.auto-dot.off {{ background:#64748b; }}
.auto-label {{ font-size:0.6rem; color:var(--text-muted); font-family:var(--mono); }}
.auto-popover {{
  position:absolute; left:calc(100% + 16px); bottom:-8px;
  background:var(--bg-card); border:1px solid var(--border-accent);
  border-radius:var(--radius); padding:14px; width:180px;
  box-shadow:0 8px 24px rgba(0,0,0,0.4); z-index:200;
  margin-bottom:8px;
}}
.auto-popover-title {{
  font-size:0.75rem; font-weight:600; color:var(--text-primary);
  margin-bottom:10px; text-transform:uppercase; letter-spacing:0.05em;
}}
.auto-toggle-row {{
  display:flex; justify-content:space-between; align-items:center;
  margin-bottom:8px; font-size:0.75rem; color:var(--text-secondary);
}}
.auto-toggle-row select {{
  background:var(--bg-input); border:1px solid var(--border-subtle);
  color:var(--text-primary); border-radius:4px; padding:3px 6px;
  font-size:0.7rem; font-family:var(--mono);
}}
.auto-toggle-row input[type="checkbox"] {{
  accent-color:var(--accent-primary); width:16px; height:16px;
}}
/* ── Main Content ── */
.main-content {{
  margin-left:var(--sidebar-w);
  flex:1; padding:28px 36px;
  max-width:1400px;
  min-height:100vh;
}}
.tab {{ display:none; animation:fadeIn 0.25s ease; }}
.tab.active {{ display:block; }}
@keyframes fadeIn {{ from{{ opacity:0; transform:translateY(6px); }} to{{ opacity:1; transform:translateY(0); }} }}
/* ── Toast ── */
.toast {{
  position:fixed; top:20px; right:20px; z-index:200;
  background:var(--success-glow); color:var(--success);
  padding:14px 20px; border-radius:var(--radius);
  border:1px solid rgba(52,211,153,0.25);
  font-weight:500; font-size:0.9rem;
  animation:slideIn 0.3s ease, fadeOut 0.5s ease 3s forwards;
  box-shadow:0 4px 20px rgba(0,0,0,0.3);
}}
@keyframes slideIn {{ from{{ transform:translateX(100px); opacity:0; }} to{{ transform:translateX(0); opacity:1; }} }}
@keyframes fadeOut {{ to{{ opacity:0; transform:translateY(-10px); }} }}
/* ── Hero / Net Worth ── */
.hero-row {{
  display:flex; gap:24px; align-items:stretch; margin-bottom:24px; flex-wrap:wrap;
}}
.hero-row .hero {{ flex:0 0 auto; min-width:220px; margin-bottom:0; }}
.hero-chart-card {{ display:flex; flex-direction:column; }}
.hero-chart-card .card-title {{ margin-bottom:8px; }}
.hero {{
  margin-bottom:24px;
}}
.hero-label {{
  font-size:0.7rem; font-weight:600; text-transform:uppercase;
  letter-spacing:0.12em; color:var(--text-muted); margin-bottom:6px;
}}
.hero-value {{
  font-family:var(--mono);
  font-size:2.8rem; font-weight:700;
  background:linear-gradient(135deg, var(--accent-secondary), var(--accent-primary));
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text; letter-spacing:-0.02em;
  line-height:1.1;
}}
.hero-change {{
  display:inline-flex; align-items:center; gap:6px;
  margin-top:8px; padding:5px 12px;
  border-radius:20px; font-size:0.85rem; font-weight:600;
  font-family:var(--mono);
}}
.hero-change.pos {{ background:rgba(52,211,153,0.1); color:var(--success); }}
.hero-change.neg {{ background:rgba(248,113,113,0.1); color:var(--danger); }}
.hero-meta {{
  margin-top:8px; font-size:0.8rem; color:var(--text-muted);
}}
/* ── Market Pulse ── */
.pulse-bar {{
  display:flex; gap:12px; margin-bottom:28px;
  overflow-x:auto; padding-bottom:4px;
  -webkit-overflow-scrolling:touch;
}}
.pulse-item {{
  flex:0 0 auto; min-width:130px; max-width:160px; height:110px; position:relative;
  background:var(--bg-card); border:1px solid var(--border-subtle);
  border-radius:var(--radius); padding:14px 16px;
  display:flex; flex-direction:column; gap:6px; justify-content:flex-start;
  transition:border-color 0.2s ease, opacity 0.2s ease, transform 0.15s ease;
  cursor:grab; box-sizing:border-box;
}}
.pulse-item:active {{ cursor:grabbing; }}
.pulse-item:hover {{ border-color:var(--border-accent); }}
.pulse-item.dragging {{ opacity:0.4; transform:scale(0.95); }}
.pulse-item.drag-over {{ border-color:var(--accent-primary); box-shadow:0 0 0 1px var(--accent-primary); }}
.pulse-item.pulse-add {{
  cursor:pointer; align-items:center; justify-content:center;
  border-style:dashed; min-width:100px; opacity:0.5;
  transition:opacity 0.2s ease;
}}
.pulse-item.pulse-add:hover {{ opacity:1; border-color:var(--accent-primary); }}
.pulse-remove {{
  position:absolute; top:4px; right:6px;
  background:none; border:none; color:var(--text-muted); cursor:pointer;
  font-size:0.9rem; line-height:1; opacity:0; transition:opacity 0.15s;
  padding:2px 4px;
}}
.pulse-item:hover .pulse-remove {{ opacity:0.6; }}
.pulse-remove:hover {{ opacity:1; color:var(--danger); }}
.pulse-label {{ font-size:0.7rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-muted); font-weight:600; }}
.pulse-price {{ font-family:var(--mono); font-size:1.05rem; font-weight:600; color:var(--text-primary); }}
.pulse-price.gold {{ color:var(--gold); }}
.pulse-price.silver {{ color:var(--silver); }}
.pulse-spark {{ height:40px; margin-top:auto; }}
/* ── Chart Toggle ── */
.chart-toggle {{
  background:var(--bg-input); border:1px solid var(--border-subtle); color:var(--text-muted);
  width:28px; height:24px; border-radius:4px; cursor:pointer; font-size:0.85rem;
  display:flex; align-items:center; justify-content:center; padding:0;
  transition:all 0.15s ease;
}}
.chart-toggle:hover {{ border-color:var(--border-accent); color:var(--text-secondary); }}
.chart-toggle.active {{ background:var(--accent-primary); border-color:var(--accent-primary); color:var(--bg-primary); }}
/* ── Card ── */
.card {{
  background:var(--bg-card);
  border:1px solid var(--border-subtle);
  border-radius:var(--radius); padding:20px;
  margin-bottom:16px;
  transition:border-color 0.2s ease;
}}
.card:hover {{ border-color:var(--border-accent); }}
.card-title {{
  font-size:0.7rem; font-weight:600; text-transform:uppercase;
  letter-spacing:0.1em; color:var(--text-muted); margin-bottom:14px;
}}
.card-header {{
  display:flex; justify-content:space-between; align-items:center;
  margin-bottom:14px;
}}
.card-header .card-title {{ margin-bottom:0; }}
.card-subtitle {{
  font-size:0.8rem; color:var(--text-muted); margin-top:3px;
}}
/* ── Summary Grid ── */
.summary-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:16px;
}}
/* ── Tables ── */
table {{
  width:100%; border-collapse:separate; border-spacing:0;
}}
th {{
  color:var(--text-muted); font-size:0.65rem; font-weight:600;
  text-transform:uppercase; letter-spacing:0.08em;
  padding:10px 14px; text-align:left;
  border-bottom:1px solid var(--border-subtle);
  position:sticky; top:0; background:var(--bg-card); z-index:1;
}}
td {{
  padding:12px 14px;
  border-bottom:1px solid rgba(255,255,255,0.03);
  font-size:0.88rem;
}}
tbody tr {{ transition:background 0.15s ease; }}
tbody tr:nth-child(even) {{ background:rgba(255,255,255,0.015); }}
tbody tr:hover {{ background:rgba(212,160,23,0.04); }}
tr:last-child td {{ border-bottom:none; }}
.mono {{ font-family:var(--mono); font-size:0.85rem; }}
.over {{ color:var(--danger); font-weight:500; }}
.under {{ color:var(--success); font-weight:500; }}
.ok {{ color:var(--text-muted); }}
/* ── Inputs ── */
input, select {{
  padding:9px 12px;
  background:var(--bg-input);
  border:1px solid var(--border-subtle);
  color:var(--text-primary);
  border-radius:8px; width:100%;
  font-family:inherit; font-size:0.88rem;
  transition:all 0.2s ease;
}}
select {{ cursor:pointer; }}
select option {{ background:var(--bg-input); color:var(--text-primary); }}
input:focus, select:focus {{
  outline:none;
  border-color:var(--accent-primary);
  box-shadow:0 0 0 3px var(--accent-glow);
}}
input.num {{
  width:110px; text-align:right;
  font-family:var(--mono); font-variant-numeric:tabular-nums;
}}
/* ── Buttons ── */
button {{
  padding:10px 20px;
  background:var(--accent-primary);
  color:#09090b; border:none;
  border-radius:8px; cursor:pointer;
  font-family:inherit; font-size:0.88rem; font-weight:600;
  transition:all 0.2s ease;
  box-shadow:0 2px 8px var(--accent-glow);
}}
button:hover {{ transform:translateY(-1px); box-shadow:0 4px 16px var(--accent-glow); }}
button:active {{ transform:translateY(0); }}
button.secondary {{
  background:transparent; color:var(--text-secondary);
  border:1px solid var(--border-subtle); box-shadow:none;
}}
button.secondary:hover {{ background:rgba(255,255,255,0.05); color:var(--text-primary); transform:none; }}
button.success {{
  background:linear-gradient(135deg,#059669,var(--success));
  color:#fff; box-shadow:0 2px 8px var(--success-glow);
}}
/* ── Investment Tracker ── */
.invest-table {{ width:100%; border-collapse:separate; border-spacing:0; }}
.invest-table th {{ font-size:0.65rem; padding:8px 12px; }}
.invest-table td {{ padding:10px 12px; vertical-align:middle; }}
.invest-table tbody tr {{ transition:background 0.15s; }}
.invest-table tbody tr:hover {{ background:rgba(212,160,23,0.04); }}
.contrib-input {{
  width:90px !important; text-align:right;
  font-family:var(--mono); font-variant-numeric:tabular-nums;
  padding:7px 10px !important; font-size:0.85rem;
}}
.shortage {{ color:var(--warning); font-weight:500; font-family:var(--mono); font-size:0.85rem; }}
.surplus {{ color:var(--success); font-weight:500; font-family:var(--mono); font-size:0.85rem; }}
.complete {{ color:var(--success); font-weight:500; }}
.mini-progress {{
  height:10px; background:rgba(255,255,255,0.04);
  border-radius:5px; overflow:hidden; min-width:100px;
}}
.mini-fill {{
  height:100%;
  background:linear-gradient(90deg,var(--accent-primary),var(--accent-secondary));
  border-radius:5px; transition:width 0.3s ease;
}}
.mini-fill.low {{ background:linear-gradient(90deg,#ef4444,#f87171); }}
.mini-fill.mid {{ background:linear-gradient(90deg,#f59e0b,#fbbf24); }}
.mini-fill.done {{ background:linear-gradient(90deg,#22c55e,#34d399); }}
.progress-bar {{
  height:8px; background:rgba(255,255,255,0.04);
  border-radius:4px; overflow:hidden; margin-top:12px;
}}
.progress-fill {{
  height:100%;
  background:linear-gradient(90deg,var(--accent-primary),var(--accent-secondary));
  border-radius:4px; transition:width 0.3s ease;
}}
/* ── AI Insights ── */
/* ── Goals ── */
.goals-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:14px; }}
.goal-card {{
  padding:14px; background:var(--bg-input); border-radius:var(--radius);
  border:1px solid var(--border-subtle);
}}
/* ── Currency Selector ── */
.currency-select {{
  width:auto; padding:4px 8px; font-size:0.72rem; border-radius:6px;
  background:var(--bg-input); color:var(--text-muted); border:1px solid var(--border-subtle);
  cursor:pointer;
}}
/* ── Investment Chat ── */
.invest-chat {{ padding:14px; background:var(--bg-input); border-radius:var(--radius); }}
.chat-msg {{ padding:4px 0; line-height:1.5; }}
.chat-msg.ok {{ color:var(--success); }}
.chat-msg.err {{ color:var(--danger); }}
.chat-msg .chat-label {{ color:var(--text-muted); font-size:0.75rem; margin-right:6px; }}
/* ── Drag-to-Reorder Widgets ── */
.widget-card {{ cursor:grab; transition:transform 0.15s, box-shadow 0.15s, opacity 0.15s; }}
.widget-card:active {{ cursor:grabbing; }}
.widget-card.dragging {{ opacity:0.4; transform:scale(0.97); }}
.widget-card.drag-over {{ box-shadow:0 0 0 2px var(--accent-primary); border-radius:var(--radius); }}
.drag-handle {{ cursor:grab; color:var(--text-muted); margin-right:8px; font-size:0.9rem; opacity:0.4; transition:opacity 0.15s; }}
.drag-handle:hover {{ opacity:1; }}
/* ── Misc ── */
.label {{ font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-muted); margin-bottom:5px; display:block; }}
.page-title {{ font-size:1.1rem; font-weight:600; color:var(--text-primary); margin-bottom:4px; }}
.income-bar {{
  background:var(--bg-input); padding:16px; border-radius:var(--radius);
  margin-bottom:20px; display:flex; align-items:center; gap:16px; flex-wrap:wrap;
}}
.chart-controls {{
  display:flex; gap:10px; flex-wrap:wrap; align-items:end; margin-bottom:16px;
}}
.chart-controls .ctrl-group {{ display:flex; flex-direction:column; gap:4px; }}
.chart-controls select {{ width:auto; min-width:120px; }}
.hint {{ font-size:0.78rem; color:var(--text-muted); }}
/* ── Spending Breakdown expand/collapse ── */
.spend-row {{ cursor:pointer; transition:background 0.15s; border-bottom:1px solid var(--border-subtle); }}
.spend-row:hover {{ background:var(--bg-card-hover); }}
.spend-header {{ display:flex; align-items:center; padding:10px 12px; gap:12px; }}
.spend-chevron {{ font-size:0.65rem; color:var(--text-muted); transition:transform 0.2s; width:14px; text-align:center; flex-shrink:0; }}
.spend-row.open .spend-chevron {{ transform:rotate(90deg); }}
.spend-cat {{ flex:1; font-weight:500; font-size:0.88rem; color:var(--text-primary); }}
.spend-amounts {{ display:flex; align-items:center; gap:10px; font-family:var(--mono); font-size:0.82rem; }}
.spend-spent {{ color:var(--text-secondary); }}
.spend-budget {{ color:var(--text-muted); font-size:0.75rem; }}
.spend-bar-wrap {{ flex:0 0 120px; height:6px; background:var(--bg-input); border-radius:3px; overflow:hidden; }}
.spend-bar {{ height:100%; border-radius:3px; transition:width 0.3s ease; }}
.spend-bar.under {{ background:var(--success); }}
.spend-bar.near {{ background:var(--warning); }}
.spend-bar.over {{ background:var(--danger); }}
.spend-details {{ display:none; padding:0 12px 10px 40px; }}
.spend-row.open .spend-details {{ display:block; }}
.spend-details table {{ width:100%; font-size:0.78rem; }}
.spend-details th {{ color:var(--text-muted); font-weight:500; text-align:left; padding:4px 8px; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.05em; }}
.spend-details td {{ padding:4px 8px; color:var(--text-secondary); }}
.spend-details td.mono {{ font-family:var(--mono); }}
.spend-total {{ font-weight:600; padding:12px; display:flex; justify-content:space-between; border-top:2px solid var(--border-subtle); font-size:0.92rem; }}
.spend-empty {{ text-align:center; padding:32px; color:var(--text-muted); font-size:0.85rem; }}
.tip-box {{
  font-size:0.8rem; color:var(--text-muted); margin-top:16px;
  padding:12px; background:var(--bg-input); border-radius:8px;
}}
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:rgba(255,255,255,0.08); border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background:rgba(255,255,255,0.15); }}
/* ── Light Theme ── */
html.light {{
  --bg-primary:#f5f5f7; --bg-secondary:#eeeef0; --bg-card:#ffffff; --bg-card-hover:#fafafa;
  --bg-input:#f0f0f2; --border-subtle:rgba(0,0,0,0.08); --border-accent:rgba(212,160,23,0.3);
  --text-primary:#1a1a2e; --text-secondary:#4a4a5a; --text-muted:#7a7a8a;
}}
html.light .sidebar {{ background:var(--bg-secondary); border-color:var(--border-subtle); }}
html.light .sidebar-logo {{ background:var(--bg-card); }}
html.light input, html.light select {{ background:var(--bg-input); color:var(--text-primary); border-color:var(--border-subtle); }}
html.light select option {{ background:var(--bg-input); color:var(--text-primary); }}
html.light .hero-value {{ -webkit-text-fill-color:var(--accent-primary); }}
html.light .mobile-nav {{ background:var(--bg-secondary); }}
/* ── Loading Skeleton ── */
.skeleton {{
  background:linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
  background-size:200% 100%; animation:shimmer 1.5s infinite; border-radius:6px;
}}
html.light .skeleton {{ background:linear-gradient(90deg, rgba(0,0,0,0.04) 25%, rgba(0,0,0,0.08) 50%, rgba(0,0,0,0.04) 75%); background-size:200% 100%; }}
@keyframes shimmer {{ 0%{{ background-position:200% 0; }} 100%{{ background-position:-200% 0; }} }}
/* ── Command Palette ── */
.cmd-overlay {{
  display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6);
  z-index:300; align-items:flex-start; justify-content:center; padding-top:20vh;
}}
.cmd-overlay.open {{ display:flex; }}
.cmd-box {{
  width:90%; max-width:520px; background:var(--bg-card); border:1px solid var(--border-subtle);
  border-radius:14px; overflow:hidden; box-shadow:0 20px 60px rgba(0,0,0,0.5);
}}
.cmd-input {{
  width:100%; padding:16px 20px; background:transparent; border:none; border-bottom:1px solid var(--border-subtle);
  color:var(--text-primary); font-size:1rem; font-family:inherit; outline:none;
}}
.cmd-results {{ max-height:300px; overflow-y:auto; padding:8px; }}
.cmd-result {{
  padding:10px 14px; border-radius:8px; cursor:pointer; display:flex; align-items:center; gap:10px;
  color:var(--text-secondary); font-size:0.88rem;
}}
.cmd-result:hover, .cmd-result.active {{ background:var(--accent-glow); color:var(--text-primary); }}
.cmd-result .cmd-key {{ color:var(--text-muted); font-size:0.75rem; margin-left:auto; font-family:var(--mono); }}
.cmd-hint {{ padding:10px 14px; font-size:0.75rem; color:var(--text-muted); border-top:1px solid var(--border-subtle); text-align:center; }}
/* ── Auth Screen ── */
.auth-screen {{
  display:flex; align-items:center; justify-content:center; min-height:100vh;
  background:var(--bg-primary); flex-direction:column; gap:24px;
}}
.auth-box {{
  background:var(--bg-card); border:1px solid var(--border-subtle); border-radius:16px;
  padding:40px; text-align:center; max-width:360px; width:90%;
}}
.auth-box h1 {{ font-size:1.4rem; margin-bottom:8px; color:var(--accent-primary); }}
.auth-box input {{ margin:16px 0; text-align:center; font-size:1.2rem; letter-spacing:0.3em; }}
.auth-box .auth-error {{ color:var(--danger); font-size:0.85rem; margin-top:8px; }}
/* ── Projection Chart ── */
.projection-note {{ font-size:0.78rem; color:var(--text-muted); margin-top:8px; }}
/* ── Danger text ── */
.danger {{ color:var(--danger); font-weight:500; }}
/* ── Theme Toggle ── */
.theme-toggle {{
  width:48px; height:48px; border-radius:12px; border:none; background:none;
  color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center;
  transition:all 0.2s ease;
}}
.theme-toggle:hover {{ color:var(--text-secondary); background:rgba(255,255,255,0.04); }}
.theme-toggle svg {{ width:20px; height:20px; stroke:currentColor; fill:none; stroke-width:1.8; }}
/* ── Mobile ── */
.mobile-nav {{
  display:none;
  position:fixed; bottom:0; left:0; right:0;
  background:var(--bg-secondary);
  border-top:1px solid var(--border-subtle);
  padding:8px 0 env(safe-area-inset-bottom, 8px);
  z-index:100;
}}
.mobile-nav-inner {{
  display:flex; justify-content:space-around; align-items:center;
}}
.mob-item {{
  display:flex; flex-direction:column; align-items:center; gap:3px;
  color:var(--text-muted); text-decoration:none; font-size:0.6rem;
  font-weight:500; padding:4px 0; cursor:pointer;
  border:none; background:none;
}}
.mob-item svg {{ width:22px; height:22px; stroke:currentColor; fill:none; stroke-width:1.8; }}
.mob-item.active {{ color:var(--accent-primary); }}
@media (max-width:768px) {{
  .sidebar {{ display:none; }}
  .main-content {{ margin-left:0; padding:16px 16px 80px; }}
  .mobile-nav {{ display:block; }}
  .hero-row {{ flex-direction:column; }}
  .hero-value {{ font-size:2rem; }}
  .pulse-bar {{ gap:8px; }}
  .pulse-item {{ min-width:130px; max-width:160px; height:110px; padding:10px 12px; }}
  .summary-grid {{ grid-template-columns:1fr; }}
  .chart-controls {{ flex-direction:column; }}
  .chart-controls select {{ width:100%; }}
}}
@media (min-width:769px) and (max-width:1024px) {{
  .summary-grid {{ grid-template-columns:1fr; }}
  .main-content {{ padding:24px 24px; }}
}}

/* ── Pulse Chart Modal ── */
.pcm-overlay {{
  display:none; position:fixed; inset:0; background:rgba(0,0,0,0.72);
  z-index:1100; align-items:center; justify-content:center;
  animation:pcmFadeIn .18s ease;
}}
@keyframes pcmFadeIn {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
.pcm-overlay.active {{ display:flex; }}
.pcm-box {{
  background:var(--bg-card); border:1px solid var(--border-accent);
  border-radius:var(--radius); width:94vw; max-width:920px;
  max-height:92vh; display:flex; flex-direction:column;
  box-shadow:0 20px 60px rgba(0,0,0,0.5);
  animation:pcmSlideUp .22s ease;
}}
@keyframes pcmSlideUp {{ from {{ opacity:0;transform:translateY(20px); }} to {{ opacity:1;transform:translateY(0); }} }}
.pcm-header {{
  display:flex; align-items:center; justify-content:space-between;
  padding:18px 22px 12px; border-bottom:1px solid var(--border-subtle);
}}
.pcm-title {{ font-size:1.15rem; font-weight:700; color:var(--text-primary); }}
.pcm-price {{ font-family:var(--mono); font-size:1rem; color:var(--accent-primary); margin-left:12px; }}
.pcm-close {{
  background:none; border:none; color:var(--text-muted); font-size:1.5rem;
  cursor:pointer; padding:4px 8px; line-height:1; border-radius:4px;
}}
.pcm-close:hover {{ color:var(--text-primary); background:var(--bg-hover); }}
.pcm-controls {{
  display:flex; align-items:center; gap:6px; padding:10px 22px;
  flex-wrap:wrap;
}}
.pcm-pill {{
  padding:5px 13px; border-radius:20px; border:1px solid var(--border-subtle);
  background:transparent; color:var(--text-muted); cursor:pointer;
  font-size:0.78rem; font-weight:600; letter-spacing:0.03em;
  transition:all .15s ease;
}}
.pcm-pill:hover {{ border-color:var(--accent-primary); color:var(--text-primary); }}
.pcm-pill.active {{ background:var(--accent-primary); color:#fff; border-color:var(--accent-primary); }}
.pcm-type-toggle {{
  margin-left:auto; padding:4px 10px; border-radius:14px;
  border:1px solid var(--border-subtle); background:transparent;
  color:var(--text-muted); cursor:pointer; font-size:0.72rem; font-weight:600;
}}
.pcm-type-toggle:hover {{ border-color:var(--accent-primary); color:var(--text-primary); }}
.pcm-body {{
  flex:1; padding:8px 22px 18px; position:relative; min-height:380px;
}}
.pcm-body canvas {{ width:100%!important; height:100%!important; }}
.pcm-spinner {{
  display:none; position:absolute; inset:0; background:rgba(var(--bg-card-rgb,30,30,30),0.7);
  align-items:center; justify-content:center; z-index:2; border-radius:0 0 var(--radius) var(--radius);
}}
.pcm-spinner.show {{ display:flex; }}
.pcm-spinner::after {{
  content:""; width:32px; height:32px; border:3px solid var(--border-subtle);
  border-top-color:var(--accent-primary); border-radius:50%;
  animation:pcmSpin .7s linear infinite;
}}
@keyframes pcmSpin {{ to {{ transform:rotate(360deg); }} }}
@media (max-width:600px) {{
  .pcm-box {{ width:100vw; max-width:100vw; max-height:100vh; border-radius:0; }}
  .pcm-body {{ min-height:260px; }}
}}
</style>
</head>
<body>

{demo_banner}

<!-- Sidebar Navigation -->
<nav class="sidebar">
  <div class="sidebar-logo"><img src="/icon-192.png" alt="Nickel&amp;Dime"></div>
  <div class="sidebar-nav">
    <a class="nav-item active" data-tab="summary" href="#">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      <span class="tooltip">Summary</span>
    </a>
    <a class="nav-item" data-tab="balances" href="#">
      <svg viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
      <span class="tooltip">Balances</span>
    </a>
    <a class="nav-item" data-tab="holdings" href="#">
      <svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a4 4 0 00-8 0v2"/></svg>
      <span class="tooltip">Holdings</span>
    </a>
    <a class="nav-item" data-tab="budget" href="#">
      <svg viewBox="0 0 24 24"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
      <span class="tooltip">Budget</span>
    </a>
    <a class="nav-item" data-tab="import" href="#">
      <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      <span class="tooltip">Import</span>
    </a>
    <a class="nav-item" data-tab="history" href="#">
      <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      <span class="tooltip">Charts</span>
    </a>
    <a class="nav-item" data-tab="economics" href="#">
      <svg viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
      <span class="tooltip">Economics</span>
    </a>
  </div>
  <div class="sidebar-bottom">
    <button type="button" class="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark">
      <svg viewBox="0 0 24 24" id="theme-icon"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
    </button>
    <form method="post" action="/refresh" style="margin:0;">
      <button type="submit" class="refresh-btn" title="Refresh Prices">
        <svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
      </button>
  </form>
    <div class="auto-refresh-indicator" id="auto-refresh-indicator" onclick="toggleAutoRefreshSettings()" title="Auto-refresh settings">
      <span class="auto-dot {auto_dot_class}" id="auto-dot"></span>
      <span class="auto-label" id="auto-label">{auto_interval}m</span>
      <div id="auto-refresh-popover" class="auto-popover" style="display:none;" onclick="event.stopPropagation()">
        <div class="auto-popover-title">Auto-Refresh</div>
        <label class="auto-toggle-row">
          <span>Enabled</span>
          <input type="checkbox" id="auto-enabled" {auto_checked} onchange="saveAutoRefresh()">
        </label>
        <label class="auto-toggle-row">
          <span>Interval</span>
          <select id="auto-interval" onchange="saveAutoRefresh()">
            <option value="5" {auto_sel_5}>5 min</option>
            <option value="10" {auto_sel_10}>10 min</option>
            <option value="15" {auto_sel_15}>15 min</option>
            <option value="30" {auto_sel_30}>30 min</option>
            <option value="60" {auto_sel_60}>1 hour</option>
            <option value="120" {auto_sel_120}>2 hours</option>
            <option value="240" {auto_sel_240}>4 hours</option>
          </select>
        </label>
        <div style="font-size:0.65rem;color:var(--text-muted);margin-top:6px;line-height:1.4;">
          Runs 24/7 while server is active.<br>Captures portfolio OHLC daily.
        </div>
      </div>
    </div>
  </div>
</nav>

<!-- Mobile Bottom Nav -->
<nav class="mobile-nav">
  <div class="mobile-nav-inner">
    <button class="mob-item active" data-tab="summary"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>Home</button>
    <button class="mob-item" data-tab="holdings"><svg viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a4 4 0 00-8 0v2"/></svg>Holdings</button>
    <button class="mob-item" data-tab="budget"><svg viewBox="0 0 24 24"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>Budget</button>
    <button class="mob-item" data-tab="history"><svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Charts</button>
    <button class="mob-item" data-tab="economics"><svg viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>Econ</button>
    <button class="mob-item" data-tab="balances"><svg viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>More</button>
  </div>
</nav>

{saved_msg}

<!-- Main Content -->
<div class="main-content">

<!-- ═══ SUMMARY TAB ═══ -->
<div id="tab-summary" class="tab active">
<!-- TAB:summary -->

  <!-- Net Worth Hero + Portfolio History -->
  <div class="hero-row">
    <div class="hero">
      <div class="hero-label">Net Worth</div>
      <div class="hero-value" id="net-worth-counter" data-target="{net_worth:.2f}">${net_worth:,.2f}</div>
      <div class="hero-change {change_color}" id="hero-change-badge">
        {change_sign}${abs(daily_change):,.0f} ({change_sign}{daily_change_pct:.1f}%)
      </div>
      <div class="hero-meta" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
      <span id="last-refresh-time">{datetime.now().strftime("%B %d, %Y at %I:%M %p")}</span>
      {"" if total_debt == 0 else f'<span style="font-size:0.72rem;color:var(--text-muted);">Assets: ${total:,.0f} &middot; Debts: ${total_debt:,.0f}</span>'}
      <select id="currency-selector" class="currency-select" onchange="changeCurrency(this.value)" title="Display currency">
        <option value="USD">$ USD</option>
        <option value="EUR">&#8364; EUR</option>
        <option value="GBP">&#163; GBP</option>
        <option value="JPY">&#165; JPY</option>
        <option value="CAD">C$ CAD</option>
        <option value="AUD">A$ AUD</option>
        <option value="CHF">Fr CHF</option>
      </select>
  </div>
    </div>
    <div class="card hero-chart-card" style="flex:1;min-width:280px;margin:0;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
        <div class="card-title" style="font-size:0.8rem;margin:0;">Portfolio History</div>
        <div style="display:flex;gap:4px;">
          <button type="button" class="chart-toggle active" id="hist-line-btn" onclick="setHistoryChartType('line')" title="Line chart">&#9135;</button>
          <button type="button" class="chart-toggle" id="hist-candle-btn" onclick="setHistoryChartType('candlestick')" title="Candlestick chart">&#9649;</button>
        </div>
      </div>
      <div style="position:relative;height:160px;">
        <canvas id="history-chart"></canvas>
        {f'<p style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:var(--text-muted);font-size:0.85rem;">No history yet. Click Refresh to start logging.</p>' if len(price_history) == 0 else ''}
    </div>
  </div>
</div>

  <!-- Market Pulse (drag-and-drop reorderable) -->
  <div class="pulse-bar" id="pulse-bar">
    {pulse_html}
    <div class="pulse-item pulse-add" onclick="showAddPulseCard()" title="Add custom ticker">
      <span style="font-size:1.6rem;color:var(--text-muted);line-height:1;">+</span>
      <span class="pulse-label">Add Ticker</span>
    </div>
    {f'<div class="pulse-item pulse-add" onclick="restoreAllPulseCards()" title="Restore hidden cards"><span style="font-size:1.2rem;color:var(--text-muted);line-height:1;">&#x21ba;</span><span class="pulse-label">Restore ({hidden_count})</span></div>' if hidden_count > 0 else ""}
  </div>
  <!-- Add pulse card modal -->
  <div id="pulse-add-modal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:1000;align-items:center;justify-content:center;">
    <div style="background:var(--bg-card);border:1px solid var(--border-accent);border-radius:var(--radius);padding:24px;max-width:340px;width:90%;">
      <div class="card-title" style="margin-bottom:14px;">Add Market Ticker</div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div class="ctrl-group"><span class="label">Ticker Symbol</span><input type="text" id="pulse-add-ticker" placeholder="AAPL, TSLA, ETH..." style="text-transform:uppercase;"></div>
        <div class="ctrl-group"><span class="label">Display Label (optional)</span><input type="text" id="pulse-add-label" placeholder="Apple"></div>
        <div class="ctrl-group"><span class="label">Type</span><select id="pulse-add-type" style="width:100%;"><option value="stock">Stock / ETF</option><option value="crypto">Crypto</option></select></div>
        <div style="display:flex;gap:8px;justify-content:flex-end;">
          <button type="button" class="secondary" onclick="hideAddPulseCard()">Cancel</button>
          <button type="button" onclick="addPulseCard()">Add</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Pulse Chart Modal -->
  <div class="pcm-overlay" id="pcm-overlay" onclick="if(event.target===this)closePulseChart()">
    <div class="pcm-box">
      <div class="pcm-header">
        <div style="display:flex;align-items:center;gap:4px;">
          <span class="pcm-title" id="pcm-title"></span>
          <span class="pcm-price" id="pcm-price"></span>
        </div>
        <button type="button" class="pcm-close" onclick="closePulseChart()">&times;</button>
      </div>
      <div class="pcm-controls" id="pcm-controls">
        <button type="button" class="pcm-pill active" data-pcm-p="1d" data-pcm-i="1m">1D</button>
        <button type="button" class="pcm-pill" data-pcm-p="5d" data-pcm-i="5m">5D</button>
        <button type="button" class="pcm-pill" data-pcm-p="1mo" data-pcm-i="15m">1M</button>
        <button type="button" class="pcm-pill" data-pcm-p="3mo" data-pcm-i="1d">3M</button>
        <button type="button" class="pcm-pill" data-pcm-p="6mo" data-pcm-i="1d">6M</button>
        <button type="button" class="pcm-pill" data-pcm-p="1y" data-pcm-i="1d">1Y</button>
        <button type="button" class="pcm-pill" data-pcm-p="5y" data-pcm-i="1wk">5Y</button>
        <button type="button" class="pcm-pill" data-pcm-p="max" data-pcm-i="1mo">Max</button>
        <button type="button" class="pcm-type-toggle" id="pcm-type-toggle" onclick="togglePcmChartType()">Candlestick</button>
      </div>
      <div class="pcm-body">
        <canvas id="pcm-canvas"></canvas>
        <div class="pcm-spinner" id="pcm-spinner"></div>
      </div>
    </div>
  </div>

  <!-- Two Column Grid (Drag-to-Reorder) -->
  <div class="summary-grid" id="summary-widgets">
    <!-- Left Column -->
    <div class="widget-col" id="widget-col-left">
      <!-- Allocation Donut -->
      <div class="card widget-card" draggable="true" data-widget="allocation-donut">
        <div class="card-title"><span class="drag-handle" title="Drag to reorder">&#x2630;</span> Portfolio Allocation</div>
        <div style="position:relative;height:260px;">
          <canvas id="allocation-donut"></canvas>
        </div>
      </div>

      <!-- Allocation Table -->
      <div class="card widget-card" draggable="true" data-widget="allocation-table">
        <div class="card-title"><span class="drag-handle" title="Drag to reorder">&#x2630;</span> Allocation vs Target</div>
        <table>
          <thead><tr><th>Bucket</th><th>Value</th><th>%</th><th>Target</th><th>Drift</th></tr></thead>
          <tbody>{alloc_rows}</tbody>
        </table>
      </div>

      <!-- Debt Overview -->
      {"" if not debts else '''<div class="card widget-card" draggable="true" data-widget="debt-overview">
        <div class="card-title"><span class="drag-handle" title="Drag to reorder">&#x2630;</span> Debt Overview</div>
        <table>
          <thead><tr><th>Account</th><th style="text-align:right">Balance</th><th style="text-align:right">Payment</th><th style="text-align:center">Payoff</th></tr></thead>
          <tbody>''' + "".join(
            f'<tr><td>{d.get("name","")}</td>'
            f'<td style="text-align:right" class="mono">${float(d.get("balance",0)):,.0f}</td>'
            f'<td style="text-align:right" class="mono">${float(d.get("monthly_payment",0)):,.0f}</td>'
            f'<td style="text-align:center" class="mono hint">{int(float(d.get("balance",0))/float(d.get("monthly_payment",0))) if float(d.get("monthly_payment",0) or 0) > 0 else 0} mo</td></tr>'
            for d in debts
          ) + f'''</tbody>
          <tfoot><tr style="font-weight:600;border-top:2px solid var(--border-subtle);">
            <td>Total Debt</td>
            <td style="text-align:right" class="mono" colspan="3">${total_debt:,.0f}</td>
          </tr></tfoot>
        </table>
        <p class="hint" style="margin-top:8px;">Manage debts on the <a href="/?tab=budget" style="color:var(--accent-primary);">Budget</a> tab.</p>
      </div>'''}

    </div>

    <!-- Right Column -->
    <div class="widget-col" id="widget-col-right">
      <!-- Monthly Investments -->
      <div class="card widget-card" draggable="true" data-widget="monthly-investments">
        <div class="card-header">
          <div>
            <div class="card-title"><span class="drag-handle" title="Drag to reorder">&#x2630;</span> Monthly Investments</div>
            <div class="card-subtitle">{datetime.strptime(current_month, "%Y-%m").strftime("%B %Y")} &middot; Budget: ${savings_budget:,.0f} &rarr; ${total_target:,}</div>
          </div>
          <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="newMonth()">New Month</button>
        </div>
        <table class="invest-table">
          <thead><tr><th>Category</th><th style="text-align:right">Target</th><th style="text-align:right">Contributed</th><th style="text-align:right">Status</th><th style="text-align:center">Progress</th></tr></thead>
          <tbody>{investment_rows_html}</tbody>
          <tfoot>
            <tr style="font-weight:600;border-top:2px solid var(--border-subtle);">
              <td>Total</td>
              <td style="text-align:right" class="mono">${total_target:,}</td>
              <td style="text-align:right;color:var(--accent-primary)" class="mono">${total_contributed:,}</td>
              <td style="text-align:right" class="mono {'surplus' if total_remaining <= 0 else 'shortage'}">{f'+${abs(total_remaining):,}' if total_remaining < 0 else f'${total_remaining:,} left'}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
        <div class="progress-bar" style="margin-top:14px;">
          <div class="progress-fill" id="total-progress-fill" style="width:{min(progress_pct, 100)}%"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:8px;font-size:0.8rem;">
          <span class="hint">Progress: <strong style="color:var(--text-primary)" id="total-progress-pct">{progress_pct}%</strong></span>
          <button type="button" class="secondary" style="padding:5px 12px;font-size:0.75rem;" onclick="saveContributions()">Save Changes</button>
        </div>
        <!-- Quick Log Chat -->
        <div class="invest-chat" style="margin-top:14px;">
          <div id="chat-log" style="max-height:120px;overflow-y:auto;margin-bottom:8px;font-size:0.82rem;"></div>
          <div style="display:flex;gap:8px;">
            <input type="text" id="invest-chat-input" placeholder="e.g. $100 to gold etf, $50 crypto" style="flex:1;font-size:0.85rem;padding:8px 12px;">
            <button type="button" onclick="processInvestChat()" style="padding:8px 14px;font-size:0.8rem;white-space:nowrap;">Log</button>
          </div>
          <p class="hint" style="margin-top:6px;">Type amounts and categories to quickly update contributions. Separate multiple with commas.</p>
        </div>
      </div>
    </div>
  </div>

  <!-- Goal Tracking -->
  <div class="card" style="margin-top:20px;">
    <div class="card-header">
      <div class="card-title">Financial Goals</div>
      <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="showGoalForm()">+ Add Goal</button>
    </div>
    <div id="goal-form" style="display:none;margin-bottom:14px;padding:14px;background:var(--bg-input);border-radius:var(--radius);">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;">
        <div class="ctrl-group"><span class="label">Goal Name</span><input type="text" id="goal-name" placeholder="Emergency Fund" style="width:180px;"></div>
        <div class="ctrl-group"><span class="label">Target ($)</span><input type="number" id="goal-target" class="num" step="100"></div>
        <div class="ctrl-group"><span class="label">Current ($)</span><input type="number" id="goal-current" class="num" step="100" value="0"></div>
        <div class="ctrl-group"><span class="label">Target Date</span><input type="date" id="goal-date"></div>
        <button type="button" onclick="saveGoal()" style="padding:8px 14px;font-size:0.8rem;">Save</button>
      </div>
    </div>
    <div class="goals-grid" id="goals-container">{goals_html if goals_html else '<p class="hint">No goals set. Click + Add Goal to start tracking.</p>'}</div>
  </div>
<!-- /TAB:summary -->
</div>

<!-- ═══ BALANCES TAB ═══ -->
<div id="tab-balances" class="tab">
<!-- TAB:balances -->
  <div class="card">
    <div class="card-title">Account Balances</div>
    <p class="hint" style="margin-bottom:14px;">Managed accounts: Stash, Acorns, 401ks, Fundrise, Masterworks</p>
    <form method="post" action="/save/balances">
      <table><thead><tr><th>Account</th><th style="text-align:right">Value ($)</th></tr></thead><tbody>{balance_rows}</tbody></table>
      <button type="submit" class="success" style="margin-top:16px;">Save Balances</button>
    </form>
  </div>
<!-- /TAB:balances -->
</div>

<!-- ═══ BUDGET TAB ═══ -->
<div id="tab-budget" class="tab">
<!-- TAB:budget -->
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-title">Monthly Budget</div>
        <div class="card-subtitle">{datetime.strptime(budget_month, "%Y-%m").strftime("%B %Y")} &middot; Savings &rarr; Investments: ${savings_budget:,.0f}</div>
      </div>
      <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="newBudgetMonth()">New Month</button>
    </div>
    <form method="post" action="/save/budget">
      <div class="income-bar">
        <div>
          <span class="label">Monthly Income</span>
          <input type="text" name="monthly_income" value="{monthly_income}" class="num" style="width:140px;font-size:1rem;font-weight:600;">
        </div>
        <p class="hint" style="margin:0;">Income changes automatically adjust your investment targets.</p>
      </div>
      <table><thead><tr><th>Category</th><th style="text-align:right">Budget ($)</th></tr></thead><tbody>{budget_rows}{budget_totals_row}</tbody></table>
      <button type="submit" class="success" style="margin-top:16px;">Save Budget</button>
    </form>
  </div>

  <!-- Spending vs Budget Breakdown -->
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-title">Spending vs Budget</div>
        <div class="card-subtitle">Click a category to see individual transactions</div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <select id="spend-month-select" onchange="renderSpendingBreakdown()" style="padding:4px 8px;font-size:0.78rem;width:auto;min-width:130px;"></select>
      </div>
    </div>
    <div id="spending-breakdown"></div>
  </div>

  <!-- Spending Trends -->
  <div class="card">
    <div class="card-title">Spending Trends</div>
    <p class="hint" style="margin-bottom:12px;">Monthly spending by category (log transactions below to populate)</p>
    <div style="position:relative;height:200px;">
      <canvas id="spending-chart"></canvas>
  </div>
</div>

  <!-- Debt Tracker -->
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-title">Debt Tracker</div>
        <div class="card-subtitle">Total debt: ${total_debt:,.0f} &middot; Monthly payments: ${total_debt_payments:,.0f}</div>
      </div>
      <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="addDebtRow()">+ Add Debt</button>
    </div>
    <form method="post" action="/save/debts" id="debt-form">
      <table>
        <thead><tr><th>Name</th><th style="text-align:right">Balance ($)</th><th style="text-align:right">Monthly Payment ($)</th><th style="text-align:center">Payoff</th><th></th></tr></thead>
        <tbody id="debt-tbody">{debt_rows_html}</tbody>
        <tfoot>
          <tr style="font-weight:600;border-top:2px solid var(--border-subtle);">
            <td>Total</td>
            <td style="text-align:right" class="mono">${total_debt:,.2f}</td>
            <td style="text-align:right" class="mono">${total_debt_payments:,.2f}</td>
            <td></td><td></td>
          </tr>
        </tfoot>
      </table>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;">
        <p class="hint" style="margin:0;">Update balances monthly as you pay down debt. Balances are subtracted from assets for your net worth.</p>
        <button type="submit" class="success" style="padding:6px 14px;font-size:0.8rem;">Save Debts</button>
      </div>
    </form>
  </div>

  <!-- Transaction Log -->
  <div class="card">
    <div class="card-header">
      <div class="card-title">Transaction Log</div>
      <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="addTransaction()">+ Add</button>
    </div>
    <div id="txn-form" style="display:none;margin-bottom:14px;padding:14px;background:var(--bg-input);border-radius:var(--radius);">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;">
        <div class="ctrl-group"><span class="label">Date</span><input type="date" id="txn-date" value="{txn_date_val}"></div>
        <div class="ctrl-group"><span class="label">Category</span>
          <select id="txn-cat">{txn_cat_options}</select>
        </div>
        <div class="ctrl-group"><span class="label">Amount ($)</span><input type="number" id="txn-amount" class="num" step="0.01"></div>
        <div class="ctrl-group"><span class="label">Note</span><input type="text" id="txn-note" placeholder="Optional" style="width:160px;"></div>
        <button type="button" onclick="saveTxn()" style="padding:8px 14px;font-size:0.8rem;">Save</button>
      </div>
    </div>
    <div id="txn-list" style="max-height:300px;overflow-y:auto;">
      <table><thead><tr><th>Date</th><th>Category</th><th>Amount</th><th>Note</th></tr></thead><tbody id="txn-body"></tbody></table>
    </div>
  </div>

  <!-- Recurring Transactions -->
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-title">Recurring Transactions</div>
        <div class="card-subtitle">Bills, subscriptions, and income that auto-populate each month</div>
      </div>
      <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="showRecurringForm()">+ Add</button>
    </div>
    <div id="recurring-form" style="display:none;margin-bottom:14px;padding:14px;background:var(--bg-input);border-radius:var(--radius);">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;">
        <div class="ctrl-group"><span class="label">Name</span><input type="text" id="rec-name" placeholder="Netflix, Rent, etc." style="width:160px;"></div>
        <div class="ctrl-group"><span class="label">Amount ($)</span><input type="number" id="rec-amount" class="num" step="0.01"></div>
        <div class="ctrl-group"><span class="label">Category</span>
          <select id="rec-cat">{txn_cat_options}</select>
        </div>
        <div class="ctrl-group"><span class="label">Frequency</span>
          <select id="rec-freq">
            <option value="monthly">Monthly</option>
            <option value="weekly">Weekly</option>
            <option value="biweekly">Bi-weekly</option>
            <option value="quarterly">Quarterly</option>
            <option value="yearly">Yearly</option>
          </select>
        </div>
        <button type="button" onclick="saveRecurring()" style="padding:8px 14px;font-size:0.8rem;">Save</button>
      </div>
    </div>
    <div style="max-height:250px;overflow-y:auto;">
      <table>
        <thead><tr><th>Name</th><th style="text-align:right">Amount</th><th>Category</th><th>Frequency</th><th></th></tr></thead>
        <tbody id="recurring-body">{recurring_rows_html}</tbody>
      </table>
    </div>
    <div style="margin-top:12px;display:flex;gap:12px;flex-wrap:wrap;">
      <button type="button" class="success" style="padding:6px 14px;font-size:0.8rem;" onclick="applyRecurring()">Apply to This Month</button>
      <button type="button" class="secondary" style="padding:6px 14px;font-size:0.8rem;" onclick="detectRecurring()">Detect from History</button>
      <span class="hint" style="align-self:center;">Scan past transactions for recurring patterns</span>
    </div>

    <!-- Suggested Recurring (populated dynamically) -->
    <div id="recurring-suggestions" style="display:none;margin-top:16px;padding:16px;background:var(--bg-input);border-radius:var(--radius);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div>
          <strong style="color:var(--accent-primary);">Suggested Recurring</strong>
          <span class="hint" style="margin-left:8px;">Detected from your transaction history</span>
        </div>
        <button type="button" class="secondary" style="padding:3px 10px;font-size:0.7rem;" onclick="document.getElementById('recurring-suggestions').style.display='none'">Dismiss All</button>
      </div>
      <div style="max-height:300px;overflow-y:auto;">
        <table>
          <thead><tr><th>Name</th><th style="text-align:right">Amount</th><th>Category</th><th>Frequency</th><th>Seen</th><th></th></tr></thead>
          <tbody id="suggested-recurring-body"></tbody>
        </table>
      </div>
    </div>
  </div>
<!-- /TAB:budget -->
</div>

<!-- ═══ HOLDINGS TAB ═══ -->
<div id="tab-holdings" class="tab">
<!-- TAB:holdings -->
  <div class="card">
    <div class="card-title">Holdings</div>
    <p class="hint" style="margin-bottom:14px;">Stocks &amp; ETFs with live prices. Use value override to lock values.</p>
    <form method="post" action="/save/holdings">
      <div style="overflow-x:auto;">
        <table><thead><tr><th>Account</th><th>Ticker</th><th>Class</th><th>Qty</th><th style="text-align:right">Price</th><th style="text-align:right">Total</th><th style="text-align:right">Override</th><th>Notes</th></tr></thead><tbody>{holding_rows}{totals_row}</tbody></table>
      </div>
      <button type="submit" class="success" style="margin-top:16px;">Save Holdings</button>
    </form>
  </div>

  <!-- Physical Metals -->
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-title">Physical Metals</div>
        <div class="card-subtitle">Track gold &amp; silver purchases — values update with live spot prices</div>
      </div>
      <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="toggleMetalForm()">+ Add Purchase</button>
    </div>
    <div id="metal-form" style="display:none;margin-bottom:14px;padding:14px;background:var(--bg-input);border-radius:var(--radius);">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;">
        <div class="ctrl-group"><span class="label">Metal</span>
          <select id="metal-type">
            <option value="Gold">Gold</option>
            <option value="Silver">Silver</option>
          </select>
        </div>
        <div class="ctrl-group"><span class="label">Form</span><input type="text" id="metal-form-desc" placeholder="1oz Bar, Coin, etc." style="width:120px;"></div>
        <div class="ctrl-group"><span class="label">Qty (oz)</span><input type="number" id="metal-qty" class="num" step="0.0001" style="width:90px;"></div>
        <div class="ctrl-group"><span class="label">Cost/oz ($)</span><input type="number" id="metal-cost" class="num" step="0.01" style="width:100px;"></div>
        <div class="ctrl-group"><span class="label">Date</span><input type="date" id="metal-date" value="{txn_date_val}"></div>
        <div class="ctrl-group"><span class="label">Note</span><input type="text" id="metal-note" placeholder="Optional" style="width:120px;"></div>
        <button type="button" onclick="saveMetalPurchase()" style="padding:8px 14px;font-size:0.8rem;">Save</button>
      </div>
    </div>
    <div style="display:flex;gap:20px;margin-bottom:12px;">
      <div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);flex:1;text-align:center;">
        <div class="hint" style="margin-bottom:4px;">Gold (oz)</div>
        <div class="mono" style="font-size:1.1rem;color:gold;">{metals_gold_oz:.4g}</div>
      </div>
      <div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);flex:1;text-align:center;">
        <div class="hint" style="margin-bottom:4px;">Silver (oz)</div>
        <div class="mono" style="font-size:1.1rem;color:silver;">{metals_silver_oz:.4g}</div>
      </div>
      <div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);flex:1;text-align:center;">
        <div class="hint" style="margin-bottom:4px;">Total Value</div>
        <div class="mono" style="font-size:1.1rem;color:#58a6ff;">${metals_total_value:,.2f}</div>
      </div>
      <div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);flex:1;text-align:center;">
        <div class="hint" style="margin-bottom:4px;">Gain / Loss</div>
        <div class="mono" style="font-size:1.1rem;{metals_gl_cls}">${metals_total_gl:+,.2f}</div>
      </div>
    </div>
    <div style="max-height:300px;overflow-y:auto;">
      <table>
        <thead><tr><th>Metal</th><th>Form</th><th style="text-align:right">Qty (oz)</th><th style="text-align:right">Cost/oz</th><th style="text-align:right">Spot</th><th style="text-align:right">Value</th><th style="text-align:right">G/L</th><th>Date</th><th></th></tr></thead>
        <tbody>{metals_rows_html}{metals_totals_row}</tbody>
      </table>
    </div>
  </div>

  <!-- Dividend & Fee Tracking -->
  <div class="card">
    <div class="card-header">
      <div>
        <div class="card-title">Dividends &amp; Fees</div>
        <div class="card-subtitle">Track income from dividends and costs from fees</div>
      </div>
      <button type="button" class="secondary" style="padding:5px 10px;font-size:0.75rem;" onclick="showDivForm()">+ Log</button>
    </div>
    <div id="div-form" style="display:none;margin-bottom:14px;padding:14px;background:var(--bg-input);border-radius:var(--radius);">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;">
        <div class="ctrl-group"><span class="label">Date</span><input type="date" id="div-date" value="{txn_date_val}"></div>
        <div class="ctrl-group"><span class="label">Ticker</span><input type="text" id="div-ticker" placeholder="SPY" style="width:90px;text-transform:uppercase;"></div>
        <div class="ctrl-group"><span class="label">Amount ($)</span><input type="number" id="div-amount" class="num" step="0.01"></div>
        <div class="ctrl-group"><span class="label">Type</span>
          <select id="div-type">
            <option value="dividend">Dividend</option>
            <option value="fee">Fee</option>
          </select>
        </div>
        <div class="ctrl-group"><span class="label">Note</span><input type="text" id="div-note" placeholder="Optional" style="width:140px;"></div>
        <button type="button" onclick="saveDividend()" style="padding:8px 14px;font-size:0.8rem;">Save</button>
      </div>
    </div>
    <div style="display:flex;gap:20px;margin-bottom:12px;">
      <div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);flex:1;text-align:center;">
        <div class="hint" style="margin-bottom:4px;">Total Dividends</div>
        <div class="mono" style="font-size:1.1rem;color:var(--success);" id="div-total-inc">$0.00</div>
      </div>
      <div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);flex:1;text-align:center;">
        <div class="hint" style="margin-bottom:4px;">Total Fees</div>
        <div class="mono" style="font-size:1.1rem;color:var(--danger);" id="div-total-fee">$0.00</div>
      </div>
      <div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);flex:1;text-align:center;">
        <div class="hint" style="margin-bottom:4px;">Net Income</div>
        <div class="mono" style="font-size:1.1rem;font-weight:600;" id="div-total-net">$0.00</div>
      </div>
    </div>
    <div style="position:relative;height:160px;margin-bottom:12px;">
      <canvas id="div-chart"></canvas>
    </div>
    <div style="max-height:250px;overflow-y:auto;">
      <table>
        <thead><tr><th>Date</th><th>Ticker</th><th style="text-align:right">Amount</th><th>Type</th><th>Note</th></tr></thead>
        <tbody>{div_rows_html}</tbody>
      </table>
    </div>
  </div>
<!-- /TAB:holdings -->
</div>

<!-- ═══ IMPORT TAB ═══ -->
<div id="tab-import" class="tab">
<!-- TAB:import -->
  <div class="card">
    <div class="card-title">Import Data</div>
    <p class="hint" style="margin-bottom:16px;">Upload a positions CSV from your brokerage to sync holdings.</p>
    <form method="post" action="/import/csv" enctype="multipart/form-data">
      <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:end;">
        <div>
          <span class="label">Source</span>
          <select name="source">
        <option value="fidelity">Fidelity</option>
        <option value="stash">Stash</option>
        <option value="acorns_invest">Acorns Invest</option>
        <option value="acorns_later">Acorns Later</option>
        <option value="fundrise">Fundrise</option>
          </select>
        </div>
        <div style="flex:1;min-width:200px;">
          <span class="label">CSV File</span>
          <input type="file" name="csv_file" accept=".csv" required style="padding:7px 0;">
        </div>
      <button type="submit">Import CSV</button>
      </div>
    </form>
    <div class="tip-box" style="margin-top:14px;">
      <strong>Fidelity:</strong> Accounts &amp; Trade &rarr; Account Positions &rarr; Download. Only "Individual" positions imported.
  </div>
</div>

  <!-- Bank / Credit Card Statement Import -->
  <div class="card">
    <div class="card-title">Import Bank / Credit Card Statement</div>
    <p class="hint" style="margin-bottom:16px;">Upload one or more CSV/PDF statements to auto-import and categorize spending transactions into your budget tracker.</p>
    <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:end;">
      <div style="flex:1;min-width:200px;">
        <span class="label">Statements (CSV or PDF — select multiple)</span>
        <input type="file" id="stmt-file" accept=".csv,.pdf" multiple style="padding:7px 0;">
      </div>
      <button type="button" onclick="previewStatement()" style="padding:8px 14px;">Preview</button>
    </div>

    <!-- Preview area -->
    <div id="stmt-preview" style="display:none;margin-top:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div>
          <strong id="stmt-summary"></strong>
          <span class="hint" id="stmt-cat-summary" style="margin-left:12px;"></span>
        </div>
        <button type="button" onclick="importStatement()" style="padding:8px 18px;">Import All</button>
      </div>
      <div style="max-height:350px;overflow-y:auto;">
        <table>
          <thead><tr><th>Date</th><th>Description</th><th>Amount</th><th>Category</th></tr></thead>
          <tbody id="stmt-rows"></tbody>
        </table>
      </div>
    </div>

    <div style="display:flex;justify-content:space-between;align-items:start;margin-top:14px;gap:12px;">
      <div class="tip-box" style="flex:1;margin-top:0;">
        <strong>Supported formats:</strong> CSV and PDF statements from Chase, Bank of America, Wells Fargo, Capital One, Citi, Discover, USAA, Apple Card, Coinbase, Golden 1, and most banks.<br>
        <strong>How to export:</strong> Log into your bank &rarr; Statements or Activity &rarr; Download as CSV or PDF.
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;flex-shrink:0;">
        <button type="button" class="secondary" onclick="undoLastImport()" style="padding:6px 14px;font-size:0.78rem;white-space:nowrap;color:var(--danger);">Undo Last Import</button>
        <button type="button" class="secondary" onclick="clearAllTransactions()" style="padding:6px 14px;font-size:0.78rem;white-space:nowrap;color:var(--danger);">Clear All Transactions</button>
      </div>
    </div>
  </div>

<!-- /TAB:import -->
</div>

<!-- ═══ CHARTS TAB ═══ -->
<div id="tab-history" class="tab">
<!-- TAB:history -->
  <!-- Projected Growth -->
  <div class="card">
    <div class="card-title">Projected Growth</div>
    <p class="hint" style="margin-bottom:12px;">Pick rate, contribution, and horizon. Drag the timeline slider to see projected value at any year.</p>
    <div class="chart-controls" style="margin-bottom:16px;">
      <div class="ctrl-group">
        <span class="label">Rate of Return</span>
        <div style="display:flex;align-items:center;gap:8px;">
          <input type="range" id="proj-rate" min="1" max="15" value="7" step="0.5" style="width:100px;">
          <span id="proj-rate-val" style="font-family:var(--mono);font-size:0.9rem;">7%</span>
        </div>
      </div>
      <div class="ctrl-group">
        <span class="label">Monthly Contribution</span>
        <input type="number" id="proj-monthly" class="num" value="{int(monthly_contribution)}" step="100" min="0" style="width:120px;">
      </div>
      <div class="ctrl-group">
        <span class="label">Time Horizon (years)</span>
        <div style="display:flex;align-items:center;gap:8px;">
          <input type="range" id="proj-years" min="1" max="40" value="30" step="1" style="width:100px;">
          <span id="proj-years-val" style="font-family:var(--mono);font-size:0.9rem;">30</span>
        </div>
      </div>
    </div>
    <div id="projection-chart-wrap" style="position:relative;height:300px;">
      <canvas id="projection-chart"></canvas>
      <div id="projection-crosshair" style="position:absolute;top:0;bottom:0;width:2px;background:var(--accent-primary);pointer-events:none;display:none;"></div>
      <div id="projection-crosshair-label" style="position:absolute;top:8px;left:50%;transform:translateX(-50%);background:var(--bg-card);border:1px solid var(--border-accent);padding:6px 12px;border-radius:8px;font-family:var(--mono);font-size:0.85rem;pointer-events:none;display:none;"></div>
    </div>
    <div class="ctrl-group" style="margin-top:12px;">
      <span class="label">Timeline</span>
      <input type="range" id="proj-timeline" min="0" max="30" value="30" step="1" style="flex:1;max-width:300px;">
      <span id="proj-timeline-val" style="font-family:var(--mono);font-size:0.9rem;">Year 30</span>
    </div>
    <div id="projection-summary" style="display:flex;gap:24px;flex-wrap:wrap;margin-top:16px;padding-top:12px;border-top:1px solid var(--border-subtle);font-size:0.85rem;">
      <span><strong>Starting value:</strong> <span id="proj-start-val"></span></span>
      <span><strong>Ending value:</strong> <span id="proj-end-val"></span></span>
      <span><strong>Total contributions:</strong> <span id="proj-total-contrib"></span></span>
      <span><strong>Growth from returns:</strong> <span id="proj-growth"></span></span>
    </div>
    <p class="projection-note" style="margin-top:12px;">Projections are estimates only. Past performance does not guarantee future results.</p>
  </div>

  <!-- Monte Carlo Projections -->
  <div class="card">
    <div class="card-title">Monte Carlo Projections</div>
    <p class="hint" style="margin-bottom:12px;">1,000 randomized simulations based on historical volatility. Shaded bands show 10th-90th percentile outcomes.</p>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin-bottom:12px;">
      <div class="ctrl-group">
        <span class="label">Years</span>
        <select id="mc-years">
          <option value="5">5</option>
          <option value="10" selected>10</option>
          <option value="20">20</option>
          <option value="30">30</option>
        </select>
      </div>
      <div class="ctrl-group">
        <span class="label">Monthly Contrib</span>
        <input type="number" id="mc-contrib" class="num" value="{int(monthly_contribution)}" step="100" style="width:110px;">
      </div>
      <button type="button" class="secondary" style="padding:8px 14px;font-size:0.8rem;" onclick="runMonteCarlo()">Simulate</button>
    </div>
    <div style="position:relative;height:300px;">
      <canvas id="mc-chart"></canvas>
    </div>
  </div>

  <!-- Drawdown Analysis -->
  <div class="card">
    <div class="card-title">Drawdown Analysis</div>
    <p class="hint" style="margin-bottom:12px;">Portfolio drawdowns from peak values over recorded history</p>
    <div style="position:relative;height:200px;">
      <canvas id="drawdown-chart"></canvas>
    </div>
    <div id="drawdown-stats" style="display:flex;gap:16px;flex-wrap:wrap;margin-top:12px;"></div>
  </div>

  <!-- Performance Attribution -->
  <div class="card">
    <div class="card-title">Performance Attribution</div>
    <p class="hint" style="margin-bottom:12px;">Portfolio return contribution by asset class</p>
    <div style="display:flex;gap:20px;flex-wrap:wrap;">
      <div style="position:relative;height:260px;flex:1;min-width:280px;">
        <canvas id="perf-attr-chart"></canvas>
      </div>
      <div style="flex:1;min-width:250px;" id="perf-attr-table"></div>
    </div>
  </div>

  <!-- Tax-Loss Harvesting -->
  {tlh_card_html}

  <div class="card">
    <div class="card-title">Market Charts</div>
    <p class="hint" style="margin-bottom:16px;">Historical price data from Yahoo Finance</p>
    <div class="chart-controls">
      <div class="ctrl-group">
        <span class="label">Asset</span>
        <select id="market-asset">
          <option value="GC=F">Gold</option>
          <option value="SI=F">Silver</option>
          <option value="SPY">SPY (S&amp;P 500)</option>
          <option value="VTI">VTI (Total Market)</option>
          <option value="DX-Y.NYB">Dollar Index (DXY)</option>
          <option value="^VIX">VIX (Volatility)</option>
          <option value="CL=F">Oil (WTI Crude)</option>
          <option value="HG=F">Copper</option>
          <option value="BTC-USD">Bitcoin</option>
          <option value="ETH-USD">Ethereum</option>
          <option value="^TNX">10Y Treasury</option>
          <option value="2YY=F">2Y Treasury</option>
          <option value="10Y2Y-SPREAD">10Y-2Y Spread</option>
        </select>
    </div>
      <div class="ctrl-group">
        <span class="label">Period</span>
        <select id="market-period">
          <option value="5d">1W</option>
          <option value="1mo" selected>1M</option>
          <option value="3mo">3M</option>
          <option value="6mo">6M</option>
          <option value="1y">1Y</option>
          <option value="5y">5Y</option>
          <option value="max">Max</option>
        </select>
  </div>
      <div class="ctrl-group">
        <span class="label">Type</span>
        <select id="chart-type">
          <option value="line">Line</option>
          <option value="candlestick">Candlestick</option>
        </select>
    </div>
      <div class="ctrl-group">
        <span class="label">Scale</span>
        <select id="chart-scale">
          <option value="linear">Linear</option>
          <option value="logarithmic">Log</option>
        </select>
      </div>
      <div class="ctrl-group" style="justify-content:flex-end;gap:6px;flex-direction:row;">
        <button type="button" id="load-market-chart" class="secondary" style="padding:8px 14px;font-size:0.8rem;">Load</button>
        <button type="button" id="reset-zoom" class="secondary" style="padding:8px 14px;font-size:0.8rem;">Reset Zoom</button>
      </div>
    </div>
    <p class="hint" style="margin-bottom:6px;">Drag to pan &middot; Scroll to zoom &middot; Double-click to reset</p>
    <div style="position:relative;height:400px;">
      <canvas id="market-chart"></canvas>
    </div>
    <p id="market-chart-status" class="hint" style="margin-top:10px;"></p>
  </div>
<!-- /TAB:history -->
</div>

<!-- ═══ ECONOMICS TAB (lazy-loaded) ═══ -->
<div id="tab-economics" class="tab">
<!-- TAB:economics -->
  <div data-lazy-tab="economics" style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 20px;color:var(--text-muted);">
    <div style="width:32px;height:32px;border:3px solid rgba(255,255,255,0.1);border-top-color:var(--accent-primary);border-radius:50%;animation:spin 0.8s linear infinite;"></div>
    <p style="margin-top:16px;">Loading economics data&hellip;</p>
  </div>
<!-- /TAB:economics -->
</div>

</div><!-- /main-content -->

<!-- Command Palette -->
<div class="cmd-overlay" id="cmd-overlay">
  <div class="cmd-box">
    <input class="cmd-input" id="cmd-input" type="text" placeholder="Search holdings, assets, pages..." autocomplete="off">
    <div class="cmd-results" id="cmd-results"></div>
    <div class="cmd-hint">Navigate with &uarr;&darr; &middot; Enter to select &middot; Esc to close</div>
  </div>
</div>

<script>
var PRICE_HISTORY_DATA = {history_json};
var BUCKETS_DATA = {buckets_json};
var TARGETS_DATA = {targets_json};

/* ── Tab Switching with lazy-load ── */
var _tabLoaded = {{ "{active_tab}": true }};
_tabLoaded["economics"] = false;

function _injectTabContent(tabEl, html) {{
  tabEl.innerHTML = html;
  var scripts = tabEl.querySelectorAll("script");
  scripts.forEach(function(oldScript) {{
    var ns = document.createElement("script");
    ns.textContent = oldScript.textContent;
    document.head.appendChild(ns);
    oldScript.remove();
  }});
}}

var _budgetDataLoaded = false;
function _initBudgetListeners() {{
  if (_budgetDataLoaded) return;
  _budgetDataLoaded = true;
  fetch("/api/budget-data")
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      TRANSACTIONS = d.transactions || [];
      BUDGET_LIMITS = d.budget_limits || {{}};
      BUDGET_CATS = d.budget_cats || [];
      renderTxns();
      renderSpendingBreakdown();
      buildSpendingChart();
    }})
    .catch(function() {{ _budgetDataLoaded = false; }});
}}

function _postTabInit(t) {{
  if (t === "economics" && typeof loadFredData === "function") loadFredData();
  if (t === "history") {{
    if (typeof loadMarketChart === "function") {{ _initMarketChartListeners(); loadMarketChart(); }}
    if (typeof buildProjectionChart === "function") buildProjectionChart();
    if (typeof runMonteCarlo === "function") runMonteCarlo();
    if (typeof buildDrawdownChart === "function") buildDrawdownChart();
    if (typeof buildPerfAttribution === "function") buildPerfAttribution();
  }}
  if (t === "budget") _initBudgetListeners();
}}

function showTab(t) {{
  document.querySelectorAll(".tab").forEach(function(d) {{ d.classList.remove("active"); }});
  document.querySelectorAll(".nav-item, .mob-item").forEach(function(l) {{ l.classList.remove("active"); }});
  var el = document.getElementById("tab-" + t);
  if (el) el.classList.add("active");
  document.querySelectorAll('[data-tab="' + t + '"]').forEach(function(l) {{ l.classList.add("active"); }});

  if (!_tabLoaded[t] && el && el.querySelector("[data-lazy-tab]")) {{
    fetch("/api/tab-content/" + t)
      .then(function(r) {{ return r.text(); }})
      .then(function(html) {{
        _injectTabContent(el, html);
        _tabLoaded[t] = true;
        _postTabInit(t);
      }})
      .catch(function(err) {{
        el.innerHTML = '<div style="text-align:center;padding:60px;color:var(--danger);">Failed to load tab. <button onclick="showTab(' + JSON.stringify(t) + ')" style="color:var(--accent-primary);text-decoration:underline;background:none;border:none;cursor:pointer;">Retry</button></div>';
      }});
  }} else {{
    if (t === "economics" && typeof loadFredData === "function") loadFredData();
  }}
  var url = "/" + (t === "summary" ? "" : t);
  if (window.location.pathname !== url) history.pushState({{tab:t}}, "", url);
}}
window.addEventListener("popstate", function(e) {{ if(e.state && e.state.tab) showTab(e.state.tab); }});
document.querySelectorAll(".nav-item, .mob-item").forEach(function(a) {{
  a.addEventListener("click", function(e) {{ e.preventDefault(); showTab(this.getAttribute("data-tab")); }});
}});
var tabMap = {{"balances":"balances","budget":"budget","holdings":"holdings","import":"import","history":"history","economics":"economics","charts":"history"}};
var pathTab = window.location.pathname.substring(1);
var tab = tabMap[pathTab] || new URLSearchParams(window.location.search).get("tab") || "summary";
showTab(tab);

/* ── Allocation Donut ── */
function buildDonut() {{
  var labels = Object.keys(BUCKETS_DATA);
  var values = Object.values(BUCKETS_DATA);
  var colorMap = {{
    "Gold":"#d4a017", "Silver":"#c0c0c0", "Equities":"#34d399", "Crypto":"#818cf8",
    "Cash":"#64748b", "RealEstate":"#06b6d4", "Art":"#e879f9", "ManagedBlend":"#fb923c",
    "RetirementBlend":"#a78bfa", "RealAssets":"#06b6d4"
  }};
  var fallback = ["#f87171","#fbbf24","#2dd4bf","#a3e635","#f472b6"];
  var fi = 0;
  var colors = labels.map(function(l) {{ return colorMap[l] || fallback[fi++ % fallback.length]; }});
  var ctx = document.getElementById("allocation-donut");
  if (!ctx || typeof Chart === "undefined") return;
  new Chart(ctx, {{
    type: "doughnut",
    data: {{
      labels: labels,
      datasets: [{{ data: values, backgroundColor: colors.slice(0, labels.length), borderWidth: 0, hoverBorderWidth: 2, hoverBorderColor: "#fff" }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      cutout: "65%",
      plugins: {{
        legend: {{ position: "right", labels: {{ color: "#94a3b8", font: {{ size: 11, family: "Inter" }}, padding: 12, usePointStyle: true, pointStyle: "circle" }} }},
        tooltip: {{
          backgroundColor: "rgba(9,9,11,0.95)",
          titleColor: "#f1f5f9", bodyColor: "#94a3b8",
          borderColor: "rgba(255,255,255,0.1)", borderWidth: 1,
          padding: 12, cornerRadius: 8,
          callbacks: {{ label: function(c) {{ return c.label + ": $" + c.raw.toLocaleString(undefined,{{maximumFractionDigits:0}}); }} }}
        }}
      }}
    }}
  }});
}}

/* ── Portfolio History Chart ── */
var _histChartType = "line";
function setHistoryChartType(type) {{
  _histChartType = type;
  document.getElementById("hist-line-btn").classList.toggle("active", type === "line");
  document.getElementById("hist-candle-btn").classList.toggle("active", type === "candlestick");
  buildHistoryChart("total");
}}
function buildHistoryChart(metric) {{
  metric = metric || "total";
  var ctx = document.getElementById("history-chart");
  if (window.historyChart) window.historyChart.destroy();

  var labels = PRICE_HISTORY_DATA.map(function(r) {{ return r.date; }});

  if (_histChartType === "candlestick" && PRICE_HISTORY_DATA.length >= 2) {{
    // Candlestick mode using OHLC data with timestamps
    var ohlcData = PRICE_HISTORY_DATA.map(function(r) {{
      return {{
        x: new Date(r.date).getTime(),
        o: r.open || r.total,
        h: r.high || r.total,
        l: r.low || r.total,
        c: r.close || r.total,
      }};
    }});
    window.historyChart = new Chart(ctx, {{
      type: "candlestick",
      data: {{
        datasets: [{{
          label: "Portfolio Value",
          data: ohlcData,
          color: {{
            up: "rgba(52,211,153,1)",
            down: "rgba(248,113,113,1)",
            unchanged: "rgba(148,163,184,1)",
          }},
          borderColor: {{
            up: "rgba(52,211,153,1)",
            down: "rgba(248,113,113,1)",
            unchanged: "rgba(148,163,184,1)",
          }},
        }}]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            yAlign:"bottom", caretPadding:8,
            backgroundColor:"rgba(9,9,11,0.95)", titleColor:"#f1f5f9", bodyColor:"#94a3b8",
            borderColor:"rgba(255,255,255,0.1)", borderWidth:1, padding:12, cornerRadius:8,
            bodyFont: {{ family: "'JetBrains Mono', monospace", size: 11 }},
            callbacks: {{
              label: function(ctx) {{
                var d = ctx.raw;
                return [
                  " O: $" + d.o.toLocaleString(undefined, {{maximumFractionDigits:0}}),
                  " H: $" + d.h.toLocaleString(undefined, {{maximumFractionDigits:0}}),
                  " L: $" + d.l.toLocaleString(undefined, {{maximumFractionDigits:0}}),
                  " C: $" + d.c.toLocaleString(undefined, {{maximumFractionDigits:0}}),
                ];
              }}
            }}
          }}
        }},
        scales: {{
          x: {{ type: "time", time:{{ unit:"day", tooltipFormat:"MMM d, yyyy" }}, ticks:{{ maxTicksLimit:8, color:"#64748b", font:{{size:10}} }}, grid:{{ color:"rgba(255,255,255,0.03)" }} }},
          y: {{ ticks:{{ color:"#64748b", font:{{size:10}}, callback: function(v) {{ return "$" + (v/1000).toFixed(0) + "K"; }} }}, grid:{{ color:"rgba(255,255,255,0.03)" }} }}
        }}
      }}
    }});
  }} else {{
    // Line mode using close/total values with proper time-based x-axis
    var pointData = PRICE_HISTORY_DATA.map(function(r) {{ return {{ x: r.date, y: r.close || r.total }}; }});
    var fmt = function(v) {{ return v != null ? "$" + v.toLocaleString(undefined, {{maximumFractionDigits:0}}) : "—"; }};
    var validData = pointData.filter(function(p) {{ return p.y != null && isFinite(p.y); }});
    var vals = validData.map(function(p) {{ return p.y; }});
    var dataMin = vals.length ? Math.min.apply(null, vals) : 0;
    var dataMax = vals.length ? Math.max.apply(null, vals) : 0;
    var padding = dataMin === dataMax ? Math.max(dataMax * 0.02, 500) : Math.max((dataMax - dataMin) * 0.15, dataMax * 0.005);
    window.historyChart = new Chart(ctx, {{
      type: "line",
      data: {{
        datasets: [{{ label: "Portfolio Value", data: pointData, borderColor: "#d4a017", backgroundColor: "rgba(212,160,23,0.12)", fill: true, tension: 0.35, pointRadius: PRICE_HISTORY_DATA.length < 30 ? 4 : 0, pointHoverRadius: 6, pointHoverBackgroundColor: "#d4a017", pointBackgroundColor: "#d4a017", borderWidth: 2.5 }}]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
      interaction: {{ intersect: false, mode: "nearest", axis: "x" }},
      plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            yAlign:"bottom", caretPadding:8,
            backgroundColor:"rgba(9,9,11,0.95)", titleColor:"#f1f5f9", bodyColor:"#94a3b8",
            borderColor:"rgba(255,255,255,0.1)", borderWidth:1, padding:12, cornerRadius:8,
            bodyFont: {{ family: "'JetBrains Mono', monospace", size: 11 }},
            callbacks: {{
              title: function(items) {{ return items[0] ? items[0].raw.x : ""; }},
              label: function(c) {{
                var r = PRICE_HISTORY_DATA[c.dataIndex];
                if (r && r.open) {{
                  return [
                    " Close: " + fmt(c.raw.y),
                    " Day Range: " + fmt(r.low) + " – " + fmt(r.high),
                  ];
                }}
                return " " + fmt(c.raw.y);
              }}
            }}
          }}
      }},
      scales: {{
          x: {{ type: "time", time: {{ unit: PRICE_HISTORY_DATA.length > 90 ? "week" : "day", tooltipFormat: "yyyy-MM-dd" }}, ticks:{{ maxTicksLimit:8, color:"#64748b", font:{{size:10}} }}, grid:{{ color:"rgba(255,255,255,0.03)" }} }},
          y: {{ min: Math.floor((dataMin - padding) / 1000) * 1000, max: Math.ceil((dataMax + padding) / 1000) * 1000, ticks:{{ color:"#64748b", font:{{size:10}}, callback: function(v) {{ return "$" + (v/1000).toFixed(0) + "K"; }} }}, grid:{{ color:"rgba(255,255,255,0.03)" }} }}
        }}
      }}
    }});
  }}
}}

/* ── Sparklines ── */
function renderSparkCanvas(canvasId, values) {{
  var canvas = document.getElementById(canvasId);
  if (!canvas || !values || values.length < 2) return;
  var ctx = canvas.getContext("2d");
  var w = canvas.width = canvas.offsetWidth * 2;
  var h = canvas.height = canvas.offsetHeight * 2;
  ctx.scale(2, 2);
  var cw = canvas.offsetWidth, ch = canvas.offsetHeight;
  var mn = Math.min.apply(null, values), mx = Math.max.apply(null, values);
  var range = mx - mn || 1;
  var up = values[values.length-1] >= values[0];
  ctx.beginPath();
  ctx.strokeStyle = up ? "#34d399" : "#f87171";
  ctx.lineWidth = 1.5; ctx.lineJoin = "round";
  for (var i = 0; i < values.length; i++) {{
    var x = (i / (values.length - 1)) * cw;
    var y = ch - ((values[i] - mn) / range) * (ch - 4) - 2;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();
  ctx.lineTo(cw, ch); ctx.lineTo(0, ch); ctx.closePath();
  var grad = ctx.createLinearGradient(0, 0, 0, ch);
  grad.addColorStop(0, up ? "rgba(52,211,153,0.15)" : "rgba(248,113,113,0.15)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = grad; ctx.fill();
}}
function loadAllSparklines() {{
  // Dynamically build spark map from all pulse items with spark canvases
  var map = {{}};
  var cryptoSymbols = [];
  document.querySelectorAll(".pulse-spark").forEach(function(c) {{
    var id = c.id;
    if (id) {{
      var sym = id.substring(6); // remove "spark-"
      if (sym.match(/^[A-Z]{{1,3}}-F$/)) sym = sym.replace("-F", "=F");
      var parent = c.closest(".pulse-item");
      var ptype = parent && parent.dataset.pulseType ? parent.dataset.pulseType : "stock";
      map[sym] = id;
      if (ptype === "crypto") cryptoSymbols.push(sym);
    }}
  }});
  if (Object.keys(map).length === 0) return;
  var url = "/api/sparklines?symbols=" + encodeURIComponent(Object.keys(map).join(","));
  if (cryptoSymbols.length) url += "&crypto=" + encodeURIComponent(cryptoSymbols.join(","));
  fetch(url)
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      for (var sym in map) {{
        if (data[sym] && data[sym].length > 1) renderSparkCanvas(map[sym], data[sym]);
      }}
    }})
    .catch(function() {{}});
}}

/* ── Market Charts ── */
var marketChart = null;
function loadMarketChart() {{
  var assetEl = document.getElementById("market-asset");
  if (!assetEl) return;
  var symbol = assetEl.value;
  var period = document.getElementById("market-period").value;
  var chartType = document.getElementById("chart-type").value;
  var scaleType = document.getElementById("chart-scale").value;
  var status = document.getElementById("market-chart-status");
  if (status) status.textContent = "Loading...";
  fetch("/api/historical?symbol=" + encodeURIComponent(symbol) + "&period=" + encodeURIComponent(period))
    .then(function(r) {{ return r.json(); }})
    .then(function(json) {{
      if (json.error) {{ status.textContent = "Error: " + json.error; return; }}
      var ctx = document.getElementById("market-chart");
      if (marketChart) marketChart.destroy();
      var color = symbol.includes("BTC") || symbol.includes("ETH") ? "#f5c842" : "#d4a017";
      var zoomCfg = {{ pan:{{ enabled:true, mode:"xy" }}, zoom:{{ wheel:{{ enabled:true, speed:0.03 }}, pinch:{{ enabled:true }}, mode:"xy" }} }};
      var tooltipCfg = {{ yAlign:"bottom", caretPadding:8, backgroundColor:"rgba(9,9,11,0.95)", titleColor:"#f1f5f9", bodyColor:"#94a3b8", borderColor:"rgba(255,255,255,0.1)", borderWidth:1, padding:12, cornerRadius:8 }};
      if (chartType === "candlestick") {{
        var ohlcData = json.data.map(function(d) {{ return {{ x:new Date(d.date).getTime(), o:d.o, h:d.h, l:d.l, c:d.c }}; }});
      marketChart = new Chart(ctx, {{
          type:"candlestick",
          data:{{ datasets:[{{ label:symbol, data:ohlcData, color:{{ up:"#34d399",down:"#f87171",unchanged:"#64748b" }}, borderColor:{{ up:"#34d399",down:"#f87171",unchanged:"#64748b" }} }}] }},
          options:{{ responsive:true, maintainAspectRatio:false, plugins:{{ legend:{{display:false}}, tooltip:tooltipCfg, zoom:zoomCfg }},
            scales:{{ x:{{ type:"timeseries", time:{{unit:"day"}}, ticks:{{color:"#64748b",font:{{size:10}}}}, grid:{{color:"rgba(255,255,255,0.03)"}} }}, y:{{ type:scaleType, ticks:{{color:"#64748b",font:{{size:10}}}}, grid:{{color:"rgba(255,255,255,0.03)"}} }} }}
          }}
        }});
      }} else {{
        var labels = json.data.map(function(d) {{ return d.date; }});
        var values = json.data.map(function(d) {{ return d.c; }});
        marketChart = new Chart(ctx, {{
          type:"line",
          data:{{ labels:labels, datasets:[{{ label:symbol, data:values, borderColor:color, backgroundColor:color+"12", fill:true, tension:0.3, pointRadius:0, pointHoverRadius:5, pointHoverBackgroundColor:color, borderWidth:2 }}] }},
          options:{{ responsive:true, maintainAspectRatio:false, interaction:{{ intersect:false, mode:"index" }},
            plugins:{{ legend:{{display:false}}, tooltip:Object.assign({{}}, tooltipCfg, {{ callbacks:{{ label:function(c){{ return c.raw!=null ? "$"+c.raw.toLocaleString(undefined,{{minimumFractionDigits:2,maximumFractionDigits:2}}) : "—"; }} }} }}), zoom:zoomCfg }},
            scales:{{ x:{{ ticks:{{maxTicksLimit:10,color:"#64748b",font:{{size:10}}}}, grid:{{color:"rgba(255,255,255,0.03)"}} }}, y:{{ type:scaleType, ticks:{{color:"#64748b",font:{{size:10}}}}, grid:{{color:"rgba(255,255,255,0.03)"}} }} }}
        }}
      }});
      }}
      var first=json.data[0].c, last=json.data[json.data.length-1].c;
      var change = last && first ? ((last-first)/first*100).toFixed(2) : 0;
      var arrow = change>=0 ? "+" : ""; var clr = change>=0 ? "#34d399" : "#f87171";
      status.innerHTML = "<span style='color:"+clr+";font-weight:600;font-family:var(--mono)'>"+arrow+change+"%</span> &middot; Latest: <strong style='font-family:var(--mono)'>$"+last.toLocaleString(undefined,{{minimumFractionDigits:2}})+"</strong>";
    }})
    .catch(function(e) {{ status.textContent = "Error: " + e; }});
}}
function _initMarketChartListeners() {{
  var lmc = document.getElementById("load-market-chart");
  if (lmc && !lmc._bound) {{
    lmc._bound = true;
    lmc.addEventListener("click", loadMarketChart);
    document.getElementById("market-asset").addEventListener("change", loadMarketChart);
    document.getElementById("market-period").addEventListener("change", loadMarketChart);
    document.getElementById("chart-type").addEventListener("change", loadMarketChart);
    document.getElementById("chart-scale").addEventListener("change", loadMarketChart);
    document.getElementById("reset-zoom").addEventListener("click", function() {{ if(marketChart) marketChart.resetZoom(); }});
  }}
}}
_initMarketChartListeners();

/* ── Investment Tracker ── */
function updateProgressBar(input) {{
  var key=input.dataset.key, target=parseFloat(input.dataset.target)||1, contributed=parseFloat(input.value)||0;
  var pct=Math.min((contributed/target)*100,100), diff=contributed-target;
  var bar=document.getElementById("progress-"+key);
  if(bar) {{ bar.style.width=pct+"%"; bar.className="mini-fill "+(pct<40?"low":pct<90?"mid":"done"); }}
  var st=document.getElementById("status-"+key);
  if(st) {{
    if(diff>=0) {{ st.textContent="+$"+diff.toFixed(0); st.className=diff>0?"surplus":"complete"; }}
    else {{ st.textContent="-$"+Math.abs(diff).toFixed(0); st.className="shortage"; }}
  }}
  updateTotals();
}}
function updateTotals() {{
  var tc=0, tt=0;
  document.querySelectorAll(".contrib-input").forEach(function(i) {{ tc+=parseFloat(i.value)||0; tt+=parseFloat(i.dataset.target)||0; }});
  var rem=tt-tc, pct=tt>0?Math.min((tc/tt)*100,100):0;
  var row=document.querySelector(".invest-table tfoot tr");
  if(row) {{
    var cells=row.querySelectorAll("td");
    if(cells[2]) cells[2].innerHTML="<span class='mono' style='color:var(--accent-primary)'>$"+tc.toFixed(0)+"</span>";
    if(cells[3]) cells[3].innerHTML="<span class='mono' style='color:"+(rem>0?"var(--warning)":"var(--success)")+"'>$"+rem.toFixed(0)+" left</span>";
  }}
  var pf=document.getElementById("total-progress-fill"); if(pf) pf.style.width=pct+"%";
  var pl=document.getElementById("total-progress-pct"); if(pl) pl.textContent=Math.round(pct)+"%";
}}
function saveContributions() {{
  var data={{}};
  document.querySelectorAll(".contrib-input").forEach(function(i) {{ data[i.dataset.key]=parseFloat(i.value)||0; }});
  fetch("/api/save-contributions",{{ method:"POST", headers:{{"Content-Type":"application/json"}}, body:JSON.stringify(data) }})
  .then(function(r){{ return r.json(); }})
  .then(function(res){{
    if(res.success) {{
      var btn=document.querySelector("button[onclick*='saveContributions']");
      if(btn) {{ var orig=btn.textContent; btn.textContent="Saved!"; setTimeout(function(){{ btn.textContent=orig; }},1500); }}
    }}
  }});
}}
function newMonth() {{
  if(!confirm("Start a new month? This resets all investment contributions to $0.")) return;
  fetch("/api/new-month",{{method:"POST"}}).then(function(r){{return r.json();}}).then(function(d){{ if(d.success) location.reload(); }});
}}
function newBudgetMonth() {{
  if(!confirm("Start a new budget month? This updates both budget and investment months, and resets contributions.")) return;
  fetch("/api/new-budget-month",{{method:"POST"}}).then(function(r){{return r.json();}}).then(function(d){{ if(d.success) location.reload(); }});
}}
var saveTimeout;
document.querySelectorAll(".contrib-input").forEach(function(input) {{
  input.addEventListener("input", function() {{ updateProgressBar(this); clearTimeout(saveTimeout); saveTimeout=setTimeout(saveContributions,1000); }});
  input.addEventListener("change", function() {{ updateProgressBar(this); clearTimeout(saveTimeout); saveTimeout=setTimeout(saveContributions,500); }});
}});

/* ── Investment Quick-Log Chat ── */
var INVEST_ALIASES = {{
  "gold etf": "gold_etf", "gold": "gold_etf", "gld": "gold_etf", "gldm": "gold_etf", "iau": "gold_etf",
  "gold savings": "gold_phys_save", "gold save": "gold_phys_save", "gold physical": "gold_phys_save", "physical gold": "gold_phys_save",
  "silver etf": "silver_etf", "silver": "silver_etf", "slv": "silver_etf", "pslv": "silver_etf",
  "silver savings": "silver_phys_save", "silver save": "silver_phys_save", "silver physical": "silver_phys_save", "physical silver": "silver_phys_save",
  "crypto": "crypto", "bitcoin": "crypto", "btc": "crypto", "eth": "crypto", "ethereum": "crypto", "coinbase": "crypto",
  "equities": "equities", "stocks": "equities", "stock": "equities", "spy": "equities", "voo": "equities",
  "xar": "equities", "fidelity": "equities", "etf": "equities", "index": "equities",
  "real assets": "real_assets", "real estate": "real_assets", "fundrise": "real_assets", "masterworks": "real_assets", "art": "real_assets",
  "cash": "cash", "cash reserve": "cash", "savings": "cash", "emergency": "cash",
  "stash": "equities", "stash personal": "equities", "stash smart": "equities",
  "stash retirement": "equities", "retirement": "equities", "401k": "equities", "ira": "equities",
  "acorns": "equities", "acorns invest": "equities", "acorns later": "equities",
}};
var INVEST_NAMES = {{
  "gold_etf": "Gold ETF", "gold_phys_save": "Gold Savings",
  "silver_etf": "Silver ETF", "silver_phys_save": "Silver Savings",
  "crypto": "Crypto", "equities": "Equities",
  "real_assets": "Real Assets", "cash": "Cash Reserve",
}};
function matchCategory(text) {{
  var t = text.toLowerCase().trim();
  // Exact match first
  if (INVEST_ALIASES[t]) return INVEST_ALIASES[t];
  // Partial match
  for (var alias in INVEST_ALIASES) {{
    if (t.indexOf(alias) !== -1 || alias.indexOf(t) !== -1) return INVEST_ALIASES[alias];
  }}
  // Fuzzy: check each word
  var words = t.split(/\s+/);
  for (var w = 0; w < words.length; w++) {{
    if (INVEST_ALIASES[words[w]]) return INVEST_ALIASES[words[w]];
  }}
  return null;
}}
function processInvestChat() {{
  var input = document.getElementById("invest-chat-input");
  var log = document.getElementById("chat-log");
  var raw = input.value.trim();
  if (!raw) return;

  // Split by comma for multiple entries
  var entries = raw.split(",");
  var results = [];
  var hasMetalEntry = false;
  var hasContribEntry = false;
  entries.forEach(function(entry) {{
    entry = entry.trim();
    if (!entry) return;

    // ── Physical metals purchase detection ──
    // Patterns: "bought 5oz silver at $31", "bought 1oz gold for $2700",
    //           "added 10oz silver bar", "5oz gold at $2800"
    var metalMatch = entry.match(/(?:bought|added|purchased|buy)?\s*(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)\s+(?:of\s+)?(gold|silver)(?:\s+([\w\s]+?))?(?:\s+(?:at|for|@)\s+\$?\s*(\d+(?:\.\d{{1,2}})?))?/i);
    if (!metalMatch) {{
      // Also try: "gold 5oz at $2800"
      metalMatch = entry.match(/(?:bought|added|purchased|buy)?\s*(gold|silver)\s+(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces)(?:\s+([\w\s]+?))?(?:\s+(?:at|for|@)\s+\$?\s*(\d+(?:\.\d{{1,2}})?))?/i);
      if (metalMatch) {{
        // Rearrange so [1]=qty, [2]=metal, [3]=form, [4]=price
        var _m = metalMatch;
        metalMatch = [_m[0], _m[2], _m[1], _m[3], _m[4]];
      }}
    }}
    if (metalMatch) {{
      var mQty = parseFloat(metalMatch[1]);
      var mMetal = metalMatch[2].charAt(0).toUpperCase() + metalMatch[2].slice(1).toLowerCase();
      var mForm = (metalMatch[3] || "").trim();
      var mCost = metalMatch[4] ? parseFloat(metalMatch[4]) : 0;
      if (mQty <= 0) {{
        results.push({{ ok: false, msg: "Quantity must be > 0" }});
        return;
      }}
      // POST to physical metals API
      fetch("/api/physical-metals", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ metal: mMetal, form: mForm, qty_oz: mQty, cost_per_oz: mCost, date: "", note: "Logged via chat" }})
      }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
        var div = document.createElement("div");
        if (d.ok) {{
          var priceNote = mCost > 0 ? " at $" + mCost.toFixed(2) + "/oz" : "";
          div.className = "chat-msg ok";
          div.innerHTML = '<span class="chat-label">&#10003;</span>Logged ' + mQty + 'oz ' + mMetal + priceNote;
        }} else {{
          div.className = "chat-msg err";
          div.innerHTML = '<span class="chat-label">&#10007;</span>' + (d.error || "Error saving metal");
        }}
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
      }}).catch(function() {{
        var div = document.createElement("div");
        div.className = "chat-msg err";
        div.innerHTML = '<span class="chat-label">&#10007;</span>Network error saving metal';
        log.appendChild(div);
      }});
      hasMetalEntry = true;
      return;  // Don't process as contribution
    }}

    // ── Normal contribution + holdings/balance processing ──
    // Extract dollar amount: $100, 100, etc.
    var amountMatch = entry.match(/\$?\s*(\d+(?:\.\d{{1,2}})?)/);
    if (!amountMatch) {{
      results.push({{ ok: false, msg: 'No amount found in "' + entry + '"' }});
      return;
    }}
    var amount = parseFloat(amountMatch[1]);
    // Remove the amount portion to get the category text
    var catText = entry.replace(amountMatch[0], "").replace(/^\s*to\s+/i, "").replace(/\s*to\s*$/i, "").trim();
    catText = catText.replace(/^to\s+/i, "").replace(/^add\s+/i, "").trim();
    if (!catText) {{
      results.push({{ ok: false, msg: 'No category found in "' + entry + '"' }});
      return;
    }}
    // Parse optional "in [account]" suffix: "100 to pslv in fidelity"
    var acctMatch = catText.match(/^(.+?)\s+(?:in|at|for)\s+(.+)$/i);
    var rawTarget = acctMatch ? acctMatch[1].trim() : catText;
    var acctHint = acctMatch ? acctMatch[2].trim() : "";

    // Try contribution category match
    var key = matchCategory(rawTarget);
    if (key) {{
      var field = document.querySelector('.contrib-input[data-key="' + key + '"]');
      if (field) {{
        var oldVal = parseFloat(field.value) || 0;
        var newVal = oldVal + amount;
        field.value = Math.round(newVal);
        updateProgressBar(field);
        hasContribEntry = true;
        results.push({{ ok: true, msg: '+$' + amount.toFixed(0) + ' to ' + INVEST_NAMES[key] + ' (now $' + Math.round(newVal) + ')' }});
      }}
    }}

    // Also try to update holdings/balances via quick-update API
    // (rawTarget could be a ticker like PSLV, or a balance account like Fundrise)
    fetch("/api/quick-update", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ amount: amount, target: rawTarget, account: acctHint }})
    }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
      var div = document.createElement("div");
      if (d.ok && d.type === "holding") {{
        div.className = "chat-msg ok";
        var sharesNote = d.shares_added ? ' (+' + d.shares_added + ' shares @ $' + d.price.toFixed(2) + ')' : '';
        var cashNote = d.cash_deducted ? ' | SPAXX: $' + d.old_cash.toLocaleString(undefined, {{maximumFractionDigits:0}}) + ' &rarr; $' + d.new_cash.toLocaleString(undefined, {{maximumFractionDigits:0}}) : '';
        div.innerHTML = '<span class="chat-label">&#10003;</span>' + d.ticker + (d.account ? ' (' + d.account + ')' : '') + ': $' + d.old_value.toLocaleString(undefined, {{maximumFractionDigits:0}}) + ' &rarr; $' + d.new_value.toLocaleString(undefined, {{maximumFractionDigits:0}}) + sharesNote + cashNote;
        log.appendChild(div);
      }} else if (d.ok && d.type === "balance") {{
        div.className = "chat-msg ok";
        div.innerHTML = '<span class="chat-label">&#10003;</span>' + d.name + ': $' + d.old_value.toLocaleString(undefined, {{maximumFractionDigits:0}}) + ' &rarr; $' + d.new_value.toLocaleString(undefined, {{maximumFractionDigits:0}});
        log.appendChild(div);
      }} else if (!key) {{
        // Only show error if we also failed the contribution match
        div.className = "chat-msg err";
        div.innerHTML = '<span class="chat-label">&#10007;</span>No match for "' + rawTarget + '" in contributions, holdings, or balances';
        log.appendChild(div);
      }}
      log.scrollTop = log.scrollHeight;
    }}).catch(function() {{}});
  }});

  // Render results in chat log
  results.forEach(function(r) {{
    var div = document.createElement("div");
    div.className = "chat-msg " + (r.ok ? "ok" : "err");
    div.innerHTML = '<span class="chat-label">' + (r.ok ? "&#10003;" : "&#10007;") + '</span>' + r.msg;
    log.appendChild(div);
  }});
  log.scrollTop = log.scrollHeight;

  // Clear input and auto-save contributions if any
  input.value = "";
  if (hasContribEntry && results.some(function(r) {{ return r.ok; }})) {{
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveContributions, 500);
    updateTotals();
  }}
}}
// Allow Enter key to submit
document.getElementById("invest-chat-input").addEventListener("keydown", function(e) {{
  if (e.key === "Enter") {{ e.preventDefault(); processInvestChat(); }}
}});

/* ── Pulse Card Drag & Drop + Add/Remove ── */
(function() {{
  var bar = document.getElementById("pulse-bar");
  if (!bar) return;
  var pulseDragSrc = null;

  function setupPulseDrag() {{
    bar.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {{
      item.addEventListener("dragstart", function(e) {{
        pulseDragSrc = item;
        item.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", item.dataset.pulseId);
      }});
      item.addEventListener("dragend", function() {{
        item.classList.remove("dragging");
        bar.querySelectorAll(".drag-over").forEach(function(el) {{ el.classList.remove("drag-over"); }});
        pulseDragSrc = null;
      }});
      item.addEventListener("dragover", function(e) {{
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (item !== pulseDragSrc && !item.classList.contains("pulse-add")) item.classList.add("drag-over");
      }});
      item.addEventListener("dragleave", function() {{ item.classList.remove("drag-over"); }});
      item.addEventListener("drop", function(e) {{
        e.preventDefault();
        item.classList.remove("drag-over");
        if (!pulseDragSrc || pulseDragSrc === item || item.classList.contains("pulse-add")) return;
        // Insert before or after based on position
        var rect = item.getBoundingClientRect();
        var midX = rect.left + rect.width / 2;
        if (e.clientX < midX) {{
          bar.insertBefore(pulseDragSrc, item);
        }} else {{
          bar.insertBefore(pulseDragSrc, item.nextSibling);
        }}
        savePulseOrder();
      }});
    }});
  }}

  function savePulseOrder() {{
    var order = [];
    bar.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {{
      order.push(item.dataset.pulseId);
    }});
    fetch("/api/pulse-order", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ order: order }})
    }});
  }}

  setupPulseDrag();
  window._setupPulseDrag = setupPulseDrag;
}})();

function showAddPulseCard() {{
  var modal = document.getElementById("pulse-add-modal");
  modal.style.display = "flex";
  document.getElementById("pulse-add-ticker").value = "";
  document.getElementById("pulse-add-label").value = "";
  document.getElementById("pulse-add-ticker").focus();
}}
function hideAddPulseCard() {{
  document.getElementById("pulse-add-modal").style.display = "none";
}}
function addPulseCard() {{
  var ticker = document.getElementById("pulse-add-ticker").value.trim().toUpperCase();
  var label = document.getElementById("pulse-add-label").value.trim() || ticker;
  var ptype = (document.getElementById("pulse-add-type") || {{}}).value || "stock";
  if (!ticker) return alert("Please enter a ticker symbol.");
  fetch("/api/pulse-cards", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ ticker: ticker, label: label, type: ptype }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.success) location.reload();
    else alert(d.error || "Failed to add ticker.");
  }});
}}
function removePulseCard(id) {{
  if (!confirm("Remove this card from the pulse bar?")) return;
  fetch("/api/pulse-cards/" + encodeURIComponent(id), {{ method: "DELETE" }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ if (d.success) location.reload(); }});
}}
function restoreAllPulseCards() {{
  fetch("/api/pulse-cards/restore-all", {{ method: "POST" }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ if (d.success) location.reload(); }});
}}

/* ── Pulse Chart Modal ── */
(function() {{
  var PCM_SYMBOL_MAP = {{
    "gold": "GC=F", "silver": "SI=F", "au_ag": "AUAG-RATIO",
    "dxy": "DX-Y.NYB", "vix": "^VIX", "oil": "CL=F", "copper": "HG=F",
    "tnx_10y": "^TNX", "tnx_2y": "^IRX", "btc": "BTC", "spy": "SPY"
  }};
  var pcmChart = null;
  var pcmPollId = null;
  var pcmState = {{ symbol: "", label: "", type: "stock", period: "1d", interval: "1m", chartType: "line" }};

  function pcmResolveSymbol(pulseId, pulseType) {{
    if (PCM_SYMBOL_MAP[pulseId]) return {{ sym: PCM_SYMBOL_MAP[pulseId], type: pulseId === "btc" ? "crypto" : "stock" }};
    if (pulseId.startsWith("custom-")) {{
      var ticker = pulseId.substring(7);
      return {{ sym: ticker, type: pulseType || "stock" }};
    }}
    return {{ sym: pulseId, type: pulseType || "stock" }};
  }}

  function openPulseChart(pulseId, label, pulseType) {{
    var resolved = pcmResolveSymbol(pulseId, pulseType);
    pcmState.symbol = resolved.sym;
    pcmState.type = resolved.type;
    pcmState.label = label;
    pcmState.period = "1d";
    pcmState.interval = "1m";
    pcmState.chartType = "line";
    document.getElementById("pcm-title").textContent = label;
    document.getElementById("pcm-price").textContent = "";
    document.getElementById("pcm-type-toggle").textContent = "Candlestick";
    var pills = document.querySelectorAll(".pcm-pill");
    pills.forEach(function(p) {{ p.classList.remove("active"); }});
    if (pills.length > 0) pills[0].classList.add("active");
    document.getElementById("pcm-overlay").classList.add("active");
    document.body.style.overflow = "hidden";
    loadPulseChart();
    startPcmPoll();
  }}
  window.openPulseChart = openPulseChart;

  function closePulseChart() {{
    document.getElementById("pcm-overlay").classList.remove("active");
    document.body.style.overflow = "";
    stopPcmPoll();
    if (pcmChart) {{ pcmChart.destroy(); pcmChart = null; }}
  }}
  window.closePulseChart = closePulseChart;

  function togglePcmChartType() {{
    var btn = document.getElementById("pcm-type-toggle");
    if (pcmState.chartType === "line") {{
      pcmState.chartType = "candlestick";
      btn.textContent = "Line";
    }} else {{
      pcmState.chartType = "line";
      btn.textContent = "Candlestick";
    }}
    loadPulseChart();
  }}
  window.togglePcmChartType = togglePcmChartType;

  function startPcmPoll() {{
    stopPcmPoll();
    if (pcmState.period === "1d") {{
      pcmPollId = setInterval(function() {{
        if (document.getElementById("pcm-overlay").classList.contains("active")) loadPulseChart(true);
        else stopPcmPoll();
      }}, 60000);
    }}
  }}

  function stopPcmPoll() {{
    if (pcmPollId) {{ clearInterval(pcmPollId); pcmPollId = null; }}
  }}

  function loadPulseChart(silent) {{
    var spinner = document.getElementById("pcm-spinner");
    if (!silent) spinner.classList.add("show");
    var url = "/api/historical?symbol=" + encodeURIComponent(pcmState.symbol)
      + "&period=" + pcmState.period
      + "&interval=" + pcmState.interval
      + "&type=" + pcmState.type;
    fetch(url).then(function(r) {{ return r.json(); }}).then(function(resp) {{
      spinner.classList.remove("show");
      if (resp.error || !resp.data || resp.data.length === 0) {{
        if (pcmChart) {{ pcmChart.destroy(); pcmChart = null; }}
        document.getElementById("pcm-price").textContent = "(no data)";
        return;
      }}
      var d = resp.data;
      var lastPrice = d[d.length - 1].c;
      var firstPrice = d[0].o || d[0].c;
      var chg = lastPrice - firstPrice;
      var chgPct = firstPrice ? ((chg / firstPrice) * 100) : 0;
      var sign = chg >= 0 ? "+" : "";
      var noDollar = ["AUAG-RATIO","^VIX","^TNX","^IRX","10Y2Y-SPREAD","DX-Y.NYB"].indexOf(pcmState.symbol) >= 0;
      var prefix = noDollar ? "" : "$";
      document.getElementById("pcm-price").textContent = prefix + lastPrice.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}})
        + "  " + sign + chg.toFixed(2) + " (" + sign + chgPct.toFixed(2) + "%)";
      document.getElementById("pcm-price").style.color = chg >= 0 ? "var(--accent-green, #22c55e)" : "var(--danger, #ef4444)";
      renderPcmChart(d);
    }}).catch(function() {{
      spinner.classList.remove("show");
    }});
  }}

  function renderPcmChart(data) {{
    var canvas = document.getElementById("pcm-canvas");
    if (pcmChart) {{ pcmChart.destroy(); pcmChart = null; }}
    var isIntraday = pcmState.interval && ["1m","2m","5m","15m","30m","60m","1h"].indexOf(pcmState.interval) >= 0;
    var timeUnit = "day";
    if (isIntraday) timeUnit = "minute";
    else if (["1wk"].indexOf(pcmState.interval) >= 0) timeUnit = "week";
    else if (["1mo"].indexOf(pcmState.interval) >= 0) timeUnit = "month";

    if (pcmState.chartType === "candlestick") {{
      var candles = data.map(function(p) {{
        return {{ x: new Date(p.date).getTime(), o: p.o, h: p.h, l: p.l, c: p.c }};
      }});
      var candleXScale = isIntraday
        ? {{ type: "timeseries", time: {{ unit: timeUnit }}, grid: {{ color: "rgba(255,255,255,0.04)" }}, ticks: {{ color: "rgba(255,255,255,0.5)", maxTicksLimit: 10 }} }}
        : {{ type: "time", time: {{ unit: timeUnit, tooltipFormat: "MMM d, yyyy" }}, grid: {{ color: "rgba(255,255,255,0.04)" }}, ticks: {{ color: "rgba(255,255,255,0.5)", maxTicksLimit: 10 }} }};
      pcmChart = new Chart(canvas.getContext("2d"), {{
        type: "candlestick",
        data: {{ datasets: [{{
          label: pcmState.label,
          data: candles,
          color: {{ up: "rgba(34,197,94,0.9)", down: "rgba(239,68,68,0.9)", unchanged: "rgba(100,116,139,0.8)" }},
          borderColor: {{ up: "rgba(34,197,94,1)", down: "rgba(239,68,68,1)", unchanged: "rgba(100,116,139,1)" }}
        }}] }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          scales: {{
            x: candleXScale,
            y: {{ position: "right", grid: {{ color: "rgba(255,255,255,0.04)" }}, ticks: {{ color: "rgba(255,255,255,0.5)" }} }}
          }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{ yAlign: "bottom", caretPadding: 8, backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0", borderColor: "rgba(99,102,241,0.4)", borderWidth: 1 }}
          }}
        }}
      }});
    }} else {{
      var closes = data.map(function(p) {{ return p.c; }});
      var first = closes[0]; var last = closes[closes.length - 1];
      var lineColor = last >= first ? "rgba(34,197,94,0.9)" : "rgba(239,68,68,0.9)";
      var fillColor = last >= first ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)";

      // Intraday: even spacing (no gaps for closed hours), show simplified tick labels
      // Daily+: proportional time axis so weekends/holidays show proper gaps
      var xScale, chartData;
      if (isIntraday) {{
        // Format labels: show date at session boundaries, time otherwise
        var tickLabels = data.map(function(p, i) {{
          var dt = new Date(p.date);
          var prev = i > 0 ? new Date(data[i-1].date) : null;
          if (!prev || dt.toDateString() !== prev.toDateString()) {{
            return dt.toLocaleDateString(undefined, {{month:"short", day:"numeric"}});
          }}
          return "";
        }});
        xScale = {{ type: "category", labels: tickLabels,
          grid: {{ color: "rgba(255,255,255,0.04)" }},
          ticks: {{ color: "rgba(255,255,255,0.5)", maxTicksLimit: 8, autoSkip: true, maxRotation: 0 }}
        }};
        chartData = {{ labels: tickLabels, datasets: [{{
          label: pcmState.label, data: closes,
          borderColor: lineColor, backgroundColor: fillColor,
          borderWidth: 2, pointRadius: 0, pointHitRadius: 8,
          fill: true, tension: 0.15
        }}] }};
      }} else {{
        var pointData = data.map(function(p) {{ return {{ x: p.date, y: p.c }}; }});
        xScale = {{ type: "time", time: {{ unit: timeUnit, tooltipFormat: "MMM d, yyyy" }},
          grid: {{ color: "rgba(255,255,255,0.04)" }},
          ticks: {{ color: "rgba(255,255,255,0.5)", maxTicksLimit: 8 }}
        }};
        chartData = {{ datasets: [{{
          label: pcmState.label, data: pointData,
          borderColor: lineColor, backgroundColor: fillColor,
          borderWidth: 2, pointRadius: 0, pointHitRadius: 8,
          fill: true, tension: 0.15
        }}] }};
      }}

      pcmChart = new Chart(canvas.getContext("2d"), {{
        type: "line",
        data: chartData,
        options: {{
          responsive: true, maintainAspectRatio: false,
          interaction: {{ mode: "nearest", axis: "x", intersect: false }},
          scales: {{
            x: xScale,
            y: {{ position: "right", grid: {{ color: "rgba(255,255,255,0.04)" }}, ticks: {{ color: "rgba(255,255,255,0.5)" }} }}
          }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              yAlign: "bottom", caretPadding: 8,
              backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0",
              borderColor: "rgba(99,102,241,0.4)", borderWidth: 1,
              callbacks: {{
                title: function(items) {{
                  var idx = items[0] ? items[0].dataIndex : 0;
                  var p = data[idx];
                  if (!p) return "";
                  var dt = new Date(p.date);
                  return isIntraday ? dt.toLocaleString(undefined, {{month:"short", day:"numeric", hour:"numeric", minute:"2-digit"}}) : p.date;
                }},
                label: function(ctx) {{
                  var noDollar = ["AUAG-RATIO","^VIX","^TNX","^IRX","10Y2Y-SPREAD","DX-Y.NYB"].indexOf(pcmState.symbol) >= 0;
                  var prefix = noDollar ? "" : "$";
                  var val = isIntraday ? ctx.raw : ctx.raw.y;
                  return pcmState.label + ": " + prefix + Number(val).toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
                }}
              }}
            }},
            crosshair: false
          }}
        }}
      }});
    }}
  }}

  // Timescale pill click handlers
  document.getElementById("pcm-controls").addEventListener("click", function(e) {{
    var pill = e.target.closest(".pcm-pill");
    if (!pill) return;
    document.querySelectorAll(".pcm-pill").forEach(function(p) {{ p.classList.remove("active"); }});
    pill.classList.add("active");
    pcmState.period = pill.dataset.pcmP;
    pcmState.interval = pill.dataset.pcmI;
    stopPcmPoll();
    loadPulseChart();
    startPcmPoll();
  }});

  // Attach click handlers to all pulse items (guard against drag)
  var pcmDragHappened = false;
  document.querySelectorAll(".pulse-item:not(.pulse-add)").forEach(function(item) {{
    item.addEventListener("dragstart", function() {{ pcmDragHappened = true; }});
    item.addEventListener("click", function(e) {{
      if (e.target.closest(".pulse-remove")) return;
      if (pcmDragHappened) {{ pcmDragHappened = false; return; }}
      var pid = item.dataset.pulseId;
      var label = item.querySelector(".pulse-label") ? item.querySelector(".pulse-label").textContent : pid;
      var ptype = item.dataset.pulseType || "stock";
      openPulseChart(pid, label, ptype);
    }});
    item.style.cursor = "pointer";
  }});

  // Close on Escape key
  document.addEventListener("keydown", function(e) {{
    if (e.key === "Escape" && document.getElementById("pcm-overlay").classList.contains("active")) {{
      closePulseChart();
    }}
  }});
}})();

/* ── Init on load ── */
buildDonut();
if (PRICE_HISTORY_DATA.length > 0) buildHistoryChart("total");
setTimeout(loadAllSparklines, 300);
var toast = document.getElementById("toast-msg");
if (toast) setTimeout(function() {{ toast.style.display="none"; }}, 4000);

/* ── Auto-Refresh Settings ── */
function toggleAutoRefreshSettings() {{
  var pop = document.getElementById("auto-refresh-popover");
  pop.style.display = pop.style.display === "none" ? "block" : "none";
}}
function saveAutoRefresh() {{
  var enabled = document.getElementById("auto-enabled").checked;
  var interval = parseInt(document.getElementById("auto-interval").value);
  fetch("/api/auto-refresh", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ enabled: enabled, interval_minutes: interval }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    var dot = document.getElementById("auto-dot");
    var label = document.getElementById("auto-label");
    dot.className = "auto-dot " + (enabled ? "on" : "off");
    label.textContent = interval + "m";
    var t = document.createElement("div");
    t.className = "toast";
    t.style.background = "rgba(52,211,153,0.15)";
    t.style.color = "var(--success)";
    t.textContent = "Auto-refresh saved";
    document.body.appendChild(t);
    setTimeout(function() {{ t.remove(); }}, 2500);
    if (window._periodicPollInterval) clearInterval(window._periodicPollInterval);
    if (enabled && interval >= 5) startPeriodicLivePoll(interval);
  }}).catch(function() {{
    var t = document.createElement("div");
    t.className = "toast";
    t.style.background = "rgba(248,113,113,0.15)";
    t.style.color = "var(--danger)";
    t.textContent = "Failed to save auto-refresh";
    document.body.appendChild(t);
    setTimeout(function() {{ t.remove(); }}, 3500);
  }});
}}
// Close popover when clicking outside
document.addEventListener("click", function(e) {{
  var pop = document.getElementById("auto-refresh-popover");
  var ind = document.getElementById("auto-refresh-indicator");
  if (pop && ind && !pop.contains(e.target) && !ind.contains(e.target)) {{
    pop.style.display = "none";
  }}
}});

function applyLiveDataToDOM(d) {{
  if (!d || !d.total || d.total <= 0) return;
  // Update "last refresh" timestamp
  var ts = document.getElementById("last-refresh-time");
  if (ts) {{
    var now = new Date();
    var opts = {{ year:"numeric", month:"long", day:"numeric", hour:"numeric", minute:"2-digit", hour12:true }};
    ts.textContent = now.toLocaleDateString("en-US", opts);
  }}
  var fxRate = (typeof BASE_CURRENCY !== "undefined" && BASE_CURRENCY !== "USD" && typeof FX_RATES !== "undefined" && FX_RATES[BASE_CURRENCY]) ? FX_RATES[BASE_CURRENCY] : 1;
  var sym = (typeof CURRENCY_SYMBOLS !== "undefined" && BASE_CURRENCY !== "USD" && CURRENCY_SYMBOLS[BASE_CURRENCY]) ? CURRENCY_SYMBOLS[BASE_CURRENCY] : "$";
  var nw = document.getElementById("net-worth-counter");
  if (nw) {{ nw.dataset.target = d.total; nw.textContent = sym + (d.total * fxRate).toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}}); }}
  var heroChange = document.getElementById("hero-change-badge");
  if (heroChange && typeof d.daily_change === "number" && typeof d.daily_change_pct === "number") {{
    var dc = d.daily_change;
    var sign = dc >= 0 ? "+" : "";
    heroChange.textContent = sign + "$" + Math.abs(dc).toLocaleString(undefined, {{maximumFractionDigits:0}}) + " (" + sign + d.daily_change_pct.toFixed(1) + "%)";
    heroChange.className = "hero-change " + (dc >= 0 ? "pos" : "neg");
  }}
  var pulseMap = {{
    "gold": {{val: d.gold, fmt: "dollar0"}},
    "silver": {{val: d.silver, fmt: "dollar2"}},
    "au_ag": {{val: d.gold_silver_ratio, fmt: "raw2"}},
    "btc": {{val: d.btc, fmt: "dollar0"}},
    "spy": {{val: d.spy, fmt: "dollar2"}},
    "dxy": {{val: d.dxy, fmt: "nodollar2"}},
    "vix": {{val: d.vix, fmt: "nodollar2"}},
    "oil": {{val: d.oil, fmt: "dollar2"}},
    "copper": {{val: d.copper, fmt: "dollar2"}},
    "tnx_10y": {{val: d.tnx_10y, fmt: "pct"}},
    "tnx_2y": {{val: d.tnx_2y, fmt: "pct"}}
  }};
  for (var dKey in d) {{
    if (dKey.indexOf("custom_") === 0 && d[dKey]) {{
      pulseMap[dKey.replace("_", "-")] = {{val: d[dKey], fmt: "dollar2"}};
    }}
  }}
  document.querySelectorAll("[data-pulse-price]").forEach(function(el) {{
    var pid = el.getAttribute("data-pulse-price");
    var entry = pulseMap[pid];
    if (!entry || !entry.val) return;
    var v = entry.val;
    if (entry.fmt === "dollar0") el.textContent = "$" + v.toLocaleString(undefined, {{minimumFractionDigits:0, maximumFractionDigits:0}});
    else if (entry.fmt === "dollar2") el.textContent = "$" + v.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
    else if (entry.fmt === "nodollar2") el.textContent = v.toFixed(2);
    else if (entry.fmt === "pct") el.textContent = v.toFixed(2) + "%";
    else if (entry.fmt === "raw2") el.textContent = v.toFixed(2);
  }});
  // Update physical metals spot prices on holdings page
  var spotCells = document.querySelectorAll(".metal-spot-cell");
  spotCells.forEach(function(cell) {{
    var metal = cell.getAttribute("data-metal-spot");
    var newSpot = (metal === "gold") ? d.gold : d.silver;
    if (!newSpot || newSpot <= 0) return;
    cell.textContent = "$" + newSpot.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
    // Update value cell (next sibling) and G/L cell
    var qty = parseFloat(cell.getAttribute("data-metal-qty")) || 0;
    var cost = parseFloat(cell.getAttribute("data-metal-cost")) || 0;
    var valCell = cell.nextElementSibling;
    if (valCell) {{
      var newVal = qty * newSpot;
      valCell.textContent = "$" + newVal.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
      var glCell = valCell.nextElementSibling;
      if (glCell && cost > 0) {{
        var gl = newVal - (qty * cost);
        glCell.textContent = (gl >= 0 ? "$+" : "$") + gl.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
        glCell.style.color = gl >= 0 ? "var(--success)" : "var(--danger)";
      }}
    }}
  }});
}}
function startPeriodicLivePoll(intervalMin) {{
  if (window._periodicPollInterval) clearInterval(window._periodicPollInterval);
  var ms = Math.max(5, intervalMin) * 60 * 1000;
  window._periodicPollInterval = setInterval(function() {{
    fetch("/api/live-data").then(function(r) {{ return r.json(); }}).then(applyLiveDataToDOM).catch(function() {{}});
  }}, ms);
}}

/* ── Phase 1: Theme Toggle ── */
function toggleTheme() {{
  document.documentElement.classList.toggle("light");
  var isLight = document.documentElement.classList.contains("light");
  localStorage.setItem("wos-theme", isLight ? "light" : "dark");
  var icon = document.getElementById("theme-icon");
  if (icon) icon.innerHTML = isLight
    ? '<path d="M21 12.79A9 9 0 1111.21 3a7 7 0 009.79 9.79z"/>'
    : '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
  // Rebuild charts for theme
  if (window.historyChart) buildHistoryChart("total");
}}
if (localStorage.getItem("wos-theme") === "light") {{ document.documentElement.classList.add("light"); }}

/* ── Phase 1: Command Palette (Ctrl+K) ── */
var cmdItems = [
  {{ label:"Summary", tab:"summary", keys:"" }},
  {{ label:"Balances", tab:"balances", keys:"" }},
  {{ label:"Budget", tab:"budget", keys:"" }},
  {{ label:"Holdings", tab:"holdings", keys:"" }},
  {{ label:"Import CSV", tab:"import", keys:"" }},
  {{ label:"Market Charts", tab:"history", keys:"" }},
  {{ label:"Economics", tab:"economics", keys:"" }},
  {{ label:"Refresh Prices", action:"refresh", keys:"" }},
];
// Add holdings as searchable items
{holdings_tickers_json}.forEach(function(t) {{
  if (t) cmdItems.push({{ label:t + " (holding)", tab:"holdings", keys:t }});
}});
var cmdActive = 0;
function openCmd() {{
  var o = document.getElementById("cmd-overlay");
  o.classList.add("open");
  var inp = document.getElementById("cmd-input");
  inp.value = ""; inp.focus();
  filterCmd("");
}}
function closeCmd() {{ document.getElementById("cmd-overlay").classList.remove("open"); }}
function filterCmd(q) {{
  q = q.toLowerCase();
  var results = cmdItems.filter(function(i) {{ return !q || i.label.toLowerCase().includes(q) || i.keys.toLowerCase().includes(q); }});
  var container = document.getElementById("cmd-results");
  cmdActive = 0;
  container.innerHTML = results.slice(0,8).map(function(r,i) {{
    return '<div class="cmd-result'+(i===0?' active':'')+'" data-idx="'+i+'" onclick="execCmd('+i+')">'+r.label+'</div>';
  }}).join("");
  window._cmdFiltered = results.slice(0,8);
}}
function execCmd(i) {{
  var item = window._cmdFiltered[i];
  if (!item) return;
  closeCmd();
  if (item.action === "refresh") {{ document.querySelector(".refresh-btn").closest("form").submit(); return; }}
  if (item.tab) showTab(item.tab);
}}
document.getElementById("cmd-input").addEventListener("input", function() {{ filterCmd(this.value); }});
document.getElementById("cmd-input").addEventListener("keydown", function(e) {{
  var items = document.querySelectorAll(".cmd-result");
  if (e.key === "ArrowDown") {{ e.preventDefault(); cmdActive = Math.min(cmdActive+1, items.length-1); items.forEach(function(el,i){{ el.classList.toggle("active",i===cmdActive); }}); }}
  else if (e.key === "ArrowUp") {{ e.preventDefault(); cmdActive = Math.max(cmdActive-1, 0); items.forEach(function(el,i){{ el.classList.toggle("active",i===cmdActive); }}); }}
  else if (e.key === "Enter") {{ e.preventDefault(); execCmd(cmdActive); }}
  else if (e.key === "Escape") {{ closeCmd(); }}
}});
document.getElementById("cmd-overlay").addEventListener("click", function(e) {{ if(e.target===this) closeCmd(); }});
document.addEventListener("keydown", function(e) {{
  if ((e.ctrlKey||e.metaKey) && e.key==="k") {{ e.preventDefault(); openCmd(); }}
  else if (e.key==="Escape") closeCmd();
}});

/* ── Phase 1: Keyboard Shortcuts ── */
document.addEventListener("keydown", function(e) {{
  if (document.getElementById("cmd-overlay").classList.contains("open")) return;
  if (e.target.tagName==="INPUT"||e.target.tagName==="SELECT"||e.target.tagName==="TEXTAREA") return;
  if (e.key==="1") showTab("summary");
  else if (e.key==="2") showTab("balances");
  else if (e.key==="3") showTab("budget");
  else if (e.key==="4") showTab("holdings");
  else if (e.key==="5") showTab("import");
  else if (e.key==="6") showTab("history");
  else if (e.key==="r"&&!e.ctrlKey) {{ document.querySelector(".refresh-btn").closest("form").submit(); }}
}});

/* ── Phase 2: Transaction Tracking ── */
var TRANSACTIONS = [];
var BUDGET_LIMITS = {{}};
var BUDGET_CATS = [];
/* ── Debt Tracker ── */
function addDebtRow() {{
  var tbody = document.getElementById("debt-tbody");
  var idx = tbody.querySelectorAll("tr").length;
  var row = document.createElement("tr");
  row.innerHTML = '<td><input type="text" name="debt_name_' + idx + '" value="" placeholder="e.g. Student Loan" style="width:100%;border:none;background:transparent;color:var(--text-primary);font-size:0.85rem;"></td>'
    + '<td><input type="text" name="debt_bal_' + idx + '" value="0.00" class="num"></td>'
    + '<td><input type="text" name="debt_pmt_' + idx + '" value="0.00" class="num"></td>'
    + '<td class="mono hint" style="text-align:center;">\u2014</td>'
    + '<td><button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;color:var(--danger);">x</button></td>';
  tbody.appendChild(row);
  row.querySelector("button").addEventListener("click", function() {{ this.closest("tr").remove(); }});
  row.querySelector("input").focus();
}}
function removeDebt(idx) {{
  // Submit form with that row removed — we mark it for deletion
  var row = document.getElementById("debt-tbody").querySelectorAll("tr")[idx];
  if (row) row.remove();
  // Re-index remaining rows
  var rows = document.getElementById("debt-tbody").querySelectorAll("tr");
  rows.forEach(function(r, i) {{
    var inputs = r.querySelectorAll("input");
    if (inputs[0]) inputs[0].name = "debt_name_" + i;
    if (inputs[1]) inputs[1].name = "debt_bal_" + i;
    if (inputs[2]) inputs[2].name = "debt_pmt_" + i;
  }});
}}

function addTransaction() {{ document.getElementById("txn-form").style.display = document.getElementById("txn-form").style.display==="none"?"block":"none"; }}
function renderTxns() {{
  var body = document.getElementById("txn-body");
  if (!body) return;
  body.innerHTML = TRANSACTIONS.slice().reverse().slice(0,50).map(function(t) {{
    return "<tr><td class='mono'>"+t.date+"</td><td>"+t.category+"</td><td class='mono'>$"+parseFloat(t.amount).toFixed(2)+"</td><td class='hint'>"+( t.note||"")+"</td></tr>";
  }}).join("");
}}
function saveTxn() {{
  var txn = {{
    date: document.getElementById("txn-date").value,
    category: document.getElementById("txn-cat").value,
    amount: parseFloat(document.getElementById("txn-amount").value)||0,
    note: document.getElementById("txn-note").value
  }};
  if (!txn.amount) return;
  fetch("/api/add-transaction", {{ method:"POST", headers:{{"Content-Type":"application/json"}}, body:JSON.stringify(txn) }})
    .then(function(r){{ return r.json(); }})
    .then(function(d) {{
      if(d.success) {{
        TRANSACTIONS.push(txn);
        renderTxns();
        document.getElementById("txn-amount").value="";
        document.getElementById("txn-note").value="";
        buildSpendingChart();
        renderSpendingBreakdown();
      }}
    }});
}}
/* ── Spending vs Budget Breakdown ── */
function renderSpendingBreakdown() {{
  var container = document.getElementById("spending-breakdown");
  var monthSelect = document.getElementById("spend-month-select");
  if (!container) return;

  // Build month options from transactions
  var monthSet = {{}};
  TRANSACTIONS.forEach(function(t) {{
    if (t.date) monthSet[t.date.substring(0,7)] = true;
  }});
  var months = Object.keys(monthSet).sort().reverse();
  if (months.length === 0) {{
    container.innerHTML = '<div class="spend-empty">No transactions logged yet. Import statements or add transactions to see spending breakdown.</div>';
    return;
  }}

  // Populate month selector if empty
  if (monthSelect && monthSelect.options.length === 0) {{
    months.forEach(function(m) {{
      var opt = document.createElement("option");
      var d = new Date(m + "-15");
      opt.value = m;
      opt.textContent = d.toLocaleDateString("en-US", {{ year:"numeric", month:"long" }});
      monthSelect.appendChild(opt);
    }});
  }}

  var selectedMonth = monthSelect ? monthSelect.value : months[0];
  if (!selectedMonth) selectedMonth = months[0];

  // Filter transactions for selected month
  var monthTxns = TRANSACTIONS.filter(function(t) {{
    return t.date && t.date.substring(0,7) === selectedMonth;
  }});

  // Separate income (negative amounts) from expenses (positive amounts)
  var byExpenseCat = {{}};
  var incomeTxns = [];
  var totalExpenses = 0;
  var totalIncome = 0;
  monthTxns.forEach(function(t) {{
    var amt = parseFloat(t.amount) || 0;
    var cat = t.category || "Other";
    var isIncome = amt < 0 || t.type === "income" || cat === "Income";
    if (isIncome) {{
      incomeTxns.push(t);
      totalIncome += Math.abs(amt);
    }} else {{
      if (!byExpenseCat[cat]) byExpenseCat[cat] = {{ total: 0, txns: [] }};
      byExpenseCat[cat].total += amt;
      byExpenseCat[cat].txns.push(t);
      totalExpenses += amt;
    }}
  }});

  // Sort expense categories: budgeted ones first (by spent desc), then Other at end
  var cats = Object.keys(byExpenseCat).sort(function(a, b) {{
    if (a === "Other") return 1;
    if (b === "Other") return -1;
    return byExpenseCat[b].total - byExpenseCat[a].total;
  }});

  var totalBudget = 0;
  Object.values(BUDGET_LIMITS).forEach(function(v) {{ totalBudget += v; }});

  var html = '';

  // ── Income section (if any) ──
  if (incomeTxns.length > 0) {{
    var incomeSorted = incomeTxns.slice().sort(function(a,b) {{ return b.date.localeCompare(a.date); }});
    html += '<div class="spend-row">';
    html += '  <div class="spend-header" style="background:rgba(52,211,153,0.04);">';
    html += '    <span class="spend-chevron">&#9654;</span>';
    html += '    <span class="spend-cat" style="color:var(--success);">&#9660; Income / Credits</span>';
    html += '    <div class="spend-amounts">';
    html += '      <span style="color:var(--success);font-family:var(--mono);font-size:0.82rem;">+$' + totalIncome.toLocaleString(undefined, {{minimumFractionDigits:2}}) + '</span>';
    html += '      <span class="spend-budget">' + incomeTxns.length + ' transaction' + (incomeTxns.length > 1 ? 's' : '') + '</span>';
    html += '    </div>';
    html += '    <div style="flex:0 0 120px;"></div>';
    html += '  </div>';
    html += '  <div class="spend-details">';
    html += '    <table><thead><tr><th>Date</th><th>Description / Note</th><th style="text-align:right">Amount</th></tr></thead><tbody>';
    incomeSorted.forEach(function(t) {{
      var desc = t.description || t.note || "—";
      var amt = Math.abs(parseFloat(t.amount));
      html += '<tr><td class="mono">' + t.date + '</td><td>' + desc + '</td><td class="mono" style="text-align:right;color:var(--success);">+$' + amt.toFixed(2) + '</td></tr>';
    }});
    html += '    </tbody></table>';
    html += '  </div>';
    html += '</div>';
    html += '<div style="height:6px;border-bottom:2px solid var(--border-subtle);margin-bottom:2px;"></div>';
  }}

  // ── Expense categories ──
  cats.forEach(function(cat) {{
    var spent = byExpenseCat[cat].total;
    var limit = BUDGET_LIMITS[cat] || 0;
    var pct = limit > 0 ? Math.min((spent / limit) * 100, 100) : (spent > 0 ? 100 : 0);
    var barClass = pct >= 100 ? "over" : pct >= 75 ? "near" : "under";
    var overAmt = limit > 0 && spent > limit ? spent - limit : 0;

    var budgetText = limit > 0
      ? "/ $" + limit.toLocaleString(undefined, {{minimumFractionDigits:0}})
      : '<span style="color:var(--text-muted);font-style:italic;">no budget</span>';

    var overTag = overAmt > 0
      ? ' <span style="color:var(--danger);font-size:0.72rem;font-weight:600;">+$' + overAmt.toFixed(0) + ' over</span>'
      : '';

    // Sort transactions by date descending
    var txns = byExpenseCat[cat].txns.slice().sort(function(a,b) {{ return b.date.localeCompare(a.date); }});

    html += '<div class="spend-row">';
    html += '  <div class="spend-header">';
    html += '    <span class="spend-chevron">&#9654;</span>';
    html += '    <span class="spend-cat">' + cat + '</span>';
    html += '    <div class="spend-amounts">';
    html += '      <span class="spend-spent">$' + spent.toLocaleString(undefined, {{minimumFractionDigits:2}}) + '</span>';
    html += '      <span class="spend-budget">' + budgetText + overTag + '</span>';
    html += '    </div>';
    html += '    <div class="spend-bar-wrap"><div class="spend-bar ' + barClass + '" style="width:' + pct + '%"></div></div>';
    html += '  </div>';
    html += '  <div class="spend-details">';
    html += '    <table><thead><tr><th>Date</th><th>Description / Note</th><th style="text-align:right">Amount</th></tr></thead><tbody>';
    txns.forEach(function(t) {{
      var desc = t.description || t.note || "—";
      html += '<tr><td class="mono">' + t.date + '</td><td>' + desc + '</td><td class="mono" style="text-align:right">$' + parseFloat(t.amount).toFixed(2) + '</td></tr>';
    }});
    html += '    </tbody></table>';
    html += '  </div>';
    html += '</div>';
  }});

  // Also show budgeted categories with $0 spent
  Object.keys(BUDGET_LIMITS).forEach(function(cat) {{
    if (!byExpenseCat[cat] && BUDGET_LIMITS[cat] > 0) {{
      html += '<div class="spend-row">';
      html += '  <div class="spend-header">';
      html += '    <span class="spend-chevron" style="visibility:hidden">&#9654;</span>';
      html += '    <span class="spend-cat" style="color:var(--text-muted)">' + cat + '</span>';
      html += '    <div class="spend-amounts">';
      html += '      <span class="spend-spent" style="color:var(--text-muted)">$0.00</span>';
      html += '      <span class="spend-budget">/ $' + BUDGET_LIMITS[cat].toLocaleString(undefined, {{minimumFractionDigits:0}}) + '</span>';
      html += '    </div>';
      html += '    <div class="spend-bar-wrap"><div class="spend-bar under" style="width:0%"></div></div>';
      html += '  </div>';
      html += '</div>';
    }}
  }});

  // ── Summary: Income / Expenses / Net Cash Flow ──
  html += '<div class="spend-total" style="flex-direction:column;gap:4px;">';
  if (totalIncome > 0) {{
    html += '<div style="display:flex;justify-content:space-between;width:100%;color:var(--success);">';
    html += '  <span>Income / Credits</span>';
    html += '  <span class="mono">+$' + totalIncome.toLocaleString(undefined, {{minimumFractionDigits:2}}) + '</span>';
    html += '</div>';
  }}
  html += '<div style="display:flex;justify-content:space-between;width:100%;">';
  html += '  <span>Total Expenses</span>';
  html += '  <span class="mono">$' + totalExpenses.toLocaleString(undefined, {{minimumFractionDigits:2}}) + (totalBudget > 0 ? ' / $' + totalBudget.toLocaleString(undefined, {{minimumFractionDigits:0}}) : '') + '</span>';
  html += '</div>';
  if (totalIncome > 0) {{
    var netCashFlow = totalIncome - totalExpenses;
    var netColor = netCashFlow >= 0 ? "var(--success)" : "var(--danger)";
    var netSign = netCashFlow >= 0 ? "+" : "-";
    html += '<div style="display:flex;justify-content:space-between;width:100%;border-top:1px solid var(--border-subtle);padding-top:6px;margin-top:2px;">';
    html += '  <span style="font-weight:700;">Net Cash Flow</span>';
    html += '  <span class="mono" style="color:' + netColor + ';font-weight:700;">' + netSign + '$' + Math.abs(netCashFlow).toLocaleString(undefined, {{minimumFractionDigits:2}}) + '</span>';
    html += '</div>';
  }}
  html += '</div>';

  container.innerHTML = html;
  // Event delegation for expand/collapse
  container.querySelectorAll(".spend-header").forEach(function(header) {{
    header.addEventListener("click", function() {{
      var row = this.closest(".spend-row");
      if (row) row.classList.toggle("open");
    }});
  }});
}}
/* ── Statement Import ── */
var stmtData = null;
function previewStatement() {{
  var fileInput = document.getElementById("stmt-file");
  if (!fileInput.files.length) {{ alert("Please select a CSV or PDF file first."); return; }}
  var files = fileInput.files;
  var allTransactions = [];
  var totalAmount = 0;
  var byCat = {{}};
  var processed = 0;
  var errors = [];

  document.getElementById("stmt-preview").style.display = "none";
  document.getElementById("stmt-summary").textContent = "Processing " + files.length + " file(s)...";

  function processNext(idx) {{
    if (idx >= files.length) {{
      // All files processed — merge results
      if (errors.length > 0 && allTransactions.length === 0) {{
        alert("Errors:\\n" + errors.join("\\n"));
        return;
      }}
      stmtData = {{
        transactions: allTransactions,
        total_count: allTransactions.length,
        total_amount: Math.round(totalAmount * 100) / 100,
        by_category: byCat
      }};
      var errNote = errors.length > 0 ? " (" + errors.length + " file(s) had issues)" : "";
      var incomeAmt = 0, expenseAmt = 0;
      allTransactions.forEach(function(t) {{ if (t.amount < 0) incomeAmt += Math.abs(t.amount); else expenseAmt += t.amount; }});
      var summaryParts = allTransactions.length + " transactions from " + files.length + " file(s)";
      if (incomeAmt > 0) summaryParts += " | Expenses: $" + expenseAmt.toLocaleString(undefined, {{minimumFractionDigits:2}}) + " | Income: +$" + incomeAmt.toLocaleString(undefined, {{minimumFractionDigits:2}});
      else summaryParts += ", $" + expenseAmt.toLocaleString(undefined, {{minimumFractionDigits:2}}) + " total";
      document.getElementById("stmt-summary").textContent = summaryParts + errNote;
      var catParts = [];
      for (var cat in byCat) {{ catParts.push(cat + ": $" + byCat[cat].toFixed(0)); }}
      document.getElementById("stmt-cat-summary").textContent = catParts.join(" | ");
      var cats = BUDGET_CATS.slice();
      // Add "Income" to category list if not already present
      if (cats.indexOf("Income") === -1) cats = ["Income"].concat(cats);
      var rows = allTransactions.map(function(t, i) {{
        // If detected category doesn't exist in budget, map to "Other" (unless it's Income)
        var effectiveCat = t.category;
        if (cats.indexOf(effectiveCat) === -1) effectiveCat = "Other";
        var opts = cats.map(function(c) {{ return "<option" + (c === effectiveCat ? " selected" : "") + ">" + c + "</option>"; }}).join("");
        var isIncome = t.amount < 0 || t.type === "income" || effectiveCat === "Income";
        var amtDisplay = isIncome ? '<span style="color:var(--success);">+$' + Math.abs(t.amount).toFixed(2) + '</span>' : '$' + t.amount.toFixed(2);
        return "<tr" + (isIncome ? " style='background:rgba(52,211,153,0.03);'" : "") + "><td class='mono'>" + t.date + "</td><td style='max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>" + t.description + "</td><td class='mono'>" + amtDisplay + "</td><td><select class='stmt-cat' data-idx='" + i + "' style='padding:4px 6px;font-size:0.78rem;'>" + opts + "</select></td></tr>";
      }}).join("");
      document.getElementById("stmt-rows").innerHTML = rows;
      document.getElementById("stmt-preview").style.display = "block";
      return;
    }}

    var formData = new FormData();
    formData.append("statement_file", files[idx]);
    fetch("/api/statement-preview", {{ method:"POST", body:formData }})
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        if (data.error) {{
          errors.push(files[idx].name + ": " + data.error);
        }} else {{
          // Merge transactions
          allTransactions = allTransactions.concat(data.transactions || []);
          totalAmount += data.total_amount || 0;
          for (var cat in (data.by_category || {{}})) {{
            byCat[cat] = (byCat[cat] || 0) + data.by_category[cat];
          }}
        }}
        processNext(idx + 1);
      }})
      .catch(function(e) {{
        errors.push(files[idx].name + ": " + e.message);
        processNext(idx + 1);
      }});
  }}
  processNext(0);
}}
function undoLastImport() {{
  if (!confirm("Undo the last statement import? This will remove all transactions added in the most recent import.")) return;
  fetch("/api/undo-import", {{ method:"POST" }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (d.success) {{
        alert(d.message);
        location.reload();
      }} else {{
        alert(d.error || "Nothing to undo.");
      }}
    }}).catch(function(e) {{ alert("Error: " + e.message); }});
}}
function clearAllTransactions() {{
  var count = TRANSACTIONS.length;
  if (!count) {{ alert("No transactions to clear."); return; }}
  if (!confirm("Delete ALL " + count + " transactions and reset spending history? This cannot be undone.")) return;
  fetch("/api/clear-transactions", {{ method:"POST" }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (d.success) {{
        alert(d.message);
        location.reload();
      }} else {{
        alert(d.error || "Failed to clear.");
      }}
    }}).catch(function(e) {{ alert("Error: " + e.message); }});
}}
function importStatement() {{
  if (!stmtData || !stmtData.transactions.length) return;
  // Collect category overrides
  var overrides = {{}};
  document.querySelectorAll(".stmt-cat").forEach(function(sel) {{
    var idx = parseInt(sel.dataset.idx);
    var txn = stmtData.transactions[idx];
    if (txn && sel.value !== txn.category) {{
      overrides[txn.description] = sel.value;
    }}
  }});
  // Use fetch API to submit all transactions at once
  fetch("/import/statement-batch", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ transactions: stmtData.transactions, category_overrides: overrides }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.success) {{
      location.href = "/?saved=" + encodeURIComponent(d.message) + "&tab=import" + (d.detect_recurring ? "&detect_recurring=1" : "");
    }} else {{
      alert(d.error || "Import failed");
    }}
  }}).catch(function(e) {{ alert("Import error: " + e.message); }});
}}

/* ── Phase 2: Spending Trends Chart ── */
function buildSpendingChart() {{
  var ctx = document.getElementById("spending-chart");
  if (!ctx || typeof Chart==="undefined") return;
  // Aggregate transactions by month/category
  var months = {{}};
  TRANSACTIONS.forEach(function(t) {{
    var m = t.date ? t.date.substring(0,7) : "unknown";
    if (!months[m]) months[m] = {{}};
    months[m][t.category] = (months[m][t.category]||0) + (parseFloat(t.amount)||0);
  }});
  var labels = Object.keys(months).sort().slice(-6);
  var cats = BUDGET_CATS.length ? BUDGET_CATS : [];
  var colors = ["#d4a017","#f5c842","#34d399","#818cf8","#f87171","#06b6d4","#a78bfa","#fb923c"];
  var datasets = cats.map(function(cat,i) {{
    return {{ label:cat, data:labels.map(function(m){{ return months[m]&&months[m][cat]?months[m][cat]:0; }}), backgroundColor:colors[i%colors.length] }};
  }});
  if (window._spendChart) window._spendChart.destroy();
  window._spendChart = new Chart(ctx, {{
    type:"bar",
    data:{{ labels:labels, datasets:datasets }},
    options:{{ responsive:true, maintainAspectRatio:false, plugins:{{ legend:{{ labels:{{ color:"#94a3b8", font:{{size:10}} }} }} }},
      scales:{{ x:{{ stacked:true, ticks:{{color:"#64748b",font:{{size:10}}}}, grid:{{display:false}} }}, y:{{ stacked:true, ticks:{{color:"#64748b",font:{{size:10}}}}, grid:{{color:"rgba(255,255,255,0.03)"}} }} }}
    }}
  }});
}}
/* ── Phase 2: Benchmark Overlay ── */
function addBenchmark() {{
  if (!window.historyChart || PRICE_HISTORY_DATA.length < 2) return;
  fetch("/api/historical?symbol=SPY&period=1y")
    .then(function(r){{ return r.json(); }})
    .then(function(json) {{
      if (!json.data || json.data.length < 2) return;
      // Normalize to percentage change from first value
      var spyFirst = json.data[0].c;
      var spyPct = json.data.map(function(d) {{ return ((d.c / spyFirst) - 1) * 100; }});
      var spyLabels = json.data.map(function(d) {{ return d.date; }});
      if (window.historyChart.data.datasets.length < 2) {{
        var spyPoints = json.data.map(function(d, i) {{ return {{ x: d.date, y: spyPct[i] }}; }}).slice(-PRICE_HISTORY_DATA.length);
        window.historyChart.data.datasets.push({{
          label: "SPY Benchmark", data: spyPoints,
          borderColor: "#64748b", borderDash:[5,3], borderWidth:1.5, fill:false, tension:0.3, pointRadius:0
        }});
        window.historyChart.update();
      }}
    }}).catch(function(){{}});
}}

/* ── Phase 3: Projected Growth Chart (interactive) ── */
var PROJ_CURRENT = {total:.2f};
var projectionChart = null;
var projectionData = {{ labels: [], values: [] }};

function projFV(initial, monthly, annualRate, months) {{
  if (annualRate <= 0) return initial + monthly * months;
  var r = annualRate / 100 / 12;
  var n = months;
  return initial * Math.pow(1 + r, n) + monthly * ((Math.pow(1 + r, n) - 1) / r);
}}

function rebuildProjectionData() {{
  var projMonthlyEl = document.getElementById("proj-monthly");
  if (!projMonthlyEl) return null;
  var current = PROJ_CURRENT;
  var monthly = parseFloat(projMonthlyEl.value) || 0;
  var ratePct = parseFloat(document.getElementById("proj-rate").value) || 7;
  var years = parseInt(document.getElementById("proj-years").value, 10) || 30;
  var months = years * 12;
  var labels = [];
  var values = [];
  for (var m = 0; m <= months; m += 3) {{
    labels.push((m / 12).toFixed(1) + "Y");
    values.push(Math.round(projFV(current, monthly, ratePct, m)));
  }}
  if (months > 0 && labels[labels.length - 1] !== (years + "Y")) {{
    labels.push(years + "Y");
    values.push(Math.round(projFV(current, monthly, ratePct, months)));
  }}
  projectionData = {{ labels: labels, values: values }};
  return {{ labels: labels, values: values, years: years, monthly: monthly, ratePct: ratePct }};
}}

function updateProjectionSummary(data) {{
  var current = PROJ_CURRENT;
  var endVal = data.values[data.values.length - 1];
  var totalContrib = data.monthly * (data.years * 12);
  var growth = endVal - current - totalContrib;
  document.getElementById("proj-start-val").textContent = "$" + current.toLocaleString(undefined, {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }});
  document.getElementById("proj-end-val").textContent = "$" + endVal.toLocaleString(undefined, {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }});
  document.getElementById("proj-total-contrib").textContent = "$" + totalContrib.toLocaleString(undefined, {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }});
  document.getElementById("proj-growth").textContent = "$" + growth.toLocaleString(undefined, {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }});
}}

function updateProjectionChart() {{
  var data = rebuildProjectionData();
  if (!data) return;
  document.getElementById("proj-rate-val").textContent = data.ratePct + "%";
  document.getElementById("proj-years-val").textContent = data.years;
  var timelineEl = document.getElementById("proj-timeline");
  timelineEl.max = data.years;
  if (parseInt(timelineEl.value, 10) > data.years) timelineEl.value = data.years;
  updateProjectionTimelineLabel();

  if (projectionChart) {{
    projectionChart.data.labels = data.labels;
    projectionChart.data.datasets[0].data = data.values;
    projectionChart.update();
  }} else {{
    var ctx = document.getElementById("projection-chart");
    if (!ctx || typeof Chart === "undefined") return;
    projectionChart = new Chart(ctx, {{
      type: "line",
      data: {{
        labels: data.labels,
        datasets: [{{
          label: "Projected value",
          data: data.values,
          borderColor: "rgba(212,160,23,0.9)",
          backgroundColor: "rgba(212,160,23,0.1)",
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          pointHoverRadius: 4
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ intersect: false, mode: "index" }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              label: function(c) {{ return "$" + c.raw.toLocaleString(undefined, {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }}); }}
            }}
          }}
        }},
        scales: {{
          x: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }}, maxTicksLimit: 12 }}, grid: {{ display: false }} }},
          y: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }}, callback: function(v) {{ return "$" + (v/1000).toFixed(0) + "K"; }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }}
        }}
      }}
    }});
  }}
  updateProjectionSummary(data);
  setTimeout(updateProjectionTimelineLabel, 50);
}}

function updateProjectionTimelineLabel() {{
  var year = parseInt(document.getElementById("proj-timeline").value, 10);
  document.getElementById("proj-timeline-val").textContent = "Year " + year;
  var data = projectionData;
  if (!data.values || data.values.length === 0) return;
  var years = parseInt(document.getElementById("proj-years").value, 10) || 30;
  var idx = Math.round((year / years) * (data.values.length - 1));
  idx = Math.min(idx, data.values.length - 1);
  var val = data.values[idx];
  var crosshair = document.getElementById("projection-crosshair");
  var label = document.getElementById("projection-crosshair-label");
  if (crosshair && label && projectionChart) {{
    var xScale = projectionChart.scales.x;
    if (xScale && data.labels.length > 0) {{
      var left = xScale.getPixelForValue(data.labels[idx]);
      crosshair.style.left = left + "px";
      crosshair.style.display = "block";
      label.textContent = "Year " + year + ": $" + (val || 0).toLocaleString(undefined, {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }});
      label.style.display = "block";
    }}
  }}
}}

function buildProjectionChart() {{
  updateProjectionChart();
  ["proj-rate", "proj-monthly", "proj-years"].forEach(function(id) {{
    var el = document.getElementById(id);
    if (el) el.addEventListener("input", updateProjectionChart);
  }});
  var timelineEl = document.getElementById("proj-timeline");
  if (timelineEl) {{
    timelineEl.addEventListener("input", updateProjectionTimelineLabel);
  }}
}}
buildProjectionChart();

/* FRED_JS_START */
/* ── FRED Economics ── */
var fredTooltipOpts = {{ yAlign: "bottom", caretPadding: 8, backgroundColor: "rgba(30,30,30,0.95)", titleColor: "#e2e8f0", bodyColor: "#e2e8f0", borderColor: "rgba(99,102,241,0.4)", borderWidth: 1 }};
var fredCharts = {{}};
function fredSeries(data, id) {{ var e = data[id]; return (e && e.data) ? e.data : []; }}
function fredLatest(arr) {{ for (var i = (arr && arr.length) ? arr.length - 1 : -1; i >= 0; i--) if (arr[i].value != null) return arr[i].value; return null; }}
function fredLineChart(canvasId, points, label, yFmt) {{
  var ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === "undefined") return;
  var labels = (points || []).map(function(p) {{ return p.date; }});
  var values = (points || []).map(function(p) {{ return p.value; }});
  if (fredCharts[canvasId]) {{
    fredCharts[canvasId].data.labels = labels;
    fredCharts[canvasId].data.datasets[0].data = values;
    fredCharts[canvasId].update();
    return;
  }}
  var yCallback = yFmt === "billions" ? function(v) {{ return (v/1e3).toFixed(1) + "T"; }} : yFmt === "pct" ? function(v) {{ return v != null ? Number(v).toFixed(1) + "%" : ""; }} : function(v) {{ return v != null ? Number(v).toLocaleString() : ""; }};
  fredCharts[canvasId] = new Chart(ctx, {{
    type: "line",
    data: {{ labels: labels, datasets: [{{ label: label, data: values, borderColor: "rgba(212,160,23,0.9)", backgroundColor: "rgba(212,160,23,0.1)", fill: true, tension: 0.2, pointRadius: 0, pointHitRadius: 20 }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: "index", intersect: false }}, plugins: {{ legend: {{ display: false }}, tooltip: fredTooltipOpts }}, scales: {{ x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 8 }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b", callback: yCallback }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }}
  }});
}}
function fredBarChart(canvasId, points, label, colorFn) {{
  var ctx = document.getElementById(canvasId);
  if (!ctx || typeof Chart === "undefined") return;
  var labels = (points || []).map(function(p) {{ return p.date; }});
  var values = (points || []).map(function(p) {{ return p.value; }});
  var colors = (colorFn && values) ? values.map(colorFn) : "rgba(212,160,23,0.6)";
  if (fredCharts[canvasId]) {{
    fredCharts[canvasId].data.labels = labels;
    fredCharts[canvasId].data.datasets[0].data = values;
    fredCharts[canvasId].data.datasets[0].backgroundColor = colors;
    fredCharts[canvasId].update();
    return;
  }}
  fredCharts[canvasId] = new Chart(ctx, {{
    type: "bar",
    data: {{ labels: labels, datasets: [{{ label: label, data: values, backgroundColor: colors }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: "index", intersect: false }}, plugins: {{ legend: {{ display: false }}, tooltip: fredTooltipOpts }}, scales: {{ x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 8 }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b" }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }}
  }});
}}
function renderFredDebt(data) {{
  var debt = fredSeries(data, "GFDEBTN");
  var debtGdp = fredSeries(data, "GFDEGDQ188S");
  var deficit = fredSeries(data, "FYFSD");
  var interest = fredSeries(data, "A091RC1Q027SBEA");
  var gdp = fredSeries(data, "GDP");
  var receipts = fredSeries(data, "W006RC1Q027SBEA");
  var outlays = fredSeries(data, "W068RCQ027SBEA");
  var deficitPct = fredSeries(data, "FYFSGDA188S");
  var spendingPct = fredSeries(data, "FYONGDA188S");
  var interestPct = fredSeries(data, "FYOIGDA188S");
  var latestDebt = fredLatest(debt);
  var latestGdp = fredLatest(gdp);
  var latestDeficit = fredLatest(deficit);
  var latestInterest = fredLatest(interest);
  var latestDeficitPct = fredLatest(deficitPct);
  var latestSpendingPct = fredLatest(spendingPct);
  var latestInterestPct = fredLatest(interestPct);
  var debtPct = (latestGdp && latestDebt) ? (latestDebt / (latestGdp * 1e3) * 100).toFixed(1) : null;
  var defPctStr = latestDeficitPct != null ? (latestDeficitPct < 0 ? (Math.abs(latestDeficitPct).toFixed(1) + '% deficit') : (latestDeficitPct.toFixed(1) + '% surplus')) : null;
  var el = document.getElementById("fred-debt-stats");
  var subStyle = 'style="font-size:0.7rem;color:var(--text-muted);font-family:var(--mono);margin-top:2px;"';
  if (el) el.innerHTML =
    (latestDebt != null ? '<div class="pulse-item"><span class="pulse-label">Total Debt</span><span class="pulse-price">$' + (latestDebt/1e6).toFixed(2) + 'T</span>' + (debtPct ? '<span ' + subStyle + '>' + debtPct + '% of GDP</span>' : '') + '</div>' : '')
    + (fredLatest(gdp) != null ? '<div class="pulse-item"><span class="pulse-label">GDP</span><span class="pulse-price">$' + (fredLatest(gdp)/1e3).toFixed(2) + 'T</span></div>' : '')
    + (latestDeficit != null ? '<div class="pulse-item"><span class="pulse-label">Annual Deficit</span><span class="pulse-price">$' + (latestDeficit/1e6).toFixed(2) + 'T</span>' + (defPctStr ? '<span ' + subStyle + '>' + defPctStr + '</span>' : '') + '</div>' : '')
    + (latestInterest != null ? '<div class="pulse-item"><span class="pulse-label">Interest (Q)</span><span class="pulse-price">$' + (latestInterest/1e3).toFixed(2) + 'T</span>' + (latestInterestPct != null ? '<span ' + subStyle + '>' + latestInterestPct.toFixed(1) + '% of GDP</span>' : '') + '</div>' : '')
    + (latestSpendingPct != null ? '<div class="pulse-item"><span class="pulse-label">Gov Spending</span><span class="pulse-price">$' + (latestGdp ? (latestGdp * 1e3 * latestSpendingPct / 100 / 1e6).toFixed(2) : '?') + 'T</span><span ' + subStyle + '>' + latestSpendingPct.toFixed(1) + '% of GDP</span></div>' : '')
    + (latestSpendingPct != null && latestDeficitPct != null ? (function() {{ var revPct = latestSpendingPct + latestDeficitPct; var revDollar = latestGdp ? (latestGdp * 1e3 * revPct / 100 / 1e6).toFixed(2) : '?'; return '<div class="pulse-item"><span class="pulse-label">Gov Revenue</span><span class="pulse-price">$' + revDollar + 'T</span><span ' + subStyle + '>' + revPct.toFixed(1) + '% of GDP</span></div>'; }})() : '');
  fredLineChart("fred-chart-debt", debt, "Debt", "billions");
  fredLineChart("fred-chart-debt-gdp", debtGdp, "Debt/GDP %", "pct");
  fredBarChart("fred-chart-deficit", deficit, "Deficit", function(v) {{ return v >= 0 ? "rgba(52,211,153,0.6)" : "rgba(248,113,113,0.6)"; }});
  fredLineChart("fred-chart-interest", interest, "Interest", "billions");
  fredLineChart("fred-chart-deficit-pct", deficitPct, "Deficit/Surplus % GDP", "pct");
  fredLineChart("fred-chart-spending-pct", spendingPct, "Spending % GDP", "pct");
  fredLineChart("fred-chart-interest-pct", interestPct, "Interest % GDP", "pct");
  if (receipts.length && outlays.length) {{
    fredCharts["fred-chart-revenue-spending"] && fredCharts["fred-chart-revenue-spending"].destroy();
    var allDates = {{}};
    receipts.forEach(function(p) {{ allDates[p.date] = true; }});
    outlays.forEach(function(p) {{ allDates[p.date] = true; }});
    var dates = Object.keys(allDates).sort();
    var rVals = dates.map(function(d) {{ var p = receipts.find(function(x) {{ return x.date === d; }}); return p ? p.value : null; }});
    var oVals = dates.map(function(d) {{ var p = outlays.find(function(x) {{ return x.date === d; }}); return p ? p.value : null; }});
    var ctx = document.getElementById("fred-chart-revenue-spending");
    if (ctx) {{ fredCharts["fred-chart-revenue-spending"] = new Chart(ctx, {{ type: "line", data: {{ labels: dates, datasets: [{{ label: "Receipts", data: rVals, borderColor: "rgba(52,211,153,0.9)", fill: false, tension: 0.2, pointRadius: 0 }}, {{ label: "Outlays", data: oVals, borderColor: "rgba(248,113,113,0.9)", fill: false, tension: 0.2, pointRadius: 0 }}] }}, options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: "index", intersect: false }}, plugins: {{ legend: {{ labels: {{ color: "#94a3b8" }} }}, tooltip: fredTooltipOpts }}, scales: {{ x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 8 }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b", callback: function(v) {{ return v != null ? v.toFixed(0) + " B" : ""; }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }} }}); }}
  }}
}}
function renderFredInflation(data) {{
  var cpi = fredSeries(data, "CPIAUCSL");
  var core = fredSeries(data, "CPILFESL");
  var pce = fredSeries(data, "PCEPI");
  var el = document.getElementById("fred-inflation-stats");
  if (el) el.innerHTML = (fredLatest(cpi) != null ? '<div class="pulse-item"><span class="pulse-label">CPI-U</span><span class="pulse-price">' + fredLatest(cpi).toFixed(2) + '</span></div>' : '') + (fredLatest(core) != null ? '<div class="pulse-item"><span class="pulse-label">Core CPI</span><span class="pulse-price">' + fredLatest(core).toFixed(2) + '</span></div>' : '') + (fredLatest(pce) != null ? '<div class="pulse-item"><span class="pulse-label">PCE</span><span class="pulse-price">' + fredLatest(pce).toFixed(2) + '</span></div>' : '');
  fredCharts["fred-chart-inflation"] && fredCharts["fred-chart-inflation"].destroy();
  var ctx = document.getElementById("fred-chart-inflation");
  if (!ctx || !cpi.length) return;
  var labels = cpi.map(function(p) {{ return p.date; }});
  var cpiV = cpi.map(function(p) {{ return p.value; }});
  var coreV = labels.map(function(d) {{ var p = core.find(function(x) {{ return x.date === d; }}); return p ? p.value : null; }});
  var pceV = labels.map(function(d) {{ var p = pce.find(function(x) {{ return x.date === d; }}); return p ? p.value : null; }});
  fredCharts["fred-chart-inflation"] = new Chart(ctx, {{
    type: "line",
    data: {{ labels: labels, datasets: [{{ label: "CPI-U", data: cpiV, borderColor: "rgba(212,160,23,0.9)", fill: false, pointRadius: 0 }}, {{ label: "Core CPI", data: coreV, borderColor: "rgba(100,116,139,0.9)", fill: false, pointRadius: 0 }}, {{ label: "PCE", data: pceV, borderColor: "rgba(52,211,153,0.7)", fill: false, pointRadius: 0 }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ labels: {{ color: "#94a3b8" }} }} }}, scales: {{ x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 10 }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b" }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }}
  }});
}}
function fredValueAt(arr, dateStr) {{ for (var i = (arr && arr.length) ? arr.length - 1 : -1; i >= 0; i--) if (arr[i].date <= dateStr) return arr[i].value; return null; }}
function renderFredMonetary(data) {{
  var fed = fredSeries(data, "FEDFUNDS");
  var m2 = fredSeries(data, "M2SL");
  var el = document.getElementById("fred-monetary-stats");
  if (el) el.innerHTML = (fredLatest(fed) != null ? '<div class="pulse-item"><span class="pulse-label">Fed Funds</span><span class="pulse-price">' + fredLatest(fed).toFixed(2) + '%</span></div>' : '') + (fredLatest(m2) != null ? '<div class="pulse-item"><span class="pulse-label">M2</span><span class="pulse-price">$' + (fredLatest(m2)/1e3).toFixed(2) + 'T</span></div>' : '');
  fredLineChart("fred-chart-fedfunds", fed, "Fed Funds Rate", "pct");
  fredLineChart("fred-chart-m2", m2, "M2", "billions");
  var ycLabels = ["1M","3M","6M","1Y","2Y","5Y","10Y","20Y","30Y"];
  var ycIds = ["DGS1MO","DGS3MO","DGS6MO","DGS1","DGS2","DGS5","DGS10","DGS20","DGS30"];
  var now = new Date();
  var nowStr = now.getFullYear() + "-" + String(now.getMonth()+1).padStart(2,"0") + "-" + String(now.getDate()).padStart(2,"0");
  var pastStr = (now.getFullYear()-1) + "-" + String(now.getMonth()+1).padStart(2,"0") + "-" + String(now.getDate()).padStart(2,"0");
  var currentRates = ycIds.map(function(id) {{ return fredLatest(fredSeries(data, id)); }});
  var pastRates = ycIds.map(function(id) {{ return fredValueAt(fredSeries(data, id), pastStr); }});
  var hasCurrent = currentRates.some(function(v) {{ return v != null; }});
  var ctx = document.getElementById("fred-chart-yield-curve");
  if (ctx && typeof Chart !== "undefined" && hasCurrent) {{
    fredCharts["fred-chart-yield-curve"] && fredCharts["fred-chart-yield-curve"].destroy();
    fredCharts["fred-chart-yield-curve"] = new Chart(ctx, {{
      type: "line",
      data: {{ labels: ycLabels, datasets: [{{ label: "Current", data: currentRates, borderColor: "rgba(212,160,23,0.9)", backgroundColor: "rgba(212,160,23,0.1)", fill: true, tension: 0.2, pointRadius: 3 }}, {{ label: "1Y ago", data: pastRates, borderColor: "rgba(100,116,139,0.7)", borderDash: [4,2], fill: false, pointRadius: 2 }}] }},
      options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: "index", intersect: false }}, plugins: {{ legend: {{ labels: {{ color: "#94a3b8" }} }}, tooltip: fredTooltipOpts }}, scales: {{ x: {{ ticks: {{ color: "#64748b" }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b", callback: function(v) {{ return v != null ? Number(v).toFixed(1) + "%" : ""; }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }}
    }});
  }}
}}
function renderFredCredit(data) {{
  var hy = fredSeries(data, "BAMLH0A0HYM2");
  var el = document.getElementById("fred-credit-stats");
  var latest = fredLatest(hy);
  if (el) {{
    var cls = latest != null && latest >= 5 ? "neg" : "pos";
    el.innerHTML = (latest != null ? '<div class="pulse-item"><span class="pulse-label">HY OAS</span><span class="pulse-price">' + latest.toFixed(2) + '%</span></div><div class="pulse-item"><span class="pulse-label">Signal</span><span class="pulse-price ' + cls + '">' + (latest >= 5 ? "STRESS" : latest >= 4 ? "ELEVATED" : "NORMAL") + '</span></div>' : '');
  }}
  fredCharts["fred-chart-hy-spread"] && fredCharts["fred-chart-hy-spread"].destroy();
  var ctx = document.getElementById("fred-chart-hy-spread");
  if (!ctx || !hy.length) return;
  var labels = hy.map(function(p) {{ return p.date; }});
  var values = hy.map(function(p) {{ return p.value; }});
  var threshold5 = values.map(function() {{ return 5; }});
  fredCharts["fred-chart-hy-spread"] = new Chart(ctx, {{
    type: "line",
    data: {{ labels: labels, datasets: [{{ label: "HY OAS %", data: values, borderColor: "rgba(248,113,113,0.9)", backgroundColor: "rgba(248,113,113,0.1)", fill: true, tension: 0.2, pointRadius: 0 }}, {{ label: "Stress (5%)", data: threshold5, borderColor: "rgba(248,113,113,0.4)", borderDash: [6,3], borderWidth: 1, pointRadius: 0, fill: false }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: "index", intersect: false }}, plugins: {{ legend: {{ labels: {{ color: "#94a3b8" }} }}, tooltip: fredTooltipOpts }}, scales: {{ x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 8 }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b", callback: function(v) {{ return v != null ? Number(v).toFixed(1) + "%" : ""; }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }}
  }});
}}
function renderFredRealYields(data) {{
  var realY = fredSeries(data, "DFII10");
  var be5 = fredSeries(data, "T5YIE");
  var be10 = fredSeries(data, "T10YIE");
  var el = document.getElementById("fred-realyield-stats");
  var latestReal = fredLatest(realY);
  var latestBE5 = fredLatest(be5);
  var latestBE10 = fredLatest(be10);
  if (el) el.innerHTML = (latestReal != null ? '<div class="pulse-item"><span class="pulse-label">10Y Real Yield</span><span class="pulse-price">' + latestReal.toFixed(2) + '%</span></div>' : '') + (latestBE5 != null ? '<div class="pulse-item"><span class="pulse-label">5Y Breakeven</span><span class="pulse-price">' + latestBE5.toFixed(2) + '%</span></div>' : '') + (latestBE10 != null ? '<div class="pulse-item"><span class="pulse-label">10Y Breakeven</span><span class="pulse-price">' + latestBE10.toFixed(2) + '%</span></div>' : '');
  fredLineChart("fred-chart-real-yield", realY, "10Y Real Yield %", "pct");
  fredCharts["fred-chart-breakeven"] && fredCharts["fred-chart-breakeven"].destroy();
  var ctx = document.getElementById("fred-chart-breakeven");
  if (!ctx) return;
  var labels = be10.length ? be10.map(function(p) {{ return p.date; }}) : be5.map(function(p) {{ return p.date; }});
  var be5V = labels.map(function(d) {{ var p = be5.find(function(x) {{ return x.date === d; }}); return p ? p.value : null; }});
  var be10V = labels.map(function(d) {{ var p = be10.find(function(x) {{ return x.date === d; }}); return p ? p.value : null; }});
  fredCharts["fred-chart-breakeven"] = new Chart(ctx, {{
    type: "line",
    data: {{ labels: labels, datasets: [{{ label: "5Y Breakeven", data: be5V, borderColor: "rgba(96,165,250,0.9)", fill: false, tension: 0.2, pointRadius: 0 }}, {{ label: "10Y Breakeven", data: be10V, borderColor: "rgba(212,160,23,0.9)", fill: false, tension: 0.2, pointRadius: 0 }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: "index", intersect: false }}, plugins: {{ legend: {{ labels: {{ color: "#94a3b8" }} }}, tooltip: fredTooltipOpts }}, scales: {{ x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 8 }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b", callback: function(v) {{ return v != null ? Number(v).toFixed(1) + "%" : ""; }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }}
  }});
}}
function renderFredFedBS(data) {{
  var walcl = fredSeries(data, "WALCL");
  var el = document.getElementById("fred-fedbs-stats");
  var latest = fredLatest(walcl);
  if (el) el.innerHTML = (latest != null ? '<div class="pulse-item"><span class="pulse-label">Fed Total Assets</span><span class="pulse-price">$' + (latest/1e6).toFixed(2) + 'T</span></div>' : '');
  fredLineChart("fred-chart-fedbs", walcl, "Fed Balance Sheet", "billions");
}}
function renderFredSahm(data) {{
  var sahm = fredSeries(data, "SAHMREALTIME");
  var el = document.getElementById("fred-sahm-stats");
  var latest = fredLatest(sahm);
  if (el) {{
    var cls = latest != null && latest >= 0.5 ? "neg" : "pos";
    el.innerHTML = (latest != null ? '<div class="pulse-item"><span class="pulse-label">Sahm Rule</span><span class="pulse-price">' + latest.toFixed(2) + '</span></div><div class="pulse-item"><span class="pulse-label">Signal</span><span class="pulse-price ' + cls + '">' + (latest >= 0.5 ? "RECESSION" : "NORMAL") + '</span></div>' : '');
  }}
  fredCharts["fred-chart-sahm"] && fredCharts["fred-chart-sahm"].destroy();
  var ctx = document.getElementById("fred-chart-sahm");
  if (!ctx || !sahm.length) return;
  var labels = sahm.map(function(p) {{ return p.date; }});
  var values = sahm.map(function(p) {{ return p.value; }});
  var threshold50 = values.map(function() {{ return 0.5; }});
  fredCharts["fred-chart-sahm"] = new Chart(ctx, {{
    type: "line",
    data: {{ labels: labels, datasets: [{{ label: "Sahm Rule", data: values, borderColor: "rgba(251,191,36,0.9)", backgroundColor: "rgba(251,191,36,0.1)", fill: true, tension: 0.2, pointRadius: 0 }}, {{ label: "Recession Threshold (0.50)", data: threshold50, borderColor: "rgba(248,113,113,0.6)", borderDash: [6,3], borderWidth: 2, pointRadius: 0, fill: false }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: "index", intersect: false }}, plugins: {{ legend: {{ labels: {{ color: "#94a3b8" }} }}, tooltip: fredTooltipOpts }}, scales: {{ x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 8 }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: "#64748b" }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }} }} }}
  }});
}}
function renderFredLabor(data) {{
  var unrate = fredSeries(data, "UNRATE");
  var claims = fredSeries(data, "ICSA");
  var el = document.getElementById("fred-labor-stats");
  if (el) el.innerHTML = (fredLatest(unrate) != null ? '<div class="pulse-item"><span class="pulse-label">Unemployment</span><span class="pulse-price">' + fredLatest(unrate).toFixed(1) + '%</span></div>' : '') + (fredLatest(claims) != null ? '<div class="pulse-item"><span class="pulse-label">Jobless Claims</span><span class="pulse-price">' + (fredLatest(claims)/1000).toFixed(1) + 'K</span></div>' : '');
  fredLineChart("fred-chart-unemployment", unrate, "Unemployment %", "pct");
  fredLineChart("fred-chart-claims", claims, "Initial Claims", null);
}}
function renderFredGrowth(data) {{
  var gdpGr = fredSeries(data, "A191RL1Q225SBEA");
  var sent = fredSeries(data, "UMCSENT");
  var el = document.getElementById("fred-growth-stats");
  if (el) el.innerHTML = (fredLatest(gdpGr) != null ? '<div class="pulse-item"><span class="pulse-label">Real GDP Growth</span><span class="pulse-price">' + fredLatest(gdpGr).toFixed(1) + '%</span></div>' : '') + (fredLatest(sent) != null ? '<div class="pulse-item"><span class="pulse-label">Consumer Sentiment</span><span class="pulse-price">' + fredLatest(sent).toFixed(1) + '</span></div>' : '');
  fredLineChart("fred-chart-gdp-growth", gdpGr, "Real GDP Growth %", "pct");
  fredLineChart("fred-chart-sentiment", sent, "Sentiment", null);
}}
function renderFredHousing(data) {{
  var cs = fredSeries(data, "CSUSHPINSA");
  var mort = fredSeries(data, "MORTGAGE30US");
  var el = document.getElementById("fred-housing-stats");
  if (el) el.innerHTML = (fredLatest(cs) != null ? '<div class="pulse-item"><span class="pulse-label">Case-Shiller</span><span class="pulse-price">' + fredLatest(cs).toFixed(1) + '</span></div>' : '') + (fredLatest(mort) != null ? '<div class="pulse-item"><span class="pulse-label">30Y Mortgage</span><span class="pulse-price">' + fredLatest(mort).toFixed(2) + '%</span></div>' : '');
  fredLineChart("fred-chart-housing", cs, "Case-Shiller", null);
  fredLineChart("fred-chart-mortgage", mort, "30Y Mortgage %", "pct");
}}
var fredDataCache = {{}};
var fredSectionsLoaded = {{}};
var FRED_SECTION_SERIES = {{
  debt: "GFDEBTN,GFDEGDQ188S,FYFSD,A091RC1Q027SBEA,GDP,W006RC1Q027SBEA,W068RCQ027SBEA,FYFSGDA188S,FYONGDA188S,FYOIGDA188S",
  inflation: "CPIAUCSL,CPILFESL,PCEPI",
  monetary: "FEDFUNDS,M2SL,WALCL",
  monetary_yc: "DGS1MO,DGS3MO,DGS6MO,DGS1,DGS2,DGS5,DGS10,DGS20,DGS30",
  credit: "BAMLH0A0HYM2",
  realyields: "DFII10,T5YIE,T10YIE",
  fedbs: "WALCL",
  sahm: "SAHMREALTIME",
  labor: "UNRATE,ICSA",
  growth: "A191RL1Q225SBEA,UMCSENT",
  housing: "CSUSHPINSA,MORTGAGE30US"
}};
function fredMergeData(target, incoming) {{ for (var k in incoming) if (incoming[k] && incoming[k].data) target[k] = incoming[k]; }}
function fredSafeJson(r) {{
  if (!r.ok) return Promise.reject(new Error("HTTP " + r.status));
  return r.json().catch(function(e) {{ return Promise.reject(new Error("Invalid JSON: " + e.message)); }});
}}
function fredFetchSection(sectionId, horizon, statusEl) {{
  if (fredSectionsLoaded[sectionId]) return Promise.resolve();
  var ids = FRED_SECTION_SERIES[sectionId];
  if (!ids) return Promise.resolve();
  var url = "/api/fred-data?series_ids=" + encodeURIComponent(ids);
  if (horizon) url += "&horizon=" + encodeURIComponent(horizon);
  var p = fetch(url).then(fredSafeJson).then(function(data) {{
    fredMergeData(fredDataCache, data);
    fredSectionsLoaded[sectionId] = true;
    return data;
  }});
  if (sectionId === "monetary") {{
    var ycIds = FRED_SECTION_SERIES["monetary_yc"];
    if (ycIds && !fredSectionsLoaded["monetary_yc"]) {{
      var ycUrl = "/api/fred-data?series_ids=" + encodeURIComponent(ycIds);
      if (horizon) ycUrl += "&horizon=" + encodeURIComponent(horizon);
      p = Promise.all([p, fetch(ycUrl).then(fredSafeJson).then(function(data) {{
        fredMergeData(fredDataCache, data);
        fredSectionsLoaded["monetary_yc"] = true;
        return data;
      }})]);
    }}
  }}
  return p;
}}
function fredRefreshSectionPeriod(sectionId, horizon) {{
  var ids = FRED_SECTION_SERIES[sectionId];
  if (!ids) return;
  var url = "/api/fred-data?series_ids=" + encodeURIComponent(ids) + "&horizon=" + encodeURIComponent(horizon);
  fetch(url).then(fredSafeJson).then(function(data) {{
    fredMergeData(fredDataCache, data);
    fredRenderAll();
  }}).catch(function() {{}});
}}
function fredRenderAll(data) {{
  if (!data) data = fredDataCache;
  renderFredDebt(data);
  renderFredInflation(data);
  renderFredMonetary(data);
  renderFredCredit(data);
  renderFredRealYields(data);
  renderFredFedBS(data);
  renderFredSahm(data);
  renderFredLabor(data);
  renderFredGrowth(data);
  renderFredHousing(data);
}}
var _fredObserver = null;
var _fredInited = false;
function loadFredData() {{
  var status = document.getElementById("fred-load-status");
  var horizonSelect = document.getElementById("fred-horizon");
  function getHorizon() {{ return (horizonSelect && horizonSelect.value) || "1y"; }}
  if (_fredInited) {{
    if (Object.keys(fredDataCache).length > 0) fredRenderAll();
    return;
  }}
  _fredInited = true;
  if (status) status.textContent = "Loading… (debt & inflation first)";
  fredFetchSection("debt", getHorizon()).then(function() {{
    return fredFetchSection("inflation", getHorizon());
  }}).then(function() {{
    if (status) status.textContent = "Data loaded. Scroll for more sections.";
    fredRenderAll();
  }}).catch(function(err) {{
    console.error("FRED load error:", err);
    if (status) status.textContent = "Failed: " + (err.message || err);
    _fredInited = false;
  }});
  _fredObserver = new IntersectionObserver(function(entries) {{
    entries.forEach(function(e) {{
      if (!e.isIntersecting) return;
      var m = e.target.id && e.target.id.match(/^fred-section-(.+)$/);
      if (!m) return;
      var sectionId = m[1];
      if (fredSectionsLoaded[sectionId]) return;
      fredFetchSection(sectionId, getHorizon()).then(function() {{
        fredRenderAll();
      }}).catch(function() {{}});
    }});
  }}, {{ rootMargin: "100px", threshold: 0.1 }});
  ["debt","inflation","monetary","credit","realyields","fedbs","sahm","labor","growth","housing"].forEach(function(id) {{
    var el = document.getElementById("fred-section-" + id);
    if (el) _fredObserver.observe(el);
  }});
  document.querySelectorAll(".fred-period-select").forEach(function(sel) {{
    sel.addEventListener("change", function() {{
      var section = this.getAttribute("data-section");
      var horizon = this.value;
      fredRefreshSectionPeriod(section, horizon);
    }});
  }});
  var btn = document.getElementById("fred-refresh-btn");
  if (btn) btn.onclick = function() {{
    fredDataCache = {{}};
    fredSectionsLoaded = {{}};
    var sections = Object.keys(FRED_SECTION_SERIES);
    var done = 0;
    var total = sections.length;
    if (status) status.textContent = "Refreshing (0/" + total + ")…";
    var chain = Promise.resolve();
    sections.forEach(function(sec) {{
      chain = chain.then(function() {{
        var ids = FRED_SECTION_SERIES[sec];
        return fetch("/api/fred-data?series_ids=" + encodeURIComponent(ids) + "&refresh=1&horizon=" + encodeURIComponent(getHorizon()))
          .then(fredSafeJson)
          .then(function(data) {{
            fredMergeData(fredDataCache, data);
            fredSectionsLoaded[sec] = true;
            done++;
            if (status) status.textContent = "Refreshing (" + done + "/" + total + ")…";
            fredRenderAll();
          }});
      }});
    }});
    chain.then(function() {{
      if (status) status.textContent = "Refreshed.";
    }}).catch(function(err) {{
      if (status) status.textContent = "Refresh error: " + (err.message || err);
    }});
  }};
  if (horizonSelect) horizonSelect.onchange = function() {{
    var h = getHorizon();
    if (status) status.textContent = "Loading " + (h === "max" ? "full history" : h) + "…";
    fetch("/api/fred-data?horizon=" + encodeURIComponent(h)).then(fredSafeJson).then(function(data) {{
      fredDataCache = data;
      Object.keys(FRED_SECTION_SERIES).forEach(function(k) {{ fredSectionsLoaded[k] = true; }});
      if (status) status.textContent = "Data loaded.";
      fredRenderAll();
    }}).catch(function(err) {{ if (status) status.textContent = "Load failed: " + (err.message || err); }});
  }};
}}
/* FRED_JS_END */

/* ── Phase 3: Price Alerts ── */
var PRICE_ALERTS = {alerts_json};
function checkAlerts(prices) {{
  PRICE_ALERTS.forEach(function(a) {{
    var current = prices[a.symbol];
    if (!current) return;
    if ((a.direction==="above" && current >= a.target) || (a.direction==="below" && current <= a.target)) {{
      if (!a.triggered) {{
        a.triggered = true;
        showAlertNotification(a.symbol + " is " + a.direction + " $" + a.target + " (now $" + current.toFixed(2) + ")");
      }}
    }}
  }});
}}
function showAlertNotification(msg) {{
  var div = document.createElement("div");
  div.className = "toast";
  div.style.background = "rgba(212,160,23,0.15)";
  div.style.color = "var(--accent-primary)";
  div.style.borderColor = "rgba(212,160,23,0.3)";
  div.textContent = msg;
  document.body.appendChild(div);
  setTimeout(function() {{ div.remove(); }}, 5000);
}}

/* ── Phase 4: PWA Service Worker Registration ── */
if ("serviceWorker" in navigator) {{
  navigator.serviceWorker.register("/sw.js").catch(function(){{}});
}}

/* ── Phase 4: Onboarding detection ── */
(function() {{
  if (!localStorage.getItem("wos-onboarded") && {num_holdings} === 0) {{
    var overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:400;display:flex;align-items:center;justify-content:center;";
    overlay.innerHTML = '<div style="background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:16px;padding:36px;max-width:460px;width:90%;text-align:center;">' +
      '<h2 style="color:var(--accent-primary);margin-bottom:12px;">Welcome to Nickel&amp;Dime</h2>' +
      '<p style="color:var(--text-secondary);margin-bottom:20px;font-size:0.9rem;">Get started in 3 easy steps:</p>' +
      '<div style="text-align:left;color:var(--text-secondary);font-size:0.88rem;line-height:1.8;">' +
      '<div style="margin-bottom:8px;"><span style="color:var(--accent-primary);font-weight:700;">1.</span> Set up your <b>Budget</b> (income &amp; expenses)</div>' +
      '<div style="margin-bottom:8px;"><span style="color:var(--accent-primary);font-weight:700;">2.</span> <b>Import</b> a Fidelity CSV or add holdings manually</div>' +
      '<div style="margin-bottom:8px;"><span style="color:var(--accent-primary);font-weight:700;">3.</span> Update <b>Balances</b> for blended accounts</div>' +
      '</div>' +
      '<button id="wos-onboard-btn" style="margin-top:20px;padding:10px 28px;background:var(--accent-primary);color:#09090b;border:none;border-radius:8px;font-weight:600;cursor:pointer;">Get Started</button>' +
      '</div>';
    document.body.appendChild(overlay);
    document.getElementById("wos-onboard-btn").onclick = function() {{ overlay.remove(); localStorage.setItem("wos-onboarded","1"); }};
  }}
}})();

/* ── Phase 4: Multi-currency stub ── */
var WOS_CURRENCY = localStorage.getItem("wos-currency") || "USD";

/* ── Recurring Transactions ── */
function showRecurringForm() {{
  var f = document.getElementById("recurring-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}}
function saveRecurring() {{
  var name = document.getElementById("rec-name").value.trim();
  var amount = parseFloat(document.getElementById("rec-amount").value) || 0;
  var category = document.getElementById("rec-cat").value;
  var frequency = document.getElementById("rec-freq").value;
  if (!name || amount <= 0) {{ alert("Name and amount are required."); return; }}
  fetch("/api/recurring", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ name: name, amount: amount, category: category, frequency: frequency }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) location.reload();
    else alert(d.error || "Error saving recurring transaction.");
  }}).catch(function() {{ alert("Network error."); }});
}}
function deleteRecurring(idx) {{
  if (!confirm("Remove this recurring transaction?")) return;
  fetch("/api/recurring?idx=" + idx, {{ method: "DELETE" }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ if (d.ok) location.reload(); }})
    .catch(function() {{}});
}}
function applyRecurring() {{
  fetch("/api/recurring/apply", {{ method: "POST" }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (d.ok) {{ alert("Added " + d.count + " recurring transactions for this month."); location.reload(); }}
      else alert(d.error || "Error applying recurring transactions.");
    }}).catch(function() {{ alert("Network error."); }});
}}

/* ── Detect Recurring from Transaction History ── */
var _suggestedRecurring = [];
function detectRecurring() {{
  var btn = event.target;
  btn.textContent = "Scanning...";
  btn.disabled = true;
  fetch("/api/recurring/detect")
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      btn.textContent = "Detect from History";
      btn.disabled = false;
      _suggestedRecurring = d.suggestions || [];
      if (_suggestedRecurring.length === 0) {{
        alert("No recurring patterns detected. Import more bank statements to build history.");
        return;
      }}
      renderSuggestions();
    }}).catch(function() {{
      btn.textContent = "Detect from History";
      btn.disabled = false;
      alert("Error scanning transactions.");
    }});
}}
function renderSuggestions() {{
  var container = document.getElementById("recurring-suggestions");
  var tbody = document.getElementById("suggested-recurring-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  _suggestedRecurring.forEach(function(s, idx) {{
    var tr = document.createElement("tr");
    tr.innerHTML = '<td>' + s.name + '</td>' +
      '<td class="mono" style="text-align:right">$' + s.amount.toFixed(2) + '</td>' +
      '<td>' + s.category + '</td>' +
      '<td>' + s.frequency + '</td>' +
      '<td class="hint">' + s.occurrences + 'x in ' + s.months.length + ' months</td>' +
      '<td style="white-space:nowrap;">' +
        '<button type="button" class="success" style="padding:2px 8px;font-size:0.7rem;margin-right:4px;" onclick="acceptSuggestion(' + idx + ')">Add</button>' +
        '<button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;" onclick="dismissSuggestion(' + idx + ')">Skip</button>' +
      '</td>';
    tbody.appendChild(tr);
  }});
  container.style.display = _suggestedRecurring.length > 0 ? "block" : "none";
}}
function acceptSuggestion(idx) {{
  var s = _suggestedRecurring[idx];
  if (!s) return;
  fetch("/api/recurring", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ name: s.name, amount: s.amount, category: s.category, frequency: s.frequency }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) {{
      _suggestedRecurring.splice(idx, 1);
      renderSuggestions();
      // Add to the main recurring table immediately
      var mainBody = document.getElementById("recurring-body");
      if (mainBody) {{
        var tr = document.createElement("tr");
        var newIdx = mainBody.children.length;
        tr.innerHTML = '<td>' + s.name + '</td><td class="mono">$' + s.amount.toFixed(2) + '</td><td>' + s.category + '</td><td>' + s.frequency + '</td><td><button type="button" class="secondary" style="padding:2px 8px;font-size:0.7rem;" onclick="deleteRecurring(' + newIdx + ')">x</button></td>';
        mainBody.appendChild(tr);
      }}
    }}
  }}).catch(function() {{}});
}}
function dismissSuggestion(idx) {{
  _suggestedRecurring.splice(idx, 1);
  renderSuggestions();
}}
// Auto-detect recurring after statement import
(function() {{
  var params = new URLSearchParams(window.location.search);
  if (params.get("detect_recurring") === "1") {{
    setTimeout(function() {{ detectRecurring(); }}, 800);
  }}
}})();

/* ── Physical Metals ── */
function toggleMetalForm() {{
  var f = document.getElementById("metal-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}}
function saveMetalPurchase() {{
  var metal = document.getElementById("metal-type").value;
  var form = document.getElementById("metal-form-desc").value.trim();
  var qty = parseFloat(document.getElementById("metal-qty").value) || 0;
  var cost = parseFloat(document.getElementById("metal-cost").value) || 0;
  var date = document.getElementById("metal-date").value;
  var note = document.getElementById("metal-note").value.trim();
  if (qty <= 0) {{ alert("Quantity must be greater than 0."); return; }}
  fetch("/api/physical-metals", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ metal: metal, form: form, qty_oz: qty, cost_per_oz: cost, date: date, note: note }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) location.reload();
    else alert(d.error || "Error saving.");
  }}).catch(function() {{ alert("Network error."); }});
}}
function deleteMetalRow(idx) {{
  if (!confirm("Remove this metals entry?")) return;
  fetch("/api/physical-metals", {{
    method: "DELETE",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ index: idx }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) location.reload();
    else alert(d.error || "Error removing.");
  }}).catch(function() {{ alert("Network error."); }});
}}

/* ── Dividend & Fee Tracking ── */
var DIVIDENDS = {dividends_json};
function showDivForm() {{
  var f = document.getElementById("div-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}}
function saveDividend() {{
  var date = document.getElementById("div-date").value;
  var ticker = document.getElementById("div-ticker").value.trim().toUpperCase();
  var amount = parseFloat(document.getElementById("div-amount").value) || 0;
  var dtype = document.getElementById("div-type").value;
  var note = document.getElementById("div-note").value.trim();
  if (!ticker || amount <= 0) {{ alert("Ticker and amount are required."); return; }}
  fetch("/api/dividends", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ date: date, ticker: ticker, amount: amount, type: dtype, note: note }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) location.reload();
    else alert(d.error || "Error saving.");
  }}).catch(function() {{ alert("Network error."); }});
}}
function buildDivChart() {{
  var ctx = document.getElementById("div-chart");
  if (!ctx || typeof Chart === "undefined" || DIVIDENDS.length === 0) return;
  // Group by month
  var months = {{}};
  DIVIDENDS.forEach(function(d) {{
    var m = d.date ? d.date.substring(0, 7) : "unknown";
    if (!months[m]) months[m] = {{ div: 0, fee: 0 }};
    if (d.type === "dividend") months[m].div += d.amount || 0;
    else months[m].fee += d.amount || 0;
  }});
  var labels = Object.keys(months).sort().slice(-12);
  var divData = labels.map(function(m) {{ return months[m].div; }});
  var feeData = labels.map(function(m) {{ return -months[m].fee; }});
  new Chart(ctx, {{
    type: "bar",
    data: {{
      labels: labels,
      datasets: [
        {{ label: "Dividends", data: divData, backgroundColor: "rgba(52,211,153,0.7)" }},
        {{ label: "Fees", data: feeData, backgroundColor: "rgba(248,113,113,0.7)" }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: "#94a3b8", font: {{ size: 10 }} }} }} }},
      scales: {{
        x: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }} }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }}
      }}
    }}
  }});
  // Update summary totals
  var totalDiv = 0, totalFee = 0;
  DIVIDENDS.forEach(function(d) {{
    if (d.type === "dividend") totalDiv += d.amount || 0;
    else totalFee += d.amount || 0;
  }});
  var netInc = totalDiv - totalFee;
  var fmt = function(v) {{ return "$" + v.toLocaleString(undefined, {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}); }};
  var elInc = document.getElementById("div-total-inc"); if (elInc) elInc.textContent = fmt(totalDiv);
  var elFee = document.getElementById("div-total-fee"); if (elFee) elFee.textContent = fmt(totalFee);
  var elNet = document.getElementById("div-total-net");
  if (elNet) {{ elNet.textContent = (netInc >= 0 ? "+" : "-") + fmt(Math.abs(netInc)); elNet.style.color = netInc >= 0 ? "var(--success)" : "var(--danger)"; }}
}}
buildDivChart();

/* ── Drag-to-Reorder Dashboard Widgets ── */
(function() {{
  var dragSrc = null;
  function setupDrag() {{
    document.querySelectorAll(".widget-card").forEach(function(card) {{
      card.addEventListener("dragstart", function(e) {{
        dragSrc = card;
        card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", card.dataset.widget);
      }});
      card.addEventListener("dragend", function() {{
        card.classList.remove("dragging");
        document.querySelectorAll(".drag-over").forEach(function(el) {{ el.classList.remove("drag-over"); }});
        dragSrc = null;
      }});
      card.addEventListener("dragover", function(e) {{
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        if (card !== dragSrc) card.classList.add("drag-over");
      }});
      card.addEventListener("dragleave", function() {{
        card.classList.remove("drag-over");
      }});
      card.addEventListener("drop", function(e) {{
        e.preventDefault();
        card.classList.remove("drag-over");
        if (!dragSrc || dragSrc === card) return;
        // Swap positions
        var parent = card.parentNode;
        var srcParent = dragSrc.parentNode;
        var srcNext = dragSrc.nextElementSibling;
        if (srcNext === card) {{
          parent.insertBefore(dragSrc, card.nextElementSibling);
        }} else {{
          var cardNext = card.nextElementSibling;
          srcParent.insertBefore(card, srcNext);
          parent.insertBefore(dragSrc, cardNext);
        }}
        saveWidgetOrder();
      }});
    }});
  }}
  function saveWidgetOrder() {{
    var order = {{}};
    document.querySelectorAll(".widget-col").forEach(function(col) {{
      var colId = col.id;
      var widgets = [];
      col.querySelectorAll(".widget-card").forEach(function(w) {{
        widgets.push(w.dataset.widget);
      }});
      order[colId] = widgets;
    }});
    localStorage.setItem("wos-widget-order", JSON.stringify(order));
    // Also persist to server
    fetch("/api/widget-order", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(order)
    }}).catch(function() {{}});
  }}
  function restoreWidgetOrder() {{
    // Try localStorage first (faster), fall back to server-saved order
    var saved = localStorage.getItem("wos-widget-order");
    if (!saved) {{
      // Try from server-rendered config
      var serverOrder = {widget_order_json};
      if (serverOrder && Object.keys(serverOrder).length > 0) {{
        saved = JSON.stringify(serverOrder);
      }}
    }}
    if (!saved) return;
    try {{
      var order = JSON.parse(saved);
      for (var colId in order) {{
        var col = document.getElementById(colId);
        if (!col) continue;
        order[colId].forEach(function(widgetId) {{
          var widget = document.querySelector('[data-widget="' + widgetId + '"]');
          if (widget) col.appendChild(widget);
        }});
      }}
    }} catch(e) {{}}
  }}
  restoreWidgetOrder();
  setupDrag();
}})();

/* ── Goal Tracking ── */
var GOALS = {goals_json};
function showGoalForm() {{
  var f = document.getElementById("goal-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}}
function saveGoal() {{
  var name = document.getElementById("goal-name").value.trim();
  var target = parseFloat(document.getElementById("goal-target").value) || 0;
  var current = parseFloat(document.getElementById("goal-current").value) || 0;
  var date = document.getElementById("goal-date").value;
  if (!name || target <= 0) {{ alert("Name and target amount are required."); return; }}
  fetch("/api/goals", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ name: name, target: target, current: current, target_date: date }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) location.reload();
  }}).catch(function() {{ alert("Error saving goal."); }});
}}
function deleteGoal(idx) {{
  if (!confirm("Remove this goal?")) return;
  fetch("/api/goals?idx=" + idx, {{ method: "DELETE" }})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{ if (d.ok) location.reload(); }});
}}
function updateGoalAmount(idx) {{
  var val = prompt("Enter current amount for this goal:");
  if (val === null) return;
  var amount = parseFloat(val);
  if (isNaN(amount)) return;
  fetch("/api/goals/update", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ idx: idx, current: amount }})
  }}).then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.ok) location.reload();
  }});
}}

/* ── Monte Carlo Simulation ── */
function runMonteCarlo() {{
  var mcYearsEl = document.getElementById("mc-years");
  if (!mcYearsEl) return;
  var years = parseInt(mcYearsEl.value) || 10;
  var contrib = parseFloat(document.getElementById("mc-contrib").value) || 0;
  var current = {total:.2f};
  var annualReturn = 0.07;
  var annualVol = 0.15;  // ~15% annual volatility (historical S&P)
  var monthlyReturn = annualReturn / 12;
  var monthlyVol = annualVol / Math.sqrt(12);
  var months = years * 12;
  var sims = 1000;
  var allPaths = [];
  for (var s = 0; s < sims; s++) {{
    var path = [current];
    var val = current;
    for (var m = 0; m < months; m++) {{
      // Box-Muller for normal random
      var u1 = Math.random(), u2 = Math.random();
      var z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      var ret = monthlyReturn + monthlyVol * z;
      val = val * (1 + ret) + contrib;
      path.push(Math.max(val, 0));
    }}
    allPaths.push(path);
  }}
  // Calculate percentiles at each month
  var labels = [];
  var p10 = [], p25 = [], p50 = [], p75 = [], p90 = [];
  for (var m = 0; m <= months; m++) {{
    if (m % (months > 120 ? 6 : 3) === 0 || m === months) {{
      labels.push(m < 12 ? m + "mo" : (m/12).toFixed(0) + "Y");
      var vals = allPaths.map(function(p) {{ return p[m]; }}).sort(function(a,b) {{ return a - b; }});
      p10.push(vals[Math.floor(sims * 0.1)]);
      p25.push(vals[Math.floor(sims * 0.25)]);
      p50.push(vals[Math.floor(sims * 0.5)]);
      p75.push(vals[Math.floor(sims * 0.75)]);
      p90.push(vals[Math.floor(sims * 0.9)]);
    }}
  }}
  var ctx = document.getElementById("mc-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (window._mcChart) window._mcChart.destroy();
  window._mcChart = new Chart(ctx, {{
    type: "line",
    data: {{
      labels: labels,
      datasets: [
        {{ label: "90th %ile", data: p90, borderColor: "rgba(212,160,23,0.3)", backgroundColor: "rgba(212,160,23,0.05)", fill: "+1", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.6)", tension: 0.3 }},
        {{ label: "75th %ile", data: p75, borderColor: "rgba(212,160,23,0.5)", backgroundColor: "rgba(212,160,23,0.08)", fill: "+1", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.8)", tension: 0.3 }},
        {{ label: "Median", data: p50, borderColor: "var(--accent-primary)", borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: "#d4a017", tension: 0.3, fill: false }},
        {{ label: "25th %ile", data: p25, borderColor: "rgba(212,160,23,0.5)", backgroundColor: "rgba(212,160,23,0.08)", fill: "+1", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.8)", tension: 0.3 }},
        {{ label: "10th %ile", data: p10, borderColor: "rgba(212,160,23,0.3)", backgroundColor: "transparent", borderWidth: 1, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: "rgba(212,160,23,0.6)", tension: 0.3 }}
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: "index", intersect: false }},
      plugins: {{
        legend: {{ labels: {{ color: "#94a3b8", font: {{ size: 10 }} }} }},
        tooltip: {{
          yAlign: "bottom", caretPadding: 8,
          mode: "index", intersect: false,
          backgroundColor: "rgba(15,23,42,0.95)",
          titleColor: "#e2e8f0",
          bodyColor: "#cbd5e1",
          borderColor: "rgba(212,160,23,0.4)",
          borderWidth: 1,
          padding: 12,
          bodyFont: {{ family: "'JetBrains Mono', monospace", size: 12 }},
          callbacks: {{
            title: function(items) {{ return items[0].label; }},
            label: function(ctx) {{
              var val = ctx.raw;
              var formatted = val >= 1000000
                ? "$" + (val/1000000).toFixed(2) + "M"
                : "$" + Math.round(val).toLocaleString();
              return " " + ctx.dataset.label + ":  " + formatted;
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }}, maxTicksLimit: 12 }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }}, callback: function(v) {{ return "$" + (v >= 1000000 ? (v/1000000).toFixed(1) + "M" : (v/1000).toFixed(0) + "K"); }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }}
      }}
    }}
  }});
}}
// Auto-run on Charts tab
setTimeout(runMonteCarlo, 500);

/* ── Drawdown Analysis ── */
function buildDrawdownChart() {{
  if (PRICE_HISTORY_DATA.length < 3) return;
  if (!document.getElementById("drawdown-chart")) return;
  var labels = [], drawdowns = [];
  var peak = 0;
  var maxDD = 0, maxDDDate = "", recoveryDays = 0, inDD = false, ddStart = "";
  PRICE_HISTORY_DATA.forEach(function(e) {{
    var t = e.total || 0;
    if (t > peak) {{ peak = t; inDD = false; }}
    var dd = peak > 0 ? ((t - peak) / peak) * 100 : 0;
    if (dd < maxDD) {{ maxDD = dd; maxDDDate = e.date; }}
    labels.push(e.date);
    drawdowns.push(dd);
  }});
  var ctx = document.getElementById("drawdown-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (window._ddChart) window._ddChart.destroy();
  window._ddChart = new Chart(ctx, {{
    type: "line",
    data: {{
      labels: labels,
      datasets: [{{
        label: "Drawdown %",
        data: drawdowns,
        borderColor: "rgba(248,113,113,0.8)",
        backgroundColor: "rgba(248,113,113,0.15)",
        fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.3
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: {{ yAlign: "bottom", caretPadding: 8 }}}},
      scales: {{
        x: {{ ticks: {{ color: "#64748b", font: {{ size: 9 }}, maxTicksLimit: 10 }}, grid: {{ display: false }} }},
        y: {{ max: 0, ticks: {{ color: "#64748b", font: {{ size: 10 }}, callback: function(v) {{ return v.toFixed(1) + "%"; }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }}
      }}
    }}
  }});
  // Stats
  var statsEl = document.getElementById("drawdown-stats");
  if (statsEl) {{
    statsEl.innerHTML = '<div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
      '<div class="hint" style="margin-bottom:4px;">Max Drawdown</div>' +
      '<div class="mono" style="font-size:1.1rem;color:var(--danger);">' + maxDD.toFixed(1) + '%</div>' +
      '<div class="hint" style="margin-top:2px;">' + maxDDDate + '</div>' +
      '</div>' +
      '<div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
      '<div class="hint" style="margin-bottom:4px;">Current from Peak</div>' +
      '<div class="mono" style="font-size:1.1rem;color:' + (drawdowns.length > 0 && drawdowns[drawdowns.length-1] < -1 ? 'var(--danger)' : 'var(--success)') + ';">' +
      (drawdowns.length > 0 ? drawdowns[drawdowns.length-1].toFixed(1) : '0') + '%</div>' +
      '</div>' +
      '<div style="padding:10px 16px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
      '<div class="hint" style="margin-bottom:4px;">Data Points</div>' +
      '<div class="mono" style="font-size:1.1rem;">' + PRICE_HISTORY_DATA.length + '</div>' +
      '</div>';
  }}
}}
buildDrawdownChart();

/* ── Performance Attribution ── */
var PERF_DATA = {perf_json};
function buildPerfAttribution() {{
  if (!document.getElementById("perf-attr-chart")) return;
  var buckets = PERF_DATA.buckets;
  var total = PERF_DATA.total;
  if (!buckets || total <= 0) return;
  var labels = Object.keys(buckets);
  var values = labels.map(function(b) {{ return buckets[b]; }});
  var pcts = labels.map(function(b) {{ return ((buckets[b] / total) * 100).toFixed(1); }});
  var colorMap = {{ "Cash":"#64748b","Equities":"#34d399","Gold":"#d4a017","Silver":"#a0a0a0","Crypto":"#818cf8","RealAssets":"#06b6d4","Art":"#f472b6","ManagedBlend":"#fb923c" }};
  var colors = labels.map(function(b) {{ return colorMap[b] || "#94a3b8"; }});
  var ctx = document.getElementById("perf-attr-chart");
  if (!ctx || typeof Chart === "undefined") return;
  new Chart(ctx, {{
    type: "bar",
    data: {{
      labels: labels,
      datasets: [{{ label: "Value ($)", data: values, backgroundColor: colors }}]
    }},
    options: {{
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: function(ctx) {{ return "$" + ctx.raw.toLocaleString() + " (" + pcts[ctx.dataIndex] + "%)"; }} }} }}
      }},
      scales: {{
        x: {{ ticks: {{ color: "#64748b", font: {{ size: 10 }}, callback: function(v) {{ return "$" + (v/1000).toFixed(0) + "K"; }} }}, grid: {{ color: "rgba(255,255,255,0.03)" }} }},
        y: {{ ticks: {{ color: "#94a3b8", font: {{ size: 11 }} }}, grid: {{ display: false }} }}
      }}
    }}
  }});
  // Build table
  var tableEl = document.getElementById("perf-attr-table");
  if (tableEl) {{
    var rows = '<table><thead><tr><th>Asset Class</th><th style="text-align:right">Value</th><th style="text-align:right">Weight</th></tr></thead><tbody>';
    labels.forEach(function(b, i) {{
      rows += '<tr><td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' + colors[i] + ';margin-right:8px;"></span>' + b + '</td><td class="mono" style="text-align:right">$' + values[i].toLocaleString() + '</td><td class="mono" style="text-align:right">' + pcts[i] + '%</td></tr>';
    }});
    rows += '</tbody></table>';
    if (PERF_DATA.overall_return !== 0) {{
      rows += '<div style="margin-top:12px;padding:10px;background:var(--bg-input);border-radius:var(--radius);text-align:center;">' +
        '<span class="hint">Overall Return: </span><strong class="mono" style="color:' + (PERF_DATA.overall_return >= 0 ? 'var(--success)' : 'var(--danger)') + ';">' + (PERF_DATA.overall_return >= 0 ? '+' : '') + PERF_DATA.overall_return.toFixed(1) + '%</strong>' +
        '</div>';
    }}
    tableEl.innerHTML = rows;
  }}
}}
buildPerfAttribution();

/* ── Multi-Currency ── */
var FX_RATES = {{}};
var BASE_CURRENCY = localStorage.getItem("wos-currency") || "USD";
var CURRENCY_SYMBOLS = {{ "USD":"$", "EUR":"\u20ac", "GBP":"\u00a3", "JPY":"\u00a5", "CAD":"C$", "AUD":"A$", "CHF":"Fr" }};
(function() {{
  var sel = document.getElementById("currency-selector");
  if (sel) sel.value = BASE_CURRENCY;
  if (BASE_CURRENCY !== "USD") fetchFxAndConvert(BASE_CURRENCY);
}})();
function changeCurrency(currency) {{
  localStorage.setItem("wos-currency", currency);
  BASE_CURRENCY = currency;
  if (currency === "USD") {{
    location.reload();
    return;
  }}
  fetchFxAndConvert(currency);
}}
function fetchFxAndConvert(currency) {{
  fetch("/api/fx-rate?to=" + currency)
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (d.rate) {{
        FX_RATES[currency] = d.rate;
        convertDisplayCurrency(d.rate, CURRENCY_SYMBOLS[currency] || currency + " ");
      }}
    }}).catch(function() {{}});
}}
function convertDisplayCurrency(rate, symbol) {{
  // Convert net worth
  var nw = document.getElementById("net-worth-counter");
  if (nw) {{
    var usdVal = parseFloat(nw.dataset.target) || 0;
    var converted = usdVal * rate;
    nw.textContent = symbol + converted.toLocaleString(undefined, {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
  }}
  // Convert dollar amounts in portfolio-value contexts (not market prices)
  // Target: allocation table values, holdings totals, goal amounts, budget values
  document.querySelectorAll("td, .mono, .goal-card .mono, .hero-change").forEach(function(el) {{
    var text = el.textContent.trim();
    // Only convert values that start with $ and haven't been converted yet
    if (text.match(/^\$[\d,]+/) && !el.dataset.fxDone) {{
      el.dataset.fxDone = "1";
      el.dataset.fxOriginal = text;
      var num = parseFloat(text.replace(/[$,]/g, ""));
      if (!isNaN(num) && num > 0) {{
        el.textContent = symbol + (num * rate).toLocaleString(undefined, {{ minimumFractionDigits: 0, maximumFractionDigits: 0 }});
      }}
    }}
  }});
}}

/* ── Background price refresh on page load ── */
(function() {{
  function _startLongPoll() {{
    var enabled = document.getElementById("auto-enabled") && document.getElementById("auto-enabled").checked;
    var interval = parseInt((document.getElementById("auto-interval") && document.getElementById("auto-interval").value) || 15);
    if (enabled !== false && interval >= 5) startPeriodicLivePoll(interval);
  }}
  // Immediate poll: update from cache right away (before bg-refresh finishes)
  fetch("/api/live-data").then(function(r) {{ return r.json(); }}).then(applyLiveDataToDOM).catch(function() {{}});
  // Kick off background refresh, then poll for fresh data
  fetch("/api/bg-refresh", {{ method:"POST" }}).then(function() {{
    var polls = 0;
    var maxPolls = 8;
    function pollLive() {{
      polls++;
      fetch("/api/live-data").then(function(r) {{ return r.json(); }}).then(function(d) {{
        applyLiveDataToDOM(d);
        if (polls < maxPolls) {{ setTimeout(pollLive, 3000); }} else {{ _startLongPoll(); }}
      }}).catch(function() {{
        if (polls < maxPolls) setTimeout(pollLive, 3000); else _startLongPoll();
      }});
    }}
    setTimeout(pollLive, 4000);
  }}).catch(function() {{
    _startLongPoll();
  }});
}})();

</script>
</body>
</html>"""

    # ── Lazy-load: strip non-active tab content to reduce page size ──
    import re as _re
    _placeholder = '<div class="tab-placeholder" data-lazy-tab="{t}"><div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 20px;color:var(--text-muted);"><div style="width:32px;height:32px;border:3px solid rgba(255,255,255,0.1);border-top-color:var(--accent-primary);border-radius:50%;animation:spin 0.8s linear infinite;"></div><p style="margin-top:16px;">Loading...</p></div></div>'
    for _tab in ["summary", "balances", "budget", "holdings", "import", "history", "economics"]:
        if _tab == active_tab:
            continue
        _start_m = f"<!-- TAB:{_tab} -->"
        _end_m = f"<!-- /TAB:{_tab} -->"
        _si = html.find(_start_m)
        _ei = html.find(_end_m)
        if _si != -1 and _ei != -1:
            html = html[:_si + len(_start_m)] + "\n" + _placeholder.format(t=_tab) + "\n" + html[_ei:]

    return html

