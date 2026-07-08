"""
Injecte des corrections dans un fichier IFC.
Permet d'ajouter/modifier des attributs, propriétés, quantités et matériaux
selon les erreurs détectées par la validation.
"""
import io
import os
import ifcopenshell
from ifcopenshell import guid
from typing import Dict, List, Optional, Any


PSET_CORRECTIONS_NAME = "Pset_IFCAnalyzer_Corrections"


def fix_ifc_from_corrections(
    input_path: str,
    corrections: List[Dict[str, Any]],
    remove_original_pset: bool = False,
) -> bytes:
    """
    Ouvre un fichier IFC, applique les corrections, retourne les bytes modifiés.
    
    corrections: liste de dicts :
      {
        "element_id": "abc...",
        "attribute": "Height",
        "source": "qto",        # attribute | material | pset | qto
        "qto_name": "Qto_WallBaseQuantities",  # pour qto
        "pset_name": "Pset_WallCommon",        # pour pset
        "data_type": "IfcLengthMeasure",       # optionnel, pour qto
        "value": "3.5"
      }
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Fichier IFC non trouvé : {input_path}")

    ifc_file = ifcopenshell.open(input_path)
    owner_history = _get_or_create_owner_history(ifc_file)
    applied = 0

    for corr in corrections:
        element_id = corr.get("element_id")
        if not element_id:
            continue
        entity = _find_entity_by_guid(ifc_file, element_id)
        if not entity:
            continue
        try:
            source = corr.get("source", "")
            if source == "attribute":
                _fix_attribute(entity, corr["attribute"], corr.get("value", ""))
            elif source == "material":
                _fix_material(ifc_file, entity, corr.get("value", ""))
            elif source == "pset":
                _fix_pset(ifc_file, entity, owner_history,
                          corr["pset_name"], corr["attribute"], corr.get("value"))
            elif source == "qto":
                _fix_qto(ifc_file, entity, owner_history,
                         corr.get("qto_name", ""), corr["attribute"], corr.get("value"),
                         corr.get("data_type", "IfcLengthMeasure"))
            applied += 1
        except Exception:
            pass  # une correction échouée ne bloque pas les autres

    return _save_to_bytes(ifc_file)


def _find_entity_by_guid(ifc_file, guid_value: str):
    """Trouve une entité IFC par son GlobalId."""
    try:
        return ifc_file.by_guid(guid_value)
    except Exception:
        # Fallback : recherche manuelle
        for entity in ifc_file:
            try:
                if getattr(entity, "GlobalId", None) == guid_value:
                    return entity
            except Exception:
                continue
    return None


def _get_or_create_owner_history(ifc_file):
    histories = ifc_file.by_type("IfcOwnerHistory")
    if histories:
        return histories[0]
    person = ifc_file.create_entity("IfcPerson", Identification="IFCAnalyzer")
    org = ifc_file.create_entity("IfcOrganization", Name="IFCAnalyzer")
    p_and_o = ifc_file.create_entity("IfcPersonAndOrganization",
                                     ThePerson=person, TheOrganization=org)
    app = ifc_file.create_entity("IfcApplication",
        ApplicationDeveloper=org, Version="1.0",
        ApplicationFullName="IFC Analyzer", ApplicationIdentifier="IFCAnalyzer")
    return ifc_file.create_entity("IfcOwnerHistory",
        OwningUser=p_and_o, OwningApplication=app,
        ChangeAction="ADDED", CreationDate=0)


# ============================================================
# FIX: attribute
# ============================================================

ATTR_TYPE_MAP = {
    "OverallHeight": "IfcPositiveLengthMeasure",
    "OverallWidth": "IfcPositiveLengthMeasure",
    "Thickness": "IfcPositiveLengthMeasure",
}

def _fix_attribute(entity, name: str, value):
    """Modifie un attribut directement sur l'entité IFC."""
    parsed = _parse_value(value, ATTR_TYPE_MAP.get(name))
    try:
        setattr(entity, name, parsed)
    except Exception:
        pass


# ============================================================
# FIX: material
# ============================================================

