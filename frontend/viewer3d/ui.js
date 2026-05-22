/**
 * UI helpers : panneau de détails, recherche, badges de statut.
 */

const STATUS_BADGE_COLORS = {
    "in_building":   "#9ca3af",
    "démonté":       "#f97316",
    "transporté":    "#3b82f6",
    "stocké":        "#a855f7",
    "à réutiliser":  "#10b981",
    "réutilisé":     "#10b981",
    "à recycler":    "#ef4444",
};

const TYPE_EN = {
    IFCWALL: "Wall",
    IFCWALLSTANDARDCASE: "Wall",
    IFCCURTAINWALL: "Curtain wall",
    IFCDOOR: "Door",
    IFCWINDOW: "Window",
    IFCSLAB: "Slab",
    IFCROOF: "Roof",
    IFCSTAIR: "Stairs",
};

const STATUS_LABELS_EN = {
    "in_building":  "In building",
    "démonté":      "Dismantled",
    "transporté":   "In transit",
    "stocké":       "Stored",
    "réutilisé":    "Reused",
    "à réutiliser": "To reuse",
    "à recycler":   "To recycle",
};
const CONDITION_LABELS_EN = { "Neuf": "New", "Bon": "Good", "Moyen": "Fair", "Mauvais": "Poor" };
const AGE_LABELS_EN = {
    "Inférieur à 2 ans":  "Under 2 years",
    "Entre 2 et 10 ans":  "2–10 years",
    "Entre 10 et 50 ans": "10–50 years",
    "Supérieur à 50 ans": "Over 50 years",
};

function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function fr(ifcType) {
    return TYPE_EN[ifcType] || ifcType || "—";
}

function formatNum(v) {
    if (v == null || v === "") return null;
    const n = Number(v);
    if (!isFinite(n)) return null;
    return Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(2).replace(/\.?0+$/, "");
}

/** Extrait dimensions (hauteur, longueur, épaisseur, surface, volume) depuis les PSets IFC. */
function extractDimensions(psets) {
    const out = {};
    if (!Array.isArray(psets)) return out;
    const keys = {
        height:    ["Height", "OverallHeight", "Hauteur"],
        length:    ["Length", "OverallWidth", "Width", "Longueur", "Largeur"],
        thickness: ["Thickness", "Depth", "Width", "Épaisseur"],
        area:      ["NetArea", "GrossArea", "Area"],
        volume:    ["NetVolume", "GrossVolume", "Volume"],
    };
    for (const pset of psets) {
        const props = pset?.HasProperties || pset?.Quantities || [];
        for (const p of props) {
            const name = p?.Name?.value;
            if (!name) continue;
            const val =
                p?.NominalValue?.value ?? p?.LengthValue?.value ??
                p?.AreaValue?.value ?? p?.VolumeValue?.value ?? p?.Value?.value;
            if (val == null) continue;
            for (const [outKey, candidates] of Object.entries(keys)) {
                if (out[outKey] != null) continue;
                if (candidates.some(c => name.toLowerCase() === c.toLowerCase())) {
                    out[outKey] = val;
                }
            }
        }
    }
    return out;
}

export function renderDetails(panelEl, info, trackerData) {
    if (!info) {
        panelEl.innerHTML = `
            <div class="v3d-details-empty">
                <i data-lucide="mouse-pointer-click"></i>
                <p>Click an object to see its details.</p>
            </div>`;
        if (window.lucide) lucide.createIcons();
        return;
    }

    const dims = extractDimensions(info.psets);
    const status = trackerData?.status || null;
    const statusColor = status ? (STATUS_BADGE_COLORS[status] || "#94a3b8") : null;
    const material = info.materials?.length
        ? info.materials.join(", ")
        : (trackerData?.material || "—");

    const rows = [];
    const addRow = (k, v) => {
        if (v == null || v === "") return;
        rows.push(`<div class="v3d-detail-row"><span class="v3d-key">${escapeHtml(k)}</span><span class="v3d-val">${escapeHtml(v)}</span></div>`);
    };

    addRow("Type", fr(info.ifcType));
    addRow("Material", material);
    if (dims.height)    addRow("Height",    `${formatNum(dims.height)} m`);
    if (dims.length)    addRow("Length",    `${formatNum(dims.length)} m`);
    if (dims.thickness) addRow("Thickness", `${formatNum(dims.thickness)} m`);
    if (dims.area)      addRow("Area",      `${formatNum(dims.area)} m²`);
    if (dims.volume)    addRow("Volume",    `${formatNum(dims.volume)} m³`);
    if (trackerData?.ifc_location)  addRow("Floor", trackerData.ifc_location);
    if (trackerData?.condition)     addRow("Condition", CONDITION_LABELS_EN[trackerData.condition] || trackerData.condition);
    if (trackerData?.age_estimated) addRow("Estimated age", AGE_LABELS_EN[trackerData.age_estimated] || trackerData.age_estimated);

    panelEl.innerHTML = `
        <div class="v3d-detail-card">
            <div class="v3d-detail-title">${escapeHtml(info.name)}</div>
            <div class="v3d-detail-subtitle">${escapeHtml(info.globalId || `expressID ${info.expressID}`)}</div>
            ${status ? `<div style="margin-bottom:.8rem;"><span class="v3d-status-badge" style="background:${statusColor}22;color:${statusColor};border:1px solid ${statusColor}">${escapeHtml(STATUS_LABELS_EN[status] || status)}</span></div>` : ""}
            ${rows.join("")}
        </div>
        ${info.description ? `<div class="v3d-detail-card"><div class="v3d-key" style="margin-bottom:.4rem;">Description</div><div style="font-size:.85rem;color:#cbd5e1;">${escapeHtml(info.description)}</div></div>` : ""}
    `;
}

export function renderSearchResults(listEl, items, onClick) {
    if (!items.length) {
        listEl.innerHTML = `<li style="color:#64748b;cursor:default;">No results.</li>`;
        return;
    }
    listEl.innerHTML = items.slice(0, 50).map((it, idx) => `
        <li data-idx="${idx}">
            ${escapeHtml(it.name)}
            <span class="v3d-mini-id">${escapeHtml(it.globalId || `eid ${it.expressID}`)}</span>
        </li>
    `).join("");
    listEl.querySelectorAll("li[data-idx]").forEach(li => {
        li.addEventListener("click", () => {
            const idx = Number(li.dataset.idx);
            onClick?.(items[idx]);
        });
    });
}

export function setLoading(overlayEl, textEl, visible, text) {
    if (visible) {
        overlayEl.classList.remove("hidden");
        if (text && textEl) textEl.textContent = text;
    } else {
        overlayEl.classList.add("hidden");
    }
}

export function showEmpty(emptyEl, visible) {
    emptyEl.classList.toggle("hidden", !visible);
}
