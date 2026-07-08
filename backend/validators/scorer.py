"""
Scorer — calcule les scores de qualité par type et globaux.
"""
from __future__ import annotations

from typing import List, Dict


class QualityScorer:
    @staticmethod
    def compute(results: List[dict]) -> dict:
        if not results:
            return {
                "total_elements": 0, "elements_validated": 0,
                "global_score": 0, "grade": "-",
                "blocking_count": 0, "warning_count": 0,
                "per_type": {}, "elements": [],
            }
        total = len(results)
        global_score = round(sum(r["score"] for r in results) / total, 1)
        blocking = sum(1 for r in results if r["blocking"])
        warnings = sum(r["warnings"] for r in results)
        per_type = {}
        for r in results:
            t = r["type"]
            if t not in per_type:
                per_type[t] = {"total": 0, "score_sum": 0, "blocking": 0, "warnings": 0}
            per_type[t]["total"] += 1
            per_type[t]["score_sum"] += r["score"]
            if r["blocking"]:
                per_type[t]["blocking"] += 1
            per_type[t]["warnings"] += r["warnings"]
        for t, v in per_type.items():
            v["score"] = round(v["score_sum"] / v["total"], 1)
            del v["score_sum"]
        return {
            "total_elements": total, "elements_validated": total,
            "global_score": global_score,
            "grade": QualityScorer._grade(global_score),
            "blocking_count": blocking, "warning_count": warnings,
            "per_type": per_type, "elements": results,
        }

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90: return "A"
        if score >= 70: return "B"
        if score >= 50: return "C"
        return "D"
