"""Budget API routes: budget config, transactions, recurring, categorization.

Budget is available to all tiers (free + pro). Only advanced features
like CSV import and recurring rules use @requires_pro.
"""

import csv
import hashlib
import io
from datetime import date as dt_date, datetime, timedelta

from flask import Blueprint, jsonify, request as flask_request
from flask_login import login_required, current_user
from sqlalchemy import func, extract

from ..extensions import db
from ..utils.auth import requires_pro
from ..models.budget import BudgetConfig, Transaction, RecurringTransaction, CategoryRule

api_budget_bp = Blueprint("api_budget", __name__)

BUDGET_TEMPLATES = {
    "simple": {
        "name": "Simple (50/30/20)",
        "categories": [
            {"name": "Needs", "limit": 50, "is_percent": True},
            {"name": "Wants", "limit": 30, "is_percent": True},
            {"name": "Savings", "limit": 20, "is_percent": True},
        ],
    },
    "detailed": {
        "name": "Detailed Monthly",
        "categories": [
            {"name": "Housing", "limit": 0},
            {"name": "Utilities", "limit": 0},
            {"name": "Groceries", "limit": 0},
            {"name": "Transport", "limit": 0},
            {"name": "Insurance", "limit": 0},
            {"name": "Healthcare", "limit": 0},
            {"name": "Dining Out", "limit": 0},
            {"name": "Entertainment", "limit": 0},
            {"name": "Shopping", "limit": 0},
            {"name": "Subscriptions", "limit": 0},
            {"name": "Savings", "limit": 0},
            {"name": "Other", "limit": 0},
        ],
    },
    "investor": {
        "name": "Investor Focus",
        "categories": [
            {"name": "Living Expenses", "limit": 0},
            {"name": "Investment Contributions", "limit": 0},
            {"name": "Emergency Fund", "limit": 0},
            {"name": "Debt Payments", "limit": 0},
            {"name": "Discretionary", "limit": 0},
        ],
    },
}


@api_budget_bp.route("/budget-data")
@login_required
def budget_data():
    """Return the user's budget config and recent transactions."""
    from ..models.settings import UserSettings
    config = BudgetConfig.query.filter_by(user_id=current_user.id).first()
    recent_txns = (Transaction.query
                   .filter_by(user_id=current_user.id)
                   .order_by(Transaction.date.desc())
                   .limit(200)
                   .all())

    categories = list(config.categories) if config else []
    monthly_income = config.monthly_income if config else 0

    inv_budget = _compute_monthly_investment_budget(current_user.id)
    if inv_budget > 0:
        found = False
        for cat in categories:
            if cat.get("name", "").lower() == "investments":
                cat["limit"] = inv_budget
                found = True
                break
        if not found:
            categories.append({"name": "Investments", "limit": inv_budget})
        for cat in categories:
            if cat.get("name", "").lower() in ("savings/investments", "savings / investments"):
                cat["name"] = "Savings"

    budget_limits = {}
    budget_cats = []
    for cat in categories:
        name = cat.get("name", "")
        limit_val = float(cat.get("limit", 0))
        if cat.get("is_percent") and monthly_income:
            limit_val = monthly_income * limit_val / 100.0
        budget_limits[name] = limit_val
        budget_cats.append(name)

    return jsonify({
        "budget": {
            "monthly_income": monthly_income,
            "categories": categories,
            "rollover_enabled": config.rollover_enabled if config else False,
        },
        "budget_limits": budget_limits,
        "budget_cats": budget_cats,
        "transfer_categories": list(TRANSFER_CATEGORIES),
        "transactions": [
            {"id": t.id, "date": t.date.isoformat(), "description": t.description,
             "amount": t.amount, "category": t.category, "source": t.source,
             "is_transfer": t.category in TRANSFER_CATEGORIES}
            for t in recent_txns
        ],
    })


@api_budget_bp.route("/budget-data", methods=["POST"])
@login_required

