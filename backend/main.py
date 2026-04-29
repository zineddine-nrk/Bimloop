"""
Serveur FastAPI principal pour l'analyse de fichiers IFC.
Gère l'upload, le traitement et le renvoi des résultats.
"""

import os
import shutil
import tempfile
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from ifc_parser import parse_ifc_file
from utils import enrichir_elements, calculer_resume
from btp_match import filter_by_type, group_elements, generate_csv, generate_pdf
from pemd_report import generate_pemd_pdf
from table_pdf import generate_table_pdf
from tracker import (
    init_db, import_components, get_all_components,
    get_component, update_status, generate_qr_png, get_stats,
    STATUTS_VALIDES,
)


# Initialisation de l'application FastAPI
app = FastAPI(
    title="IFC Analyzer - Analyse de durabilité",
    description="Application d'analyse de fichiers IFC pour la durabilité",
    version="1.0.0",
)

# Configuration CORS pour permettre les requêtes du frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.post("/api/upload")
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


class BtpMatchRequest(BaseModel):
    elements: List[dict]
    type_name: Optional[str] = None
    format: str = "csv"


@app.post("/api/export-btpmatch")
async def export_btpmatch(req: BtpMatchRequest):
    """
    Génère un export BTP Match (CSV ou PDF) depuis les éléments IFC.
    Regroupe les éléments similaires et calcule les quantités.
    """
    filtered = filter_by_type(req.elements, req.type_name)
    if not filtered:
        raise HTTPException(status_code=400, detail="Aucun élément trouvé pour ce type.")

    grouped = group_elements(filtered)

    if req.format == "pdf":
        content = generate_pdf(grouped, req.type_name or "Tous")
        filename = f"btpmatch-{(req.type_name or 'tous').lower()}.pdf"
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        content = generate_csv(grouped)
        filename = f"btpmatch-{(req.type_name or 'tous').lower()}.csv"
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


class PemdReportRequest(BaseModel):
    elements: List[dict]
    project_name: Optional[str] = "Projet IFC"


@app.post("/api/export-pemd")
async def export_pemd(req: PemdReportRequest):
    """
    Génère un rapport PEMD (Tableau 1) en PDF depuis les éléments IFC extraits.
    Groupe les éléments par catégorie PEMD et génère un document structuré.
    """
    if not req.elements:
        raise HTTPException(status_code=400, detail="Aucun élément fourni.")
    try:
        pdf_bytes = generate_pemd_pdf(req.elements, req.project_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur génération PDF PEMD : {str(e)}")

    filename = "diagnostic_pemd_tableau1.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================
# EXPORT TABLE PDF — générique
# ============================================================

class TablePdfRequest(BaseModel):
    title: str
    headers: List[str]
    rows: List[List[str]]
    filename: Optional[str] = "export.pdf"


@app.post("/api/export-table-pdf")
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

class StatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None


@app.post("/api/tracker/import")
async def tracker_import(req: ImportRequest):
    """Importe les composants depuis le JSON IFC dans la base de tracking."""
    result = import_components(req.components)
    return {"success": True, **result}


@app.get("/api/tracker/components")
async def tracker_list(status: Optional[str] = None, type: Optional[str] = None):
    """Liste tous les composants avec filtres optionnels."""
    return get_all_components(status_filter=status, type_filter=type)


@app.get("/api/tracker/component/{component_id}")
async def tracker_detail(component_id: str):
    """Détail d'un composant avec son historique de statuts."""
    comp = get_component(component_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Composant introuvable.")
    return comp


@app.post("/api/tracker/component/{component_id}/status")
async def tracker_update_status(component_id: str, req: StatusUpdateRequest):
    """Met à jour le statut d'un composant."""
    try:
        result = update_status(component_id, req.status, req.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="Composant introuvable.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.get("/api/tracker/component/{component_id}/qr")
async def tracker_qr(component_id: str, request: Request):
    """Génère un QR code PNG pointant vers la page détail du composant."""
    comp = get_component(component_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Composant introuvable.")
    base_url = str(request.base_url).rstrip("/")
    png_bytes = generate_qr_png(component_id, base_url)
    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/tracker/stats")
async def tracker_stats():
    """Statistiques globales du tracking."""
    return get_stats()


@app.get("/api/tracker/statuts")
async def tracker_statuts():
    """Liste des statuts valides."""
    return STATUTS_VALIDES


# Pages HTML du tracker (servies comme fichiers statiques)
@app.get("/tracker")
async def tracker_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "tracker.html"))

@app.get("/tracker/{component_id}")
async def tracker_detail_page(component_id: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "tracker_detail.html"))


@app.get("/api/health")
async def health_check():
    """Vérification de l'état du serveur."""
    return {"status": "ok", "message": "Le serveur fonctionne correctement"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
