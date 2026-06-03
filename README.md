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
- **Authentification JWT** avec rôles `user`/`admin` pour sécuriser les routes API

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
- PostgreSQL

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

### 3. Configurer l'authentification (PostgreSQL + JWT)

Définir les variables d'environnement suivantes :

```bash
# Exemple local
set DATABASE_URL=postgresql+psycopg://bimloop:bimloop@localhost:5432/bimloop
set JWT_SECRET_KEY=change-me
set JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 4. Lancer le serveur

```bash
cd backend
python main.py
```

Ou avec uvicorn directement :

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Accéder à l'application

Ouvrir un navigateur et aller à : **http://localhost:8000**
Page de connexion : **http://localhost:8000/login**

## 🔧 Stack technique

- **Backend** : Python, FastAPI, ifcopenshell
- **Auth** : JWT, PostgreSQL
- **Frontend** : HTML, CSS, JavaScript (vanilla)
- **Icons** : Lucide Icons
- **Fonts** : Inter (Google Fonts)

## 📌 Notes

- Aucun Machine Learning utilisé
- Les règles de durabilité sont basées sur des règles simples (dictionnaires)
- L'interface est entièrement en français
