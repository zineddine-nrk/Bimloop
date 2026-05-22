/**
 * Point d'entrée du viewer 3D.
 * Orchestre :
 *   - Le chargement de la liste des projets Tracker
 *   - Le chargement du fichier IFC (depuis Tracker ou disque local)
 *   - Les interactions UI (filtres, recherche, picking, coloration par statut)
 */
import { IFCViewer } from "./viewer.js";
import { renderDetails, renderSearchResults, setLoading, showEmpty } from "./ui.js";

// ====== Capture globale des erreurs (débogage) ======
window.addEventListener("error", (e) => {
    console.error("[viewer3d] window error:", e.message, e.filename, e.lineno, e.error);
});
window.addEventListener("unhandledrejection", (e) => {
    console.error("[viewer3d] unhandled rejection:", e.reason);
});

// ====== Refs DOM ======
const canvas             = document.getElementById("threeCanvas");
const projectSelect      = document.getElementById("projectSelect");
const localIfcInput      = document.getElementById("localIfcInput");
const detailsPanel       = document.getElementById("detailsPanel");
const loadingOverlay     = document.getElementById("loadingOverlay");
const loadingText        = document.getElementById("loadingText");
const emptyState         = document.getElementById("emptyState");
const searchInput        = document.getElementById("searchInput");
const searchResults      = document.getElementById("searchResults");
const categoryFilters    = document.getElementById("categoryFilters");
const colorByStatusToggle = document.getElementById("colorByStatusToggle");
const resetCamBtn        = document.getElementById("resetCamBtn");
const toggleWireframeBtn = document.getElementById("toggleWireframeBtn");
const modelInfo          = document.getElementById("modelInfo");

// ====== État ======
const viewer = new IFCViewer(canvas);
let currentProjectId = null;
let trackerComponentsByGlobalId = new Map(); // globalId → componentRecord
let searchableElements = [];
let wireframeOn = false;

// ====== Chargement liste projets ======
async function loadProjects() {
    try {
        const res = await fetch("/api/tracker/projects");
        if (!res.ok) return;
        const projects = await res.json();
        projectSelect.innerHTML =
            `<option value="">— Select a project —</option>` +
            projects.map(p => `<option value="${p.id}">${p.name} (${p.component_count})</option>`).join("");
    } catch (err) {
        console.warn("Failed to load projects:", err);
    }
}

// ====== Chargement IFC depuis projet Tracker ======
async function loadProjectIfc(projectId) {
    setLoading(loadingOverlay, loadingText, true, "Checking source IFC…");
    try {
        // Vérifier si le projet a un IFC source
        const infoRes = await fetch(`/api/tracker/projects/${projectId}/ifc-info`);
        const info = await infoRes.json();
        if (!info?.has_ifc) {
            alert("This project has no source IFC file. Upload it from the Tracker (\"Export to IFC\" button).");
            setLoading(loadingOverlay, loadingText, false);
            return;
        }
        currentProjectId = projectId;
        // Charger les composants du tracker pour la coloration / détails
        await loadTrackerComponents(projectId);
        // Charger l'IFC
        setLoading(loadingOverlay, loadingText, true, "Downloading IFC file…");
        const ifcUrl = `/api/tracker/projects/${projectId}/ifc-raw`;
        await viewer.loadFromUrl(ifcUrl, (xhr) => {
            if (xhr.lengthComputable) {
                const pct = Math.round((xhr.loaded / xhr.total) * 100);
                loadingText.textContent = `Loading model: ${pct}%`;
            }
        });
        await onModelLoaded();
    } catch (err) {
        console.error(err);
        alert(`Loading error: ${err.message || err}`);
    } finally {
        setLoading(loadingOverlay, loadingText, false);
    }
}

async function loadTrackerComponents(projectId) {
    try {
        const res = await fetch(`/api/tracker/components?project_id=${projectId}`);
        if (!res.ok) return;
        const list = await res.json();
        trackerComponentsByGlobalId.clear();
        for (const c of list) {
            // l'id stocké peut être suffixé "__pN" → on prend le préfixe (GlobalId IFC)
            const gid = (c.id || "").split("__p")[0];
            if (gid) trackerComponentsByGlobalId.set(gid, c);
        }
    } catch (err) {
        console.warn("Tracker components fetch failed:", err);
    }
}

