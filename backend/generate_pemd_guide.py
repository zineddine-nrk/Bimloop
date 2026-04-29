"""
Générateur du guide PEMD — Tableau 1 (Produits potentiellement réemployables).
Exécuter : python generate_pemd_guide.py
Le fichier guide_pemd_tableau1.pdf sera créé dans le dossier courant.
"""

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
# PALETTE DE COULEURS
# ============================================================
BLEU_FONCE  = colors.HexColor("#1e3a5f")
BLEU_MOYEN  = colors.HexColor("#2563eb")
BLEU_CLAIR  = colors.HexColor("#dbeafe")
VERT        = colors.HexColor("#059669")
VERT_CLAIR  = colors.HexColor("#d1fae5")
ORANGE      = colors.HexColor("#d97706")
ORANGE_CLAIR= colors.HexColor("#fef3c7")
ROUGE_CLAIR = colors.HexColor("#fee2e2")
GRIS_CLAIR  = colors.HexColor("#f3f4f6")
GRIS_TEXTE  = colors.HexColor("#374151")
BLANC       = colors.white


# ============================================================
# STYLES
# ============================================================

def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "titre_principal": ParagraphStyle(
            "TitrePrincipal",
            fontSize=22, fontName="Helvetica-Bold",
            textColor=BLANC, alignment=TA_CENTER,
            spaceAfter=4, leading=28,
        ),
        "sous_titre_couv": ParagraphStyle(
            "SousTitreCouv",
            fontSize=12, fontName="Helvetica",
            textColor=colors.HexColor("#bfdbfe"), alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "h1": ParagraphStyle(
            "H1", fontSize=15, fontName="Helvetica-Bold",
            textColor=BLEU_FONCE, spaceBefore=18, spaceAfter=6,
            borderPad=4, leading=20,
        ),
        "h2": ParagraphStyle(
            "H2", fontSize=12, fontName="Helvetica-Bold",
            textColor=BLEU_MOYEN, spaceBefore=12, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "H3", fontSize=10, fontName="Helvetica-Bold",
            textColor=GRIS_TEXTE, spaceBefore=8, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "Body", fontSize=9.5, fontName="Helvetica",
            textColor=GRIS_TEXTE, spaceAfter=5, leading=14,
            alignment=TA_JUSTIFY,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold", fontSize=9.5, fontName="Helvetica-Bold",
            textColor=GRIS_TEXTE, spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "Bullet", fontSize=9.5, fontName="Helvetica",
            textColor=GRIS_TEXTE, spaceAfter=3, leading=14,
            leftIndent=16, bulletIndent=4,
        ),
        "info_box": ParagraphStyle(
            "InfoBox", fontSize=9, fontName="Helvetica",
            textColor=colors.HexColor("#1e40af"), leading=14,
        ),
        "warning_box": ParagraphStyle(
            "WarningBox", fontSize=9, fontName="Helvetica",
            textColor=colors.HexColor("#92400e"), leading=14,
        ),
        "table_header": ParagraphStyle(
            "TableHeader", fontSize=8, fontName="Helvetica-Bold",
            textColor=BLANC, alignment=TA_CENTER,
        ),
        "table_cell": ParagraphStyle(
            "TableCell", fontSize=7.5, fontName="Helvetica",
            textColor=GRIS_TEXTE, leading=11,
        ),
        "tag": ParagraphStyle(
            "Tag", fontSize=8, fontName="Helvetica-Bold",
            textColor=VERT,
        ),
        "footer": ParagraphStyle(
            "Footer", fontSize=7.5, fontName="Helvetica",
            textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER,
        ),
    }
    return styles


# ============================================================
# COMPOSANTS RÉUTILISABLES
# ============================================================

def info_box(text, s, color_bg=BLEU_CLAIR, color_border=BLEU_MOYEN, style_key="info_box"):
    """Encadré d'information coloré."""
    content = [[Paragraph(text, s[style_key])]]
    t = Table(content, colWidths=[16.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color_bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEAFTER", (0, 0), (0, -1), 4, color_border),
    ]))
    return t


def warning_box(text, s):
    return info_box(text, s, ORANGE_CLAIR, ORANGE, "warning_box")


