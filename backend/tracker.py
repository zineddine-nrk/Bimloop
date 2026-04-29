"""
Module de tracking des composants IFC.
Base de données SQLite avec historique des changements de statut.
"""

import sqlite3
import io
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

import qrcode
from qrcode.image.pure import PyPNGImage

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, "tracker.db")

# Statuts valides et leur ordre logique
STATUTS_VALIDES = ["in_building", "démonté", "transporté", "stocké", "réutilisé"]


# ============================================================
# INITIALISATION DB
# ============================================================

def init_db():
    """Crée les tables si elles n'existent pas."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS components (
                id          TEXT PRIMARY KEY,
                type        TEXT,
                material    TEXT,
                ifc_location TEXT,
                status      TEXT DEFAULT 'in_building',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id TEXT NOT NULL,
                old_status  TEXT,
                new_status  TEXT NOT NULL,
                note        TEXT,
                changed_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (component_id) REFERENCES components(id)
            )
        """)
        conn.commit()


# ============================================================
# IMPORT DEPUIS JSON IFC
# ============================================================

def import_components(components: List[Dict]) -> Dict[str, int]:
    """
    Importe une liste de composants depuis l'export JSON IFC.
    Ignore les composants déjà présents (upsert sur id).
    Retourne le nombre de créés / mis à jour.
    """
    init_db()
    created, updated = 0, 0
    with sqlite3.connect(DB_PATH) as conn:
        for c in components:
            cid = c.get("id")
            if not cid:
                continue
            existing = conn.execute(
                "SELECT id FROM components WHERE id = ?", (cid,)
            ).fetchone()
            if existing:
                conn.execute("""
                    UPDATE components
                    SET type=?, material=?, ifc_location=?, updated_at=datetime('now')
                    WHERE id=?
                """, (c.get("type"), c.get("material"), c.get("ifc_location"), cid))
                updated += 1
            else:
                conn.execute("""
                    INSERT INTO components (id, type, material, ifc_location, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    cid, c.get("type"), c.get("material"),
                    c.get("ifc_location"), c.get("status", "in_building"),
                ))
                # Enregistrer le statut initial dans l'historique
                conn.execute("""
                    INSERT INTO status_history (component_id, old_status, new_status, note)
                    VALUES (?, NULL, ?, 'Import initial IFC')
                """, (cid, c.get("status", "in_building")))
                created += 1
        conn.commit()
    return {"created": created, "updated": updated}


# ============================================================
# LECTURE
# ============================================================

def _row_to_dict(row, cursor) -> Dict:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def get_all_components(status_filter: Optional[str] = None,
                       type_filter: Optional[str] = None) -> List[Dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        query = "SELECT * FROM components WHERE 1=1"
        params = []
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        if type_filter:
            query += " AND type = ?"
            params.append(type_filter)
        query += " ORDER BY updated_at DESC"
        cur = conn.execute(query, params)
        return [_row_to_dict(r, cur) for r in cur.fetchall()]


def get_component(component_id: str) -> Optional[Dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT * FROM components WHERE id = ?", (component_id,))
        row = cur.fetchone()
        if not row:
            return None
        comp = _row_to_dict(row, cur)
        # Charger l'historique
        cur2 = conn.execute("""
            SELECT * FROM status_history
            WHERE component_id = ?
            ORDER BY changed_at DESC
        """, (component_id,))
        comp["history"] = [_row_to_dict(r, cur2) for r in cur2.fetchall()]
        return comp


# ============================================================
# CHANGEMENT DE STATUT
# ============================================================

def update_status(component_id: str, new_status: str,
                  note: Optional[str] = None) -> Dict[str, Any]:
    """Met à jour le statut d'un composant et enregistre l'historique."""
    if new_status not in STATUTS_VALIDES:
        raise ValueError(f"Statut invalide : {new_status}. Valeurs : {STATUTS_VALIDES}")

    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT status FROM components WHERE id = ?", (component_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Composant introuvable : {component_id}")

        old_status = row[0]
        conn.execute("""
            UPDATE components SET status = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (new_status, component_id))
        conn.execute("""
            INSERT INTO status_history (component_id, old_status, new_status, note)
            VALUES (?, ?, ?, ?)
        """, (component_id, old_status, new_status, note))
        conn.commit()

    return {"id": component_id, "old_status": old_status, "new_status": new_status}


# ============================================================
# QR CODE
# ============================================================

def generate_qr_png(component_id: str, base_url: str) -> bytes:
    """Génère un QR code PNG pointant vers /tracker/{component_id}."""
    url = f"{base_url}/tracker/{component_id}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================
# STATS
# ============================================================

def get_stats() -> Dict:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
        by_status = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) FROM components GROUP BY status"
        ).fetchall():
            by_status[row[0]] = row[1]
        by_type = {}
        for row in conn.execute(
            "SELECT type, COUNT(*) FROM components GROUP BY type"
        ).fetchall():
            by_type[row[0]] = row[1]
    return {"total": total, "by_status": by_status, "by_type": by_type}
