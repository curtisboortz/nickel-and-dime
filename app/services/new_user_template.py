"""New-user template & onboarding personalization.

Two-layer setup for brand-new signups:

1. **Baseline** (apply_new_user_template): loads a committed JSON template and
   seeds UserSettings display preferences, CustomPulseCard rows, and
   first-month MonthlyInvestment categories. Idempotent. Called from
   auth.register so every new user has a populated dashboard from the start.

2. **Personalization** (apply_wizard_answers): layers interest + risk-based
   customization on top of the baseline -- sets targets.tactical from an
   allocation preset, adds interest-driven pulse cards (ETH for crypto,
   Silver+GSR for metals, etc.), and (optionally) seeds monthly investment
   targets based on a provided monthly contribution.

A companion admin endpoint (snapshot_from_user) dumps the current user's
setup back into JSON so the repo-committed template can be regenerated when
the owner tweaks their dashboard.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from ..extensions import db
from ..models.settings import (
    CustomPulseCard,
    MonthlyInvestment,
    UserSettings,
)


TEMPLATE_JSON = Path(__file__).parent / "new_user_template.json"


# ── Pulse cards always included ────────────────────────────────────────
# These built-ins ship with the baseline and should never be hidden at
# signup regardless of the user's interests. Users can still hide them
# from the dashboard UI afterward.
FIXED_PULSE_CARDS = ["spy", "btc", "gold", "vix", "oil", "tnx_10y", "dxy"]


# ── Allocation presets ─────────────────────────────────────────────────
# N&D-native presets only. Classic portfolios (All Weather, Bogle, Macro,
# etc.) are sourced from templates_service at apply time via a
# "classic:<id>" marker. The old "metals_heavy" preset was dropped -- the
# Macro Investor + Golden Butterfly classics cover that thesis better.
ALLOCATION_PRESETS = {
    "conservative": {"Equities": 30, "Real Assets": 10, "Alternatives": 5, "Cash": 15, "Fixed Income": 40},
    "balanced":     {"Equities": 55, "Real Assets": 15, "Alternatives": 5, "Cash": 5,  "Fixed Income": 20},
    "aggressive":   {"Equities": 75, "Real Assets": 15, "Alternatives": 5, "Cash": 0,  "Fixed Income": 5},
}


# ── Interest -> pulse card additions ───────────────────────────────────
# Each entry is {"builtin": "<id>"} to un-hide a built-in, or
# {"ticker": "...", "label": "..."} to add a CustomPulseCard.
INTEREST_PULSE_ADDITIONS: dict[str, list[dict[str, str]]] = {
    "crypto":      [{"ticker": "ETH-USD",     "label": "ETH"}],
    "metals":      [{"builtin": "silver"},
                    {"ticker": "GOLD/SILVER", "label": "Gold/Silver"}],
    "bonds":       [{"builtin": "tnx_2y"}],
    "commodities": [{"ticker": "HG=F",        "label": "Copper"}],
    "real_estate": [{"ticker": "VNQ",         "label": "REITs"}],
}


# ── Fallback baseline used if JSON is missing ─────────────────────────
_FALLBACK_BASELINE: dict[str, Any] = {
    "pulse_order": ["spy", "btc", "gold", "silver", "tnx_10y", "tnx_2y", "dxy", "vix", "oil"],
    "widget_order": {"pulse_size": "compact", "hidden_pulse": []},
    "dashboard_layout": ["allocation-donut", "allocation-table", "monthly-investments", "watchlist", "financial-goals"],
    "custom_pulse_cards": [],
    "monthly_investment_categories": [],
    "bucket_rollup": {},
    "rebalance_months": 6,
}


# ─────────────────────────────────────────────────────────────────────
# Template loading
# ─────────────────────────────────────────────────────────────────────

def load_template() -> dict[str, Any]:
    """Read the committed JSON template. Falls back to a built-in default."""
    try:
        if TEMPLATE_JSON.exists():
            with open(TEMPLATE_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    return dict(_FALLBACK_BASELINE)


def save_template(data: dict[str, Any]) -> None:
    """Write the template JSON to disk (used by admin snapshot endpoint)."""
    TEMPLATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(TEMPLATE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


# ─────────────────────────────────────────────────────────────────────
# Baseline application
# ─────────────────────────────────────────────────────────────────────

def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _resolve_pulse_order(pulse_order: list[str], ticker_to_custom_id: dict[str, int]) -> list[str]:
    """Replace 'custom:TICKER' placeholders with actual 'custom-<id>' entries."""
    resolved: list[str] = []
    for entry in pulse_order:
        if isinstance(entry, str) and entry.startswith("custom:"):
            ticker = entry.split(":", 1)[1]
            cid = ticker_to_custom_id.get(ticker.upper())
            if cid is not None:
                resolved.append(f"custom-{cid}")
        else:
            resolved.append(entry)
    return resolved


def apply_new_user_template(user_id: int) -> None:
    """Apply the baseline template to a user. Idempotent and fail-soft.

    Seeds display preferences on UserSettings, inserts CustomPulseCard rows,
    and creates current-month MonthlyInvestment categories (if any in the
    template). Does NOT touch holdings, snapshots, or transactions.
    """
    tmpl = load_template()

    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.session.add(settings)
        db.session.flush()

    # CustomPulseCard upserts (by user_id + ticker)
    existing_cards = {
        c.ticker.upper(): c
        for c in CustomPulseCard.query.filter_by(user_id=user_id).all()
    }
    ticker_to_id: dict[str, int] = {t: c.id for t, c in existing_cards.items()}
    for card in tmpl.get("custom_pulse_cards", []) or []:
        ticker = (card.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        label = (card.get("label") or "").strip()
        position = int(card.get("position") or 0)
        if ticker in existing_cards:
            row = existing_cards[ticker]
            if label and not row.label:
                row.label = label
        else:
            row = CustomPulseCard(
                user_id=user_id, ticker=ticker,
                label=label, position=position,
            )
            db.session.add(row)
            db.session.flush()
            existing_cards[ticker] = row
            ticker_to_id[ticker] = row.id

    # Pulse order (with custom: placeholders resolved)
    raw_pulse_order = tmpl.get("pulse_order") or []
    if raw_pulse_order:
        settings.pulse_order = _resolve_pulse_order(raw_pulse_order, ticker_to_id)

    # Widget order (merge -- preserve any user-set keys)
    tmpl_wo = tmpl.get("widget_order") or {}
    cur_wo = settings.widget_order if isinstance(settings.widget_order, dict) else {}
    merged_wo = {**tmpl_wo, **cur_wo}  # user overrides win if any
    if tmpl_wo.get("hidden_pulse") is not None and "hidden_pulse" not in cur_wo:
        merged_wo["hidden_pulse"] = tmpl_wo["hidden_pulse"]
    if tmpl_wo.get("pulse_size") and not cur_wo.get("pulse_size"):
        merged_wo["pulse_size"] = tmpl_wo["pulse_size"]
    settings.widget_order = merged_wo

    # Dashboard layout
    if tmpl.get("dashboard_layout") and not settings.dashboard_layout:
        settings.dashboard_layout = list(tmpl["dashboard_layout"])

    # Bucket rollup
    if tmpl.get("bucket_rollup") and not settings.bucket_rollup:
        settings.bucket_rollup = dict(tmpl["bucket_rollup"])

    # Rebalance months
    if tmpl.get("rebalance_months") and not settings.rebalance_months:
        settings.rebalance_months = int(tmpl["rebalance_months"])

    # Monthly investment categories for current month
    _seed_monthly_investments(
        user_id,
        tmpl.get("monthly_investment_categories", []) or [],
        month=_current_month(),
    )

    db.session.commit()


def _seed_monthly_investments(
    user_id: int,
    categories: list[dict[str, Any]],
    month: str,
) -> None:
    """Insert MonthlyInvestment rows for the given month. Upserts by category."""
    existing = {
        mi.category: mi
        for mi in MonthlyInvestment.query.filter_by(
            user_id=user_id, month=month
        ).all()
    }
    for cat in categories:
        name = (cat.get("category") or "").strip()
        if not name:
            continue
        if name in existing:
            continue  # already present, don't overwrite user's edits
        row = MonthlyInvestment(
            user_id=user_id,
            month=month,
            category=name,
            bucket=cat.get("bucket") or None,
            target=float(cat.get("target") or 0),
            contributed=0.0,
            monthly_budget=float(cat.get("monthly_budget") or 0),
        )
        db.session.add(row)


# ─────────────────────────────────────────────────────────────────────
# Wizard personalization
# ─────────────────────────────────────────────────────────────────────

def recommend_template(answers: dict[str, Any]) -> str:
    """Pick a recommended allocation from the full wizard answers.

    Returns either a N&D preset name (``conservative`` | ``balanced`` |
    ``aggressive``) or a classic template marker ``"classic:<id>"``.
    """
    risk = (answers.get("risk") or "").lower().strip()
    philo = (answers.get("philosophy") or "").lower().strip()
    horizon = (answers.get("time_horizon") or "").lower().strip()
    interests = [str(i).lower() for i in (answers.get("interests") or [])]

    if philo == "income" or horizon == "retired":
        return "classic:income-focus"
    if philo == "defensive" and risk == "conservative":
        return "classic:permanent"
    if philo == "defensive":
        return "classic:all-weather"
    if philo == "active":
        return "classic:macro-investor"
    if philo == "passive" and risk == "aggressive" and horizon == "long":
        return "classic:boglehead-3"
    if philo == "passive" and risk == "balanced":
        return "classic:60-40"
    if "metals" in interests and risk in ("balanced", "aggressive"):
        return "classic:golden-butterfly"
    if risk in ALLOCATION_PRESETS:
        return risk
    return "balanced"


# Backwards-compatible shim: older callers passed (interests, risk).
def recommend_preset(interests: list[str], risk: str) -> str:
    """Legacy wrapper kept so imports don't break. Prefer recommend_template."""
    return recommend_template({"interests": interests, "risk": risk})