// ====== Chargement IFC depuis disque local ======
localIfcInput.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    currentProjectId = null;
    trackerComponentsByGlobalId.clear();
    // Pas de projet → la coloration par statut est sans effet, on décoche
    colorByStatusToggle.checked = false;
    setLoading(loadingOverlay, loadingText, true, "Loading model…");
    try {
        await viewer.loadFromBlob(file, (xhr) => {
            if (xhr.lengthComputable) {
                const pct = Math.round((xhr.loaded / xhr.total) * 100);
                loadingText.textContent = `Loading model: ${pct}%`;
            }
        });
        await onModelLoaded();
    } catch (err) {
        console.error(err);
        alert(`Loading error: ${err.message || err}`);
    } finally {
        setLoading(loadingOverlay, loadingText, false);
        localIfcInput.value = "";
    }
});

// ====== Sélection projet ======
projectSelect.addEventListener("change", (e) => {
    const pid = e.target.value;
    if (!pid) return;
    loadProjectIfc(parseInt(pid, 10));
});

// ====== Modèle chargé : finalisation ======
async function onModelLoaded() {
    showEmpty(emptyState, false);
    modelInfo.textContent = currentProjectId
        ? `Project #${currentProjectId} • ${trackerComponentsByGlobalId.size} tracked components`
        : `Local file`;

    // Indexer les éléments pour la recherche
    setLoading(loadingOverlay, loadingText, true, "Indexing elements…");
    searchableElements = await viewer.listSearchableElements();
    setLoading(loadingOverlay, loadingText, false);

    // Coloration par statut si un projet est lié
    if (currentProjectId && colorByStatusToggle.checked) {
        await applyStatusColoring();
    }
}

// ====== Coloration par statut ======
async function applyStatusColoring() {
    if (!currentProjectId) {
        alert("Color by status only works for IFC files loaded from a Tracker project.\nPick a project in the dropdown above, then re-enable the toggle.");
        colorByStatusToggle.checked = false;
        return;
    }
    const statusMap = new Map();
    for (const [gid, comp] of trackerComponentsByGlobalId.entries()) {
        if (comp.status) statusMap.set(gid, comp.status);
    }
    if (statusMap.size === 0) {
        alert("No status data found for this project's components.");
        colorByStatusToggle.checked = false;
        return;
    }
    setLoading(loadingOverlay, loadingText, true, "Applying status colors…");
    try {
        await viewer.colorByStatus(statusMap);
    } finally {
        setLoading(loadingOverlay, loadingText, false);
    }
}

colorByStatusToggle.addEventListener("change", async () => {
    if (colorByStatusToggle.checked) await applyStatusColoring();
    else await viewer.clearStatusColoring();
});

// ====== Filtres catégorie ======
categoryFilters.querySelectorAll(".v3d-chip").forEach(chip => {
    chip.addEventListener("click", async () => {
        categoryFilters.querySelectorAll(".v3d-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        await viewer.filterByCategory(chip.dataset.cat);
    });
});

// ====== Picking au clic (avec détection de drag pour ne pas piquer pendant un orbit) ======
let pointerDownPos = null;
canvas.addEventListener("pointerdown", (e) => {
    pointerDownPos = { x: e.clientX, y: e.clientY };
});
canvas.addEventListener("pointerup", async (e) => {
    if (!pointerDownPos) return;
    const dx = e.clientX - pointerDownPos.x;
    const dy = e.clientY - pointerDownPos.y;
    pointerDownPos = null;
    if (Math.hypot(dx, dy) > 4) return; // drag → pas un clic

    const info = await viewer.pickAtPointer(e);
    if (!info) {
        viewer.clearHighlight();
        renderDetails(detailsPanel, null);
        return;
    }
    await viewer.highlight(info.expressID, false);
    const trackerData = info.globalId ? trackerComponentsByGlobalId.get(info.globalId) : null;
    renderDetails(detailsPanel, info, trackerData);
});

// ====== Recherche ======
let searchDebounce = null;
searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
        const q = searchInput.value.trim().toLowerCase();
        if (!q) { searchResults.innerHTML = ""; return; }
        const matches = searchableElements.filter(it =>
            (it.name || "").toLowerCase().includes(q) ||
            (it.globalId || "").toLowerCase().includes(q)
        );
        renderSearchResults(searchResults, matches, async (item) => {
            await viewer.highlight(item.expressID, true);
            const info = await viewer.getElementInfo(item.expressID);
            const trackerData = info?.globalId ? trackerComponentsByGlobalId.get(info.globalId) : null;
            renderDetails(detailsPanel, info, trackerData);
        });
    }, 200);
});

// ====== Toolbar ======
resetCamBtn.addEventListener("click", () => viewer.resetCamera());
toggleWireframeBtn.addEventListener("click", () => {
    wireframeOn = !wireframeOn;
    viewer.setWireframe(wireframeOn);
    toggleWireframeBtn.classList.toggle("active", wireframeOn);
});

// ====== Init ======
loadProjects();
