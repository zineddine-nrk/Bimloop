"""
Serveur FastAPI principal pour l'analyse de fichiers IFC.
Gère l'upload, le traitement et le renvoi des résultats.
"""

import os
import shutil
import tempfile
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ifc_parser import parse_ifc_file
from utils import enrichir_elements, calculer_resume
from table_pdf import generate_table_pdf
from tracker import (
    init_db, import_components, get_all_components,
    get_component, update_status, generate_qr_png, get_stats,
    get_statuses_by_ids, STATUTS_VALIDES,
    list_projects, create_project, get_project, delete_project,
    update_component_meta, CONDITIONS_VALIDES, AGES_VALIDES,
    set_project_ifc, get_project_ifc,
    project_belongs_to_user, component_belongs_to_user,
)
from ifc_exporter import export_ifc_with_statuses
from reuse_csv import generate_reuse_csv
from di_csv import generate_di_csv
from btp_match_pdf import generate_btp_match_pdf
from extraction_pemd_pdf import generate_extraction_pemd_pdf, generate_extraction_pemd_csv
from auth_db import init_auth_db
from auth_routes import auth_router
from auth_security import get_current_user


# Initialisation de l'application FastAPI
app = FastAPI(
    title="IFC Analyzer - Analyse de durabilité",
    description="Application d'analyse de fichiers IFC pour la durabilité",
    version="1.0.0",
)

protected_api = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])

# Configuration CORS pour permettre les requêtes du frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_auth():
    init_auth_db()

# Dossier pour les fichiers uploadés
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "ifc_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Chemin vers le dossier frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


# Servir les fichiers statiques du frontend
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_frontend():
    """Sert la page d'accueil du frontend."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/login")
async def login_page():
    """Sert la page de connexion."""
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


@protected_api.post("/upload")
async def upload_ifc(file: UploadFile = File(...)):
    """
    Endpoint pour uploader et analyser un fichier IFC.
    
    Args:
        file: Fichier IFC uploadé
        
    Returns:
        Résultats de l'analyse (éléments, résumé, messages)
    """
    # Vérifier l'extension du fichier
    if not file.filename.lower().endswith(".ifc"):
        raise HTTPException(
            status_code=400,
            detail="Format de fichier invalide. Veuillez charger un fichier .ifc"
        )

    # Sauvegarder le fichier temporairement
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la sauvegarde du fichier : {str(e)}"
        )

    # Parser le fichier IFC
    try:
        result = parse_ifc_file(file_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'analyse du fichier IFC : {str(e)}"
        )
    finally:
        # Nettoyer le fichier temporaire
        if os.path.exists(file_path):
            os.remove(file_path)

    # Enrichir les éléments avec volume, recyclabilité, réutilisabilité
    elements = enrichir_elements(result["elements"])

    # Calculer le résumé global
    resume = calculer_resume(elements)

    return {
        "success": True,
        "message": f"Fichier « {file.filename} » chargé et analysé avec succès",
        "elements": elements,
        "resume": resume,
        "avertissements": result["messages"],
    }


# ============================================================
# EXPORT TABLE PDF — générique
# ============================================================

class TablePdfRequest(BaseModel):
    title: str
    headers: List[str]
    rows: List[List[str]]
    filename: Optional[str] = "export.pdf"


class ExtractionPemdRequest(BaseModel):
    elements: List[Dict[str, Any]]
    format: str = "pdf"
    project_label: Optional[str] = ""


@protected_api.post("/export-pemd-extraction")
async def export_pemd_extraction(req: ExtractionPemdRequest):
    """Export PEMD (PDF ou CSV) de tous les composants depuis la page Extraction."""
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        if req.format == "csv":
            content = generate_extraction_pemd_csv(req.elements)
            filename = f"pemd_extraction_{date_str}.csv"
            return Response(
                content=content,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        else:
            content = generate_extraction_pemd_pdf(req.elements, req.project_label or "")
            filename = f"pemd_extraction_{date_str}.pdf"
            return Response(
                content=content,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
    except Exception as e:
        import traceback
        print("[export-pemd-extraction] ERREUR :\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Erreur export PEMD : {type(e).__name__} — {e}")


@protected_api.post("/export-table-pdf")
async def export_table_pdf(req: TablePdfRequest):
    pdf_bytes = generate_table_pdf(req.title, req.headers, req.rows)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{req.filename}"'},
    )


# ============================================================
# TRACKER — Routes de suivi des composants IFC
# ============================================================

class ImportRequest(BaseModel):
    components: List[dict]
    project_name: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None

class BulkStatusUpdateRequest(BaseModel):
    ids: List[str]
    status: str
    note: Optional[str] = None

class MetaUpdateRequest(BaseModel):
    condition: Optional[str] = None
    comment: Optional[str] = None
    lifespan_months: Optional[int] = None
    age_estimated: Optional[str] = None

class BulkMetaUpdateRequest(BaseModel):
    ids: List[str]
    condition: Optional[str] = None
    age_estimated: Optional[str] = None
    comment: Optional[str] = None


def _verify_ownership(project_id: int, user_id: int):
    """Lève HTTP 404 si le projet n'existe pas ou n'appartient pas à l'utilisateur."""
    if not project_belongs_to_user(project_id, user_id):
        raise HTTPException(status_code=404, detail="Projet introuvable.")