def _resolve_allocation(preset_name: str,
                        answers: dict[str, Any]) -> dict[str, float] | None:
    """Return the bucket -> percentage mapping for the chosen preset.

    Supports N&D presets, ``"classic:<id>"`` template ids, a user-supplied
    custom allocation, or ``"skip"`` / ``""`` (returns None).
    """
    if preset_name == "custom":
        custom = answers.get("custom_allocation") or None
        if not isinstance(custom, dict):
            return None
        return {str(k): float(v) for k, v in custom.items() if v}
    if preset_name in ALLOCATION_PRESETS:
        return dict(ALLOCATION_PRESETS[preset_name])
    if preset_name == "skip":
        return None
    if preset_name.startswith("classic:"):
        from .templates_service import get_template
        tpl = get_template(preset_name.split(":", 1)[1])
        if not tpl:
            return None
        return {k: float(v) for k, v in tpl.get("allocations", {}).items()}
    return None


def _child_buckets_in(alloc: dict[str, float]) -> list[str]:
    """Return buckets in the allocation that are normally rolled up into a
    parent per BUCKET_PARENTS (e.g. Gold -> Real Assets). These should stay
    standalone so the user sees them as distinct slices in the donut.
    """
    from ..utils.buckets import BUCKET_PARENTS, normalize_bucket
    out = []
    for bucket in alloc.keys():
        normed = normalize_bucket(bucket)
        if normed in BUCKET_PARENTS:
            out.append(normed)
    return out