def section_title(num, titre, s):
    """Titre de section numérotée avec barre colorée."""
    data = [[
        Paragraph(f"<b>{num}</b>", ParagraphStyle("Num", fontSize=13, fontName="Helvetica-Bold",
                                                    textColor=BLANC, alignment=TA_CENTER)),
        Paragraph(titre, ParagraphStyle("SecT", fontSize=13, fontName="Helvetica-Bold",
                                         textColor=BLANC)),
    ]]
    t = Table(data, colWidths=[1 * cm, 15.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLEU_FONCE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 10),
    ]))
    return t


def colonne_card(numero, nom, explication, conseil, s):
    """Carte explicative pour une colonne du tableau PEMD."""
    header = [[
        Paragraph(f"Colonne {numero}", ParagraphStyle("CN", fontSize=8, fontName="Helvetica-Bold",
                                                       textColor=BLEU_MOYEN)),
        Paragraph(f"<b>{nom}</b>", ParagraphStyle("CNom", fontSize=10, fontName="Helvetica-Bold",
                                                   textColor=BLEU_FONCE)),
    ]]
    body_rows = [
        [Paragraph("Explication :", s["h3"]), Paragraph(explication, s["body"])],
        [Paragraph("Conseil :", s["h3"]), Paragraph(conseil, s["body"])],
    ]

    header_t = Table(header, colWidths=[3 * cm, 13.5 * cm])
    header_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLAIR),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))

    body_t = Table(body_rows, colWidths=[3 * cm, 13.5 * cm])
    body_t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.HexColor("#e5e7eb")),
    ]))

    outer = Table([[header_t], [body_t]], colWidths=[16.5 * cm])
    outer.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return outer


# ============================================================
# CONSTRUCTION DU DOCUMENT
# ============================================================

