# IFC Analyzer — Analyse de Durabilité

Application web MVP pour analyser des fichiers IFC (Building Information Model) et extraire des informations utiles pour une analyse de durabilité.

## 🧩 Fonctionnalités

- **Upload** de fichiers `.ifc`
- **Extraction** automatique : Murs, Fenêtres, Dalles, Escaliers, Murs rideaux
- **Dimensions** : hauteur, longueur, épaisseur, volume
- **Matériaux** : extraction automatique depuis le fichier IFC
- **Durabilité** : recyclabilité et réutilisabilité de chaque élément
- **Filtres** dynamiques par type d'élément
- **Résumé** global avec statistiques et pourcentages

## 📁 Structure du projet

```
ifc-analyzer/
├── backend/
│   ├── main.py          # Serveur FastAPI
│   ├── ifc_parser.py    # Extraction des données IFC
│   ├── utils.py         # Calculs et règles de durabilité
│   └── __init__.py
├── frontend/
│   ├── index.html       # Page principale
│   ├── styles.css       # Styles CSS
│   └── script.js        # Logique frontend
├── requirements.txt     # Dépendances Python
└── README.md
```

## 🚀 Installation et lancement

### Prérequis

- Python 3.9+
- pip

### 1. Créer un environnement virtuel (recommandé)

```bash
cd ifc-analyzer
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Lancer le serveur

```bash
cd backend
python main.py
```

Ou avec uvicorn directement :

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Accéder à l'application

Ouvrir un navigateur et aller à : **http://localhost:8000**

## 🔧 Stack technique

- **Backend** : Python, FastAPI, ifcopenshell
- **Frontend** : HTML, CSS, JavaScript (vanilla)
- **Icons** : Lucide Icons
- **Fonts** : Inter (Google Fonts)

## 📌 Notes

- Aucun Machine Learning utilisé
- Les règles de durabilité sont basées sur des règles simples (dictionnaires)
- L'interface est entièrement en français