def apply_wizard_answers(user_id: int, answers: dict[str, Any]) -> None:
    """Personalize the user's setup based on wizard survey answers.

    Expected answers keys:
        experience:   "beginner" | "intermediate" | "advanced"
        time_horizon: "short" | "medium" | "long" | "retired"
        interests:    list of {"equities","crypto","metals","real_estate",
                               "bonds","commodities","alternatives"}
        philosophy:   "passive" | "active" | "defensive" | "income" | "unsure"
        risk:         "conservative" | "balanced" | "aggressive" | "custom"
        allocation_preset: name from ALLOCATION_PRESETS, "classic:<id>",
                           "custom", "skip", or empty
        custom_allocation: {bucket: pct, ...} if preset == "custom"
        monthly_contribution: float (optional)
        frequency: "monthly" | "biweekly" | "weekly" (optional)
    """
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.session.add(settings)
        db.session.flush()

    interests = list(answers.get("interests") or [])

    # ── Allocation targets ─────────────────────────────────────────
    preset_name = answers.get("allocation_preset") or ""
    alloc = _resolve_allocation(preset_name, answers)
    if alloc is None and preset_name not in ("skip", "custom"):
        # No explicit preset provided -- fall back to our recommender.
        alloc = _resolve_allocation(recommend_template(answers), answers)

    if alloc:
        tactical = {
            bucket: {"target": round(float(pct), 2), "min": 0, "max": 100}
            for bucket, pct in alloc.items() if pct and pct > 0
        }
        cur_targets = settings.targets if isinstance(settings.targets, dict) else {}
        cur_targets = dict(cur_targets)
        cur_targets["tactical"] = tactical
        settings.targets = cur_targets
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(settings, "targets")

        # ── Bucket rollup safety ───────────────────────────────────
        # Classic templates may target child buckets (Gold, International,
        # Real Estate, Crypto). Mark them standalone so the user's donut
        # shows them as distinct slices rather than rolling them into
        # Real Assets / Equities / Alternatives.
        children_in_alloc = _child_buckets_in(alloc)
        if children_in_alloc:
            cur_rollup = settings.bucket_rollup if isinstance(settings.bucket_rollup, dict) else {}
            new_rollup = dict(cur_rollup)
            for child in children_in_alloc:
                # Only set if user hasn't explicitly overridden it.
                if child not in new_rollup:
                    new_rollup[child] = None
            settings.bucket_rollup = new_rollup
            flag_modified(settings, "bucket_rollup")

    # ── Interest-driven pulse cards ───────────────────────────────
    existing_tickers = {
        c.ticker.upper()
        for c in CustomPulseCard.query.filter_by(user_id=user_id).all()
    }
    wo = settings.widget_order if isinstance(settings.widget_order, dict) else {}
    wo = dict(wo)
    hidden = list(wo.get("hidden_pulse") or [])
    pulse_order = list(settings.pulse_order or [])

    for interest in interests:
        for add in INTEREST_PULSE_ADDITIONS.get(interest, []):
            if "builtin" in add:
                bid = add["builtin"]
                if bid in hidden:
                    hidden.remove(bid)
                if bid not in pulse_order:
                    pulse_order.append(bid)
            elif "ticker" in add:
                ticker = add["ticker"].strip().upper()
                if ticker in existing_tickers:
                    continue
                label = add.get("label", "").strip()
                position = len(pulse_order)
                card = CustomPulseCard(
                    user_id=user_id, ticker=ticker,
                    label=label, position=position,
                )
                db.session.add(card)
                db.session.flush()
                existing_tickers.add(ticker)
                pulse_order.append(f"custom-{card.id}")

    wo["hidden_pulse"] = hidden
    settings.widget_order = wo
    settings.pulse_order = pulse_order

    # ── Monthly contribution -> investment categories ────────────
    contribution = answers.get("monthly_contribution")
    try:
        contribution = float(contribution) if contribution is not None else None
    except (TypeError, ValueError):
        contribution = None

    frequency = answers.get("frequency") or ""
    if contribution is not None and contribution > 0:
        settings.contribution_amount = contribution
        if frequency in ("monthly", "biweekly", "weekly"):
            settings.contribution_frequency = frequency

        if alloc:
            _seed_wizard_monthly_investments(
                user_id,
                alloc,
                contribution,
                interests,
                month=_current_month(),
            )

    # ── Persist raw answers ──────────────────────────────────────
    settings.onboarding_answers = answers
    settings.onboarding_completed = True

    db.session.commit()