def build_document(filename="guide_pemd_tableau1.pdf"):
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    s = build_styles()
    story = []

    # ── PAGE DE COUVERTURE ────────────────────────────────────
    couv_data = [[
        Paragraph("GUIDE PRATIQUE", s["titre_principal"]),
        Paragraph("Diagnostic PEMD — Tableau 1", ParagraphStyle(
            "T2", fontSize=17, fontName="Helvetica-Bold", textColor=BLANC,
            alignment=TA_CENTER, spaceAfter=6,
        )),
        Paragraph("Produits potentiellement réemployables", s["sous_titre_couv"]),
        Spacer(1, 0.3 * cm),
        Paragraph("Comment remplir chaque colonne du CERFA PEMD", ParagraphStyle(
            "Sub2", fontSize=10, fontName="Helvetica", textColor=colors.HexColor("#93c5fd"),
            alignment=TA_CENTER,
        )),
    ]]
    couv_t = Table([[c] for c in couv_data[0]], colWidths=[16.5 * cm])
    couv_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLEU_FONCE),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(couv_t)
    story.append(Spacer(1, 0.8 * cm))

    story.append(info_box(
        "📋  Ce guide accompagne le professionnel chargé du Diagnostic PEMD dans le remplissage du "
        "Tableau 1 du CERFA. Il est conçu pour être compréhensible même sans expertise préalable.",
        s,
    ))
    story.append(Spacer(1, 0.6 * cm))

    # ── SECTION 1 : INTRODUCTION ──────────────────────────────
    story.append(section_title("1", "Introduction — Qu'est-ce que le PEMD ?", s))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        "Le <b>Diagnostic PEMD</b> (Produits, Équipements, Matériaux et Déchets) est un document "
        "réglementaire obligatoire en France avant toute démolition ou rénovation significative d'un "
        "bâtiment. Il est encadré par le décret n°2021-822 du 25 juin 2021.",
        s["body"],
    ))
    story.append(Paragraph(
        "Son objectif principal est d'<b>identifier et quantifier les éléments réemployables</b> "
        "avant qu'ils ne soient détruits, afin de favoriser l'économie circulaire dans le secteur "
        "de la construction.",
        s["body"],
    ))

    story.append(Paragraph("Le PEMD est obligatoire lorsque :", s["h2"]))
    obligations = [
        ("Démolition", "Surface de plancher > 1 000 m² ou immeuble classé"),
        ("Rénovation", "Coût des travaux > 1 M€ HT ou surface > 1 000 m²"),
        ("Démolition partielle", "Dès que plus de 50 % de la structure est affectée"),
    ]
    for titre, detail in obligations:
        story.append(Paragraph(f"• <b>{titre} :</b> {detail}", s["bullet"]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Le Tableau 1 concerne exclusivement :", s["h2"]))
    story.append(info_box(
        "🔄  Les produits et matériaux <b>potentiellement réemployables</b>, c'est-à-dire ceux qui "
        "peuvent être déposés intact et réutilisés dans un autre bâtiment ou projet.",
        s,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ── SECTION 2 : CATÉGORIES ────────────────────────────────
    story.append(PageBreak())
    story.append(section_title("2", "Les catégories du PEMD (Tableau 1)", s))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Le CERFA PEMD organise les éléments en <b>grandes familles</b>. Voici les principales "
        "catégories concernant le réemploi :",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    categories = [
        ("1",  "Terres et pierres naturelles",        "Pierre calcaire de façade (mur porteur)", GRIS_CLAIR),
        ("2",  "Produits minéraux et matériaux",       "Brique pleine ancienne (cloison)", BLANC),
        ("3",  "Éléments de structure",                "Poutres en bois de chêne (plancher)", GRIS_CLAIR),
        ("4",  "Éléments de façade",                   "Bardage bois en bon état", BLANC),
        ("5",  "Aménagements intérieurs",               "Cloison amovible aluminium-verre", GRIS_CLAIR),
        ("6",  "Menuiseries extérieures & intérieures","Porte intérieure en chêne massif 204×83 cm", BLANC),
        ("7",  "Équipements techniques",               "Radiateur fonte, tableau électrique modulaire", GRIS_CLAIR),
        ("8",  "Mobilier & équipements fixes",         "Rayonnages métalliques, sanitaires", BLANC),
    ]

    cat_data = [[
        Paragraph("<b>Catégorie</b>", s["table_header"]),
        Paragraph("<b>Libellé</b>", s["table_header"]),
        Paragraph("<b>Exemple d'élément réemployable</b>", s["table_header"]),
    ]]
    for num, lib, ex, bg in categories:
        cat_data.append([
            Paragraph(f"<b>{num}</b>", ParagraphStyle("CatNum", fontSize=9, fontName="Helvetica-Bold",
                                                        textColor=BLEU_MOYEN, alignment=TA_CENTER)),
            Paragraph(lib, s["table_cell"]),
            Paragraph(ex, ParagraphStyle("ExCell", fontSize=7.5, fontName="Helvetica",
                                          textColor=VERT, leading=11)),
        ])

    cat_table = Table(cat_data, colWidths=[1.2 * cm, 6.8 * cm, 8.5 * cm], repeatRows=1)
    row_bgs = [BLANC] * len(cat_data)
    for i, (_, _, _, bg) in enumerate(categories, start=1):
        row_bgs[i] = bg

    cat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLEU_FONCE),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLANC),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        *[("BACKGROUND", (0, i), (-1, i), row_bgs[i]) for i in range(1, len(cat_data))],
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 0.4 * cm))
    story.append(warning_box(
        "⚠️  Un même bâtiment peut avoir des éléments dans plusieurs catégories. "
        "N'hésitez pas à créer une ligne par type d'élément distinct.",
        s,
    ))

    # ── SECTION 3 : COLONNES ─────────────────────────────────
    story.append(PageBreak())
    story.append(section_title("3", "Comment remplir chaque colonne du Tableau 1", s))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Le Tableau 1 comporte <b>9 colonnes</b>. Voici une explication détaillée de chacune :",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    colonnes = [
        (
            "A", "Catégorie",
            "Indiquer le numéro et le libellé de la catégorie PEMD correspondante (voir Section 2). "
            "En cas de doute entre deux catégories, choisissez la plus spécifique.",
            "Écrire : « 6 — Menuiseries » plutôt que « Produits divers ».",
        ),
        (
            "B", "Description / Désignation",
            "Décrire précisément l'élément : matériau principal, usage, emplacement dans le bâtiment. "
            "La description doit permettre à un tiers de l'identifier sans visite.",
            "Écrire : « Porte intérieure bois chêne massif, étage 2, RDC bureau » et non « porte ».",
        ),
        (
            "C", "Quantité réemployable",
            "Indiquer uniquement le nombre d'unités en bon état, pouvant être déposées et réutilisées. "
            "Ne pas confondre avec la quantité totale présente dans le bâtiment.",
            "Si 20 portes existent mais que 14 sont en bon état → indiquer 14.",
        ),
        (
            "D", "Unité",
            "Choisir l'unité adaptée à l'élément :\n"
            "• U (unité) → portes, fenêtres, radiateurs\n"
            "• m² → cloisons, bardages, planchers\n"
            "• ml (mètre linéaire) → poutres, rails\n"
            "• m³ → pierres, bois en volume",
            "Toujours préciser l'unité même si elle semble évidente.",
        ),
        (
            "E", "Dimensions",
            "Indiquer Hauteur × Largeur (× Profondeur si nécessaire) en centimètres ou millimètres. "
            "Pour les surfaces, indiquer les dimensions d'un élément type.",
            "Ex : H=204 cm × L=83 cm pour une porte standard. Mesurer sur site si possible.",
        ),
        (
            "F", "Matériaux",
            "Préciser le matériau principal de l'élément. Cela permet d'évaluer sa valeur de réemploi "
            "et son mode de traitement si non réemployé.",
            "Bois massif, acier galvanisé, aluminium laqué, PVC, verre feuilleté, fonte…",
        ),
        (
            "G", "État",
            "Évaluer l'état apparent de l'élément selon l'échelle :\n"
            "• Neuf → jamais utilisé ou usage très limité\n"
            "• Bon → fonctionnel, pas de défaut visible\n"
            "• Moyen → usure visible mais réparable\n"
            "• Mauvais → dégradé (ne pas inclure dans le tableau 1)",
            "Être honnête : surestimer l'état peut nuire à la crédibilité du diagnostic.",
        ),
        (
            "H", "Âge estimé",
            "Estimer l'année de pose ou l'âge de l'élément. Si inconnu, indiquer une fourchette "
            "(ex : 1980-1990). Consulter les permis de construire, plans ou DOE du bâtiment.",
            "Sources utiles : carnet d'entretien, factures, plans architecturaux, permis de construire.",
        ),
        (
            "I", "Type d'assemblage",
            "Indiquer comment l'élément est fixé à la structure :\n"
            "• Mécanique → vissé, boulonné, chevillé (dépose facile)\n"
            "• Chimique → collé, soudé, enduit (dépose difficile)\n"
            "• Mixte → combinaison des deux",
            "Un assemblage mécanique favorise le réemploi. Préciser si démontage spécialisé requis.",
        ),
    ]

    for num, nom, explication, conseil in colonnes:
        story.append(KeepTogether([
            colonne_card(num, nom, explication, conseil, s),
            Spacer(1, 0.25 * cm),
        ]))

    # ── SECTION 4 : EXEMPLE CONCRET ──────────────────────────
    story.append(PageBreak())
    story.append(section_title("4", "Exemple concret — Tableau rempli", s))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Voici un exemple de Tableau 1 rempli pour une rénovation de bureaux (bâtiment années 1980, "
        "2 étages, 800 m²) :",
        s["body"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    ex_headers = ["Cat.", "Description", "Qté", "Unité", "Dimensions", "Matériau", "État", "Âge", "Assemblage"]
    ex_rows = [
        ["6", "Porte intérieure, RDC + étage 1", "18", "U", "H204×L83 cm", "Chêne massif", "Bon", "~1985", "Mécanique"],
        ["6", "Fenêtre double vitrage, façade nord", "12", "U", "H120×L90 cm", "Aluminium laqué", "Moyen", "~2005", "Mécanique"],
        ["5", "Cloison amovible aluminium-verre", "45", "m²", "H280 cm", "Alu + Verre", "Bon", "~2010", "Mécanique"],
        ["7", "Radiateur acier, circuits indépendants", "24", "U", "H60×L80 cm", "Acier émaillé", "Bon", "~1985", "Mécanique"],
        ["3", "Poutre IPN acier, plancher R+1", "8", "ml", "Long. 6 m", "Acier S235", "Bon", "~1980", "Mécanique"],
    ]

    ex_data = [[Paragraph(h, s["table_header"]) for h in ex_headers]]
    for i, row in enumerate(ex_rows):
        bg = GRIS_CLAIR if i % 2 == 0 else BLANC
        ex_data.append([Paragraph(cell, s["table_cell"]) for cell in row])

    col_w = [0.7*cm, 4.5*cm, 0.8*cm, 1*cm, 2.2*cm, 2*cm, 1.2*cm, 1.2*cm, 2*cm]
    ex_table = Table(ex_data, colWidths=col_w, repeatRows=1)
    row_colors = [("BACKGROUND", (0, i+1), (-1, i+1), GRIS_CLAIR if i % 2 == 0 else BLANC)
                  for i in range(len(ex_rows))]
    ex_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLEU_FONCE),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLANC),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        *row_colors,
    ]))
    story.append(ex_table)
    story.append(Spacer(1, 0.4 * cm))
    story.append(info_box(
        "💡  Dans cet exemple, toutes les fixations sont mécaniques → facilité de dépose. "
        "Les éléments en mauvais état ont été exclus du tableau (ex : 6 portes abîmées non listées).",
        s,
    ))

    # ── SECTION 5 : CONSEILS ─────────────────────────────────
    story.append(PageBreak())
    story.append(section_title("5", "Conseils pratiques", s))
    story.append(Spacer(1, 0.3 * cm))

    conseils = [
        (
            "❌  Erreurs courantes à éviter",
            ROUGE_CLAIR,
            colors.HexColor("#dc2626"),
            [
                "Inclure des éléments en mauvais état dans le Tableau 1 (réservé au réemployable).",
                "Confondre la quantité totale et la quantité réemployable.",
                "Utiliser des descriptions vagues : « menuiseries » sans préciser le type.",
                "Oublier l'unité ou les dimensions (rendant l'offre de réemploi inexploitable).",
                "Ne pas distinguer les assemblages chimiques (difficiles à déposer).",
            ],
        ),
        (
            "❓  Données manquantes : que faire ?",
            ORANGE_CLAIR,
            ORANGE,
            [
                "Âge inconnu → écrire « inconnu » ou une estimation par décennie (ex : « 1990-2000 »).",
                "Matériau incertain → indiquer le matériau probable et ajouter « (à confirmer) ».",
                "Dimensions non mesurées → mentionner « dimensions standard » avec la norme si connue.",
                "État difficile à évaluer → se référer à un diagnostiqueur ou noter « à expertiser ».",
            ],
        ),
        (
            "🤔  Choisir entre plusieurs catégories",
            BLEU_CLAIR,
            BLEU_MOYEN,
            [
                "En cas de doute, préférez la catégorie la plus spécifique.",
                "Une porte-fenêtre → catégorie 6 (menuiseries) et non 4 (façades).",
                "Un système de plafond suspendu avec intégration lumineuse → catégorie 5 ou 7 selon la "
                "dominante (structure ou équipement).",
                "Consultez le guide officiel du Ministère ou l'annexe du CERFA si incertain.",
            ],
        ),
        (
            "✅  Bonnes pratiques générales",
            VERT_CLAIR,
            VERT,
            [
                "Effectuer la visite de terrain avec un appareil photo et un mètre laser.",
                "Regrouper les éléments similaires (mêmes dimensions, même état) sur une seule ligne.",
                "Coordonner avec le maître d'ouvrage pour accéder aux plans et DOE du bâtiment.",
                "Faire valider le tableau par un économiste de la construction ou un diagnostiqueur certifié.",
                "Transmettre le PEMD aux entreprises de démolition avant le démarrage des travaux.",
            ],
        ),
    ]

    for titre, bg, border, items in conseils:
        title_row = [[Paragraph(f"<b>{titre}</b>", ParagraphStyle(
            "ConseilTitle", fontSize=10, fontName="Helvetica-Bold",
            textColor=border,
        ))]]
        items_rows = [[Paragraph(f"• {item}", s["bullet"])] for item in items]

        all_rows = title_row + items_rows
        t = Table(all_rows, colWidths=[16.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BACKGROUND", (0, 0), (-1, 0), bg),
            ("LINEAFTER", (0, 0), (0, -1), 4, border),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ("TOPPADDING", (0, 1), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 1), (-1, -2), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(KeepTogether([t, Spacer(1, 0.3 * cm)]))

    # ── PIED DE PAGE FINAL ────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d1d5db")))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Guide basé sur le décret n°2021-822 du 25 juin 2021 — CERFA PEMD — Tableau 1 (Produits potentiellement réemployables) | "
        "Document à usage pédagogique, non substitut à un diagnostic officiel.",
        s["footer"],
    ))

    doc.build(story)
    print(f"✅  PDF généré : {filename}")


if __name__ == "__main__":
    build_document("guide_pemd_tableau1.pdf")
