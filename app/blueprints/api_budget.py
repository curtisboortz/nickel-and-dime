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
    config = BudgetConfig.query.filter_by(user_id=current_user.id).first()
    recent_txns = (Transaction.query
                   .filter_by(user_id=current_user.id)
                   .order_by(Transaction.date.desc())
                   .limit(200)
                   .all())

    categories = config.categories if config else []
    monthly_income = config.monthly_income if config else 0

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
        "transactions": [
            {"id": t.id, "date": t.date.isoformat(), "description": t.description,
             "amount": t.amount, "category": t.category, "source": t.source}
            for t in recent_txns
        ],
    })


@api_budget_bp.route("/budget-data", methods=["POST"])
@login_required

def save_budget():
    """Save budget configuration (income, categories, rollover)."""
    data = flask_request.get_json(silent=True) or {}
    config = BudgetConfig.query.filter_by(user_id=current_user.id).first()
    if not config:
        config = BudgetConfig(user_id=current_user.id)
        db.session.add(config)
    if "monthly_income" in data:
        config.monthly_income = float(data["monthly_income"])
    if "categories" in data:
        config.categories = data["categories"]
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


@api_budget_bp.route("/spending-insights")
@login_required
def spending_insights():
    """Month-over-month spending comparison and savings rate."""
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

    this_total = sum(abs(v) for v in this_month.values() if v < 0)
    last_total = sum(abs(v) for v in last_month.values() if v < 0)

    savings_rate = 0
    if monthly_income > 0:
        savings_rate = round((monthly_income - this_total) / monthly_income * 100, 1)

    all_cats = sorted(set(list(this_month.keys()) + list(last_month.keys())))
    comparisons = []
    for cat in all_cats:
        curr = abs(this_month.get(cat, 0))
        prev = abs(last_month.get(cat, 0))
        change_pct = round((curr - prev) / prev * 100, 1) if prev > 0 else 0
        comparisons.append({
            "category": cat,
            "this_month": curr,
            "last_month": prev,
            "change_pct": change_pct,
        })

    comparisons.sort(key=lambda x: x["this_month"], reverse=True)

    return jsonify({
        "savings_rate": savings_rate,
        "this_month_total": this_total,
        "last_month_total": last_total,
        "month_change_pct": round((this_total - last_total) / last_total * 100, 1) if last_total > 0 else 0,
        "comparisons": comparisons,
    })


@api_budget_bp.route("/investments")
@login_required
def get_investments():
    """Return monthly investment categories for the current or given month."""
    from ..models.settings import MonthlyInvestment, UserSettings
    month = flask_request.args.get("month", dt_date.today().strftime("%Y-%m"))
    rows = (MonthlyInvestment.query
            .filter_by(user_id=current_user.id, month=month)
            .order_by(MonthlyInvestment.id)
            .all())
    settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    contribution_plan = (settings.contribution_plan or {}) if settings else {}
    targets_data = (settings.targets or {}) if settings else {}
    contribution_amount = (settings.contribution_amount or 0) if settings else 0
    freq = (settings.contribution_frequency or "biweekly") if settings else "biweekly"
    if freq == "biweekly":
        monthly_budget = round(contribution_amount * 26 / 12, 2)
    elif freq == "weekly":
        monthly_budget = round(contribution_amount * 52 / 12, 2)
    else:
        monthly_budget = contribution_amount

    return jsonify({
        "month": month,
        "monthly_budget": monthly_budget,
        "categories": [
            {"id": r.id, "category": r.category, "target": r.target, "contributed": r.contributed}
            for r in rows
        ],
        "targets": targets_data,
        "contribution_plan": contribution_plan,
    })


@api_budget_bp.route("/investments", methods=["POST"])
@login_required

def save_investments():
    """Save monthly investment contributions."""
    from ..models.settings import MonthlyInvestment
    data = flask_request.get_json(silent=True) or {}
    month = data.get("month", dt_date.today().strftime("%Y-%m"))
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
        else:
            cat = item.get("category", "").strip()
            if not cat:
                continue
            row = MonthlyInvestment(
                user_id=current_user.id,
                month=month,
                category=cat,
                target=float(item.get("target", 0)),
                contributed=float(item.get("contributed", 0)),
            )
            db.session.add(row)
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
                category=r.category, target=r.target, contributed=0,
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
