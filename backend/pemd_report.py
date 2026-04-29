"""
Générateur de rapport PEMD (Tableau 1) depuis des éléments IFC extraits.
Utilise les données déjà extraites par le backend IFC Analyzer.
"""

import io
from collections import defaultdict
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)


# ============================================================
# CORRESPONDANCE TYPE IFC → CATÉGORIE PEMD
# ============================================================

PEMD_CATEGORY_MAP = {
    "Porte":      {"code": "6.2", "label": " Portes, fenêtres, fermetures, protections solaires", "unite": "U"},
    "Fenêtre":    {"code": "6.2", "label": " Portes, fenêtres, fermetures, protections solaires", "unite": "U"},
    "Mur":        {"code": "5.2", "label": " Doublages mur, matériaux de protection isolants et membranes", "unite": "m"},
    "Mur rideau": {"code": "3.3", "label": "Façades ", "unite": "U"},
    "Dalle":      {"code": "3.1", "label": "Planchers , dalles , Balcons", "unite": "m"},
    "Escalier":   {"code": "3.6", "label": "Escaliers et rampes", "unite": "U"},
}

DEFAULT_CATEGORY = {"code": "9.9", "label": "Autres éléments", "unite": "U"}


# ============================================================
# PALETTE
# ============================================================

BLEU_FONCE   = colors.HexColor("#1e3a5f")
BLEU_MOYEN   = colors.HexColor("#2563eb")
BLEU_CLAIR   = colors.HexColor("#dbeafe")
VERT         = colors.HexColor("#059669")
VERT_CLAIR   = colors.HexColor("#d1fae5")
ORANGE       = colors.HexColor("#d97706")
ORANGE_CLAIR = colors.HexColor("#fef3c7")
ROUGE_CLAIR  = colors.HexColor("#fee2e2")
GRIS_CLAIR   = colors.HexColor("#f3f4f6")
GRIS_TEXTE   = colors.HexColor("#374151")
BLANC        = colors.white


# ============================================================
# STYLES
# ============================================================

def _styles():
    s = {}
    s["h1"] = ParagraphStyle("H1", fontSize=14, fontName="Helvetica-Bold",
                              textColor=BLEU_FONCE, spaceBefore=14, spaceAfter=6)
    s["h2"] = ParagraphStyle("H2", fontSize=11, fontName="Helvetica-Bold",
                              textColor=BLEU_MOYEN, spaceBefore=10, spaceAfter=4)
    s["body"] = ParagraphStyle("Body", fontSize=9, fontName="Helvetica",
                                textColor=GRIS_TEXTE, spaceAfter=4, leading=13,
                                alignment=TA_JUSTIFY)
    s["bullet"] = ParagraphStyle("Bullet", fontSize=9, fontName="Helvetica",
                                  textColor=GRIS_TEXTE, spaceAfter=3, leading=13,
                                  leftIndent=14)
    s["th"] = ParagraphStyle("TH", fontSize=8, fontName="Helvetica-Bold",
                              textColor=BLANC, alignment=TA_CENTER)
    s["td"] = ParagraphStyle("TD", fontSize=7.5, fontName="Helvetica",
                              textColor=GRIS_TEXTE, leading=11)
    s["td_c"] = ParagraphStyle("TDC", fontSize=7.5, fontName="Helvetica",
                                textColor=GRIS_TEXTE, alignment=TA_CENTER, leading=11)
    s["footer"] = ParagraphStyle("Footer", fontSize=7, fontName="Helvetica",
                                  textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)
    s["warn"] = ParagraphStyle("Warn", fontSize=8.5, fontName="Helvetica",
                                textColor=colors.HexColor("#92400e"), leading=13)
    s["info"] = ParagraphStyle("Info", fontSize=8.5, fontName="Helvetica",
                                textColor=colors.HexColor("#1e40af"), leading=13)
    return s


# ============================================================
# HELPERS PDF
# ============================================================

def _box(text, style_p, bg, border_color):
    t = Table([[Paragraph(text, style_p)]], colWidths=[17 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEAFTER", (0, 0), (0, -1), 4, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _section_bar(code, label, count, s):
    data = [[
        Paragraph(f"<b>{code}</b>", ParagraphStyle("SC", fontSize=11, fontName="Helvetica-Bold",
                                                    textColor=BLANC, alignment=TA_CENTER)),
        Paragraph(f"<b>{label}</b>", ParagraphStyle("SL", fontSize=11, fontName="Helvetica-Bold",
                                                     textColor=BLANC)),
        Paragraph(f"{count} élément(s)", ParagraphStyle("SN", fontSize=9, fontName="Helvetica",
                                                          textColor=colors.HexColor("#93c5fd"),
                                                          alignment=TA_CENTER)),
    ]]
    t = Table(data, colWidths=[1.8 * cm, 12.5 * cm, 2.7 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLEU_FONCE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, 0), 10),
        ("LEFTPADDING", (1, 0), (1, 0), 10),
    ]))
    return t


