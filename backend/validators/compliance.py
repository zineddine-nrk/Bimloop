"""
Moteur de conformité — vérifie chaque élément IFC contre les règles de validation.
"""
from __future__ import annotations

from typing import Dict, List

import ifcopenshell
import ifcopenshell.util.element

from extractors.common import extract_material

from .rules import Rule


class ComplianceChecker:
    def __init__(self, rules: Dict[str, List[Rule]]):
        self.rules = rules

    def validate(self, entity, entity_type: str) -> dict:
        rules = self.rules.get(entity_type, [])
        checks = []
        for rule in rules:
            result = self._check_rule(entity, rule, entity_type)
            checks.append(result)
        return self._build_result(entity, entity_type, checks)

    def _check_rule(self, entity, rule: Rule, entity_type: str) -> dict:
        source = rule.source
        if source == "attribute":
            value = self._get_attribute(entity, rule.attribute)
        elif source == "pset":
            value = self._get_property(entity, rule.pset_name, rule.attribute)
        elif source == "qto":
            value = self._get_quantity(entity, rule.qto_name, rule.attribute)
        elif source == "material":
            value = self._get_material(entity)
        elif source == "location":
            value = self._get_location(entity)
        else:
            value = None
        passed, detail = self._evaluate(value, rule)
        return {
            "rule": rule.name, "description": rule.description,
            "attribute": rule.attribute, "source": source,
            "priority": rule.priority, "pset": rule.pset_name,
            "passed": passed, "detail": detail, "value": self._fmt_value(value),
        }

    def _get_attribute(self, entity, name: str):
        try: return getattr(entity, name, None)
        except: return None

    def _get_property(self, entity, pset_name: str, prop_name: str):
        try:
            for rel in getattr(entity, "IsDefinedBy", []) or []:
                if hasattr(rel, "RelatingPropertyDefinition"):
                    pset = rel.RelatingPropertyDefinition
                    if getattr(pset, "Name", "") == pset_name:
                        return self._find_in_props(pset, prop_name)
        except: pass
        try:
            for rel in entity.IsDefinedBy_inverse:
                pset = rel.RelatingPropertyDefinition
                if hasattr(pset, "Name") and pset.Name == pset_name:
                    return self._find_in_props(pset, prop_name)
        except: pass
        return None

    def _find_in_props(self, pset, name):
        if hasattr(pset, "HasProperties"):
            for p in pset.HasProperties:
                if getattr(p, "Name", "") == name:
                    return getattr(p, "NominalValue", None)
        try:
            for p in pset.HasProperties_inverse:
                if hasattr(p, "Name") and p.Name == name:
                    return p.NominalValue.wrappedValue if hasattr(p.NominalValue, "wrappedValue") else p.NominalValue
        except: pass
        return None

    def _get_quantity(self, entity, qto_name: str, qty_name: str):
        # 1) Recherche stricte dans le Qto attendu
        value = self._get_quantity_strict(entity, qto_name, qty_name)
        if value is not None:
            return value

        # 2) Fallback souple : parcours tous les quantity sets (noms en anglais/français,
        #    insensible à la casse) pour les fichiers qui ne respectent pas le qto standard.
        try:
            qsets = ifcopenshell.util.element.get_psets(entity, qtos_only=True)
            return self._find_quantity_flexible(qsets, qty_name)
        except Exception:
            pass
        return None

    def _get_quantity_strict(self, entity, qto_name: str, qty_name: str):
        try:
            for rel in getattr(entity, "IsDefinedBy", []) or []:
                qto = getattr(rel, "RelatingPropertyDefinition", None)
                if qto and getattr(qto, "Name", "") == qto_name:
                    return self._find_in_qty(qto, qty_name)
        except: pass
        try:
            for rel in entity.IsDefinedBy_inverse:
                qto = rel.RelatingPropertyDefinition
                if hasattr(qto, "Name") and qto.Name == qto_name:
                    return self._find_in_qty(qto, qty_name)
        except: pass
        return None

    def _quantity_aliases(self, qty_name: str):
        """Retourne les variantes de nom possibles pour une quantité (insensible à la casse)."""
        aliases = {qty_name.lower()}
        mapping = {
            "height": ["height", "hauteur"],
            "length": ["length", "longueur", "largeur"],
            "width": ["width", "largeur", "epaisseur", "thickness"],
            "thickness": ["thickness", "epaisseur", "width"],
        }
        for key, values in mapping.items():
            if qty_name.lower() in values:
                aliases.update(v.lower() for v in values)
        return aliases

    def _find_quantity_flexible(self, qsets, qty_name: str):
        if not isinstance(qsets, dict):
            return None
        aliases = self._quantity_aliases(qty_name)
        for qset_name, qset_data in qsets.items():
            if not isinstance(qset_data, dict):
                continue
            for key, value in qset_data.items():
                if key.lower() in aliases:
                    return value
        return None

    def _find_in_qty(self, qto, name):
        if hasattr(qto, "Quantities"):
            for q in qto.Quantities:
                if getattr(q, "Name", "") == name:
                    return getattr(q, "LengthValue", None) or getattr(q, "AreaValue", None) or getattr(q, "VolumeValue", None)
        try:
            for q in qto.Quantities_inverse:
                if hasattr(q, "Name") and q.Name == name:
                    return q.quantity.wrappedValue if hasattr(q.quantity, "wrappedValue") else q.quantity
        except: pass
        return None

    def _get_material(self, entity):
        """Utilise l'extracteur de matériau partagé pour gérer tous les cas
        (matériau simple, layer sets, constituent sets, profile sets, propriétés).
        Si l'élément parent n'a pas de matériau, remonte aux sous-éléments
        (utile pour les murs rideaux, escaliers, etc.).
        Retourne None si aucun matériau n'est trouvé pour marquer la règle en échec."""
        material = extract_material(entity)
        if material and material != "Inconnu":
            return material

        # Fallback : chercher dans les sous-éléments décomposés
        try:
            sub_materials = []
            for rel in getattr(entity, "IsDecomposedBy", []) or []:
                for sub in getattr(rel, "RelatedObjects", []) or []:
                    sub_mat = extract_material(sub)
                    if sub_mat and sub_mat != "Inconnu":
                        sub_materials.append(sub_mat)
            if sub_materials:
                # Retourne les matériaux uniques, ordonnés et sans doublon
                return ", ".join(sorted(set(sub_materials)))
        except Exception:
            pass

        return None

    def _get_location(self, entity):
        try:
            for rel in getattr(entity, "ContainedInStructure", []) or []:
                s = rel.RelatingStructure
                if s: return getattr(s, "Name", "")
        except: pass
        try:
            for rel in entity.ContainedInStructure_inverse:
                if hasattr(rel, "RelatingStructure"):
                    return getattr(rel.RelatingStructure, "Name", "")
        except: pass
        return None

    def _evaluate(self, value, rule: Rule) -> tuple:
        if value is None:
            return False, "Attribut absent"
        if hasattr(value, "wrappedValue"):
            value = value.wrappedValue
        if rule.check_not_empty:
            if isinstance(value, str) and not value.strip():
                return False, "Valeur vide"
        if rule.check_positive:
            try:
                if float(value) <= 0:
                    return False, f"Valeur non positive: {value}"
            except: return False, f"Valeur non numérique: {value}"
        return True, "OK"

    def _fmt_value(self, value) -> str:
        if value is None: return ""
        if hasattr(value, "wrappedValue"): value = value.wrappedValue
        try: return f"{float(value):.1f}".rstrip("0").rstrip(".")
        except: return str(value)[:50]

    def _build_result(self, entity, entity_type: str, checks: List[dict]) -> dict:
        total = len(checks)
        passed = sum(1 for c in checks if c["passed"])
        blocking = any(not c["passed"] and c["priority"] == "C" for c in checks)
        warnings = sum(1 for c in checks if not c["passed"] and c["priority"] == "O")
        score = round(passed / total * 100, 1) if total > 0 else 100
        return {
            "element_id": getattr(entity, "GlobalId", "?"),
            "type": entity_type,
            "name": getattr(entity, "Name", ""),
            "checks": checks,
            "total_checks": total,
            "passed_checks": passed,
            "score": score,
            "grade": self._grade(score),
            "blocking": blocking,
            "warnings": warnings,
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90: return "A"
        if score >= 70: return "B"
        if score >= 50: return "C"
        return "D"
