"""
Générateur de rapport — produit le rapport JSON et PDF de validation IFC.
"""
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Dict, List

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak,
)
from reportlab.platypus.flowables import HRFlowable


def to_json(report: dict) -> str:
    """Sérialise le rapport en JSON formatté."""
    return json.dumps(report, ensure_ascii=False, indent=2)


def to_pdf(report: dict, project_name: str = "") -> bytes:
    """Génère le PDF du rapport de validation."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.fontSize = 16
    title_style.spaceAfter = 8

    h2_style = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=6,
                               textColor=colors.HexColor("#1e3a5f"))
    normal = styles["Normal"]
    normal.fontSize = 9

    story = []

    # ── Titre + Score ─────────────────────────────────────
    story.append(Paragraph("<b>Rapport de Qualité Maquette IFC</b>", title_style))
    if project_name:
        story.append(Paragraph(f"Projet : {project_name}", normal))
    story.append(Paragraph(
        f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  "
        f"Score global : <b>{report['global_score']}%</b>  |  "
        f"Grade : <b>{report['grade']}</b>",
        normal
    ))
    story.append(Spacer(1, 6))

    # ── Barre de couleur grade ────────────────────────────
    grade_colors = {"A": "#22c55e", "B": "#eab308", "C": "#f97316", "D": "#ef4444"}
    grade_labels = {"A": "Prêt pour réemploi", "B": "Réemployable avec compléments",
                    "C": "Données insuffisantes", "D": "Non conforme — maquette à enrichir"}
    g = report["grade"]
    story.append(Paragraph(
        f"<font color='{grade_colors.get(g, '#000')}'><b>{grade_labels.get(g, '')}</b></font>",
        ParagraphStyle("grade", parent=normal, fontSize=12, spaceAfter=8)
    ))

    # ── Résumé ────────────────────────────────────────────
    story.append(Paragraph(f"<b>Résumé</b>", h2_style))
    story.append(Paragraph(
        f"Éléments analysés : <b>{report['total_elements']}</b>  |  "
        f"Éléments non conformes : <b><font color='red'>{report['blocking_count']}</font></b>",
        normal
    ))
    story.append(Spacer(1, 8))

    # ── Tableau par type ──────────────────────────────────
    story.append(Paragraph("<b>Par type d'élément</b>", h2_style))
    per_type = report.get("per_type", {})
    if per_type:
        type_data = [["Type", "Nombre", "Score", "Grade", "Bloquants"]]
        for t, v in sorted(per_type.items()):
            type_data.append([
                t.replace("Ifc", ""),
                str(v["total"]),
                f"{v['score']}%",
                QualityScorer_grade(v["score"]),
                str(v["blocking"]),
            ])
        tbl = Table(type_data, colWidths=[90, 70, 70, 70, 70])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 12))

    # ── Éléments critiques ────────────────────────────────
    criticals = [e for e in report.get("elements", []) if e["blocking"]]
    if criticals:
        story.append(Paragraph(
            f"<b><font color='red'>🔴 Éléments bloquants ({len(criticals)})</font></b>",
            ParagraphStyle("crit", parent=h2_style, textColor=colors.HexColor("#dc2626"))
        ))
        for elem in criticals:
            missing = [c for c in elem["checks"] if not c["passed"]]
            story.append(Paragraph(
                f"<b>{elem['type'].replace('Ifc','')}</b> — {elem['name']} "
                f"(Score : {elem['score']}% | Grade : {elem['grade']})",
                normal
            ))
            for m in missing:
                story.append(Paragraph(
                    f"&nbsp;&nbsp;&nbsp;❌ <b>{m['attribute']}</b> : {m['description']} <i>({m['detail']})</i>",
                    ParagraphStyle("miss", parent=normal, fontSize=8, leftIndent=20, textColor=colors.HexColor("#dc2626"))
                ))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 6))

    # ── Éléments conformes ────────────────────────────────
    ok_list = [e for e in report.get("elements", []) if not e["blocking"]]
    story.append(Paragraph(
        f"<b><font color='green'>✅ Éléments conformes ({len(ok_list)})</font></b>",
        ParagraphStyle("ok", parent=h2_style, textColor=colors.HexColor("#16a34a"))
    ))

    # ── Échelle des grades ────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Paragraph("<b>Échelle des grades</b>", h2_style))
    scale = [
        ("A", "≥ 90%", "Prêt pour réemploi"),
        ("B", "70-89%", "Réemployable avec compléments"),
        ("C", "50-69%", "Données insuffisantes — enrichir la maquette"),
        ("D", "< 50%", "Non conforme — maquette à enrichir impérativement"),
    ]
    for g, rng, label in scale:
        story.append(Paragraph(
            f"<font color='{grade_colors[g]}'><b>{g}</b></font> ({rng}) : {label}",
            normal
        ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


def QualityScorer_grade(score: float) -> str:
    """Helper pour le tableau par type."""
    if score >= 90:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"
