"""
Pipeline de validation — orchestre le parsing, la validation, le scoring et le rapport.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from .rules import RULES
from .compliance import ComplianceChecker
from .scorer import QualityScorer
from .report_generator import to_json, to_pdf

# Types IFC à valider (dans l'ordre de priorité)
VALIDATION_TYPES = ["IfcDoor", "IfcWindow", "IfcWall", "IfcBeam", "IfcSlab", "IfcStair", "IfcCurtainWall"]


class ValidationPipeline:
    """Pipeline complet de validation de maquette IFC."""

    def __init__(self):
        self.rules = RULES
        self.checker = ComplianceChecker(RULES)
        self.scorer = QualityScorer()

    @staticmethod
    def _is_sub_element(element) -> bool:
        """Vérifie si un élément est un sous-élément décomposé d'un autre type
        (ex: palier d'escalier modélisé comme IfcSlab décomposé par IfcStair)."""
        try:
            for rel in (getattr(element, "Decomposes", None) or []):
                parent = getattr(rel, "RelatingObject", None)
                if parent and not parent.is_a(element.is_a()):
                    return True
        except Exception:
            pass
        return False

    def execute(self, ifc_file_path: str, project_name: str = "") -> dict:
        """Exécute le pipeline complet sur un fichier IFC.
        Retourne le rapport complet (dict)."""
        import ifcopenshell
        model = ifcopenshell.open(ifc_file_path)

        results = []
        for entity_type in VALIDATION_TYPES:
            if entity_type not in self.rules:
                continue
            try:
                entities = model.by_type(entity_type)
            except Exception:
                entities = []

            for entity in entities:
                # Exclure les sous-éléments décomposés d'un autre type
                if self._is_sub_element(entity):
                    continue
                try:
                    result = self.checker.validate(entity, entity_type)
                    results.append(result)
                except Exception:
                    pass

        report = self.scorer.compute(results)
        report["project"] = project_name
        report["timestamp"] = datetime.now().isoformat()
        report["ifc_file"] = ifc_file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

        # Ajouter les grades par type dans per_type
        for t, v in report.get("per_type", {}).items():
            v["grade"] = self.checker._grade(v["score"])

        return report

    def to_json(self, report: dict) -> str:
        return to_json(report)

    def to_pdf(self, report: dict, project_name: str = "") -> bytes:
        return to_pdf(report, project_name)
