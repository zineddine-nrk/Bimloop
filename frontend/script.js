/**
 * IFC Analyzer — Script Frontend
 * Gère l'upload, l'affichage des résultats, les filtres et le résumé.
 */

// ============================================================
// ÉLÉMENTS DOM
// ============================================================
const fileInput = document.getElementById("fileInput");
const selectFileBtn = document.getElementById("selectFileBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const fileNameDisplay = document.getElementById("fileName");
const loader = document.getElementById("loader");
const successMessage = document.getElementById("successMessage");
const warningsDiv = document.getElementById("warnings");
const summarySection = document.getElementById("summarySection");
const summaryCards = document.getElementById("summaryCards");
const typeCountSection = document.getElementById("typeCountSection");
const typeCountCards = document.getElementById("typeCountCards");
const filterSection = document.getElementById("filterSection");
const filterButtons = document.getElementById("filterButtons");
const tableSection = document.getElementById("tableSection");
const tableHead = document.getElementById("tableHead");
const tableBody = document.getElementById("tableBody");
const noResultsMsg = document.getElementById("noResultsMsg");
const exportAllPdfBtn = document.getElementById("exportAllPdfBtn");
const exportTypePdfBtn = document.getElementById("exportTypePdfBtn");
const exportBtpMatchBtn = document.getElementById("exportBtpMatchBtn");
const exportPemdBtn = document.getElementById("exportPemdBtn");
const exportJsonBtn = document.getElementById("exportJsonBtn");
const exportInertesBtn = document.getElementById("exportInertesBtn");
const exportEquipementsBtn = document.getElementById("exportEquipementsBtn");
const btpMatchModal = document.getElementById("btpMatchModal");
const btpTypeSelect = document.getElementById("btpTypeSelect");
const btpModalCancelBtn = document.getElementById("btpModalCancelBtn");
const btpModalExportBtn = document.getElementById("btpModalExportBtn");
const uploadCard = document.querySelector(".upload-card");

// ============================================================
// ÉTAT GLOBAL
// ============================================================
let allElements = [];
let currentFilter = "Tous";

// ============================================================
// EXPORT PDF
// ============================================================

exportAllPdfBtn.addEventListener("click",  e => showFormatPicker(e, exportAllToCsv,  () => exportAllToPdf()));
exportTypePdfBtn.addEventListener("click", e => showFormatPicker(e, exportTypeToCsv, () => exportTypeToPdf()));

function toCsvCell(value) {
    const str = typeof value === "string" ? value.replace(/<[^>]*>/g, "") : String(value ?? "");
    return `"${str.replace(/"/g, '""')}"`;
}

function buildCsv(cols, elems) {
    const header = cols.map(c => toCsvCell(c.header)).join(";");
    const rows = elems.map(e =>
        cols.map(c => toCsvCell(c.value(e))).join(";")
    );
    return [header, ...rows].join("\r\n");
}

function downloadCsv(content, filename) {
    const bom = "\uFEFF";
    const blob = new Blob([bom + content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

function exportAllToCsv() {
    const types = [...new Set(allElements.map(e => e.type))];
    const sections = types.map(typeName => {
        const elems = allElements.filter(e => e.type === typeName);
        const cols = getColumnsForType(typeName);
        return `${typeName}\r\n${buildCsv(cols, elems)}`;
    });
    downloadCsv(sections.join("\r\n\r\n"), "ifc-export-complet.csv");
}

function exportTypeToCsv() {
    const elems = currentFilter === "Tous"
        ? allElements
        : allElements.filter(e => e.type === currentFilter);
    const cols = getColumnsForType(currentFilter === "Tous" ? null : currentFilter);
    const filename = currentFilter === "Tous" ? "ifc-tous.csv" : `ifc-${currentFilter.toLowerCase()}.csv`;
    downloadCsv(buildCsv(cols, elems), filename);
}

// ============================================================
// EXPORT CSV INERTES / ÉQUIPEMENTS
// ============================================================

const TYPES_INERTES     = ["Mur", "Mur rideau", "Dalle"];
const TYPES_EQUIPEMENTS = ["Porte", "Fen\u00eatre", "Escalier"];

// Densités approx. en kg/m³ selon matériau principal
const DENSITES = {
    "béton": 2400, "beton": 2400, "concrete": 2400,
    "béton armé": 2500, "béton armé": 2500,
    "brique": 1800, "brick": 1800,
    "pierre": 2600, "stone": 2600,
    "bois": 700, "wood": 700,
    "acier": 7850, "steel": 7850,
    "aluminium": 2700, "aluminum": 2700,
    "verre": 2500, "glass": 2500,
    "plâtre": 1200, "platre": 1200,
    "gypse": 1200,
};

function getDensite(materiau) {
    if (!materiau) return 2000;
    const m = materiau.toLowerCase();
    for (const [key, val] of Object.entries(DENSITES)) {
        if (m.includes(key)) return val;
    }
    return 2000; // valeur par défaut
}

function calcVolume(elem) {
    if (elem.net_volume != null) return elem.net_volume;
    const h = elem.hauteur, l = elem.longueur, e = elem.epaisseur;
    if (elem.type === "Dalle" && elem.net_area != null && e != null)
        return Math.round(elem.net_area * e * 1000) / 1000;
    if (h != null && l != null && e != null)
        return Math.round(h * l * e * 1000) / 1000;
    return null;
}

function exportInertesCsv() {
    const elems = allElements.filter(e => TYPES_INERTES.includes(e.type));
    if (!elems.length) { alert("Aucun élément inerte trouvé."); return; }

    const cols = [
        "Nom/ID", "Type", "Étage", "Matériau",
        "Hauteur (m)", "Longueur (m)", "Épaisseur (m)",
        "Volume (m³)", "Densité (kg/m³)", "Masse (kg)"
    ];
    const header = cols.map(c => toCsvCell(c)).join(";");

    let totalVol = 0, totalMasse = 0;
    let hasVol = false;

    const rows = elems.map(e => {
        const vol = calcVolume(e);
        const dens = getDensite(e.materiau);
        const masse = vol != null ? Math.round(vol * dens) : null;
        if (vol != null) { totalVol += vol; hasVol = true; }
        if (masse != null) totalMasse += masse;
        return [
            e.nom || e.id || "",
            e.type || "",
            e.etage || "",
            e.materiau || "",
            e.hauteur ?? "",
            e.longueur ?? "",
            e.epaisseur ?? "",
            vol ?? "",
            dens,
            masse ?? "",
        ].map(toCsvCell).join(";");
    });

    const separator = ";".repeat(cols.length - 1);
    const totals = [
        toCsvCell("TOTAL"),
        toCsvCell(""), toCsvCell(""), toCsvCell(""),
        toCsvCell(""), toCsvCell(""), toCsvCell(""),
        toCsvCell(hasVol ? Math.round(totalVol * 1000) / 1000 : ""),
        toCsvCell(""),
        toCsvCell(totalMasse > 0 ? totalMasse : ""),
    ].join(";");

    const csv = [header, ...rows, "", totals].join("\r\n");
    downloadCsv(csv, "ifc-inertes.csv");
}

function exportCategorieCsv(types, filename) {
    const elems = allElements.filter(e => types.includes(e.type));
    if (!elems.length) {
        alert(`Aucun élément trouvé pour cette catégorie.`);
        return;
    }
    const sections = types
        .filter(t => elems.some(e => e.type === t))
        .map(typeName => {
            const sub = elems.filter(e => e.type === typeName);
            const cols = getColumnsForType(typeName);
            return `${typeName}\r\n${buildCsv(cols, sub)}`;
        });
    downloadCsv(sections.join("\r\n\r\n"), filename);
}

exportInertesBtn.addEventListener("click",    e => showFormatPicker(e, exportInertesCsv, exportInertesPdf));
exportEquipementsBtn.addEventListener("click", e => showFormatPicker(e, () => exportCategorieCsv(TYPES_EQUIPEMENTS, "ifc-equipements.csv"), () => exportCategoriePdf(TYPES_EQUIPEMENTS, "Équipements", "ifc-equipements.pdf")));

// ============================================================
// FORMAT PICKER (CSV / PDF)
// ============================================================

function showFormatPicker(event, csvFn, pdfFn) {
    event.stopPropagation();
    document.querySelectorAll(".fmt-picker").forEach(el => el.remove());

    const btn  = event.currentTarget;
    const rect = btn.getBoundingClientRect();

    const picker = document.createElement("div");
    picker.className = "fmt-picker";
    picker.innerHTML = `
        <button class="fmt-opt" data-fmt="csv"><span>📄</span> CSV</button>
        <button class="fmt-opt" data-fmt="pdf"><span>📑</span> PDF</button>
    `;
    picker.style.cssText = `
        position:fixed;
        top:${rect.bottom + 4}px;
        left:${rect.left}px;
        z-index:9999;
        background:white;
        border:1px solid #d1d5db;
        border-radius:8px;
        box-shadow:0 4px 16px rgba(0,0,0,.15);
        display:flex;
        flex-direction:column;
        min-width:130px;
        overflow:hidden;
    `;

    picker.querySelector('[data-fmt="csv"]').addEventListener("click", e => {
        e.stopPropagation();
        picker.remove();
        csvFn();
    });
    picker.querySelector('[data-fmt="pdf"]').addEventListener("click", e => {
        e.stopPropagation();
        picker.remove();
        pdfFn();
    });

    document.body.appendChild(picker);
    setTimeout(() => document.addEventListener("click", () => picker.remove(), { once: true }));
}

// ── PDF helpers ──────────────────────────────────────────────

function buildTableData(cols, elems) {
    return {
        headers: cols.map(c => c.header),
        rows: elems.map(e => cols.map(c => {
            const v = c.value(e);
            return typeof v === "string" ? v.replace(/<[^>]*>/g, "") : String(v ?? "");
        })),
    };
}

async function downloadTablePdf(title, headers, rows, filename) {
    const res = await fetch("/api/export-table-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, headers, rows, filename }),
    });
    if (!res.ok) { alert("Erreur génération PDF."); return; }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
}

function exportAllToPdf() {
    const types   = [...new Set(allElements.map(e => e.type))];
    const allCols = getColumnsForType(null);
    const { headers, rows } = buildTableData(allCols, allElements);
    downloadTablePdf("Export complet — IFC Analyzer", headers, rows, "ifc-export-complet.pdf");
}

function exportTypeToPdf() {
    const elems = currentFilter === "Tous"
        ? allElements
        : allElements.filter(e => e.type === currentFilter);
    const cols  = getColumnsForType(currentFilter === "Tous" ? null : currentFilter);
    const label = currentFilter === "Tous" ? "Tous les éléments" : currentFilter;
    const fname = currentFilter === "Tous" ? "ifc-tous.pdf" : `ifc-${currentFilter.toLowerCase()}.pdf`;
    const { headers, rows } = buildTableData(cols, elems);
    downloadTablePdf(`Export sélection — ${label}`, headers, rows, fname);
}

function exportCategoriePdf(types, title, filename) {
    const elems   = allElements.filter(e => types.includes(e.type));
    if (!elems.length) { alert("Aucun élément trouvé pour cette catégorie."); return; }
    const typeName = elems[0].type;
    const cols   = getColumnsForType(typeName);
    const { headers, rows } = buildTableData(cols, elems);
    downloadTablePdf(title, headers, rows, filename);
}

function exportInertesPdf() {
    const elems = allElements.filter(e => TYPES_INERTES.includes(e.type));
    if (!elems.length) { alert("Aucun élément inerte trouvé."); return; }

    const headers = [
        "Nom/ID", "Type", "Étage", "Matériau",
        "Hauteur (m)", "Longueur (m)", "Épaisseur (m)",
        "Volume (m³)", "Densité (kg/m³)", "Masse (kg)"
    ];

    let totalVol = 0, totalMasse = 0;

    const dataRows = elems.map(e => {
        const vol   = calcVolume(e);
        const dens  = getDensite(e.materiau);
        const masse = vol != null ? Math.round(vol * dens) : null;
        if (vol   != null) totalVol   += vol;
        if (masse != null) totalMasse += masse;
        return [
            e.nom || e.id || "",
            e.type || "",
            e.etage || "",
            e.materiau || "",
            e.hauteur ?? "",
            e.longueur ?? "",
            e.epaisseur ?? "",
            vol ?? "",
            dens,
            masse ?? "",
        ].map(v => String(v));
    });

    const totalVolStr   = String(Math.round(totalVol   * 1000) / 1000);
    const totalMasseStr = String(totalMasse);
    const totalRow = ["★ TOTAL", "", "", "", "", "", "", totalVolStr, "", totalMasseStr];

    const rows = [totalRow, ...dataRows, totalRow];

    downloadTablePdf("Éléments Inertes — IFC Analyzer", headers, rows, "ifc-inertes.pdf");
}

// ============================================================
// EXPORT JSON
// ============================================================

exportJsonBtn.addEventListener("click", () => {
    const mapped = allElements.map(e => ({
        id: e.id || null,
        type: e.type || null,
        material: e.materiau || null,
        ifc_location: e.etage || null,
        status: "in_building",
    }));
    const json = JSON.stringify(mapped, null, 2);
    const blob = new Blob([json], { type: "application/json;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ifc-elements.json";
    a.click();
    URL.revokeObjectURL(url);
});

// ============================================================
// RAPPORT PEMD
// ============================================================

exportPemdBtn.addEventListener("click", async () => {
    exportPemdBtn.disabled = true;
    exportPemdBtn.textContent = "Génération PEMD...";
    try {
        const response = await fetch("/api/export-pemd", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                elements: allElements,
                project_name: "Projet IFC",
            }),
        });
        if (!response.ok) {
            const err = await response.json();
            alert(`Erreur : ${err.detail || "Export PEMD échoué"}`);
            return;
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "diagnostic_pemd_tableau1.pdf";
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert(`Erreur réseau : ${err.message}`);
    } finally {
        exportPemdBtn.disabled = false;
        exportPemdBtn.textContent = "Rapport PEMD";
    }
});

// ============================================================
// BTP MATCH MODAL
// ============================================================

exportBtpMatchBtn.addEventListener("click", () => {
    // Remplir le select avec les types disponibles
    const types = ["Tous", ...new Set(allElements.map(e => e.type))];
    btpTypeSelect.innerHTML = types.map(t => `<option value="${t}">${t}</option>`).join("");
    btpMatchModal.classList.remove("hidden");
    lucide.createIcons();
});

btpModalCancelBtn.addEventListener("click", () => {
    btpMatchModal.classList.add("hidden");
});

btpMatchModal.addEventListener("click", (e) => {
    if (e.target === btpMatchModal) btpMatchModal.classList.add("hidden");
});

btpModalExportBtn.addEventListener("click", async () => {
    const typeName = btpTypeSelect.value;
    const format = document.querySelector("input[name='btpFormat']:checked").value;

    btpModalExportBtn.disabled = true;
    btpModalExportBtn.textContent = "Génération...";

    try {
        const response = await fetch("/api/export-btpmatch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                elements: allElements,
                type_name: typeName === "Tous" ? null : typeName,
                format: format,
            }),
        });

        if (!response.ok) {
            const err = await response.json();
            alert(`Erreur : ${err.detail || "Export échoué"}`);
            return;
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const label = typeName === "Tous" ? "tous" : typeName.toLowerCase();
        a.download = `btpmatch-${label}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        btpMatchModal.classList.add("hidden");
    } catch (err) {
        alert(`Erreur réseau : ${err.message}`);
    } finally {
        btpModalExportBtn.disabled = false;
        btpModalExportBtn.textContent = "Exporter";
    }
});

// ============================================================
// ÉVÉNEMENTS
// ============================================================

// Clic sur le bouton de sélection de fichier
selectFileBtn.addEventListener("click", () => fileInput.click());

// Sélection de fichier via input
fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFileSelected(file);
    }
});

// Clic sur le bouton d'analyse
analyzeBtn.addEventListener("click", () => {
    const file = fileInput.files[0];
    if (file) {
        uploadAndAnalyze(file);
    }
});

// Drag & Drop
uploadCard.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadCard.classList.add("drag-over");
});

uploadCard.addEventListener("dragleave", () => {
    uploadCard.classList.remove("drag-over");
});

uploadCard.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadCard.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file && file.name.toLowerCase().endsWith(".ifc")) {
        // Mettre à jour l'input file
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        handleFileSelected(file);
    } else {
        alert("Veuillez déposer un fichier .ifc valide.");
    }
});

// ============================================================
// FONCTIONS
// ============================================================

/**
 * Gère la sélection d'un fichier
 */
function handleFileSelected(file) {
    fileNameDisplay.textContent = `📄 ${file.name} (${formatFileSize(file.size)})`;
    analyzeBtn.disabled = false;
}

/**
 * Formate la taille d'un fichier
 */
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " o";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " Ko";
    return (bytes / (1024 * 1024)).toFixed(1) + " Mo";
}

/**
 * Upload et analyse du fichier IFC via l'API
 */
async function uploadAndAnalyze(file) {
    // Afficher le loader, masquer les anciens résultats
    showLoader(true);
    hideResults();

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Erreur lors de l'analyse");
        }

        // Stocker les éléments
        allElements = data.elements;
        currentFilter = "Tous";

        // Afficher les résultats
        showSuccessMessage(data.message);
        showWarnings(data.avertissements);
        showSummary(data.resume);
        showTypeCount(data.resume.par_type);
        showFilters(data.resume.par_type);
        showTable(allElements);

    } catch (error) {
        alert(`Erreur : ${error.message}`);
    } finally {
        showLoader(false);
    }
}

/**
 * Affiche ou masque le loader
 */
function showLoader(show) {
    loader.classList.toggle("hidden", !show);
}

/**
 * Masque tous les résultats
 */
function hideResults() {
    successMessage.classList.add("hidden");
    warningsDiv.classList.add("hidden");
    summarySection.classList.add("hidden");
    typeCountSection.classList.add("hidden");
    filterSection.classList.add("hidden");
    tableSection.classList.add("hidden");
}

/**
 * Affiche le message de succès
 */
function showSuccessMessage(message) {
    successMessage.innerHTML = `<i data-lucide="check-circle"></i> ${message}`;
    successMessage.classList.remove("hidden");
    lucide.createIcons();
}

/**
 * Affiche les avertissements (éléments manquants)
 */
function showWarnings(warnings) {
    if (!warnings || warnings.length === 0) {
        warningsDiv.classList.add("hidden");
        return;
    }

    warningsDiv.innerHTML = warnings
        .map(
            (w) => `<div class="warning-item"><i data-lucide="alert-triangle"></i> ${w}</div>`
        )
        .join("");
    warningsDiv.classList.remove("hidden");
    lucide.createIcons();
}

/**
 * Affiche le résumé global dans des cartes
 */
function showSummary(resume) {
    summaryCards.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${resume.total}</div>
            <div class="stat-label">Éléments au total</div>
        </div>
        <div class="stat-card gray">
            <div class="stat-value">${Object.keys(resume.par_type).length}</div>
            <div class="stat-label">Types d'éléments</div>
        </div>
    `;
    summarySection.classList.remove("hidden");
}

/**
 * Affiche le comptage par type dans des cartes
 */
function showTypeCount(parType) {
    if (!parType || Object.keys(parType).length === 0) {
        typeCountSection.classList.add("hidden");
        return;
    }

    // Couleurs par type
    const typeColors = {
        "Mur": "#2563eb",
        "Fenêtre": "#7c3aed",
        "Porte": "#d97706",
        "Dalle": "#0891b2",
        "Escalier": "#ea580c",
        "Mur rideau": "#059669",
    };

    typeCountCards.innerHTML = Object.entries(parType)
        .map(([type, count]) => {
            const color = typeColors[type] || "#6b7280";
            return `
                <div class="type-card" style="border-left-color: ${color}">
                    <span class="type-name">${type}</span>
                    <span class="type-count" style="background: ${color}">${count}</span>
                </div>
            `;
        })
        .join("");

    typeCountSection.classList.remove("hidden");
}

/**
 * Affiche les boutons de filtre
 */
function showFilters(parType) {
    const types = ["Tous", ...Object.keys(parType)];

    filterButtons.innerHTML = types
        .map(
            (type) =>
                `<button class="filter-btn ${type === currentFilter ? "active" : ""}" 
                         data-type="${type}">${type}</button>`
        )
        .join("");

    // Ajouter les événements de clic
    filterButtons.querySelectorAll(".filter-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            currentFilter = btn.dataset.type;
            // Mettre à jour l'état actif
            filterButtons.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            // Filtrer le tableau
            const filtered = currentFilter === "Tous"
                ? allElements
                : allElements.filter((e) => e.type === currentFilter);
            showTable(filtered);
        });
    });

    filterSection.classList.remove("hidden");
}

