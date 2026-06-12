"""
Génère un PDF PEMD (CERFA) pour l'éditeur PEMD interactif.
Tableau 1 : Caractérisation des PEM identifiés comme potentiellement réemployables.
"""

from io import BytesIO
from typing import List, Dict, Any

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)


def _ps(size: int, align=TA_CENTER, bold=False, color=colors.black):
    return ParagraphStyle(
        f"s{size}",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        alignment=align,
        textColor=color,
        leading=size + 2,
        wordWrap="CJK",
    )


# Styles
S_TITLE = _ps(14, bold=True, color=colors.HexColor("#1e3a5f"))
S_TH_MAIN = _ps(9, bold=True, color=colors.white)
S_TH_LEFT = _ps(8, bold=True, color=colors.HexColor("#1e3a5f"))
S_TH_RIGHT = _ps(8, bold=True, color=colors.HexColor("#1e3a5f"))
S_TD = _ps(8, align=TA_LEFT, color=colors.HexColor("#374151"))
S_TD_C = _ps(8, align=TA_CENTER, color=colors.HexColor("#374151"))

# Couleurs
BLUE_MAIN = colors.HexColor("#1e3a5f")
BLUE_LIGHT = colors.HexColor("#dbeafe")
BLUE_MID = colors.HexColor("#bfdbfe")
GREY_LIGHT = colors.HexColor("#f3f4f6")
WHITE = colors.white
PURPLE_LIGHT = colors.HexColor("#c7c8e0")


def generate_pemd_pdf(components: List[Dict[str, Any]], project_name: str = "") -> bytes:
    """Génère un PDF PEMD CERFA avec le tableau exact de l'image."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    story = []
    story.append(Paragraph(
        f"<b>Tableau 1 — Caractérisation des produits, équipements et matériaux (PEM) "
        f"identifiés comme potentiellement réemployables (4)</b>",
        S_TITLE
    ))
    story.append(Spacer(1, 0.4 * cm))

    # En-tête principal
    header_data = [
        [
            Paragraph("Remplissez ces colonnes", S_TH_MAIN),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            Paragraph(
                "Cochez la case pour indiquer si ces informations sont "
                "renseignées dans votre rapport de diagnostic (14)",
                S_TH_MAIN
            ),
            "",
            "",
            "",
        ],
    ]

    # En-tête colonnes
    col_headers = [
        Paragraph("Catégorie<br>(5)", S_TH_LEFT),
        Paragraph("Description<br>(6)", S_TH_LEFT),
        Paragraph("Quantité disponible et unité appropriée<br>(7)", S_TH_LEFT),
        Paragraph("Dimensions<br>(8)", S_TH_LEFT),
        Paragraph("Type principal d'assemblage<br>(9)", S_TH_LEFT),
        Paragraph("Âge estimé<br>(10)", S_TH_LEFT),
        Paragraph("État de conservation ou de fonctionnement estimé<br>(11)", S_TH_LEFT),
        Paragraph(
            "Suspectez-vous la présence de substances dangereuses "
            "ou de polluant organique persistant dans ce PEM ?<br>(12)",
            S_TH_LEFT
        ),
        Paragraph("Matériaux Constitutifs<br>(13)", S_TH_LEFT),
        Paragraph("Localisation et fonction du PEM dans le bâtiment<br>(15)", S_TH_RIGHT),
        Paragraph(
            "Conditions techniques et économiques pour permettre le réemploi du PEM<br>(16)",
            S_TH_RIGHT
        ),
        Paragraph("Informations techniques disponibles<br>(17)", S_TH_RIGHT),
        Paragraph("Précautions de dépose, transport et stockage<br>(18)", S_TH_RIGHT),
    ]

    # Données
    data = [col_headers]
    for c in components:
        data.append([
            Paragraph(c.get("pem_category") or c.get("type", "—"), S_TD),
            Paragraph(c.get("pem_description") or "—", S_TD),
            Paragraph(c.get("pem_quantity") or "—", S_TD_C),
            Paragraph(c.get("pem_dimensions") or "—", S_TD_C),
            Paragraph(c.get("pem_assembly_type") or "—", S_TD_C),
            Paragraph(c.get("pem_age") or "—", S_TD_C),
            Paragraph(c.get("pem_condition") or "—", S_TD_C),
            Paragraph("☑" if c.get("pem_hazardous") else "☐", S_TD_C),
            Paragraph(c.get("pem_materials") or c.get("material", "—"), S_TD),
            Paragraph("☑" if c.get("pem_location") else "☐", S_TD_C),
            Paragraph("☑" if c.get("pem_reuse_conditions") else "☐", S_TD_C),
            Paragraph("☑" if c.get("pem_tech_info") else "☐", S_TD_C),
            Paragraph("☑" if c.get("pem_transport_precautions") else "☐", S_TD_C),
        ])

    # Largeurs de colonnes
    page_w = landscape(A4)[0] - 2.4 * cm
    col_widths = [
        page_w * 0.10,  # Catégorie
        page_w * 0.12,  # Description
        page_w * 0.08,  # Quantité
        page_w * 0.08,  # Dimensions
        page_w * 0.08,  # Type assemblage
        page_w * 0.06,  # Âge
        page_w * 0.08,  # État
        page_w * 0.10,  # Substances dangereuses
        page_w * 0.10,  # Matériaux
        page_w * 0.08,  # Localisation
        page_w * 0.10,  # Conditions réemploi
        page_w * 0.08,  # Informations techniques
        page_w * 0.08,  # Précautions
    ]

    # Construction du tableau
    full_data = header_data + data
    tbl = Table(full_data, colWidths=col_widths, repeatRows=2)

    style_cmds = [
        # En-tête principal
        ("BACKGROUND", (0, 0), (8, 0), BLUE_MAIN),
        ("BACKGROUND", (9, 0), (12, 0), PURPLE_LIGHT),
        ("TEXTCOLOR", (0, 0), (12, 0), colors.white),
        ("SPAN", (0, 0), (8, 0)),
        ("SPAN", (9, 0), (12, 0)),
        ("VALIGN", (0, 0), (12, 0), "MIDDLE"),
        ("TOPPADDING", (0, 0), (12, 0), 6),
        ("BOTTOMPADDING", (0, 0), (12, 0), 6),
        ("LEFTPADDING", (0, 0), (12, 0), 4),
        # En-tête colonnes
        ("BACKGROUND", (0, 1), (8, 1), BLUE_MID),
        ("BACKGROUND", (9, 1), (12, 1), PURPLE_LIGHT),
        ("TEXTCOLOR", (0, 1), (12, 1), colors.HexColor("#1e3a5f")),
        ("VALIGN", (0, 1), (12, 1), "MIDDLE"),
        ("TOPPADDING", (0, 1), (12, 1), 4),
        ("BOTTOMPADDING", (0, 1), (12, 1), 4),
        ("LEFTPADDING", (0, 1), (12, 1), 3),
        # Grille
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e3a5f")),
        ("VALIGN", (0, 2), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 2), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 3),
        ("LEFTPADDING", (0, 2), (-1, -1), 3),
    ]

    # Alternance de couleurs
    for i, row in enumerate(data[1:], 2):
        bg = GREY_LIGHT if i % 2 == 0 else WHITE
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()