def save_budget():
    """Save budget configuration (income, categories, rollover)."""
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    config = BudgetConfig.query.filter_by(user_id=current_user.id).first()
    if not config:
        config = BudgetConfig(user_id=current_user.id)
        db.session.add(config)
    if "monthly_income" in data:
        config.monthly_income = float(data["monthly_income"])
    if "categories" in data:
        config.categories = data["categories"]
        for cat in data["categories"]:
            if cat.get("name", "").lower() == "investments":
                _sync_investment_budget_from_limit(current_user.id, float(cat.get("limit", 0)))
                break
    if "rollover_enabled" in data:
        config.rollover_enabled = bool(data["rollover_enabled"])
    db.session.commit()
    return jsonify({"success": True})


@api_budget_bp.route("/budget-templates")
@login_required
def get_budget_templates():
    """Return available budget category templates."""
    return jsonify({
        "templates": {
            k: {"name": v["name"], "categories": v["categories"]}
            for k, v in BUDGET_TEMPLATES.items()
        }
    })


@api_budget_bp.route("/budget-templates/<template_id>", methods=["POST"])
@login_required

def apply_budget_template(template_id):
    """Apply a budget template to the user's config."""
    template = BUDGET_TEMPLATES.get(template_id)
    if not template:
        return jsonify({"error": "Unknown template"}), 404

    config = BudgetConfig.query.filter_by(user_id=current_user.id).first()
    if not config:
        config = BudgetConfig(user_id=current_user.id)
        db.session.add(config)
    config.categories = template["categories"]
    db.session.commit()
    return jsonify({"success": True, "categories": template["categories"]})


@api_budget_bp.route("/transactions", methods=["POST"])
@login_required

def add_transaction():
    """Add a manual transaction."""
    data = flask_request.get_json(silent=True) or {}
    txn = Transaction(
        user_id=current_user.id,
        date=dt_date.fromisoformat(data.get("date", dt_date.today().isoformat())),
        description=data.get("description", ""),
        amount=float(data.get("amount", 0)),
        category=_auto_categorize(current_user.id, data.get("description", ""))
                 or data.get("category", "Other"),
        source="manual",
    )
    db.session.add(txn)
    db.session.commit()
    return jsonify({"success": True, "id": txn.id, "category": txn.category})


@api_budget_bp.route("/transactions/<int:txn_id>", methods=["PUT"])
@login_required

def update_transaction(txn_id):
    """Update an existing transaction's category or details."""
    txn = Transaction.query.filter_by(id=txn_id, user_id=current_user.id).first()
    if not txn:
        return jsonify({"error": "Not found"}), 404
    data = flask_request.get_json(silent=True) or {}
    if "category" in data:
        txn.category = data["category"]
    if "description" in data:
        txn.description = data["description"]
    if "amount" in data:
        txn.amount = float(data["amount"])
    if "date" in data:
        txn.date = dt_date.fromisoformat(data["date"])
    db.session.commit()
    return jsonify({"success": True})


@api_budget_bp.route("/transactions/<int:txn_id>", methods=["DELETE"])
@login_required

def delete_transaction(txn_id):
    """Delete a transaction."""
    txn = Transaction.query.filter_by(id=txn_id, user_id=current_user.id).first()
    if txn:
        db.session.delete(txn)
        db.session.commit()
    return jsonify({"success": True})


@api_budget_bp.route("/transactions/import-csv", methods=["POST"])
@login_required

def import_transactions_csv():
    """Import transactions from a CSV file.

    Expected columns: date, description, amount (negative = expense).
    Optional: category. Duplicates detected via hash of date+description+amount.
    """
    file = flask_request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    text = file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        try:
            raw_date = row.get("date", row.get("Date", "")).strip()
            raw_desc = row.get("description", row.get("Description",
                       row.get("memo", row.get("Memo", "")))).strip()
            raw_amount = row.get("amount", row.get("Amount",
                         row.get("debit", row.get("Debit", "0")))).strip()

            raw_amount = raw_amount.replace("$", "").replace(",", "")
            amount = float(raw_amount) if raw_amount else 0

            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"):
                try:
                    txn_date = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                errors.append(f"Row {row_num}: bad date '{raw_date}'")
                continue

            import_hash = hashlib.md5(
                f"{txn_date.isoformat()}|{raw_desc}|{amount:.2f}".encode()
            ).hexdigest()

            if Transaction.query.filter_by(user_id=current_user.id, import_hash=import_hash).first():
                skipped += 1
                continue

            category = (row.get("category", row.get("Category", "")).strip()
                        or _auto_categorize(current_user.id, raw_desc)
                        or "Other")

            txn = Transaction(
                user_id=current_user.id,
                date=txn_date,
                description=raw_desc,
                amount=amount,
                category=category,
                source="csv",
                import_hash=import_hash,
            )
            db.session.add(txn)
            imported += 1

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    db.session.commit()
    return jsonify({
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10],
    })


