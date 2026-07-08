"""
Règles de validation IFC pour le réemploi des éléments de construction.
Priorités : C = Critique, O = Obligatoire, Opt = Optionnel
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Rule:
    name: str
    description: str
    attribute: str
    source: str          # "attribute" | "pset" | "qto" | "material" | "location"
    priority: str        # "C" | "O" | "Opt"
    pset_name: str = ""
    qto_name: str = ""
    data_type: str = ""
    check_not_empty: bool = True
    check_positive: bool = False


RULES: Dict[str, List[Rule]] = {
    "IfcDoor": [
        Rule("GlobalId", "Identifiant unique pour traçabilité et QR code", "GlobalId", "attribute", "C"),
        Rule("OverallHeight", "Hauteur de la porte — nécessaire pour calcul surface PEMD", "OverallHeight", "attribute", "C", check_positive=True),
        Rule("OverallWidth", "Largeur de la porte — nécessaire pour calcul surface PEMD", "OverallWidth", "attribute", "C", check_positive=True),
        Rule("Material", "Matériau constitutif — obligatoire pour classification DI/PEMD", "Material", "material", "C"),
        Rule("Name", "Nom de l'élément — identification dans le rapport", "Name", "attribute", "O"),
        Rule("ObjectType", "Type d'objet — classification CERFA", "ObjectType", "attribute", "O"),
        Rule("FireRating", "Résistance au feu — conformité réglementaire", "FireRating", "pset", "O", pset_name="Pset_DoorCommon"),
        Rule("NetArea", "Surface nette — quantité PEMD", "Width", "qto", "O", qto_name="Qto_DoorBaseQuantities", check_positive=True),
        Rule("AssessmentCondition", "État de conservation — PEMD col. 11", "AssessmentCondition", "pset", "O", pset_name="Pset_Condition"),
        Rule("ProductionYear", "Année de fabrication — âge estimé PEMD col. 10", "ProductionYear", "pset", "O", pset_name="Pset_ManufacturerTypeInformation"),
        Rule("OperationType", "Type d'ouverture — compatibilité réemploi", "OperationType", "attribute", "Opt"),
        Rule("IsExternal", "Porte extérieure ? — filière réemploi", "IsExternal", "pset", "Opt", pset_name="Pset_DoorCommon"),
        Rule("Location", "Localisation dans le bâtiment", "Location", "location", "Opt"),
    ],
    "IfcWindow": [
        Rule("GlobalId", "Identifiant unique pour traçabilité", "GlobalId", "attribute", "C"),
        Rule("OverallHeight", "Hauteur de la fenêtre — dimensions PEMD", "OverallHeight", "attribute", "C", check_positive=True),
        Rule("OverallWidth", "Largeur de la fenêtre — dimensions PEMD", "OverallWidth", "attribute", "C", check_positive=True),
        Rule("Material", "Matériau constitutif — classification DI/PEMD", "Material", "material", "C"),
        Rule("Name", "Nom de l'élément", "Name", "attribute", "O"),
        Rule("ThermalTransmittance", "Performance thermique", "ThermalTransmittance", "pset", "O", pset_name="Pset_WindowCommon"),
        Rule("NetArea", "Surface nette — quantité PEMD", "Area", "qto", "O", qto_name="Qto_WindowBaseQuantities", check_positive=True),
        Rule("AssessmentCondition", "État de conservation", "AssessmentCondition", "pset", "O", pset_name="Pset_Condition"),
        Rule("ProductionYear", "Année de fabrication", "ProductionYear", "pset", "O", pset_name="Pset_ManufacturerTypeInformation"),
        Rule("GlazingType", "Type de vitrage — DI verre", "GlazingType", "pset", "O", pset_name="Pset_WindowCommon"),
        Rule("IsOpening", "Fenêtre ouvrante ?", "IsOpening", "pset", "Opt", pset_name="Pset_WindowCommon"),
        Rule("Location", "Localisation dans le bâtiment", "Location", "location", "Opt"),
    ],
    "IfcWall": [
        Rule("GlobalId", "Identifiant unique", "GlobalId", "attribute", "C"),
        Rule("Material", "Matériau constitutif — DI classification", "Material", "material", "C"),
        Rule("Height", "Hauteur du mur — volume DI", "Height", "qto", "C", qto_name="Qto_WallBaseQuantities", check_positive=True),
        Rule("Length", "Longueur du mur — surface DI", "Length", "qto", "C", qto_name="Qto_WallBaseQuantities", check_positive=True),
        Rule("Width", "Épaisseur du mur — volume DI", "Width", "qto", "C", qto_name="Qto_WallBaseQuantities", check_positive=True),
        Rule("Name", "Nom de l'élément", "Name", "attribute", "O"),
        Rule("ObjectType", "Type de mur (porteur, cloison)", "ObjectType", "attribute", "O"),
        Rule("LoadBearing", "Mur porteur ? — réemployabilité structurelle", "LoadBearing", "pset", "O", pset_name="Pset_WallCommon"),
        Rule("IsExternal", "Mur extérieur ? — isolation → DNDNI", "IsExternal", "pset", "O", pset_name="Pset_WallCommon"),
        Rule("FireRating", "Résistance au feu", "FireRating", "pset", "O", pset_name="Pset_WallCommon"),
        Rule("AssessmentCondition", "État de conservation", "AssessmentCondition", "pset", "O", pset_name="Pset_Condition"),
        Rule("ThermalTransmittance", "Performance thermique", "ThermalTransmittance", "pset", "Opt", pset_name="Pset_WallCommon"),
        Rule("Location", "Localisation dans le bâtiment", "Location", "location", "Opt"),
    ],
    "IfcBeam": [
        Rule("GlobalId", "Identifiant unique", "GlobalId", "attribute", "C"),
        Rule("Material", "Matériau constitutif — DI", "Material", "material", "C"),
        Rule("Length", "Longueur de la poutre — volume DI", "Length", "qto", "C", qto_name="Qto_BeamBaseQuantities", check_positive=True),
        Rule("CrossSectionArea", "Section transversale — volume DI", "CrossSectionArea", "qto", "C", qto_name="Qto_BeamBaseQuantities", check_positive=True),
        Rule("Name", "Nom de l'élément", "Name", "attribute", "O"),
        Rule("LoadBearing", "Poutre structurelle ?", "Span", "pset", "O", pset_name="Pset_BeamCommon"),
        Rule("FireRating", "Résistance au feu", "FireRating", "pset", "O", pset_name="Pset_BeamCommon"),
        Rule("AssessmentCondition", "État de conservation", "AssessmentCondition", "pset", "O", pset_name="Pset_Condition"),
        Rule("ProfileType", "Type de profilé", "ProfileType", "attribute", "Opt"),
        Rule("NetVolume", "Volume net — masse DI", "NetVolume", "qto", "Opt", qto_name="Qto_BeamBaseQuantities"),
        Rule("Location", "Localisation", "Location", "location", "Opt"),
    ],
    "IfcSlab": [
        Rule("GlobalId", "Identifiant unique", "GlobalId", "attribute", "C"),
        Rule("Material", "Matériau constitutif — DI", "Material", "material", "C"),
        Rule("Thickness", "Épaisseur de la dalle", "Thickness", "attribute", "C", check_positive=True),
        Rule("NetArea", "Surface nette — volume DI", "GrossArea", "qto", "C", qto_name="Qto_SlabBaseQuantities", check_positive=True),
        Rule("Width", "Largeur", "Width", "qto", "C", qto_name="Qto_SlabBaseQuantities", check_positive=True),
        Rule("Name", "Nom de l'élément", "Name", "attribute", "O"),
        Rule("ObjectType", "Type de dalle (plancher, toiture)", "ObjectType", "attribute", "O"),
        Rule("LoadBearing", "Dalle porteuse ?", "LoadBearing", "pset", "O", pset_name="Pset_SlabCommon"),
        Rule("IsExternal", "Dalle extérieure ?", "IsExternal", "pset", "O", pset_name="Pset_SlabCommon"),
        Rule("FireRating", "Résistance au feu", "FireRating", "pset", "O", pset_name="Pset_SlabCommon"),
        Rule("AssessmentCondition", "État de conservation", "AssessmentCondition", "pset", "O", pset_name="Pset_Condition"),
        Rule("PitchAngle", "Pente (toiture)", "PitchAngle", "pset", "Opt", pset_name="Pset_SlabCommon"),
        Rule("Location", "Localisation", "Location", "location", "Opt"),
    ],
    "IfcStair": [
        Rule("GlobalId", "Identifiant unique", "GlobalId", "attribute", "C"),
        Rule("Material", "Matériau constitutif — DI", "Material", "material", "C"),
        Rule("NumberOfRiser", "Nombre de contremarches", "NumberOfRiser", "pset", "O", pset_name="Pset_StairCommon", check_positive=True),
        Rule("NumberOfTreads", "Nombre de marches", "NumberOfTreads", "pset", "O", pset_name="Pset_StairCommon", check_positive=True),
        Rule("TreadLength", "Longueur de marche", "TreadLength", "pset", "O", pset_name="Pset_StairCommon", check_positive=True),
        Rule("RiserHeight", "Hauteur de contremarche", "RiserHeight", "pset", "O", pset_name="Pset_StairCommon", check_positive=True),
        Rule("Name", "Nom de l'élément", "Name", "attribute", "O"),
        Rule("ObjectType", "Type d'escalier", "ObjectType", "attribute", "O"),
        Rule("LoadBearing", "Escalier porteur ?", "LoadBearing", "pset", "O", pset_name="Pset_StairCommon"),
        Rule("FireRating", "Résistance au feu", "FireRating", "pset", "O", pset_name="Pset_StairCommon"),
        Rule("AssessmentCondition", "État de conservation", "AssessmentCondition", "pset", "O", pset_name="Pset_Condition"),
        Rule("Location", "Localisation", "Location", "location", "Opt"),
    ],
    "IfcCurtainWall": [
        Rule("GlobalId", "Identifiant unique", "GlobalId", "attribute", "C"),
        Rule("Material", "Matériau constitutif — DI", "Material", "material", "C"),
        Rule("Height", "Hauteur du mur rideau", "Height", "qto", "C", qto_name="Qto_CurtainWallBaseQuantities", check_positive=True),
        Rule("Length", "Longueur du mur rideau", "Length", "qto", "C", qto_name="Qto_CurtainWallBaseQuantities", check_positive=True),
        Rule("Width", "Épaisseur du mur rideau", "Width", "qto", "C", qto_name="Qto_CurtainWallBaseQuantities", check_positive=True),
        Rule("Name", "Nom de l'élément", "Name", "attribute", "O"),
        Rule("ObjectType", "Type de mur rideau", "ObjectType", "attribute", "O"),
        Rule("IsExternal", "Mur rideau extérieur ?", "IsExternal", "pset", "O", pset_name="Pset_CurtainWallCommon"),
        Rule("FireRating", "Résistance au feu", "FireRating", "pset", "O", pset_name="Pset_CurtainWallCommon"),
        Rule("AssessmentCondition", "État de conservation", "AssessmentCondition", "pset", "O", pset_name="Pset_Condition"),
        Rule("Location", "Localisation", "Location", "location", "Opt"),
    ],
}