def _verify_component_ownership(component_id: str, user_id: int):
    """Lève HTTP 404 si le composant n'existe pas ou n'appartient pas à l'utilisateur."""
    if not component_belongs_to_user(component_id, user_id):
        raise HTTPException(status_code=404, detail="Composant introuvable.")


class StatusesRequest(BaseModel):
    ids: List[str]
    project_id: Optional[int] = None


# ---- Projets ----
@protected_api.get("/tracker/projects")
async def tracker_projects(current_user=Depends(get_current_user)):
    """Liste de tous les projets (avec compte de composants)."""
    return list_projects(user_id=current_user.id)


@protected_api.delete("/tracker/projects/{project_id}")
async def tracker_delete_project(project_id: int, current_user=Depends(get_current_user)):
    """Supprime un projet, ses composants et leur historique."""
    _verify_ownership(project_id, current_user.id)
    return {"success": True, **delete_project(project_id)}


@protected_api.post("/tracker/projects/{project_id}/ifc")
async def tracker_upload_project_ifc(project_id: int, file: UploadFile = File(...), current_user=Depends(get_current_user)):
    """Stocke le fichier IFC d'origine d'un projet (à uploader une seule fois)."""
    _verify_ownership(project_id, current_user.id)
    if not file.filename.lower().endswith(".ifc"):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format .ifc")
    content = await file.read()
    info = set_project_ifc(project_id, file.filename, content)
    return {"success": True, **info}


@protected_api.get("/tracker/projects/{project_id}/ifc-info")
async def tracker_project_ifc_info(project_id: int, current_user=Depends(get_current_user)):
    """Indique si un IFC source est stocké pour ce projet."""
    _verify_ownership(project_id, current_user.id)
    info = get_project_ifc(project_id)
    return {"has_ifc": info is not None, "filename": info["filename"] if info else None}


def _build_export_filename(original: str) -> str:
    """Retourne '<base>_<YYYY-MM-DD>.ifc'.
    Strip tout suffixe '_YYYY-MM-DD' déjà présent (évite l'accumulation)."""
    import re
    from datetime import datetime
    base = original[:-4] if original.lower().endswith(".ifc") else original
    # Retire tous les '_YYYY-MM-DD' en fin de chaîne (un ou plusieurs)
    base = re.sub(r"(_\d{4}-\d{2}-\d{2})+$", "", base)
    return f"{base}_{datetime.now().strftime('%Y-%m-%d')}.ifc"


@protected_api.get("/tracker/projects/{project_id}/export-reuse-csv")
async def tracker_export_reuse_csv(project_id: int, current_user=Depends(get_current_user)):
    """Exporte un CSV de diagnostic réemploi pour les composants « à réutiliser »."""
    _verify_ownership(project_id, current_user.id)
    try:
        csv_bytes = generate_reuse_csv(project_id)
    except Exception as e:
        import traceback
        print("[export-reuse-csv] ERREUR :\n" + traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Échec de la génération CSV : {type(e).__name__} — {e}",
        )
    from datetime import datetime
    filename = f"diagnostic_reemploi_projet{project_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@protected_api.get("/tracker/projects/{project_id}/export-di-csv")