def _fix_material(ifc_file, entity, value: str):
    """Associe ou remplace le matériau d'un élément."""
    if not value or not value.strip():
        return
    material_name = value.strip()

    # Chercher un matériau existant avec le même nom
    existing_mat = None
    for mat in ifc_file.by_type("IfcMaterial"):
        if getattr(mat, "Name", None) == material_name:
            existing_mat = mat
            break

    if not existing_mat:
        existing_mat = ifc_file.create_entity("IfcMaterial", Name=material_name)

    # Chercher une association existante
    for rel in ifc_file.by_type("IfcRelAssociatesMaterial"):
        related = getattr(rel, "RelatedObjects", None) or []
        if entity in related:
            # Remplacer le matériau
            rel.RelatingMaterial = existing_mat
            return

    # Créer une nouvelle association
    ifc_file.create_entity(
        "IfcRelAssociatesMaterial",
        GlobalId=guid.new(),
        RelatedObjects=[entity],
        RelatingMaterial=existing_mat,
    )


# ============================================================
# FIX: pset
# ============================================================

PSET_BOOLEAN_ATTRS = {"IsExternal", "IsOpening", "LoadBearing", "ExtendToStructure"}
PSET_INTEGER_ATTRS = {"NumberOfRiser", "NumberOfTreads", "ProductionYear"}
PSET_FLOAT_ATTRS = {"TreadLength", "RiserHeight", "ThermalTransmittance"}

def _pset_prop_type(prop_name: str, value_str: str):
    """Détermine le type IFC pour une propriété."""
    if prop_name in PSET_BOOLEAN_ATTRS:
        return "IfcBoolean"
    if prop_name in PSET_INTEGER_ATTRS:
        return "IfcInteger"
    if prop_name in PSET_FLOAT_ATTRS:
        return "IfcReal"
    return "IfcLabel"


def _fix_pset(ifc_file, entity, owner_history, pset_name: str, prop_name: str, value_str):
    """Ajoute/modifie une propriété dans un PropertySet."""
    value = _parse_value(value_str, _pset_prop_type(prop_name, value_str))
    if value is None:
        return

    pset = _find_or_create_pset(ifc_file, entity, owner_history, pset_name)

    # Supprimer une ancienne propriété du même nom si elle existe
    existing = _find_prop_in_pset(pset, prop_name)
    if existing:
        try:
            idx = pset.HasProperties.index(existing)
            pset.HasProperties.pop(idx)
        except (ValueError, AttributeError):
            pass

    new_prop = ifc_file.create_entity(
        "IfcPropertySingleValue",
        Name=prop_name,
        NominalValue=ifc_file.create_entity(
            _pset_prop_type(prop_name, value_str), value
        ),
    )
    current = list(getattr(pset, "HasProperties", []) or [])
    current.append(new_prop)
    pset.HasProperties = current


def _find_or_create_pset(ifc_file, entity, owner_history, pset_name: str):
    """Trouve un PropertySet existant ou le crée."""
    for rel in getattr(entity, "IsDefinedBy", []) or []:
        pset = getattr(rel, "RelatingPropertyDefinition", None)
        if pset and getattr(pset, "Name", "") == pset_name:
            return pset
    try:
        for rel in entity.IsDefinedBy_inverse:
            pset = rel.RelatingPropertyDefinition
            if hasattr(pset, "Name") and pset.Name == pset_name:
                return pset
    except Exception:
        pass

    # Créer un nouveau pset
    pset = ifc_file.create_entity(
        "IfcPropertySet",
        GlobalId=guid.new(),
        OwnerHistory=owner_history,
        Name=pset_name,
    )
    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=guid.new(),
        OwnerHistory=owner_history,
        RelatedObjects=[entity],
        RelatingPropertyDefinition=pset,
    )
    return pset


def _find_prop_in_pset(pset, prop_name: str):
    """Cherche une IfcPropertySingleValue par nom dans un pset."""
    for prop in getattr(pset, "HasProperties", []) or []:
        if getattr(prop, "Name", None) == prop_name:
            return prop
    return None


# ============================================================
# FIX: qto
# ============================================================

QTO_DEFAULTS = {
    "IfcWall": "Qto_WallBaseQuantities",
    "IfcDoor": "Qto_DoorBaseQuantities",
    "IfcWindow": "Qto_WindowBaseQuantities",
    "IfcSlab": "Qto_SlabBaseQuantities",
    "IfcBeam": "Qto_BeamBaseQuantities",
    "IfcCurtainWall": "Qto_CurtainWallBaseQuantities",
}

