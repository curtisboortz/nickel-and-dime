"""PDF portfolio report generator using ReportLab.

Produces a branded single-page (or multi-page) PDF with:
 - Header with branding and date
 - Portfolio summary metrics
 - Allocation breakdown table
 - Risk / diversification metrics
 - AI insight summaries
"""

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from ..services.portfolio_service import compute_portfolio_value
from ..services.insights_service import generate_insights
from ..utils.buckets import rollup_breakdown

_BRAND = colors.HexColor("#7c3aed")
_BRAND_LIGHT = colors.HexColor("#ede9fe")
_NAVY = colors.HexColor("#1e1b4b")
_TEXT = colors.HexColor("#111827")
_TEXT_SECONDARY = colors.HexColor("#4b5563")
_TEXT_MUTED = colors.HexColor("#6b7280")
_BORDER = colors.HexColor("#e5e7eb")
_ROW_ALT = colors.HexColor("#f9fafb")
_SUCCESS = colors.HexColor("#059669")
_DANGER = colors.HexColor("#dc2626")
_WARNING = colors.HexColor("#d97706")


def _build_styles():
    """Create custom paragraph styles for the report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "NDTitle", parent=base["Title"],
            fontSize=24, textColor=_BRAND,
            spaceAfter=2, fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "NDSubtitle", parent=base["Normal"],
            fontSize=10, textColor=_TEXT_MUTED,
            alignment=TA_CENTER, spaceAfter=16,
        ),
        "heading": ParagraphStyle(
            "NDHeading", parent=base["Heading2"],
            fontSize=13, textColor=_NAVY,
            spaceBefore=18, spaceAfter=8,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "NDBody", parent=base["Normal"],
            fontSize=9, textColor=_TEXT,
            leading=14,
        ),
        "body_muted": ParagraphStyle(
            "NDBodyMuted", parent=base["Normal"],
            fontSize=9, textColor=_TEXT_SECONDARY,
            leading=14,
        ),
        "metric_label": ParagraphStyle(
            "NDMetricLabel", parent=base["Normal"],
            fontSize=8, textColor=_TEXT_MUTED,
            alignment=TA_CENTER, spaceAfter=0,
        ),
        "metric_value": ParagraphStyle(
            "NDMetricValue", parent=base["Normal"],
            fontSize=18, textColor=_NAVY,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "footer": ParagraphStyle(
            "NDFooter", parent=base["Normal"],
            fontSize=7, textColor=_TEXT_MUTED,
            alignment=TA_CENTER,
        ),
    }


def _fmt_usd(val):
    if val >= 1_000_000:
        return f"${val / 1_000_000:,.1f}M"
    if val >= 1_000:
        return f"${val:,.0f}"
    return f"${val:,.2f}"


def generate_pdf(user_id, overrides=None):
    """Generate a PDF report and return the bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )
    styles = _build_styles()
    story = []

    pv = compute_portfolio_value(user_id)
    total = pv["total"]
    raw_breakdown = pv.get("breakdown", {})
    breakdown, children = rollup_breakdown(
        raw_breakdown, overrides
    )
    insights = generate_insights(user_id, overrides)
    now = datetime.now(timezone.utc)

    story.append(Paragraph("Nickel&amp;Dime", styles["title"]))
    story.append(Paragraph(
        f"Portfolio Report — {now.strftime('%B %d, %Y')}",
        styles["subtitle"],
    ))
    story.append(HRFlowable(
        width="100%", thickness=2, color=_BRAND,
    ))
    story.append(Spacer(1, 14))

    risk = insights.get("risk_score", {})
    div_r = insights.get("diversification_ratio", {})
    conc = insights.get("concentration", {})

    metrics_data = [[
        Paragraph(_fmt_usd(total), styles["metric_value"]),
        Paragraph(
            str(risk.get("score", 0)) + "/100",
            styles["metric_value"],
        ),
        Paragraph(
            str(risk.get("vol", 0)) + "%",
            styles["metric_value"],
        ),
        Paragraph(
            str(div_r.get("ratio", 1)) + "x",
            styles["metric_value"],
        ),
    ], [
        Paragraph("Total Value", styles["metric_label"]),
        Paragraph(
            f"Risk ({risk.get('label', '')})",
            styles["metric_label"],
        ),
        Paragraph("Est. Volatility", styles["metric_label"]),
        Paragraph(
            f"Diversification ({div_r.get('label', '')})",
            styles["metric_label"],
        ),
    ]]
    metrics_table = Table(
        metrics_data,
        colWidths=[doc.width / 4] * 4,
    )
    metrics_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white),
        ("BACKGROUND", (0, 0), (-1, -1), _BRAND_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 18))

    story.append(Paragraph(
        "Allocation Breakdown", styles["heading"]
    ))
    alloc_header = [
        "Asset Class", "Value", "Weight", "Sub-Categories"
    ]
    alloc_rows = [alloc_header]
    for bucket in sorted(
        breakdown.keys(), key=lambda b: -breakdown[b]
    ):
        val = breakdown[bucket]
        pct = val / total * 100 if total > 0 else 0
        kids = children.get(bucket, {})
        kid_str = ", ".join(
            f"{k} ({v / total * 100:.1f}%)"
            for k, v in sorted(
                kids.items(), key=lambda x: -x[1]
            )
        ) if kids else "—"
        alloc_rows.append([
            bucket, _fmt_usd(val), f"{pct:.1f}%", kid_str
        ])

    alloc_table = Table(
        alloc_rows,
        colWidths=[
            1.5 * inch, 1.1 * inch,
            0.8 * inch, doc.width - 3.4 * inch,
        ],
    )
    alloc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), _TEXT),
        ("TEXTCOLOR", (3, 1), (3, -1), _TEXT_SECONDARY),
        ("GRID", (0, 0), (-1, 0), 0, _NAVY),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, _BORDER),
        ("LINEBELOW", (0, -1), (-1, -1), 1, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white, _ROW_ALT,
        ]),
    ]))
    story.append(alloc_table)
    story.append(Spacer(1, 18))

    warns = (conc.get("warnings") or [])[:5]
    if warns:
        story.append(Paragraph(
            "Concentration Warnings", styles["heading"]
        ))
        for w in warns:
            sev = w.get("severity", "medium")
            col = _DANGER if sev == "high" else _WARNING
            story.append(Paragraph(
                f'<font color="{col.hexval()}">\u25cf</font> {w["msg"]}',
                styles["body"],
            ))
        story.append(Spacer(1, 14))

    summaries = insights.get("summaries", [])
    if summaries:
        story.append(Paragraph(
            "AI Insights", styles["heading"]
        ))
        for s in summaries:
            story.append(Paragraph(
                f"\u2022 {s}", styles["body"]
            ))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 14))

    story.append(HRFlowable(
        width="100%", thickness=0.5, color=_BORDER,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Generated by Nickel&amp;Dime — nickelanddime.io | "
        "This is not financial advice.",
        styles["footer"],
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
