/**
 * IFCViewer — wrapper Three.js + web-ifc-three.
 *
 * Responsabilités :
 *   - Initialiser la scène / caméra / contrôles
 *   - Charger un fichier IFC (URL ou Blob)
 *   - Gérer le picking (raycaster) sur les sous-meshes IFC
 *   - Filtrer les éléments par catégorie IFC
 *   - Coloriser les éléments selon un statut
 *   - Recadrer / focus caméra sur un élément donné
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { IFCLoader } from "web-ifc-three";
import {
    IFCWALL, IFCWALLSTANDARDCASE, IFCCURTAINWALL,
    IFCDOOR, IFCWINDOW, IFCSLAB, IFCROOF, IFCSTAIR,
} from "web-ifc";

// ====== Mapping catégories pour les filtres ======
export const CATEGORY_TYPES = {
    walls:   [IFCWALL, IFCWALLSTANDARDCASE, IFCCURTAINWALL],
    doors:   [IFCDOOR],
    windows: [IFCWINDOW],
    slabs:   [IFCSLAB, IFCROOF],
    stairs:  [IFCSTAIR],
};

// ====== Couleurs de statut ======
export const STATUS_COLORS = {
    "in_building":   0x9ca3af,
    "démonté":       0xf97316,
    "transporté":    0x3b82f6,
    "stocké":        0xa855f7,
    "à réutiliser":  0x10b981,
    "réutilisé":     0x10b981,
    "à recycler":    0xef4444,
};
const DEFAULT_STATUS_COLOR = 0xcbd5e1;

export class IFCViewer {
    constructor(canvas) {
        this.canvas = canvas;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.ifcLoader = null;
        this.modelID = null;          // ID du modèle IFC chargé
        this.model = null;            // mesh IFC racine
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.highlightMat = new THREE.MeshLambertMaterial({
            transparent: true, opacity: 0.6, color: 0xfacc15, depthTest: false,
        });
        this.preselectMat = new THREE.MeshLambertMaterial({
            transparent: true, opacity: 0.4, color: 0xa78bfa, depthTest: false,
        });
        this._idCache = new Map();    // expressID → globalId
        this._propsCache = new Map(); // expressID → properties
        // État de filtre/coloration (pour la composition filtre + couleur)
        this._currentFilter = "all";       // clé de CATEGORY_TYPES ou "all"
        this._statusMap = null;            // Map<globalId, status> ou null si désactivé
        this._activeSubsetMeshes = new Map(); // customID → THREE.Mesh (pour picking)
        // Groupe dédié contenant tous les subsets (filtre + statut). Vider ce
        // groupe est la SEULE façon fiable de tout retirer de la scène : selon
        // les versions de web-ifc-three, `removeSubset` peut laisser des meshes
        // orphelins dans la scène.
        this._subsetGroup = new THREE.Group();
        this._subsetGroup.name = "ifc-subsets";
        this._rebuildToken = 0; // pour annuler les rebuilds concurrents
        this._init();
    }

    // ------------- Init Three.js -------------
    _init() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0f172a);

        const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
        this.camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000);
        this.camera.position.set(15, 15, 15);

        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.setSize(w, h, false);

        this.controls = new OrbitControls(this.camera, this.canvas);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;

        // Lumières
        const amb = new THREE.AmbientLight(0xffffff, 0.55);
        const dir = new THREE.DirectionalLight(0xffffff, 0.9);
        dir.position.set(20, 30, 20);
        this.scene.add(amb, dir);

        // Grille de référence
        const grid = new THREE.GridHelper(50, 50, 0x334155, 0x1e293b);
        grid.material.opacity = 0.4;
        grid.material.transparent = true;
        this.scene.add(grid);

        // Container pour tous les subsets de filtrage / coloration
        this.scene.add(this._subsetGroup);

        // Loader IFC — WASM servi par notre propre backend (/viewer3d-assets/)
        // pour éviter les problèmes de chemin bundlé par les CDN.
        this.ifcLoader = new IFCLoader();
        this._configureWasmPath();

        window.addEventListener("resize", () => this._onResize());
        this._animate();
    }

    _configureWasmPath() {
        // Le WASM web-ifc est servi par notre backend à /viewer3d-assets/
        // (chemin absolu, même origine que la page).
        const absolute = new URL("/viewer3d-assets/", window.location.origin).href;
        try {
            // Certaines versions acceptent (path, useAbsolute)
            this.ifcLoader.ifcManager.setWasmPath(absolute, true);
        } catch {
            this.ifcLoader.ifcManager.setWasmPath(absolute);
        }
    }

    _onResize() {
        const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h, false);
    }

    _animate() {
        requestAnimationFrame(() => this._animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    // ------------- Chargement IFC -------------
    async loadFromUrl(url, onProgress) {
        if (this.model) {
            await this._unload();
        }
        return new Promise((resolve, reject) => {
            this.ifcLoader.load(
                url,
                (ifcModel) => {
                    this.model = ifcModel;
                    this.modelID = ifcModel.modelID;
                    this.scene.add(ifcModel);
                    this._fitCameraToObject(ifcModel);
                    resolve(ifcModel);
                },
                (xhr) => onProgress?.(xhr),
                (err) => reject(err),
            );
        });
    }

    async loadFromBlob(blob, onProgress) {
        const url = URL.createObjectURL(blob);
        try {
            return await this.loadFromUrl(url, onProgress);
        } finally {
            // libère l'URL une fois le parse terminé
            setTimeout(() => URL.revokeObjectURL(url), 5000);
        }
    }

    async _unload() {
        if (this.modelID !== null) {
            // Retirer explicitement les subsets résiduels de la scène (ifcManager.dispose
            // ne nettoie pas toujours les meshes ajoutés à la scène par createSubset).
            for (const mesh of this._activeSubsetMeshes.values()) {
                this.scene.remove(mesh);
            }
            this._activeSubsetMeshes.clear();
            // Vider aussi notre groupe dédié (sécurité)
            while (this._subsetGroup.children.length) {
                const child = this._subsetGroup.children.pop();
                if (child.geometry) child.geometry.dispose?.();
            }

            await this.ifcLoader.ifcManager.dispose();
            this.scene.remove(this.model);
            this.model = null;
            this.modelID = null;
            this._idCache.clear();
            this._propsCache.clear();
            // Reset de l'état d'affichage pour le prochain modèle
            this._currentFilter = "all";
            this._statusMap = null;
            // Recréer l'IfcLoader car dispose() invalide l'instance
            this.ifcLoader = new IFCLoader();
            this._configureWasmPath();
        }
    }

    // ------------- Recadrage caméra -------------
    _fitCameraToObject(object, offset = 1.6) {
        const box = new THREE.Box3().setFromObject(object);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = this.camera.fov * (Math.PI / 180);
        const dist = (maxDim / (2 * Math.tan(fov / 2))) * offset;
        const dir = new THREE.Vector3(1, 0.6, 1).normalize();
        this.camera.position.copy(center).add(dir.multiplyScalar(dist));
        this.controls.target.copy(center);
        this.controls.update();
    }

    resetCamera() {
        if (this.model) this._fitCameraToObject(this.model);
    }

    // ------------- Picking -------------
    async pickAtPointer(event) {
        if (!this.model) return null;
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        this.raycaster.setFromCamera(this.mouse, this.camera);

        // Cible du raycast : si un filtre/coloriage est actif, le modèle complet
        // est caché mais Three.js raycaste quand même les objets non-visibles —
        // d'où des sélections "à travers" les murs filtrés. On limite donc le
        // raycast aux meshes effectivement affichés (filtre actif ou subsets de statut).
        let hits;
        if (this.model.visible) {
            hits = this.raycaster.intersectObject(this.model, true);
        } else {
            // Exclut le subset de surbrillance (sinon il intercepte tous les clics).
            const targets = [...this._activeSubsetMeshes.entries()]
                .filter(([id]) => id !== "selection-highlight")
                .map(([, mesh]) => mesh)
                .filter(m => m && m.visible);
            if (!targets.length) return null;
            hits = this.raycaster.intersectObjects(targets, true);
        }
        if (!hits || !hits.length) return null;

        const hit = hits[0];
        const expressID = this.ifcLoader.ifcManager.getExpressId(
            hit.object.geometry, hit.faceIndex,
        );
        if (expressID == null) return null;
        return await this.getElementInfo(expressID);
    }

    async getElementInfo(expressID) {
        let props = this._propsCache.get(expressID);
        if (!props) {
            try {
                props = await this.ifcLoader.ifcManager.getItemProperties(this.modelID, expressID);
                this._propsCache.set(expressID, props);
            } catch { return null; }
        }
        const globalId = props?.GlobalId?.value || null;
        if (globalId) this._idCache.set(expressID, globalId);

        // Type IFC humain
        const ifcType = await this.ifcLoader.ifcManager.getIfcType(this.modelID, expressID);

        // Matériaux
        let materialNames = [];
        try {
            const mats = await this.ifcLoader.ifcManager.getMaterialsProperties(this.modelID, expressID);
            materialNames = (mats || [])
                .map(m => m?.Name?.value)
                .filter(Boolean);
        } catch { /* ignore */ }

        // PropertySets pour dimensions / quantités
        let psets = [];
        try {
            psets = await this.ifcLoader.ifcManager.getPropertySets(this.modelID, expressID, true);
        } catch { /* ignore */ }

        return {
            expressID,
            globalId,
            name: props?.Name?.value || "(Sans nom)",
            ifcType,
            description: props?.Description?.value || null,
            materials: materialNames,
            psets,
            raw: props,
        };
    }

    // ------------- Highlight -------------
    async highlight(expressID, fly = true) {
        if (!this.model) return;
        const subset = this.ifcLoader.ifcManager.createSubset({
            modelID: this.modelID,
            ids: [expressID],
            material: this.highlightMat,
            scene: this.scene,
            removePrevious: true,
            customID: "selection-highlight",
        });
        if (subset) this._activeSubsetMeshes.set("selection-highlight", subset);
        if (fly && subset) this._fitCameraToObject(subset, 2.4);
    }

    clearHighlight() {
        if (!this.model) return;
        this.ifcLoader.ifcManager.removeSubset(this.modelID, this.highlightMat, "selection-highlight");
        this._activeSubsetMeshes.delete("selection-highlight");
    }

    // ------------- Helpers internes (filtre + couleur) -------------
    /** Récupère tous les expressIDs d'une catégorie de filtre. */
    async _idsOfCategory(categoryKey) {
        const types = CATEGORY_TYPES[categoryKey];
        if (!types) return [];
        const ids = [];
        for (const t of types) {
            const idsOfType = await this.ifcLoader.ifcManager.getAllItemsOfType(this.modelID, t, false);
            ids.push(...idsOfType);
        }
        return ids;
    }

    /** Crée (et trace) un subset, retire l'ancien de même customID s'il existe. */
    _addSubset(customID, ids, material) {
        if (this._activeSubsetMeshes.has(customID)) {
            this.ifcLoader.ifcManager.removeSubset(this.modelID, undefined, customID);
            this._activeSubsetMeshes.delete(customID);
        }
        if (!ids || !ids.length) return null;
        const opts = {
            modelID: this.modelID,
            ids,
            scene: this.scene,
            removePrevious: true,
            customID,
            applyBVH: false,
        };
        if (material) opts.material = material;
        const mesh = this.ifcLoader.ifcManager.createSubset(opts);
        if (mesh) {
            // Reparenter dans notre groupe dédié pour pouvoir tout nettoyer
            // d'un coup au prochain rebuild (et éviter les fuites visuelles).
            if (mesh.parent !== this._subsetGroup) this._subsetGroup.attach(mesh);
            this._activeSubsetMeshes.set(customID, mesh);
        }
        return mesh;
    }

    /** Retire tous les subsets de catégorie + statut (garde le highlight).
     *  IMPORTANT : selon les versions de web-ifc-three, `removeSubset` ne retire
     *  pas toujours le mesh de la scène quand on passe `material=undefined`.
     *  On retire donc explicitement le mesh nous-mêmes pour éviter que les
     *  anciens subsets colorés restent visibles après un changement de filtre
     *  ou la désactivation du toggle "Enable". */
    _removeFilterAndStatusSubsets() {
        // 1) Demander à web-ifc-three de libérer ses subsets internes
        for (const customID of this._activeSubsetMeshes.keys()) {
            if (customID === "selection-highlight") continue;
            try { this.ifcLoader.ifcManager.removeSubset(this.modelID, undefined, customID); } catch { /* ignore */ }
        }
        // 2) Vider complètement notre groupe → garantit qu'aucun mesh résiduel
        //    ne reste affiché, même si removeSubset n'a rien fait.
        while (this._subsetGroup.children.length) {
            const child = this._subsetGroup.children.pop();
            if (child.geometry) child.geometry.dispose?.();
        }
        // 3) Conserver uniquement le highlight de sélection dans notre index
        const hl = this._activeSubsetMeshes.get("selection-highlight");
        this._activeSubsetMeshes.clear();
        if (hl) this._activeSubsetMeshes.set("selection-highlight", hl);
    }

    /**
     * Construit les subsets colorés par statut, éventuellement restreints
     * à un ensemble d'expressIDs (filtre catégorie actif).
     * @param {Map<string,string>} statusByGlobalId
     * @param {Set<number>|null} restrictExpressIds  Si non-null, ne traite que ces IDs.
     * @param {boolean} includeRest  Si true, crée un subset neutre pour les éléments
     *                               sans statut (utile en mode filtre). Si false, on
     *                               ne colore QUE les éléments ayant un statut
     *                               (utilisé en mode "All" pour ne pas noyer les
     *                               quelques composants colorés sous une mer de gris).
     */
    async _buildStatusSubsets(statusByGlobalId, restrictExpressIds, includeRest = true) {
        const allTypes = [
            ...CATEGORY_TYPES.walls, ...CATEGORY_TYPES.doors,
            ...CATEGORY_TYPES.windows, ...CATEGORY_TYPES.slabs, ...CATEGORY_TYPES.stairs,
        ];
        const idsByStatus = {};
        const restIds = [];
        for (const t of allTypes) {
            const eids = await this.ifcLoader.ifcManager.getAllItemsOfType(this.modelID, t, false);
            for (const eid of eids) {
                if (restrictExpressIds && !restrictExpressIds.has(eid)) continue;
                let gid = this._idCache.get(eid);
                if (!gid) {
                    try {
                        const p = await this.ifcLoader.ifcManager.getItemProperties(this.modelID, eid);
                        gid = p?.GlobalId?.value;
                        if (gid) this._idCache.set(eid, gid);
                    } catch { /* skip */ }
                }
                if (!gid) { restIds.push(eid); continue; }
                const status = statusByGlobalId.get(gid);
                if (!status) { restIds.push(eid); continue; }
                (idsByStatus[status] = idsByStatus[status] || []).push(eid);
            }
        }
        if (includeRest && restIds.length) {
            const restMat = new THREE.MeshLambertMaterial({ color: DEFAULT_STATUS_COLOR, transparent: false });
            this._addSubset("status-rest", restIds, restMat);
        }
        for (const [status, ids] of Object.entries(idsByStatus)) {
            const color = STATUS_COLORS[status] ?? DEFAULT_STATUS_COLOR;
            const mat = new THREE.MeshLambertMaterial({ color, transparent: false });
            this._addSubset(`status-${status}`, ids, mat);
        }
    }

    /** Re-construit l'affichage à partir de l'état (_currentFilter + _statusMap). */
    async _rebuildDisplay() {
        if (!this.model) return;
        // Annule tout rebuild concurrent encore en vol (sinon un clic rapide
        // sur plusieurs chips peut interleaver deux constructions de subsets
        // et laisser des meshes orphelins en scène).
        const token = ++this._rebuildToken;
        this._removeFilterAndStatusSubsets();
        const isStale = () => token !== this._rebuildToken;

        const filterActive = this._currentFilter && this._currentFilter !== "all";
        const colorActive  = this._statusMap && this._statusMap.size > 0;

        if (!filterActive && !colorActive) {
            this.model.visible = true;
            return;
        }

        if (filterActive) {
            this.model.visible = false;
            const ids = await this._idsOfCategory(this._currentFilter);
            if (isStale()) return;
            const restrictSet = new Set(ids);
            if (colorActive) {
                await this._buildStatusSubsets(this._statusMap, restrictSet, /*includeRest*/ true);
            } else {
                this._addSubset("category-filter", ids, null);
            }
        } else {
            // Pas de filtre, juste coloration par statut → on GARDE le modèle
            // d'origine visible et on overlay uniquement les composants AVEC un
            // statut. Sinon, sur un IFC de 6000 composants dont une poignée ont
            // un statut, les quelques éléments colorés se noient dans une mer
            // de gris neutre et l'utilisateur a l'impression que rien n'est coloré.
            this.model.visible = true;
            await this._buildStatusSubsets(this._statusMap, null, /*includeRest*/ false);
            if (isStale()) this._removeFilterAndStatusSubsets();
        }
    }

    // ------------- Filtres par catégorie -------------
    async filterByCategory(categoryKey) {
        if (!this.model) return;
        this._currentFilter = categoryKey || "all";
        await this._rebuildDisplay();
    }

    // ------------- Coloration par statut -------------
    /**
     * Hide the base IFC model and replace it with colored subsets per status.
     * Composes with the active category filter: only elements of the filtered
     * category get colored. Typed elements without status get a neutral
     * "rest" subset so the whole building (or category) stays visible.
     * @param {Map<string, string>} statusByGlobalId
     */
    async colorByStatus(statusByGlobalId) {
        if (!this.model) return;
        this._statusMap = (statusByGlobalId && statusByGlobalId.size) ? statusByGlobalId : null;
        await this._rebuildDisplay();
    }

    async clearStatusColoring() {
        if (!this.model) return;
        this._statusMap = null;
        await this._rebuildDisplay();
    }

    // ------------- Listing pour la recherche -------------
    /** Retourne [{expressID, globalId, name, ifcType}, ...] pour les types principaux. */
    async listSearchableElements() {
        if (!this.model) return [];
        const out = [];
        const types = [
            ...CATEGORY_TYPES.walls, ...CATEGORY_TYPES.doors,
            ...CATEGORY_TYPES.windows, ...CATEGORY_TYPES.slabs, ...CATEGORY_TYPES.stairs,
        ];
        for (const t of types) {
            const ids = await this.ifcLoader.ifcManager.getAllItemsOfType(this.modelID, t, false);
            for (const eid of ids) {
                try {
                    const p = await this.ifcLoader.ifcManager.getItemProperties(this.modelID, eid);
                    out.push({
                        expressID: eid,
                        globalId: p?.GlobalId?.value || null,
                        name: p?.Name?.value || "(Sans nom)",
                    });
                } catch { /* skip */ }
            }
        }
        return out;
    }

    setWireframe(on) {
        if (!this.model) return;
        this.model.traverse(obj => {
            if (obj.material) {
                if (Array.isArray(obj.material)) obj.material.forEach(m => m.wireframe = on);
                else obj.material.wireframe = on;
            }
        });
    }
}