QTY_TYPE_MAP = {
    "Height": "IfcQuantityLength",
    "Length": "IfcQuantityLength",
    "Width": "IfcQuantityLength",
    "NetArea": "IfcQuantityArea",
    "GrossArea": "IfcQuantityArea",
    "CrossSectionArea": "IfcQuantityArea",
    "NetVolume": "IfcQuantityVolume",
    "NumberOfRiser": "IfcQuantityCount",
    "NumberOfTreads": "IfcQuantityCount",
}

QTY_VALUE_ATTR = {
    "IfcQuantityLength": "LengthValue",
    "IfcQuantityArea": "AreaValue",
    "IfcQuantityVolume": "VolumeValue",
    "IfcQuantityCount": "CountValue",
}


def _fix_qto(ifc_file, entity, owner_history, qto_name: str, qty_name: str,
             value_str: str, data_type: str = "IfcLengthMeasure"):
    """Ajoute/modifie une quantité dans un QuantitySet."""
    value = _parse_value(value_str, data_type)
    if value is None:
        return

    # Si le nom du Qto est vide, utiliser le Qto standard pour ce type d'entité
    if not qto_name or not qto_name.strip():
        entity_type = entity.is_a()
        qto_name = QTO_DEFAULTS.get(entity_type, "Qto_BaseQuantities")

    ifc_type = QTY_TYPE_MAP.get(qty_name, "IfcQuantityLength")
    qto = _find_or_create_qto(ifc_file, entity, owner_history, qto_name)

    # Supprimer une ancienne quantité du même nom
    existing = None
    for q in getattr(qto, "Quantities", []) or []:
        if getattr(q, "Name", None) == qty_name:
            existing = q
            break
    if existing:
        try:
            idx = qto.Quantities.index(existing)
            qto.Quantities.pop(idx)
        except (ValueError, AttributeError):
            pass

    value_attr = QTY_VALUE_ATTR.get(ifc_type, "LengthValue")
    new_qty = ifc_file.create_entity(
        ifc_type,
        Name=qty_name,
        **{value_attr: value},
    )
    current = list(getattr(qto, "Quantities", []) or [])
    current.append(new_qty)
    qto.Quantities = current


def _find_or_create_qto(ifc_file, entity, owner_history, qto_name: str):
    """Trouve un ElementQuantity existant ou le crée."""
    for rel in getattr(entity, "IsDefinedBy", []) or []:
        qto = getattr(rel, "RelatingPropertyDefinition", None)
        if qto and getattr(qto, "Name", "") == qto_name and qto.is_a("IfcElementQuantity"):
            return qto
    try:
        for rel in entity.IsDefinedBy_inverse:
            qto = rel.RelatingPropertyDefinition
            if hasattr(qto, "Name") and qto.Name == qto_name and qto.is_a("IfcElementQuantity"):
                return qto
    except Exception:
        pass

    # Créer un nouveau qto
    qto = ifc_file.create_entity(
        "IfcElementQuantity",
        GlobalId=guid.new(),
        OwnerHistory=owner_history,
        Name=qto_name,
        MethodOfMeasurement=None,
    )
    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=guid.new(),
        OwnerHistory=owner_history,
        RelatedObjects=[entity],
        RelatingPropertyDefinition=qto,
    )
    return qto


# ============================================================
# UTILS
# ============================================================

def _parse_value(value_str: str, data_type: str):
    """Convertit une valeur string en valeur typée pour IFC."""
    if value_str is None:
        return None
    s = str(value_str).strip()
    if not s:
        return None

    if data_type.startswith("IfcBoolean"):
        return s.lower() in ("true", "1", "oui", "yes")

    if data_type in ("IfcInteger", "IfcCountMeasure"):
        try:
            return int(float(s))
        except (TypeError, ValueError):
            return None

    if data_type in ("IfcReal", "IfcLengthMeasure", "IfcAreaMeasure",
                     "IfcVolumeMeasure", "IfcPositiveLengthMeasure"):
        try:
            return float(s)
        except (TypeError, ValueError):
            return None

    # String par défaut
    return s


def _save_to_bytes(ifc_file) -> bytes:
    """Sauvegarde un fichier IFC en mémoire et retourne les bytes."""
    try:
        return ifc_file.to_string().encode("utf-8")
    except Exception:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".ifc", delete=False)
        tmp.close()
        try:
            ifc_file.write(tmp.name)
            with open(tmp.name, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
