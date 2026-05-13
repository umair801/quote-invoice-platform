# builders/pdf_builder.py
# AgAI_27 - Quote-to-Invoice Platform
# Generates a branded PDF quote from a Quote model using ReportLab.

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

from core.models import Quote
from core.logger import get_logger

logger = get_logger(__name__)

# ─── Brand colors (professional dark + gold, no logo needed) ─────────────────
BRAND_DARK    = colors.HexColor("#1A1A2E")   # deep navy
BRAND_GOLD    = colors.HexColor("#C9A84C")   # warm gold
BRAND_LIGHT   = colors.HexColor("#F5F5F0")   # off-white background
BRAND_GRAY    = colors.HexColor("#6B6B6B")   # secondary text
BRAND_LINE    = colors.HexColor("#E0E0E0")   # table lines
WHITE         = colors.white
BLACK         = colors.black

# ─── Output directory ─────────────────────────────────────────────────────────
PDF_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pdf_output")


def _ensure_output_dir() -> str:
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
    return PDF_OUTPUT_DIR


def _build_styles() -> dict:
    """Build all paragraph styles used in the PDF."""
    base = getSampleStyleSheet()

    styles = {
        "company_name": ParagraphStyle(
            "company_name",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=WHITE,
            leading=26,
            alignment=TA_LEFT,
        ),
        "company_tagline": ParagraphStyle(
            "company_tagline",
            fontName="Helvetica",
            fontSize=8,
            textColor=BRAND_GOLD,
            leading=12,
            alignment=TA_LEFT,
        ),
        "header_right": ParagraphStyle(
            "header_right",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=WHITE,
            leading=16,
            alignment=TA_RIGHT,
        ),
        "header_right_sub": ParagraphStyle(
            "header_right_sub",
            fontName="Helvetica",
            fontSize=9,
            textColor=BRAND_GOLD,
            leading=13,
            alignment=TA_RIGHT,
        ),
        "section_label": ParagraphStyle(
            "section_label",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=BRAND_GRAY,
            leading=12,
            spaceAfter=2,
        ),
        "section_value": ParagraphStyle(
            "section_value",
            fontName="Helvetica",
            fontSize=10,
            textColor=BLACK,
            leading=14,
        ),
        "section_value_bold": ParagraphStyle(
            "section_value_bold",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=BLACK,
            leading=14,
        ),
        "table_header": ParagraphStyle(
            "table_header",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=WHITE,
            leading=12,
            alignment=TA_LEFT,
        ),
        "table_cell": ParagraphStyle(
            "table_cell",
            fontName="Helvetica",
            fontSize=9,
            textColor=BLACK,
            leading=13,
        ),
        "table_cell_right": ParagraphStyle(
            "table_cell_right",
            fontName="Helvetica",
            fontSize=9,
            textColor=BLACK,
            leading=13,
            alignment=TA_RIGHT,
        ),
        "table_cell_bold": ParagraphStyle(
            "table_cell_bold",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=BLACK,
            leading=13,
            alignment=TA_RIGHT,
        ),
        "total_label": ParagraphStyle(
            "total_label",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=BRAND_DARK,
            leading=16,
            alignment=TA_RIGHT,
        ),
        "total_value": ParagraphStyle(
            "total_value",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=BRAND_GOLD,
            leading=18,
            alignment=TA_RIGHT,
        ),
        "notes_label": ParagraphStyle(
            "notes_label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=BRAND_GRAY,
            leading=13,
            spaceBefore=4,
        ),
        "notes_text": ParagraphStyle(
            "notes_text",
            fontName="Helvetica",
            fontSize=9,
            textColor=BLACK,
            leading=13,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Helvetica",
            fontSize=8,
            textColor=BRAND_GRAY,
            leading=11,
            alignment=TA_CENTER,
        ),
        "validity": ParagraphStyle(
            "validity",
            fontName="Helvetica-Oblique",
            fontSize=8,
            textColor=BRAND_GRAY,
            leading=12,
            alignment=TA_CENTER,
        ),
    }
    return styles