// Colonnes spécifiques par type
const TYPE_COLUMNS = {
    "Mur": [
        { header: "Hauteur (m)", value: e => formatDimension(e.hauteur) },
        { header: "Longueur (m)", value: e => formatDimension(e.longueur) },
        { header: "Épaisseur (m)", value: e => formatDimension(e.epaisseur) },
        { header: "Volume (m³)", value: e => e.volume != null ? e.volume + " m³" : "" },
    ],
    "Porte": [
        { header: "Hauteur (m)", value: e => formatDimension(e.hauteur) },
        { header: "Longueur (m)", value: e => formatDimension(e.longueur) },
        { header: "Battants", value: e => e.nb_battants != null ? e.nb_battants : "" },
    ],
    "Dalle": [
        { header: "NetArea (m²)", value: e => e.net_area != null ? e.net_area : "" },
        { header: "NetVolume (m³)", value: e => e.net_volume != null ? e.net_volume : "" },
        { header: "Width (m)", value: e => formatDimension(e.epaisseur) },
    ],
    "Escalier": [
        { header: "Nb Contremarches", value: e => e.number_of_riser != null ? e.number_of_riser : "" },
        { header: "Nb Marches", value: e => e.number_of_treads != null ? e.number_of_treads : "" },
        { header: "Long. Marche (m)", value: e => e.tread_length != null ? e.tread_length : "" },
        { header: "Haut. Contremarche (m)", value: e => e.riser_height != null ? e.riser_height : "" },
    ],
    "Mur rideau": [],
};

