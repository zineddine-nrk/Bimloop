"""
Génération du CSV « Déchets inertes (DI) » selon le formulaire CERFA PEMD.

Périmètre :
- On ne compte QUE les éléments dont le matériau correspond à l'une des
  10 catégories DI réglementaires (béton, briques, tuiles, verre, etc.).
- On ne compte QUE les éléments dont le statut tracker est « à recycler »
  ou « à réutiliser » (les autres ne partent pas en DI).

Colonnes remplies :
  - Catégorie
  - Quantité estimée → Masse (tonnes), Volume (m³, optionnel)
  - % Réutilisation
  - % Recyclable
Toutes les autres colonnes sont laissées vides (non déductibles depuis l'IFC).
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

from tracker import get_all_components, get_project_ifc, get_project


# ============================================================
# CATÉGORIES DI (ordre + libellés du CERFA)
# ============================================================
# Chaque catégorie a :
#   - "label"    : libellé exact du formulaire
#   - "keywords" : mots-clés cherchés dans le matériau (lowercase, accents tolérés)
#   - "density"  : kg/m³ par défaut (utilisé si le volume IFC est connu)

DI_CATEGORIES: List[Dict] = [
    {
        "label": "Béton",
        "keywords": ["béton", "beton", "concrete"],
        "density": 2400,
    },
    {
        "label": "Briques",
        "keywords": ["brique", "brick"],
        "density": 1800,
    },
    {
        "label": "Tuiles et céramiques",
        "keywords": ["tuile", "céramique", "ceramique", "ceramic", "carrelage", "faïence", "faience"],
        "density": 2000,
    },
    {
        "label": "Mélanges de béton, tuiles et céramique ne contenant pas de substances dangereuses",
        "keywords": [],  # non auto-détectable de façon fiable
        "density": 2200,
    },
    {
        "label": "Verre (sans cadre ou montant de fenêtres)",
        "keywords": ["verre", "glass"],
        "density": 2500,
    },
    {
        "label": "Mélange bitumineux ne contenant pas de goudron",
        "keywords": ["bitume", "bitumen", "asphalte", "asphalt", "enrobé", "enrobe"],
        "density": 2300,
    },
    {
        "label": "Terres et cailloux ne contenant pas de substance dangereuse",
        "keywords": ["cailloux", "gravier", "gravel"],
        "density": 1800,
    },
    {
        "label": "Terres et pierres",
        "keywords": ["terre", "pierre", "stone", "soil"],
        "density": 1700,
    },
    {
        "label": "Déchets de matériaux à base de fibre et de verre",
        "keywords": ["laine de verre", "fibre de verre", "glass wool", "fiberglass"],
        "density": 100,
    },
    {
        "label": "Emballage en verre",
        "keywords": ["emballage verre", "glass packaging"],
        "density": 2500,
    },
]

CSV_HEADERS = [
    "Catégorie",
    "Code déchet",
    "Masse estimée (tonnes)",
    "Volume estimé (m³)",
    "Filières et exutoires identifiés",
    "% Réutilisation (sur site ou hors site)",
    "% Recyclable",
    "% Remblayage / comblement de carrière",
    "% Incinération avec valorisation énergétique",
    "% Incinération sans valorisation énergétique",
    "% Non valorisable, à enfouir",
    "Conditions techniques identifiées",
]


# ============================================================
# HELPERS
# ============================================================

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _classify(material: str) -> Optional[int]:
    """Retourne l'index de la catégorie DI correspondant au matériau, ou None.

    On évite les faux positifs en testant les libellés les plus spécifiques
    avant les plus génériques (ex. 'laine de verre' avant 'verre').
    """
    m = _norm(material)
    if not m:
        return None
    # Spécifiques d'abord (laine/fibre de verre, emballage verre)
    priority_order = [8, 9, 5, 6, 7, 2, 1, 0, 4]  # indices dans DI_CATEGORIES
    for i in priority_order:
        for kw in DI_CATEGORIES[i]["keywords"]:
            if kw in m:
                return i
    return None


def _safe_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _compute_volume(ifc_data: Dict) -> Optional[float]:
    """Volume en m³ : net_volume direct si dispo, sinon h*l*e (toutes en m)."""
    nv = _safe_float(ifc_data.get("net_volume"))
    if nv:
        return nv
    h = _safe_float(ifc_data.get("hauteur"))
    l = _safe_float(ifc_data.get("longueur"))
    e = _safe_float(ifc_data.get("epaisseur"))
    if h and l and e:
        return h * l * e
    # Dernier recours : surface nette × épaisseur (cas des dalles sans h/l)
    na = _safe_float(ifc_data.get("net_area"))
    if na and e:
        return na * e
    return None


def _ifc_id_from_stored(stored_id: str) -> str:
    if "__p" in stored_id:
        return stored_id.split("__p")[0]
    return stored_id


def _fmt(v: float, decimals: int = 2) -> str:
    if v is None:
        return ""
    return f"{round(v, decimals):.{decimals}f}".rstrip("0").rstrip(".") or "0"


# ============================================================
# GÉNÉRATION CSV
# ============================================================

def generate_di_csv(project_id: int) -> bytes:
    """Construit le CSV DI pour un projet. Retourne des bytes UTF-8 BOM."""
    if get_project(project_id) is None:
        raise ValueError(f"Projet {project_id} introuvable.")

    # 1) On prend TOUS les composants du projet (le total par catégorie sert de
    #    base au calcul des pourcentages). Le statut détermine seulement la part
    #    qui ira en réutilisation ou en recyclage.
    all_comps = get_all_components(project_id=project_id)

    # 2) Enrichissement IFC pour les volumes (obligatoire pour avoir masse/volume)
    ifc_info = get_project_ifc(project_id)
    ifc_index: Dict[str, Dict] = {}
    if ifc_info:
        try:
            from ifc_parser import parse_ifc_file
            data = parse_ifc_file(ifc_info["path"])
            elements = data.get("elements", []) if isinstance(data, dict) else data
            for el in elements:
                gid = el.get("id")
                if gid:
                    ifc_index[gid] = el
            print(f"[DI CSV] Projet {project_id} : IFC source chargé "
                  f"({len(ifc_index)} éléments indexés depuis {ifc_info.get('filename')}).")
        except Exception as e:
            import traceback
            print(f"[DI CSV] ÉCHEC parsing IFC source : {e}\n{traceback.format_exc()}")
            ifc_index = {}
    else:
        print(f"[DI CSV] Projet {project_id} : AUCUN IFC source uploadé "
              f"→ masse/volume impossibles à calculer.")

    # 3) Agrégation par catégorie DI.
    # Pour CHAQUE composant matchant une catégorie inerte, on accumule :
    #   - n_total  / vol_total  / mass_total   → base de référence de la catégorie
    #   - n_reuse  / vol_reuse  / mass_reuse   → part « à réutiliser »
    #   - n_recyc  / vol_recyc  / mass_recyc   → part « à recycler »
    # Les pourcentages s'appuient en priorité sur la masse, puis le volume,
    # puis le nombre d'éléments (selon ce qui est disponible).
    per_cat: Dict[int, Dict[str, float]] = defaultdict(
        lambda: {
            "n_total": 0,    "vol_total": 0.0,  "mass_total": 0.0,
            "n_reuse": 0,    "vol_reuse": 0.0,  "mass_reuse": 0.0,
            "n_recyc": 0,    "vol_recyc": 0.0,  "mass_recyc": 0.0,
        }
    )

    n_matched = 0
    n_with_vol = 0
    for comp in all_comps:
        cat_idx = _classify(comp.get("material") or "")
        if cat_idx is None:
            continue  # matériau non inerte → on l'ignore complètement
        n_matched += 1
        # Source des dimensions : priorité aux valeurs stockées en DB lors de
        # l'import (toujours dispo si l'import a inclus les dimensions),
        # sinon repli sur l'IFC source uploadé.
        ifc_data = ifc_index.get(_ifc_id_from_stored(comp.get("id", "")), {})
        merged = {
            "hauteur":    comp.get("hauteur")    or ifc_data.get("hauteur"),
            "longueur":   comp.get("longueur")   or ifc_data.get("longueur"),
            "epaisseur":  comp.get("epaisseur")  or ifc_data.get("epaisseur"),
            "net_area":   comp.get("net_area")   or ifc_data.get("net_area"),
            "net_volume": comp.get("net_volume") or ifc_data.get("net_volume"),
        }
        vol = _compute_volume(merged) or 0.0
        if vol > 0:
            n_with_vol += 1
        density = DI_CATEGORIES[cat_idx]["density"]
        mass_t = (vol * density) / 1000.0  # kg → tonnes

        bucket = per_cat[cat_idx]
        bucket["n_total"]    += 1
        bucket["vol_total"]  += vol
        bucket["mass_total"] += mass_t

        status = (comp.get("status") or "").strip().lower()
        if status == "à réutiliser":
            bucket["n_reuse"]    += 1
            bucket["vol_reuse"]  += vol
            bucket["mass_reuse"] += mass_t
        elif status == "à recycler":
            bucket["n_recyc"]    += 1
            bucket["vol_recyc"]  += vol
            bucket["mass_recyc"] += mass_t
        # Les autres statuts (in_building, démonté, stocké…) restent dans le
        # total mais ne comptent ni en réutilisation ni en recyclage.

    # Récap par catégorie : utile pour diagnostiquer si les statuts sont bien pris
    total_reuse = sum(b["n_reuse"] for b in per_cat.values())
    total_recyc = sum(b["n_recyc"] for b in per_cat.values())
    print(f"[DI CSV] Projet {project_id} : {len(all_comps)} composants total, "
          f"{n_matched} matchent une catégorie DI, {n_with_vol} ont un volume calculable. "
          f"Statuts marqués : {total_reuse} à réutiliser, {total_recyc} à recycler.")

    # 4) Écriture CSV : on liste TOUTES les catégories DI (lignes vides si rien)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_HEADERS)

    for idx, cat in enumerate(DI_CATEGORIES):
        agg = per_cat.get(idx)
        if agg and agg["n_total"] > 0:
            # Masse / Volume affichés = total de la catégorie (tous les composants).
            mass_str = _fmt(agg["mass_total"], 3) if agg["mass_total"] > 0 else ""
            vol_str  = _fmt(agg["vol_total"],  2) if agg["vol_total"]  > 0 else ""

            # Pourcentages : part de chaque destination par rapport au TOTAL de
            # la catégorie. Exemple : 10 000 t de béton total et seulement 5 t
            # marquées « à réutiliser » → % Réutilisation = 0,05 %, pas 100 %.
            # Les éléments non marqués (in_building, démonté…) restent au
            # dénominateur car ils représentent une masse non encore valorisée.
            if agg["mass_total"] > 0:
                pct_reuse = agg["mass_reuse"] / agg["mass_total"] * 100
                pct_recyc = agg["mass_recyc"] / agg["mass_total"] * 100
            elif agg["vol_total"] > 0:
                pct_reuse = agg["vol_reuse"] / agg["vol_total"] * 100
                pct_recyc = agg["vol_recyc"] / agg["vol_total"] * 100
            else:
                pct_reuse = agg["n_reuse"] / agg["n_total"] * 100
                pct_recyc = agg["n_recyc"] / agg["n_total"] * 100

            pct_reuse_str = f"{pct_reuse:.2f} %"
            pct_recyc_str = f"{pct_recyc:.2f} %"
        else:
            mass_str = vol_str = pct_reuse_str = pct_recyc_str = ""

        writer.writerow([
            cat["label"],     # Catégorie
            "",               # Code déchet ← non déductible
            mass_str,         # Masse estimée (tonnes)
            vol_str,          # Volume estimé (m³)
            "",               # Filières et exutoires ← case à cocher humaine
            pct_reuse_str,    # % Réutilisation
            pct_recyc_str,    # % Recyclable
            "",               # % Remblayage          ← non déductible
            "",               # % Incin. avec valo    ← non déductible
            "",               # % Incin. sans valo    ← non déductible
            "",               # % Non valorisable     ← non déductible
            "",               # Conditions techniques ← humaine
        ])

    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