async def tracker_export_di_csv(project_id: int, current_user=Depends(get_current_user)):
    """Exporte un CSV « Déchets inertes » pour les composants à recycler / à réutiliser
    appartenant aux catégories DI réglementaires (béton, briques, verre, etc.)."""
    _verify_ownership(project_id, current_user.id)
    try:
        csv_bytes = generate_di_csv(project_id)
    except Exception as e:
        import traceback
        print("[export-di-csv] ERREUR :\n" + traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Échec de la génération CSV DI : {type(e).__name__} — {e}",
        )
    from datetime import datetime
    filename = f"dechets_inertes_projet{project_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@protected_api.get("/tracker/projects/{project_id}/export-btp-match-pdf")
async def tracker_export_btp_match_pdf(project_id: int, current_user=Depends(get_current_user)):
    """Exporte un PDF BTP Match pour les composants « à réutiliser »."""
    _verify_ownership(project_id, current_user.id)
    try:
        pdf_bytes = generate_btp_match_pdf(project_id)
    except Exception as e:
        import traceback
        print("[export-btp-match-pdf] ERREUR :\n" + traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Échec de la génération PDF BTP Match : {type(e).__name__} — {e}",
        )
    from datetime import datetime
    filename = f"btp_match_projet{project_id}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@protected_api.get("/tracker/projects/{project_id}/export-ifc")
async def tracker_export_project_ifc(project_id: int, current_user=Depends(get_current_user)):
    """Génère et télécharge l'IFC enrichi à partir du fichier source stocké."""
    _verify_ownership(project_id, current_user.id)
    info = get_project_ifc(project_id)
    if not info:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier IFC source associé à ce projet. Uploadez-le d'abord.",
        )
    try:
        ifc_bytes = export_ifc_with_statuses(info["path"], project_id=project_id)
    except Exception as e:
        import traceback
        print("[export-ifc-project] ERREUR :\n" + traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Échec de l'enrichissement IFC : {type(e).__name__} — {e}",
        )
    out_filename = _build_export_filename(info["filename"])
    return Response(
        content=ifc_bytes,
        media_type="application/x-step",
        headers={"Content-Disposition": f'attachment; filename="{out_filename}"'},
    )


@protected_api.post("/tracker/statuses")
async def tracker_statuses(req: StatusesRequest, current_user=Depends(get_current_user)):
    """Retourne {id: status} pour une liste d'IDs IFC (colonne Statut du tableau)."""
    if req.project_id is not None:
        _verify_ownership(req.project_id, current_user.id)
    return get_statuses_by_ids(req.ids, project_id=req.project_id)


@protected_api.post("/tracker/import")
async def tracker_import(req: ImportRequest, current_user=Depends(get_current_user)):
    """Crée un nouveau projet et y importe les composants."""
    result = import_components(req.components, project_name=req.project_name, user_id=current_user.id)
    return {"success": True, **result}


