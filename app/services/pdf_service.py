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


def _build_styles():
    """Create custom paragraph styles for the report."""
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "NDTitle", parent=base["Title"],
            fontSize=22, textColor=colors.HexColor("#a78bfa"),
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "NDSubtitle", parent=base["Normal"],
            fontSize=10, textColor=colors.HexColor("#999999"),
            alignment=TA_CENTER, spaceAfter=16,
        ),
        "heading": ParagraphStyle(
            "NDHeading", parent=base["Heading2"],
            fontSize=13, textColor=colors.HexColor("#e2e2e2"),
            spaceBefore=16, spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "NDBody", parent=base["Normal"],
            fontSize=9, textColor=colors.HexColor("#cccccc"),
            leading=13,
        ),
        "metric_label": ParagraphStyle(
            "NDMetricLabel", parent=base["Normal"],
            fontSize=8, textColor=colors.HexColor("#999999"),
            alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "NDMetricValue", parent=base["Normal"],
            fontSize=16, textColor=colors.HexColor("#e2e2e2"),
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "footer": ParagraphStyle(
            "NDFooter", parent=base["Normal"],
            fontSize=7, textColor=colors.HexColor("#666666"),
            alignment=TA_CENTER,
        ),
    }
    return styles


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

    story.append(Paragraph("Nickel&Dime", styles["title"]))
    story.append(Paragraph(
        f"Portfolio Report — {now.strftime('%B %d, %Y')}",
        styles["subtitle"],
    ))
    story.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor("#333333"),
    ))
    story.append(Spacer(1, 12))

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
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph(
        "Allocation Breakdown", styles["heading"]
    ))
    alloc_header = [
        "Asset Class", "Value", "Weight", "Children"
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
            1.6 * inch, 1.2 * inch,
            0.8 * inch, doc.width - 3.6 * inch,
        ],
    )
    alloc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0),
         colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0),
         colors.HexColor("#a78bfa")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1),
         colors.HexColor("#cccccc")),
        ("GRID", (0, 0), (-1, -1), 0.5,
         colors.HexColor("#333333")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.HexColor("#0f0f1a"),
            colors.HexColor("#141425"),
        ]),
    ]))
    story.append(alloc_table)
    story.append(Spacer(1, 16))

    warns = (conc.get("warnings") or [])[:5]
    if warns:
        story.append(Paragraph(
            "Concentration Warnings", styles["heading"]
        ))
        for w in warns:
            sev = w.get("severity", "medium")
            col = "#f87171" if sev == "high" else "#fbbf24"
            story.append(Paragraph(
                f'<font color="{col}">●</font> {w["msg"]}',
                styles["body"],
            ))
        story.append(Spacer(1, 12))

    summaries = insights.get("summaries", [])
    if summaries:
        story.append(Paragraph(
            "AI Insights", styles["heading"]
        ))
        for s in summaries:
            story.append(Paragraph(
                f"• {s}", styles["body"]
            ))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 12))

    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#333333"),
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Generated by Nickel&Dime — nickelanddime.io | "
        "This is not financial advice.",
        styles["footer"],
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