def _seed_wizard_monthly_investments(
    user_id: int,
    allocation: dict[str, float],
    monthly_contribution: float,
    interests: list[str],
    month: str,
) -> None:
    """Create MonthlyInvestment rows from the wizard allocation.

    Splits buckets into meaningful sub-categories based on user interests
    (e.g. Real Assets -> Silver ETF + Silver Savings + Gold ETF + Gold Savings
    if metals is an interest).
    """
    existing = {
        mi.category: mi
        for mi in MonthlyInvestment.query.filter_by(
            user_id=user_id, month=month
        ).all()
    }

    rows: list[tuple[str, str, float]] = []

    # If the allocation already distinguishes Gold / Crypto as their own
    # buckets (classic templates do), don't also split the Real Assets /
    # Alternatives parents into metals / crypto sub-categories -- that would
    # double-count them.
    alloc_buckets = {b for b in allocation.keys()}
    gold_already_split = "Gold" in alloc_buckets or "Silver" in alloc_buckets
    crypto_already_split = "Crypto" in alloc_buckets

    for bucket, pct in allocation.items():
        if not pct or pct <= 0:
            continue
        bucket_target = round(monthly_contribution * (pct / 100.0), 2)

        if bucket == "Real Assets" and "metals" in interests and not gold_already_split:
            per = round(bucket_target / 4.0, 2)
            rows.extend([
                ("Silver ETF",     "Real Assets", per),
                ("Silver Savings", "Real Assets", per),
                ("Gold ETF",       "Real Assets", per),
                ("Gold Savings",   "Real Assets", per),
            ])
        elif bucket == "Alternatives" and "crypto" in interests and not crypto_already_split:
            rows.append(("Crypto", "Alternatives", bucket_target))
        elif bucket == "Cash":
            rows.append(("Cash Reserve", "Cash", bucket_target))
        elif bucket == "Fixed Income":
            rows.append(("Bonds", "Fixed Income", bucket_target))
        elif bucket == "Gold" and "metals" in interests:
            per = round(bucket_target / 2.0, 2)
            rows.extend([
                ("Gold ETF",     "Gold", per),
                ("Gold Savings", "Gold", per),
            ])
        else:
            rows.append((bucket, bucket, bucket_target))

    for category, bkt, target in rows:
        if category in existing:
            continue
        row = MonthlyInvestment(
            user_id=user_id,
            month=month,
            category=category,
            bucket=bkt,
            target=target,
            contributed=0.0,
            monthly_budget=monthly_contribution,
        )
        db.session.add(row)