// Colonnes par défaut (pour Tous, Fenêtre, Mur rideau, etc.)
const DEFAULT_COLUMNS = [
    { header: "Hauteur (m)", value: e => formatDimension(e.hauteur) },
    { header: "Longueur (m)", value: e => formatDimension(e.longueur) },
    { header: "Épaisseur (m)", value: e => formatDimension(e.epaisseur) },
    { header: "Volume (m³)", value: e => e.volume != null ? e.volume + " m³" : "" },
];

// Colonnes communes à tous les types
const COMMON_COLUMNS = [
    { header: "Nom / ID", value: e => `<span title="${e.id}">${e.nom || e.id}</span>` },
    { header: "Type", value: e => e.type },
    { header: "Étage", value: e => e.etage || "—" },
    { header: "Matériau", value: e => e.materiau || "Inconnu" },
];

function getColumnsForType(typeName) {
    // "Tous" (typeName null) : uniquement les colonnes communes
    if (!typeName) {
        return [...COMMON_COLUMNS];
    }
    const specific = TYPE_COLUMNS[typeName] || DEFAULT_COLUMNS;
    return [...COMMON_COLUMNS, ...specific];
}

/**
 * Affiche le tableau des éléments avec colonnes dynamiques
 */
function showTable(elements) {
    if (!elements || elements.length === 0) {
        tableHead.innerHTML = "";
        tableBody.innerHTML = "";
        noResultsMsg.classList.remove("hidden");
        tableSection.classList.remove("hidden");
        return;
    }

    noResultsMsg.classList.add("hidden");

    // Déterminer les colonnes selon le filtre actif
    const columns = currentFilter !== "Tous"
        ? getColumnsForType(currentFilter)
        : getColumnsForType(null);

    // Générer le thead
    tableHead.innerHTML = `<tr>${columns.map(c => `<th>${c.header}</th>`).join("")}</tr>`;

    // Générer le tbody
    tableBody.innerHTML = elements
        .map((elem) => {
            const cells = columns.map(c => {
                const titleAttr = c.title ? ` title="${c.title(elem)}"` : "";
                return `<td${titleAttr}>${c.value(elem)}</td>`;
            }).join("");
            return `<tr>${cells}</tr>`;
        })
        .join("");

    tableSection.classList.remove("hidden");
}