@api_budget_bp.route("/category-rules")
@login_required
def get_category_rules():
    """Return the user's auto-categorization rules."""
    rules = (CategoryRule.query
             .filter_by(user_id=current_user.id)
             .order_by(CategoryRule.priority.desc())
             .all())
    return jsonify({
        "rules": [{"id": r.id, "keyword": r.keyword, "category": r.category}
                  for r in rules],
    })


@api_budget_bp.route("/category-rules", methods=["POST"])
@login_required

def save_category_rule():
    """Add or update a categorization rule."""
    data = flask_request.get_json(silent=True) or {}
    keyword = data.get("keyword", "").strip().lower()
    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400
    rule = CategoryRule(
        user_id=current_user.id,
        keyword=keyword,
        category=data.get("category", "Other"),
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify({"success": True, "id": rule.id})


@api_budget_bp.route("/category-rules/<int:rule_id>", methods=["DELETE"])
@login_required

def delete_category_rule(rule_id):
    """Delete a categorization rule."""
    rule = CategoryRule.query.filter_by(id=rule_id, user_id=current_user.id).first()
    if rule:
        db.session.delete(rule)
        db.session.commit()
    return jsonify({"success": True})


TRANSFER_CATEGORIES = {"Transfer"}


def _compute_monthly_investment_budget(user_id):
    """Derive the monthly investment budget from UserSettings contribution plan."""
    from ..models.settings import UserSettings
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings or not settings.contribution_amount:
        return 0
    amt = settings.contribution_amount
    freq = settings.contribution_frequency or "biweekly"
    if freq == "biweekly":
        return round(amt * 26 / 12)
    elif freq == "weekly":
        return round(amt * 52 / 12)
    return round(amt)


def _sync_investment_budget_from_limit(user_id, monthly_limit):
    """Reverse-compute and save UserSettings.contribution_amount from a monthly limit."""
    from ..models.settings import UserSettings
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.session.add(settings)
    freq = settings.contribution_frequency or "biweekly"
    if freq == "biweekly":
        settings.contribution_amount = round(monthly_limit * 12 / 26, 2)
    elif freq == "weekly":
        settings.contribution_amount = round(monthly_limit * 12 / 52, 2)
    else:
        settings.contribution_amount = monthly_limit


@api_budget_bp.route("/spending-insights")
@login_required
def spending_insights():
    """Month-over-month spending comparison and savings rate.

    Transfers between the user's own accounts (category == "Transfer") are
    excluded from spending totals and savings-rate calculation but still
    returned under ``transfer_comparisons`` so the frontend can display them
    in a separate section.
    """
    today = dt_date.today()
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    config = BudgetConfig.query.filter_by(user_id=current_user.id).first()
    monthly_income = config.monthly_income if config else 0

    def _month_totals(start, end):
        rows = (db.session.query(Transaction.category, func.sum(Transaction.amount))
                .filter(Transaction.user_id == current_user.id,
                        Transaction.date >= start, Transaction.date < end)
                .group_by(Transaction.category)
                .all())
        return {cat: float(total) for cat, total in rows}

    this_month = _month_totals(this_month_start, this_month_start + timedelta(days=32))
    last_month = _month_totals(last_month_start, this_month_start)

    def _spending_total(month_data):
        return sum(
            abs(v) for cat, v in month_data.items()
            if v < 0 and cat not in TRANSFER_CATEGORIES
        )

    this_total = _spending_total(this_month)
    last_total = _spending_total(last_month)

    this_transfer = sum(abs(v) for cat, v in this_month.items() if cat in TRANSFER_CATEGORIES)
    last_transfer = sum(abs(v) for cat, v in last_month.items() if cat in TRANSFER_CATEGORIES)

    savings_rate = 0
    if monthly_income > 0:
        savings_rate = round((monthly_income - this_total) / monthly_income * 100, 1)

    all_cats = sorted(set(list(this_month.keys()) + list(last_month.keys())))
    comparisons = []
    transfer_comparisons = []
    for cat in all_cats:
        curr = abs(this_month.get(cat, 0))
        prev = abs(last_month.get(cat, 0))
        change_pct = round((curr - prev) / prev * 100, 1) if prev > 0 else 0
        entry = {
            "category": cat,
            "this_month": curr,
            "last_month": prev,
            "change_pct": change_pct,
        }
        if cat in TRANSFER_CATEGORIES:
            transfer_comparisons.append(entry)
        else:
            comparisons.append(entry)

    comparisons.sort(key=lambda x: x["this_month"], reverse=True)

    return jsonify({
        "savings_rate": savings_rate,
        "this_month_total": this_total,
        "last_month_total": last_total,
        "month_change_pct": round((this_total - last_total) / last_total * 100, 1) if last_total > 0 else 0,
        "comparisons": comparisons,
        "transfer_comparisons": transfer_comparisons,
        "this_month_transfers": this_transfer,
        "last_month_transfers": last_transfer,
    })


@api_budget_bp.route("/drift-targets")
@login_required
def drift_targets():
    """Compute suggested monthly investment amounts per bucket based on allocation drift."""
    from ..models.settings import UserSettings
    from ..services.portfolio_service import compute_portfolio_value
    from ..utils.buckets import rollup_breakdown, normalize_bucket, BUCKET_PARENTS

    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    rebalance_months = (settings.rebalance_months or 12) if settings else 12
    monthly_budget = _compute_monthly_investment_budget(current_user.id)
    targets_raw = (settings.targets or {}) if settings else {}
    overrides = (settings.bucket_rollup if settings and hasattr(settings, "bucket_rollup") else None)

    pv = compute_portfolio_value(current_user.id)
    total = pv["total"]
    raw_breakdown = pv.get("breakdown", {})
    breakdown, children = rollup_breakdown(raw_breakdown, overrides=overrides)
    active = targets_raw.get("tactical", targets_raw.get("catchup", {}))

    effective_parents = dict(BUCKET_PARENTS)
    if overrides:
        for child, parent in overrides.items():
            nc = normalize_bucket(child)
            if parent is None:
                effective_parents.pop(nc, None)
            else:
                effective_parents[nc] = parent

    child_target_map = {}
    for k, v in active.items():
        nk = normalize_bucket(k)
        tgt = v.get("target", 0) if isinstance(v, dict) else 0
        parent = effective_parents.get(nk)
        if parent:
            child_target_map[nk] = {"target_pct": tgt, "parent": parent}
        else:
            child_target_map[nk] = {"target_pct": tgt, "parent": None}

    all_child_values = {}
    for parent_name, child_dict in children.items():
        for ck, cv in child_dict.items():
            all_child_values[ck] = cv
    for bk, bv in breakdown.items():
        if bk not in all_child_values:
            all_child_values[bk] = bv

    bucket_info = {}
    total_target_pct = 0
    total_drift_need = 0
    for bucket, info in child_target_map.items():
        target_pct = info["target_pct"]
        if target_pct <= 0:
            continue
        current_val = all_child_values.get(bucket, 0)
        current_pct = (current_val / total * 100) if total > 0 else 0
        drift = round(current_pct - target_pct, 1)
        drift_dollars = (target_pct - current_pct) / 100 * total
        total_target_pct += target_pct
        need = max(drift_dollars, 0)
        total_drift_need += need
        bucket_info[bucket] = {
            "parent": info["parent"],
            "target_pct": target_pct,
            "current_pct": round(current_pct, 1),
            "drift": drift,
            "need": need,
        }

    # Urgency blending: smoothly interpolate between target-weight investing
    # (urgency=0) and drift-correction (urgency→max_urgency).
    # The cap scales with timeline so short timelines are more aggressive
    # and long timelines stay closer to target weights.
    _URGENCY_CAPS = {3: 0.80, 6: 0.65, 12: 0.50, 24: 0.35, 36: 0.25}
    max_urgency = _URGENCY_CAPS.get(
        rebalance_months,
        max(0.20, 0.90 - rebalance_months * 0.02),
    )
    if total_drift_need > 0 and monthly_budget > 0:
        urgency = min(
            total_drift_need / (rebalance_months * monthly_budget),
            max_urgency,
        )
    else:
        urgency = 0

    raw_totals = {}
    for bucket, bi in bucket_info.items():
        maint_weight = bi["target_pct"] / total_target_pct if total_target_pct > 0 else 0
        corr_weight = bi["need"] / total_drift_need if total_drift_need > 0 else 0
        raw_totals[bucket] = (1 - urgency) * maint_weight + urgency * corr_weight

    raw_sum = sum(raw_totals.values()) or 1
    suggestions = []
    for bucket, bi in bucket_info.items():
        suggested = round(monthly_budget * raw_totals[bucket] / raw_sum)
        suggestions.append({
            "bucket": bucket,
            "parent": bi["parent"],
            "suggested": suggested,
            "pct": round(suggested / monthly_budget * 100) if monthly_budget > 0 else 0,
            "drift": bi["drift"],
            "target_pct": bi["target_pct"],
            "current_pct": bi["current_pct"],
        })

    suggestions.sort(key=lambda x: x["suggested"], reverse=True)
    return jsonify({
        "rebalance_months": rebalance_months,
        "monthly_budget": monthly_budget,
        "portfolio_total": round(total, 2),
        "urgency": round(urgency, 2),
        "suggestions": suggestions,
    })


@api_budget_bp.route("/rebalance-months", methods=["POST"])
@login_required
def save_rebalance_months():
    """Update the user's rebalance timeline."""
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    months = int(data.get("months", 12))
    months = max(1, min(60, months))
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    settings.rebalance_months = months
    db.session.commit()
    return jsonify({"success": True, "rebalance_months": months})


@api_budget_bp.route("/investments")
@login_required
def get_investments():
    """Return monthly investment categories for the current or given month.

    Auto-initializes the current month by copying targets from the most recent
    prior month if no rows exist yet, stamping the monthly_budget at init time.
    """
    from ..models.settings import MonthlyInvestment, UserSettings
    current_month = dt_date.today().strftime("%Y-%m")
    month = flask_request.args.get("month", current_month)
    rows = (MonthlyInvestment.query
            .filter_by(user_id=current_user.id, month=month)
            .order_by(MonthlyInvestment.id)
            .all())

    live_budget = _compute_monthly_investment_budget(current_user.id)

    if not rows and month == current_month:
        prev = (MonthlyInvestment.query
                .filter_by(user_id=current_user.id)
                .filter(MonthlyInvestment.month < month)
                .order_by(MonthlyInvestment.month.desc())
                .limit(20)
                .all())
        if prev:
            prev_month = prev[0].month
            for r in prev:
                if r.month == prev_month:
                    db.session.add(MonthlyInvestment(
                        user_id=current_user.id, month=month,
                        category=r.category, bucket=r.bucket,
                        target=r.target, contributed=0,
                        monthly_budget=live_budget,
                    ))
            db.session.commit()
            rows = (MonthlyInvestment.query
                    .filter_by(user_id=current_user.id, month=month)
                    .order_by(MonthlyInvestment.id)
                    .all())

    stored_budget = rows[0].monthly_budget if rows and rows[0].monthly_budget else 0
    display_budget = stored_budget if (stored_budget and month != current_month) else live_budget

    if month == current_month and rows and not rows[0].monthly_budget:
        for r in rows:
            r.monthly_budget = live_budget
        db.session.commit()

    all_months = (db.session.query(MonthlyInvestment.month)
                  .filter_by(user_id=current_user.id)
                  .distinct()
                  .order_by(MonthlyInvestment.month.desc())
                  .limit(12)
                  .all())
    available_months = sorted(set(m[0] for m in all_months), reverse=True)

    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    rebalance_months = (settings.rebalance_months or 12) if settings else 12
    is_current = (month == current_month)

    return jsonify({
        "month": month,
        "monthly_budget": display_budget,
        "available_months": available_months,
        "is_current": is_current,
        "rebalance_months": rebalance_months,
        "categories": [
            {"id": r.id, "category": r.category, "bucket": r.bucket or "",
             "target": r.target, "contributed": r.contributed}
            for r in rows
        ],
    })


@api_budget_bp.route("/investments", methods=["POST"])
@login_required

def save_investments():
    """Save monthly investment contributions."""
    from ..models.settings import MonthlyInvestment
    data = flask_request.get_json(silent=True) or {}
    month = data.get("month", dt_date.today().strftime("%Y-%m"))
    budget = _compute_monthly_investment_budget(current_user.id)
    categories = data.get("categories", [])
    for item in categories:
        row_id = item.get("id")
        if row_id:
            row = MonthlyInvestment.query.filter_by(id=row_id, user_id=current_user.id).first()
            if row:
                if "contributed" in item:
                    row.contributed = float(item["contributed"])
                if "target" in item:
                    row.target = float(item["target"])
                if "bucket" in item:
                    row.bucket = item["bucket"] or None
        else:
            cat = item.get("category", "").strip()
            if not cat:
                continue
            row = MonthlyInvestment(
                user_id=current_user.id,
                month=month,
                category=cat,
                bucket=item.get("bucket") or None,
                target=float(item.get("target", 0)),
                contributed=float(item.get("contributed", 0)),
                monthly_budget=budget,
            )
            db.session.add(row)
    db.session.commit()
    return jsonify({"success": True})


@api_budget_bp.route("/investments/delete", methods=["POST"])
@login_required
def delete_investment_category():
    """Delete a single investment category row."""
    from ..models.settings import MonthlyInvestment
    data = flask_request.get_json(silent=True) or {}
    row_id = data.get("id")
    if row_id:
        row = MonthlyInvestment.query.filter_by(id=row_id, user_id=current_user.id).first()
        if row:
            db.session.delete(row)
            db.session.commit()
    return jsonify({"success": True})


@api_budget_bp.route("/investments/new-month", methods=["POST"])
@login_required

def new_investment_month():
    """Create a new month's investment categories, copying targets from the previous month."""
    from ..models.settings import MonthlyInvestment
    data = flask_request.get_json(silent=True) or {}
    new_month = data.get("month", dt_date.today().strftime("%Y-%m"))

    existing = MonthlyInvestment.query.filter_by(user_id=current_user.id, month=new_month).count()
    if existing > 0:
        return jsonify({"success": True, "message": "Month already exists"})

    budget = _compute_monthly_investment_budget(current_user.id)
    prev = (MonthlyInvestment.query
            .filter_by(user_id=current_user.id)
            .filter(MonthlyInvestment.month < new_month)
            .order_by(MonthlyInvestment.month.desc())
            .limit(20)
            .all())

    if prev:
        prev_month = prev[0].month
        prev_rows = [r for r in prev if r.month == prev_month]
        for r in prev_rows:
            db.session.add(MonthlyInvestment(
                user_id=current_user.id, month=new_month,
                category=r.category, bucket=r.bucket,
                target=r.target, contributed=0,
                monthly_budget=budget,
            ))
    db.session.commit()
    return jsonify({"success": True})


@api_budget_bp.route("/allocation-targets")
@login_required
def get_allocation_targets():
    """Return the user's allocation targets and current breakdown."""
    from ..models.settings import UserSettings
    from ..services.portfolio_service import compute_portfolio_value
    from ..utils.buckets import rollup_breakdown, normalize_bucket, BUCKET_PARENTS
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    targets = (settings.targets or {}) if settings else {}
    overrides = (settings.bucket_rollup if settings and hasattr(settings, "bucket_rollup") else None)
    pv = compute_portfolio_value(current_user.id)
    total = pv["total"]
    raw_breakdown = pv.get("breakdown", {})
    breakdown, children = rollup_breakdown(raw_breakdown, overrides=overrides)
    active = targets.get("tactical", targets.get("catchup", {}))

    effective_parents = dict(BUCKET_PARENTS)
    if overrides:
        for child, parent in overrides.items():
            nc = normalize_bucket(child)
            if parent is None:
                effective_parents.pop(nc, None)
            else:
                effective_parents[nc] = parent

    explicit_targets = {}
    child_targets = {}
    for k, v in active.items():
        nk = normalize_bucket(k)
        tgt = v.get("target", 0) if isinstance(v, dict) else 0
        parent = effective_parents.get(nk)
        if parent:
            child_targets.setdefault(parent, {})[nk] = tgt
        else:
            explicit_targets[nk] = tgt
            child_targets.setdefault(nk, {})

    rolled_targets = {}
    for bucket, tgt in explicit_targets.items():
        if tgt > 0:
            rolled_targets[bucket] = tgt
        else:
            rolled_targets[bucket] = sum(child_targets.get(bucket, {}).values())
    for parent in child_targets:
        if parent not in rolled_targets:
            rolled_targets[parent] = sum(child_targets[parent].values())

    rows = []
    all_buckets = sorted(set(list(breakdown.keys()) + list(rolled_targets.keys())))
    for bucket in all_buckets:
        value = breakdown.get(bucket, 0)
        pct = (value / total * 100) if total > 0 else 0
        target_pct = rolled_targets.get(bucket, 0)
        drift = round(pct - target_pct, 1)
        has_explicit = bucket in explicit_targets and explicit_targets[bucket] > 0
        row = {
            "bucket": bucket, "value": round(value, 2),
            "pct": round(pct, 1), "target": target_pct, "drift": drift,
            "explicit_target": has_explicit,
        }
        val_children = children.get(bucket, {})
        tgt_children = child_targets.get(bucket, {})
        all_child_keys = sorted(set(list(val_children.keys()) + list(tgt_children.keys())))
        if all_child_keys:
            row["children"] = []
            for ck in all_child_keys:
                cv = val_children.get(ck, 0)
                ct = tgt_children.get(ck, 0)
                cp = round(cv / total * 100, 1) if total > 0 else 0
                cd = round(cp - ct, 1) if ct else None
                row["children"].append({
                    "bucket": ck, "value": round(cv, 2),
                    "pct": cp, "target": ct, "drift": cd,
                })
        rows.append(row)

    return jsonify({"total": total, "rows": rows, "raw_targets": targets})


@api_budget_bp.route("/allocation-targets", methods=["POST"])
@login_required

def save_allocation_targets():
    """Save or update allocation targets (merges with existing)."""
    from ..models.settings import UserSettings
    data = flask_request.get_json(silent=True) or {}
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
    existing = dict(settings.targets or {})
    incoming = data.get("targets", {})
    for key, val in incoming.items():
        existing[key] = val
    settings.targets = existing
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(settings, "targets")
    db.session.commit()
    return jsonify({"success": True})


@api_budget_bp.route("/allocation-targets/delete", methods=["POST"])
@login_required

def delete_allocation_target():
    """Remove a bucket from the user's allocation targets."""
    from ..models.settings import UserSettings
    from ..utils.buckets import normalize_bucket
    data = flask_request.get_json(silent=True) or {}
    bucket = data.get("bucket", "")
    if not bucket:
        return jsonify({"error": "missing bucket"}), 400
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not settings or not settings.targets:
        return jsonify({"success": True})
    existing = dict(settings.targets or {})
    active_key = "tactical" if "tactical" in existing else "catchup"
    active = existing.get(active_key, {})
    normed = normalize_bucket(bucket)
    removed = False
    for k in list(active.keys()):
        if normalize_bucket(k) == normed:
            del active[k]
            removed = True
    if removed:
        existing[active_key] = active
        settings.targets = existing
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(settings, "targets")
        db.session.commit()
    return jsonify({"success": True, "removed": removed})


def _auto_categorize(user_id, description):
    """Apply keyword rules to auto-categorize a transaction description."""
    if not description:
        return None
    desc_lower = description.lower()
    rules = (CategoryRule.query
             .filter_by(user_id=user_id)
             .order_by(CategoryRule.priority.desc())
             .all())
    for rule in rules:
        if rule.keyword in desc_lower:
            return rule.category
    return None