# ─────────────────────────────────────────────────────────────────────
# Admin: snapshot the current user's setup into template JSON
# ─────────────────────────────────────────────────────────────────────

def snapshot_from_user(user_id: int) -> dict[str, Any]:
    """Read a user's live config and return a JSON-serializable template dict.

    The resulting dict can be saved via save_template() and committed to git.
    pulse_order entries of the form 'custom-<id>' are rewritten as
    'custom:<TICKER>' so the template is portable across user IDs.
    """
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    if not settings:
        raise ValueError(f"No UserSettings for user_id={user_id}")

    cards = CustomPulseCard.query.filter_by(user_id=user_id).order_by(
        CustomPulseCard.position, CustomPulseCard.id
    ).all()
    id_to_ticker = {c.id: c.ticker.upper() for c in cards}

    # Rewrite pulse_order: custom-<id> -> custom:TICKER
    raw_order = list(settings.pulse_order or [])
    portable_order: list[str] = []
    for entry in raw_order:
        if isinstance(entry, str) and entry.startswith("custom-"):
            try:
                cid = int(entry.split("-", 1)[1])
            except (ValueError, IndexError):
                continue
            ticker = id_to_ticker.get(cid)
            if ticker:
                portable_order.append(f"custom:{ticker}")
        else:
            portable_order.append(entry)

    # Monthly investments -- current month's categories
    month = _current_month()
    monthlies = MonthlyInvestment.query.filter_by(
        user_id=user_id, month=month
    ).order_by(MonthlyInvestment.id).all()
    monthly_categories = [
        {
            "category": mi.category,
            "bucket": mi.bucket or "",
            "target": float(mi.target or 0),
            "monthly_budget": float(mi.monthly_budget or 0),
        }
        for mi in monthlies
    ]

    wo = settings.widget_order if isinstance(settings.widget_order, dict) else {}

    return {
        "pulse_order": portable_order,
        "widget_order": {
            "pulse_size": wo.get("pulse_size", "compact"),
            "hidden_pulse": list(wo.get("hidden_pulse") or []),
        },
        "dashboard_layout": list(settings.dashboard_layout or []),
        "custom_pulse_cards": [
            {"ticker": c.ticker.upper(), "label": c.label or "", "position": c.position or 0}
            for c in cards
        ],
        "monthly_investment_categories": monthly_categories,
        "bucket_rollup": dict(settings.bucket_rollup or {}),
        "rebalance_months": int(settings.rebalance_months or 6),
    }


def snapshot_and_save(user_id: int) -> dict[str, Any]:
    """Convenience: snapshot a user and write to the template JSON on disk."""
    data = snapshot_from_user(user_id)
    save_template(data)
    return data