@protected_api.get("/tracker/components")
async def tracker_list(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    type: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Liste les composants (filtre obligatoire par projet recommandé)."""
    if project_id is not None:
        _verify_ownership(project_id, current_user.id)
    return get_all_components(
        project_id=project_id, status_filter=status, type_filter=type
    )


@protected_api.get("/tracker/component/{component_id}")
async def tracker_detail(component_id: str, current_user=Depends(get_current_user)):
    """Détail d'un composant avec son historique de statuts."""
    _verify_component_ownership(component_id, current_user.id)
    comp = get_component(component_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Composant introuvable.")
    return comp


@protected_api.post("/tracker/component/{component_id}/status")
async def tracker_update_status(component_id: str, req: StatusUpdateRequest, current_user=Depends(get_current_user)):
    """Met à jour le statut d'un composant."""
    _verify_component_ownership(component_id, current_user.id)
    try:
        result = update_status(component_id, req.status, req.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="Composant introuvable.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@protected_api.post("/tracker/components/bulk-status")
async def tracker_bulk_update_status(req: BulkStatusUpdateRequest, current_user=Depends(get_current_user)):
    """Change le statut de plusieurs composants en une seule requête."""
    if not req.ids:
        raise HTTPException(status_code=400, detail="Aucun composant sélectionné.")
    if req.status not in STATUTS_VALIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Statut invalide. Valeurs : {STATUTS_VALIDES}",
        )
    updated, errors = [], []
    for cid in req.ids:
        try:
            if not component_belongs_to_user(cid, current_user.id):
                errors.append({"id": cid, "error": "accès interdit"})
                continue
            update_status(cid, req.status, req.note)
            updated.append(cid)
        except KeyError:
            errors.append({"id": cid, "error": "introuvable"})
        except ValueError as e:
            errors.append({"id": cid, "error": str(e)})
    return {"updated": len(updated), "failed": len(errors), "errors": errors}


@protected_api.get("/tracker/component/{component_id}/qr")
async def tracker_qr(component_id: str, request: Request, current_user=Depends(get_current_user)):
    """Génère un QR code PNG pointant vers la page détail du composant."""
    _verify_component_ownership(component_id, current_user.id)
    comp = get_component(component_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Composant introuvable.")
    base_url = str(request.base_url).rstrip("/")
    png_bytes = generate_qr_png(
        component_id, base_url, project_id=comp.get("project_id")
    )
    return Response(content=png_bytes, media_type="image/png")


@protected_api.get("/tracker/stats")
async def tracker_stats(project_id: Optional[int] = None, current_user=Depends(get_current_user)):
    """Statistiques (filtrables par projet)."""
    if project_id is not None:
        _verify_ownership(project_id, current_user.id)
    return get_stats(project_id=project_id)


@protected_api.get("/tracker/statuts")
async def tracker_statuts():
    """Liste des statuts valides."""
    return STATUTS_VALIDES


@protected_api.get("/tracker/conditions")
async def tracker_conditions():
    """Liste des états (conditions) valides."""
    return CONDITIONS_VALIDES


@protected_api.get("/tracker/ages")
async def tracker_ages():
    """Liste des âges estimés valides."""
    return AGES_VALIDES


@protected_api.post("/tracker/component/{component_id}/meta")
async def tracker_update_meta(component_id: str, req: MetaUpdateRequest, current_user=Depends(get_current_user)):
    """Met à jour les métadonnées du composant (condition, commentaire, durée de vie, âge estimé)."""
    _verify_component_ownership(component_id, current_user.id)
    try:
        return update_component_meta(
            component_id,
            condition=req.condition,
            comment=req.comment,
            lifespan_months=req.lifespan_months,
            age_estimated=req.age_estimated,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Composant introuvable.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@protected_api.post("/tracker/components/bulk-meta")
async def tracker_bulk_update_meta(req: BulkMetaUpdateRequest, current_user=Depends(get_current_user)):
    """Met à jour la condition et/ou l'âge estimé pour plusieurs composants à la fois."""
    if not req.ids:
        raise HTTPException(status_code=400, detail="Aucun composant sélectionné.")
    if req.condition is None and req.age_estimated is None and req.comment is None:
        raise HTTPException(status_code=400, detail="Aucune métadonnée à mettre à jour.")
    updated, errors = [], []
    for cid in req.ids:
        try:
            if not component_belongs_to_user(cid, current_user.id):
                errors.append({"id": cid, "error": "accès interdit"})
                continue
            update_component_meta(
                cid,
                condition=req.condition,
                age_estimated=req.age_estimated,
                comment=req.comment,
            )
            updated.append(cid)
        except KeyError:
            errors.append({"id": cid, "error": "introuvable"})
        except ValueError as e:
            errors.append({"id": cid, "error": str(e)})
    return {"updated": len(updated), "failed": len(errors), "errors": errors}


# Pages HTML du tracker (servies comme fichiers statiques)
@app.get("/tracker")
async def tracker_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "tracker.html"))


@app.get("/viewer3d")
async def viewer3d_page():
    """Page du visualiseur IFC 3D."""
    return FileResponse(os.path.join(FRONTEND_DIR, "viewer3d.html"))


@app.get("/settings")
async def settings_page():
    """Page Paramètres."""
    return FileResponse(os.path.join(FRONTEND_DIR, "settings.html"))


# Cache local du WASM web-ifc (évite les soucis de CDN / chemins bundlés)
_WEB_IFC_VERSION = "0.0.39"  # pinné par web-ifc-three@0.0.125 (^0.0.39)
_WASM_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wasm_cache")
os.makedirs(_WASM_CACHE_DIR, exist_ok=True)


def _serve_wasm_asset(filename: str) -> FileResponse:
    """Télécharge (1re fois) puis sert un asset WASM web-ifc depuis le cache local.
    On essaie plusieurs versions en cascade pour trouver celle qui correspond au
    JS wrapper bundlé par jsdelivr (sinon OpenModel is not a function)."""
    allowed = {"web-ifc.wasm", "web-ifc-mt.wasm", "web-ifc-mt.worker.js"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Asset inconnu.")
    cached_path = os.path.join(_WASM_CACHE_DIR, filename)
    if not os.path.exists(cached_path):
        import urllib.request
        # Essayer jsdelivr d'abord (même source que le JS wrapper), puis unpkg
        # Plusieurs versions testées car web-ifc-three@0.0.125 est ancien.
        candidates = [
            f"https://cdn.jsdelivr.net/npm/web-ifc@{_WEB_IFC_VERSION}/{filename}",
            f"https://unpkg.com/web-ifc@{_WEB_IFC_VERSION}/{filename}",
        ]
        last_err = None
        for url in candidates:
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    data = r.read()
                with open(cached_path, "wb") as f:
                    f.write(data)
                print(f"[viewer3d] WASM téléchargé depuis : {url} ({len(data)} octets)")
                break
            except Exception as e:
                last_err = e
                continue
        else:
            raise HTTPException(status_code=502, detail=f"Échec téléchargement WASM: {last_err}")
    media = "application/wasm" if filename.endswith(".wasm") else "application/javascript"
    return FileResponse(cached_path, media_type=media)


@app.get("/viewer3d-assets/{filename}")
async def viewer3d_assets(filename: str):
    return _serve_wasm_asset(filename)


# Le bundle jsdelivr `/+esm` de web-ifc-three préfixe TOUJOURS `/app/.cache/npm/`
# à l'URL du WASM et ignore setWasmPath. On ajoute donc une route qui matche ce
# préfixe pour servir le WASM quelle que soit la stratégie du bundle.
@app.get("/app/.cache/npm/{path:path}")
async def viewer3d_jsdelivr_proxy(path: str):
    # Le "path" peut être n'importe quoi : on extrait juste le nom de fichier final.
    filename = path.rsplit("/", 1)[-1]
    return _serve_wasm_asset(filename)


@protected_api.get("/tracker/projects/{project_id}/ifc-raw")
async def tracker_project_ifc_raw(project_id: int, current_user=Depends(get_current_user)):
    """Sert le fichier IFC source brut (pour le viewer 3D)."""
    _verify_ownership(project_id, current_user.id)
    info = get_project_ifc(project_id)
    if not info or not os.path.exists(info["path"]):
        raise HTTPException(
            status_code=404,
            detail="Aucun fichier IFC source associé à ce projet.",
        )
    return FileResponse(
        info["path"],
        media_type="application/x-step",
        filename=info["filename"],
    )

# Nouvelle URL avec project_id (utilisée par les QR codes et le clic dans le tracker)
@app.get("/tracker/{project_id:int}/{component_id}")
async def tracker_detail_page_with_project(project_id: int, component_id: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "tracker_detail.html"))

# Compatibilité ascendante : /tracker/{component_id} sans project_id
@app.get("/tracker/{component_id}")
async def tracker_detail_page(component_id: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "tracker_detail.html"))


app.include_router(auth_router)
app.include_router(protected_api)


@app.get("/api/health")
async def health_check():
    """Vérification de l'état du serveur."""
    return {"status": "ok", "message": "Le serveur fonctionne correctement"}


if __name__ == "__main__":
    import uvicorn
    # reload=True désactivé : sous Windows, le reloader laisse parfois des workers
    # orphelins qui saturent le port 8000 avec des connexions CLOSE_WAIT.
    # Pour le développement, relance manuellement le serveur après modification du code Python.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