# ============================================================
# TRANSFORMATION IFC → PEMD
# ============================================================

def _dim_str(elem: Dict) -> str:
    parts = []
    h = elem.get("hauteur")
    l = elem.get("longueur")
    e = elem.get("epaisseur")
    if h: parts.append(f"H={h}m")
    if l: parts.append(f"L={l}m")
    if e: parts.append(f"ép={e}m")
    return ", ".join(parts) if parts else "—"


def _qty_display(elem: Dict, cat: Dict) -> str:
    """Calcule une quantité indicative selon l'unité PEMD."""
    unite = cat["unite"]
    if unite == "m²":
        area = elem.get("net_area")
        if area:
            return str(area)
        h = elem.get("hauteur") or 0
        l = elem.get("longueur") or 0
        if h and l:
            return str(round(h * l, 2))
    return "1"


def _description(elem: Dict, type_name: str) -> str:
    mat = elem.get("materiau") or "matériau inconnu"
    dims = _dim_str(elem)
    etage = elem.get("etage") or "étage inconnu"
    base = {
        "Porte":      f"Porte {mat}",
        "Fenêtre":    f"Fenêtre {mat}",
        "Mur":        f"Mur / cloison {mat}",
        "Mur rideau": f"Mur rideau {mat}",
        "Dalle":      f"Dalle / plancher {mat}",
        "Escalier":   f"Escalier {mat}",
    }.get(type_name, f"Élément {mat}")
    return f"{base} — {etage}" + (f" ({dims})" if dims != "—" else "")


