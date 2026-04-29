"""
Module BTP Match — export structuré des éléments IFC.

Fonctions :
  - filter_by_type      : filtre les éléments par type français
  - group_elements      : regroupe les éléments similaires et calcule les quantités
  - generate_csv        : génère le contenu CSV BTP Match
  - generate_pdf        : génère le PDF BTP Match (bytes)
"""

import io
import csv
from typing import List, Dict, Any, Optional
from collections import defaultdict

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


# ============================================================
# FILTRAGE
# ============================================================

def filter_by_type(elements: List[Dict], type_name: Optional[str]) -> List[Dict]:
    """Retourne les éléments correspondant au type français demandé."""
    if not type_name or type_name == "Tous":
        return elements
    return [e for e in elements if e.get("type") == type_name]


# ============================================================
# GROUPEMENT
# ============================================================

def group_elements(elements: List[Dict]) -> List[Dict]:
    """
    Regroupe les éléments similaires (même type + matériau + dimensions)
    et calcule la quantité pour chaque groupe.
    """
    groups: Dict[tuple, Dict] = defaultdict(lambda: {"count": 0, "sample": None})

    for elem in elements:
        key = (
            elem.get("type", ""),
            elem.get("materiau") or "Non spécifié",
            elem.get("hauteur"),
            elem.get("longueur"),
            elem.get("epaisseur"),
        )
        groups[key]["count"] += 1
        if groups[key]["sample"] is None:
            groups[key]["sample"] = elem

    result = []
    for key, data in groups.items():
        e = data["sample"]
        type_name, materiau, hauteur, longueur, epaisseur = key

        dims = []
        if hauteur is not None:
            dims.append(f"H={hauteur}m")
        if longueur is not None:
            dims.append(f"L={longueur}m")
        if epaisseur is not None:
            dims.append(f"ép={epaisseur}m")

        designation = type_name
        if dims:
            designation += f" ({', '.join(dims)})"

        result.append({
            "designation": designation,
            "materiau": materiau,
            "quantite": data["count"],
            "hauteur": hauteur,
            "longueur": longueur,
            "epaisseur": epaisseur,
        })

    result.sort(key=lambda x: (x["designation"], x["materiau"]))
    return result


# ============================================================
# EXPORT CSV
# ============================================================

def generate_csv(grouped: List[Dict]) -> bytes:
    """
    Génère le contenu CSV BTP Match.
    Retourne les bytes UTF-8 avec BOM pour Excel.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL)

    writer.writerow(["Désignation", "Matériau", "Quantité", "Hauteur (m)", "Longueur (m)", "Épaisseur (m)"])

    for row in grouped:
        writer.writerow([
            row["designation"],
            row["materiau"],
            row["quantite"],
            row["hauteur"] if row["hauteur"] is not None else "",
            row["longueur"] if row["longueur"] is not None else "",
            row["epaisseur"] if row["epaisseur"] is not None else "",
        ])

    bom = "\uFEFF"
    return (bom + output.getvalue()).encode("utf-8")


# ============================================================
# EXPORT PDF
# ============================================================

def generate_pdf(grouped: List[Dict], type_name: str) -> bytes:
    """
    Génère le PDF BTP Match lisible pour un humain.
    Retourne les bytes PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BTPTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1e40af"),
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "BTPSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    elements_pdf = []

    elements_pdf.append(Paragraph("BTP Match — Fiche Export", title_style))
    label = type_name if type_name and type_name != "Tous" else "Tous les éléments"
    elements_pdf.append(Paragraph(f"Type : {label}", subtitle_style))
    elements_pdf.append(Spacer(1, 0.3 * cm))

    headers = ["Désignation", "Matériau", "Qté", "Hauteur (m)", "Longueur (m)", "Épaisseur (m)"]
    table_data = [headers]

    for row in grouped:
        table_data.append([
            row["designation"],
            row["materiau"],
            str(row["quantite"]),
            str(row["hauteur"]) if row["hauteur"] is not None else "—",
            str(row["longueur"]) if row["longueur"] is not None else "—",
            str(row["epaisseur"]) if row["epaisseur"] is not None else "—",
        ])

    col_widths = [6 * cm, 4 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    elements_pdf.append(table)
    elements_pdf.append(Spacer(1, 0.5 * cm))

    total_qty = sum(r["quantite"] for r in grouped)
    elements_pdf.append(Paragraph(
        f"<b>Total : {len(grouped)} désignation(s), {total_qty} élément(s)</b>",
        styles["Normal"]
    ))

    doc.build(elements_pdf)
    return buffer.getvalue()