def generate_quote_pdf(
    quote: Quote,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate a branded PDF quote from a Quote model.
    Returns the absolute path to the generated PDF file.
    """
    if output_path is None:
        out_dir = _ensure_output_dir()
        output_path = os.path.join(out_dir, f"{quote.quote_number}.pdf")

    styles = _build_styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.65 * inch,
    )

    story = []
    page_width = letter[0] - 1.3 * inch

    # ─── Header banner ────────────────────────────────────────────────────────
    expiry_date = (
        datetime.now(timezone.utc) + timedelta(days=quote.valid_days)
    ).strftime("%B %d, %Y")

    header_data = [
        [
            Paragraph("SKYFRAME", styles["company_name"]),
            Paragraph(
                f"QUOTE<br/>{quote.quote_number}",
                styles["header_right"],
            ),
        ],
        [
            Paragraph(
                "Custom Framing &amp; Fine Art Printing",
                styles["company_tagline"],
            ),
            Paragraph(
                f"Valid until {expiry_date}",
                styles["header_right_sub"],
            ),
        ],
    ]

    header_table = Table(
        header_data,
        colWidths=[page_width * 0.6, page_width * 0.4],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING",   (0, 0), (0, -1), 20),
        ("RIGHTPADDING",  (1, 0), (1, -1), 20),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.25 * inch))

    # ─── Bill To + Quote Info ─────────────────────────────────────────────────
    quote_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    bill_to_lines = [
        Paragraph("BILL TO", styles["section_label"]),
        Paragraph(quote.client.client_name, styles["section_value_bold"]),
    ]
    if quote.client.contact_name:
        bill_to_lines.append(Paragraph(quote.client.contact_name, styles["section_value"]))
    if quote.client.contact_email:
        bill_to_lines.append(Paragraph(quote.client.contact_email, styles["section_value"]))
    if quote.client.contact_phone:
        bill_to_lines.append(Paragraph(quote.client.contact_phone, styles["section_value"]))
    if quote.client.billing_address:
        bill_to_lines.append(Paragraph(quote.client.billing_address, styles["section_value"]))

    info_lines = [
        Paragraph("QUOTE DETAILS", styles["section_label"]),
        Paragraph(f"Quote #: {quote.quote_number}", styles["section_value_bold"]),
        Paragraph(f"Date: {quote_date}", styles["section_value"]),
        Paragraph(f"Valid for: {quote.valid_days} days", styles["section_value"]),
        Paragraph(f"Currency: {quote.currency}", styles["section_value"]),
    ]

    if quote.artwork:
        story.append(Spacer(1, 0.05 * inch))
        artwork_parts = []
        if quote.artwork.width_inches and quote.artwork.height_inches:
            artwork_parts.append(
                f'{quote.artwork.width_inches}" x {quote.artwork.height_inches}"'
            )
        if quote.artwork.medium:
            artwork_parts.append(quote.artwork.medium)
        if quote.artwork.substrate:
            artwork_parts.append(quote.artwork.substrate)
        if artwork_parts:
            info_lines.append(
                Paragraph(f"Artwork: {', '.join(artwork_parts)}", styles["section_value"])
            )

    meta_table = Table(
        [[bill_to_lines, info_lines]],
        colWidths=[page_width * 0.55, page_width * 0.45],
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_LINE))
    story.append(Spacer(1, 0.15 * inch))

    # ─── Line items table ─────────────────────────────────────────────────────
    col_widths = [
        page_width * 0.05,   # #
        page_width * 0.18,   # Category
        page_width * 0.37,   # Description
        page_width * 0.10,   # Qty
        page_width * 0.15,   # Unit Price
        page_width * 0.15,   # Total
    ]

    table_data = [[
        Paragraph("#",           styles["table_header"]),
        Paragraph("Category",    styles["table_header"]),
        Paragraph("Description", styles["table_header"]),
        Paragraph("Qty",         styles["table_header"]),
        Paragraph("Unit Price",  styles["table_header"]),
        Paragraph("Total",       styles["table_header"]),
    ]]

    for item in quote.line_items:
        sku_text = f'<font size="7" color="#999999">{item.sku}</font><br/>' if item.sku else ""
        notes_text = f'<br/><font size="7" color="#999999">{item.notes}</font>' if item.notes else ""
        table_data.append([
            Paragraph(str(item.line_number), styles["table_cell"]),
            Paragraph(item.category.title(), styles["table_cell"]),
            Paragraph(f"{sku_text}{item.description}{notes_text}", styles["table_cell"]),
            Paragraph(str(item.quantity), styles["table_cell_right"]),
            Paragraph(f"${item.unit_price:,.2f}", styles["table_cell_right"]),
            Paragraph(f"${item.total:,.2f}", styles["table_cell_right"]),
        ])

    line_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    row_count = len(table_data)

    row_colors = []
    for i in range(1, row_count):
        if i % 2 == 0:
            row_colors.append(("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT))

    line_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
        ("TOPPADDING",    (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("TOPPADDING",    (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.5, BRAND_LINE),
        ("LINEBELOW",     (0, 0), (-1, 0), 1.5, BRAND_GOLD),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        *row_colors,
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15 * inch))

    # ─── Totals block ─────────────────────────────────────────────────────────
    totals_data = [
        [
            Paragraph("Subtotal", styles["total_label"]),
            Paragraph(f"${quote.subtotal:,.2f}", styles["table_cell_bold"]),
        ],
    ]
    if quote.tax and quote.tax > 0:
        totals_data.append([
            Paragraph("Tax", styles["total_label"]),
            Paragraph(f"${quote.tax:,.2f}", styles["table_cell_bold"]),
        ])
    totals_data.append([
        Paragraph("TOTAL", styles["total_label"]),
        Paragraph(f"${quote.total:,.2f} {quote.currency}", styles["total_value"]),
    ])

    totals_table = Table(
        totals_data,
        colWidths=[page_width * 0.75, page_width * 0.25],
    )
    totals_table.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("LINEABOVE",     (0, -1), (-1, -1), 1.5, BRAND_GOLD),
        ("TOPPADDING",    (0, -1), (-1, -1), 8),
    ]))
    story.append(totals_table)

    # ─── Notes ────────────────────────────────────────────────────────────────
    if quote.notes:
        story.append(Spacer(1, 0.15 * inch))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_LINE))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("NOTES", styles["notes_label"]))
        story.append(Paragraph(quote.notes, styles["notes_text"]))

    # ─── Validity notice ──────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_LINE))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        f"This quote is valid for {quote.valid_days} days from the date of issue ({quote_date}). "
        f"Prices are subject to change after {expiry_date}.",
        styles["validity"],
    ))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "Skyframe | Custom Framing &amp; Fine Art Printing | NYC | NJ | Miami | datawebify.com",
        styles["footer"],
    ))

    # ─── Build ────────────────────────────────────────────────────────────────
    doc.build(story)

    logger.info("pdf_quote_generated", quote_number=quote.quote_number, path=output_path)
    return output_path