def group_for_pemd(elements: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Groupe les éléments par catégorie PEMD et regroupe
    les éléments similaires (même type + matériau + dimensions).
    Retourne un dict {code_pemd: [lignes groupées]}.
    """
    # 1. Grouper par (type, matériau, dims)
    raw_groups: Dict[tuple, Dict] = defaultdict(lambda: {"count": 0, "sample": None})
    for elem in elements:
        key = (
            elem.get("type", ""),
            elem.get("materiau") or "Inconnu",
            elem.get("hauteur"),
            elem.get("longueur"),
            elem.get("epaisseur"),
        )
        raw_groups[key]["count"] += 1
        if raw_groups[key]["sample"] is None:
            raw_groups[key]["sample"] = elem

    # 2. Réorganiser par code PEMD
    by_pemd: Dict[str, List[Dict]] = defaultdict(list)
    for key, data in raw_groups.items():
        type_name = key[0]
        cat = PEMD_CATEGORY_MAP.get(type_name, DEFAULT_CATEGORY)
        sample = data["sample"]
        by_pemd[cat["code"]].append({
            "cat": cat,
            "type_name": type_name,
            "description": _description(sample, type_name),
            "quantite": data["count"],
            "qty_display": _qty_display(sample, cat),
            "unite": cat["unite"],
            "dimensions": _dim_str(sample),
            "materiau": sample.get("materiau") or "Non identifié",
            "etage": sample.get("etage") or "—",
            "sample": sample,
        })

    return dict(by_pemd)


# ============================================================
# GÉNÉRATION PDF
# ============================================================

def generate_pemd_pdf(elements: List[Dict], project_name: str = "Projet IFC") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    s = _styles()
    story = []

    by_pemd = group_for_pemd(elements)
    total = len(elements)
    types_count = defaultdict(int)
    for elem in elements:
        types_count[elem.get("type", "Autre")] += 1
    avertissements = []

    # ── COUVERTURE ──────────────────────────────────────────
    couv = Table([
        [Paragraph("DIAGNOSTIC PEMD", ParagraphStyle("CT", fontSize=20, fontName="Helvetica-Bold",
                                                       textColor=BLANC, alignment=TA_CENTER))],
        [Paragraph("Tableau 1 — Produits potentiellement réemployables",
                   ParagraphStyle("CS", fontSize=12, fontName="Helvetica",
                                  textColor=colors.HexColor("#bfdbfe"), alignment=TA_CENTER))],
        [Spacer(1, 0.2 * cm)],
        [Paragraph(f"Projet : <b>{project_name}</b>",
                   ParagraphStyle("CP", fontSize=11, fontName="Helvetica",
                                  textColor=BLANC, alignment=TA_CENTER))],
        [Paragraph(f"Généré automatiquement depuis données IFC — {total} éléments analysés",
                   ParagraphStyle("CI", fontSize=9, fontName="Helvetica",
                                  textColor=colors.HexColor("#93c5fd"), alignment=TA_CENTER))],
    ], colWidths=[17 * cm])
    couv.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLEU_FONCE),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(couv)
    story.append(Spacer(1, 0.6 * cm))

    story.append(_box(
        "📋  Ce rapport a été généré automatiquement à partir d'un fichier IFC. "
        "Les données dimensionnelles et matériaux proviennent des <b>BaseQuantities</b> et "
        "<b>PropertySets</b> de l'IFC. Les colonnes État, Âge et Assemblage doivent être "
        "complétées lors de la visite terrain.",
        s["info"], BLEU_CLAIR, BLEU_MOYEN,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ── SECTION 1 : SYNTHÈSE ────────────────────────────────
    story.append(Paragraph("1. Synthèse des éléments détectés", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLEU_MOYEN))
    story.append(Spacer(1, 0.3 * cm))

    synth_data = [[
        Paragraph("<b>Type IFC</b>", s["th"]),
        Paragraph("<b>Nb éléments</b>", s["th"]),
        Paragraph("<b>Catégorie PEMD</b>", s["th"]),
        Paragraph("<b>Code</b>", s["th"]),
    ]]
    for type_name, cnt in sorted(types_count.items()):
        cat = PEMD_CATEGORY_MAP.get(type_name, DEFAULT_CATEGORY)
        synth_data.append([
            Paragraph(type_name, s["td"]),
            Paragraph(str(cnt), s["td_c"]),
            Paragraph(cat["label"], s["td"]),
            Paragraph(cat["code"], s["td_c"]),
        ])
    synth_data.append([
        Paragraph("<b>TOTAL</b>", ParagraphStyle("Tot", fontSize=8, fontName="Helvetica-Bold",
                                                  textColor=GRIS_TEXTE)),
        Paragraph(f"<b>{total}</b>", ParagraphStyle("TotN", fontSize=8, fontName="Helvetica-Bold",
                                                     textColor=GRIS_TEXTE, alignment=TA_CENTER)),
        Paragraph("", s["td"]),
        Paragraph("", s["td"]),
    ])

    synth_t = Table(synth_data, colWidths=[4 * cm, 3 * cm, 7.5 * cm, 2.5 * cm], repeatRows=1)
    n = len(synth_data)
    synth_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLEU_FONCE),
        ("BACKGROUND", (0, n-1), (-1, n-1), GRIS_CLAIR),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        *[("BACKGROUND", (0, i), (-1, i), GRIS_CLAIR if i % 2 == 0 else BLANC)
          for i in range(1, n - 1)],
    ]))
    story.append(synth_t)
    story.append(Spacer(1, 0.5 * cm))

    # ── SECTION 2 : DÉTAIL PAR CATÉGORIE ────────────────────
    story.append(PageBreak())
    story.append(Paragraph("2. Détail par catégorie PEMD", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLEU_MOYEN))
    story.append(Spacer(1, 0.3 * cm))

    # Trier les catégories
    sorted_pemd = sorted(by_pemd.items(), key=lambda x: x[0])

    for code, lignes in sorted_pemd:
        cat_label = lignes[0]["cat"]["label"]
        total_cat = sum(l["quantite"] for l in lignes)

        story.append(KeepTogether([
            _section_bar(code, cat_label, total_cat, s),
            Spacer(1, 0.2 * cm),
        ]))

        # Tableau PEMD
        headers = ["Description", "Qté\nrégroupée", "Unité", "Dimensions", "Matériau",
                   "État*", "Âge*", "Assemblage*", "Localisation"]
        col_w = [4.5*cm, 1.5*cm, 1.2*cm, 2.8*cm, 2*cm, 1.2*cm, 1*cm, 2*cm, 1.8*cm]

        tdata = [[Paragraph(h, s["th"]) for h in headers]]

        for i, ligne in enumerate(lignes):
            bg = GRIS_CLAIR if i % 2 == 0 else BLANC
            tdata.append([
                Paragraph(ligne["description"], s["td"]),
                Paragraph(str(ligne["quantite"]), s["td_c"]),
                Paragraph(ligne["unite"], s["td_c"]),
                Paragraph(ligne["dimensions"], s["td_c"]),
                Paragraph(ligne["materiau"], s["td"]),
                Paragraph("", s["td_c"]),   # État → à compléter
                Paragraph("", s["td_c"]),   # Âge → à compléter
                Paragraph("", s["td_c"]),   # Assemblage → à compléter
                Paragraph(ligne["etage"], s["td"]),
            ])

        tbl = Table(tdata, colWidths=col_w, repeatRows=1)
        n_rows = len(tdata)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BLEU_MOYEN),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            *[("BACKGROUND", (0, i), (-1, i), GRIS_CLAIR if i % 2 == 0 else BLANC)
              for i in range(1, n_rows)],
            # Colonnes à compléter en fond légèrement jaune
            *[("BACKGROUND", (5, i), (7, i), ORANGE_CLAIR) for i in range(1, n_rows)],
        ]))

        story.append(tbl)
        story.append(Paragraph(
            "* Colonnes à compléter lors de la visite terrain (État, Âge, Assemblage).",
            ParagraphStyle("Note", fontSize=7, fontName="Helvetica",
                           textColor=colors.HexColor("#6b7280"), spaceBefore=2, spaceAfter=8),
        ))
        story.append(Spacer(1, 0.4 * cm))

        # Détecter données manquantes
        missing_mat = sum(1 for l in lignes if l["materiau"] in ("Non identifié", "Inconnu", ""))
        missing_dim = sum(1 for l in lignes if l["dimensions"] == "—")
        if missing_mat > 0:
            avertissements.append(f"Catégorie {code} : {missing_mat} élément(s) sans matériau identifié.")
        if missing_dim > 0:
            avertissements.append(f"Catégorie {code} : {missing_dim} élément(s) sans dimensions disponibles.")

    # ── SECTION 3 : INFORMATIONS À COMPLÉTER ────────────────
    story.append(PageBreak())
    story.append(Paragraph("3. Informations à compléter sur site", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BLEU_MOYEN))
    story.append(Spacer(1, 0.3 * cm))

    story.append(_box(
        "Les colonnes surlignées en jaune dans les tableaux ci-dessus doivent être renseignées "
        "lors de la <b>visite de terrain</b> par le diagnostiqueur. Voici le guide pour chaque champ :",
        s["info"], BLEU_CLAIR, BLEU_MOYEN,
    ))
    story.append(Spacer(1, 0.3 * cm))

    champs = [
        ("État", "Évaluer l'état apparent : Neuf / Bon / Moyen / Mauvais. "
                 "Seuls les éléments Bon ou Neuf sont à inclure en réemploi."),
        ("Âge", "Estimer l'année de pose ou la décennie (ex : ~1985, 1990-2000). "
                "Sources : carnet d'entretien, permis de construire, DOE."),
        ("Type d'assemblage", "Mécanique (vissé, boulonné) → réemploi facile. "
                              "Chimique (collé, soudé) → réemploi difficile. "
                              "Mixte → indiquer les deux."),
        ("Vérification terrain", "Confirmer les quantités extraites de l'IFC par comptage physique. "
                                 "Vérifier les dimensions clés avec un mètre ou un scanner laser."),
    ]
    for champ, expl in champs:
        data = [[
            Paragraph(f"<b>{champ}</b>", ParagraphStyle("CH", fontSize=9, fontName="Helvetica-Bold",
                                                          textColor=BLEU_FONCE)),
            Paragraph(expl, s["body"]),
        ]]
        t = Table(data, colWidths=[3.5 * cm, 13.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLAIR),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ]))
        story.append(t)

    story.append(Spacer(1, 0.5 * cm))

    # ── SECTION 4 : AVERTISSEMENTS ──────────────────────────
    story.append(Paragraph("4. Avertissements et limitations", s["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ORANGE))
    story.append(Spacer(1, 0.3 * cm))

    avertissements_generaux = [
        "Ce rapport est généré automatiquement depuis un fichier IFC et ne constitue pas un diagnostic officiel.",
        "Les quantités indiquées sont celles extraites du modèle IFC (peuvent différer du réel).",
        "Le classement PEMD est basé sur le type IFC ; une vérification experte est recommandée.",
        "Les éléments sans matériau ou sans dimensions dans l'IFC sont signalés ci-dessous.",
    ]
    all_warns = avertissements_generaux + avertissements

    warn_rows = [[Paragraph(f"⚠️  {w}", s["warn"])] for w in all_warns]
    warn_t = Table(warn_rows, colWidths=[17 * cm])
    warn_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ORANGE_CLAIR),
        ("LINEAFTER", (0, 0), (0, -1), 4, ORANGE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#fde68a")),
    ]))
    story.append(warn_t)
    story.append(Spacer(1, 0.5 * cm))

    # ── PIED DE PAGE ────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d1d5db")))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"Rapport PEMD généré par IFC Analyzer | Décret n°2021-822 du 25 juin 2021 | "
        f"Document de travail — à compléter par un diagnostiqueur certifié",
        s["footer"],
    ))

    doc.build(story)
    return buffer.getvalue()