/**
 * Crée un badge coloré (OUI = vert, NON = rouge, INCONNU = gris)
 */
function getBadge(value) {
    if (value === "OUI") {
        return `<span class="badge badge-oui">OUI</span>`;
    } else if (value === "NON") {
        return `<span class="badge badge-non">NON</span>`;
    } else {
        return `<span class="badge badge-inconnu">INCONNU</span>`;
    }
}

/**
 * Formate une dimension (null → tiret)
 */
function formatDimension(value) {
    return value != null ? value : "";
}

/**
 * Crée un badge de score coloré avec mini barre de progression
 */
function getScoreBadge(score) {
    const percent = Math.round(score * 100);
    let colorClass = "score-low";
    if (score >= 0.7) colorClass = "score-high";
    else if (score >= 0.4) colorClass = "score-mid";

    return `
        <div class="score-badge ${colorClass}">
            <span class="score-value">${score}</span>
            <div class="score-bar-mini">
                <div class="score-bar-fill" style="width: ${percent}%"></div>
            </div>
        </div>
    `;
}

/**
 * Retourne la classe CSS pour une carte de score
 */
function getScoreCardClass(score) {
    if (score >= 0.7) return "green";
    if (score >= 0.4) return "orange";
    return "red";
}

/**
 * Crée une barre de progression pour les cartes résumé
 */
function getScoreBar(score) {
    const percent = Math.round(score * 100);
    let color = "var(--danger)";
    if (score >= 0.7) color = "var(--success)";
    else if (score >= 0.4) color = "var(--warning)";

    return `
        <div class="score-bar-container">
            <div class="score-bar-track">
                <div class="score-bar-fill-big" style="width: ${percent}%; background: ${color}"></div>
            </div>
            <span class="score-bar-label">${percent}%</span>
        </div>
    `;
}

// ============================================================
// INITIALISATION — Lucide icons
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
});
