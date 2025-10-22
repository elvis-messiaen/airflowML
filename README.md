# Pipeline de Machine Learning avec Apache Airflow

## Description du Projet

Ce projet implémente un pipeline complet de Machine Learning utilisant Apache Airflow pour orchestrer l'ensemble du processus d'apprentissage automatique. Le pipeline effectue la prédiction de clics sur des publicités en ligne en utilisant un modèle de régression logistique.

Le système est conçu pour automatiser l'ensemble du cycle de vie d'un modèle de Machine Learning, depuis le chargement des données brutes jusqu'à la mise à disposition d'une API Flask permettant de visualiser les résultats de l'exécution.

## Architecture du Projet

### Vue d'ensemble

Le projet est structuré autour de deux DAGs (Directed Acyclic Graphs) Airflow principaux :

1. **Airflow_Lab2** : Pipeline principal de Machine Learning
2. **Airflow_Lab2_Flask** : Gestion du cycle de vie de l'API Flask

### Structure des Répertoires

```
airflowML/
│
├── dags/                          # Répertoire contenant les DAGs Airflow
│   ├── main.py                    # DAG principal du pipeline ML
│   ├── Flask_API.py               # DAG de gestion de l'API Flask
│   ├── data/                      # Données sources
│   │   ├── __init__.py
│   │   └── advertising.csv        # Dataset des publicités (107 KB)
│   ├── src/                       # Code source du pipeline ML
│   │   ├── __init__.py
│   │   └── model_development.py  # Fonctions de traitement et modélisation
│   └── templates/                 # Templates HTML pour l'API Flask
│       ├── success.html           # Page affichée en cas de succès
│       └── failure.html           # Page affichée en cas d'échec
│
├── model/                         # Modèles ML sauvegardés
│   └── model.sav                  # Modèle de régression logistique sérialisé
│
├── working_data/                  # Données intermédiaires du pipeline
│   ├── raw.pkl                    # Données brutes sérialisées
│   └── preprocessed.pkl           # Données prétraitées et divisées
│
├── configuration/                 # Fichiers de configuration Airflow
│   └── airflow.cfg               # Configuration personnalisée
│
├── logs/                          # Logs d'exécution Airflow
│
├── requirements.txt               # Dépendances Python du projet
├── setup.sh                       # Script de configuration Docker
├── .gitignore                     # Fichiers à ignorer par Git
└── airflow.cfg                    # Configuration Airflow racine

```

## Composants Principaux

### 1. Pipeline Principal (main.py)

Le DAG principal `Airflow_Lab2` orchestre l'ensemble du processus de Machine Learning avec les tâches suivantes :

#### Tâches du Pipeline

**a. task_using_linked_owner**
- Type : BashOperator
- Fonction : Tâche initiale d'identification du propriétaire
- Commande : `echo 1`
- Propriétaire : Elvis MESSIAEN

**b. load_data_task**
- Type : PythonOperator
- Fonction : Charge le fichier CSV des publicités
- Entrée : `dags/data/advertising.csv`
- Sortie : `working_data/raw.pkl`
- Implémentation : Lecture du CSV et sérialisation en pickle

**c. data_preprocessing_task**
- Type : PythonOperator
- Fonction : Prétraitement des données
- Opérations effectuées :
  - Suppression des colonnes non pertinentes (Timestamp, Ad Topic Line, Country, City)
  - Séparation des features (X) et de la cible (y = Clicked on Ad)
  - Division train/test (70/30) avec random_state=42
  - Normalisation des features numériques (MinMaxScaler et StandardScaler)
- Sortie : `working_data/preprocessed.pkl` contenant (X_train, X_test, y_train, y_test)

**d. separate_data_outputs_task**
- Type : PythonOperator
- Fonction : Fonction de passage pour maintenir la composition du DAG
- Opération : Retourne le chemin du fichier sans modification

**e. build_save_model_task**
- Type : PythonOperator
- Fonction : Construction et sauvegarde du modèle
- Algorithme : Régression Logistique (LogisticRegression de scikit-learn)
- Sortie : `model/model.sav`
- Processus :
  - Chargement des données d'entraînement
  - Entraînement du modèle
  - Sérialisation du modèle en pickle

**f. load_model_task**
- Type : PythonOperator
- Fonction : Chargement et évaluation du modèle
- Opérations :
  - Chargement du modèle sauvegardé
  - Calcul du score sur les données de test
  - Affichage du score dans les logs
  - Retour de la première prédiction

**g. send_email**
- Type : EmailOperator
- Fonction : Notification par email après le chargement du modèle
- Destinataire : elvism72@gmail.com
- Connexion : smtp_gmail
- Contenu : Confirmation de l'exécution du pipeline

**h. my_trigger_task**
- Type : TriggerDagRunOperator
- Fonction : Déclenchement du DAG Flask
- Mode : Asynchrone (wait_for_completion=False)
- Règle de déclenchement : ALL_DONE (s'exécute même en cas d'échec partiel)

#### Flux d'Exécution du Pipeline

```
task_using_linked_owner
    ↓
load_data_task
    ↓
data_preprocessing_task
    ↓
separate_data_outputs_task
    ↓
build_save_model_task
    ↓
load_model_task
    ↓
├─→ my_trigger_task
└─→ send_email
```

#### Configuration du DAG Principal

- **ID** : `Airflow_Lab2`
- **Description** : Pipeline ML pour la prédiction de clics publicitaires avec régression logistique
- **Planification** : Quotidienne (`@daily`)
- **Catchup** : Désactivé (ne réexécute pas les dates passées)
- **Tags** : `machine-learning`, `pipeline`, `production`
- **Callback d'échec** : `envoyer_email_echec()` - Envoie un email détaillé en cas d'erreur
- **Exécutions actives max** : 1 (évite les exécutions concurrentes)

### 2. API Flask (Flask_API.py)

Le DAG `Airflow_Lab2_Flask` gère le déploiement d'une API Flask permettant de consulter l'état du pipeline principal.

#### Endpoints de l'API

**a. GET /**
- Fonction : Redirection automatique
- Logique : Redirige vers `/success` ou `/failure` selon l'état du dernier run

**b. GET /success**
- Fonction : Affiche la page de succès
- Template : `templates/success.html`
- Informations affichées :
  - État de l'exécution
  - ID du run
  - Date logique
  - Date de début
  - Date de fin

**c. GET /failure**
- Fonction : Affiche la page d'échec
- Template : `templates/failure.html`
- Informations affichées :
  - État de l'exécution
  - Message d'erreur
  - Détails du run

**d. GET /health**
- Fonction : Health check
- Réponse : `ok` avec code 200

#### Fonctionnement de l'API

L'API Flask interroge l'API REST Airflow (`/api/v2`) pour récupérer l'état de la dernière exécution du DAG principal :

- **URL de l'API Airflow** : `http://airflow-apiserver:8080/api/v2/dags/Airflow_Lab2/dagRuns`
- **Authentification** : Basic Auth (FAB API)
- **Paramètres de requête** :
  - `order_by=-logical_date` : Trie par date décroissante
  - `limit=1` : Récupère uniquement la dernière exécution

#### Configuration du DAG Flask

- **ID** : `Airflow_Lab2_Flask`
- **Description** : DAG to manage Flask API lifecycle
- **Planification** : None (déclenchement manuel uniquement)
- **Tags** : `Flask_Api`
- **Port d'écoute** : 5555
- **Host** : 0.0.0.0 (accessible depuis l'extérieur)

### 3. Module de Développement du Modèle (model_development.py)

Ce module contient toutes les fonctions de traitement et de modélisation utilisées par le pipeline.

#### Fonctions Principales

**load_data() -> str**
- Charge le fichier CSV des publicités
- Retourne le chemin du fichier pickle contenant le DataFrame brut
- Gère la création automatique des répertoires nécessaires

**data_preprocessing(file_path: str) -> str**
- Charge les données brutes depuis le pickle
- Effectue le prétraitement complet :
  - Suppression des colonnes textuelles et temporelles
  - Division train/test (30% pour le test)
  - Application de transformations sur les colonnes numériques :
    - MinMaxScaler : Normalise les valeurs entre 0 et 1
    - StandardScaler : Standardise avec moyenne 0 et écart-type 1
- Retourne le chemin du fichier contenant les données prétraitées

**separate_data_outputs(file_path: str) -> str**
- Fonction de passage (passthrough)
- Maintenue pour la compatibilité avec la composition du DAG
- Retourne le chemin sans modification

**build_model(file_path: str, filename: str) -> str**
- Charge les données d'entraînement prétraitées
- Crée et entraîne un modèle de régression logistique
- Sauvegarde le modèle dans le répertoire `model/`
- Retourne le chemin du modèle sauvegardé

**load_model(file_path: str, filename: str) -> int**
- Charge le modèle sauvegardé
- Évalue les performances sur les données de test
- Affiche le score dans les logs
- Retourne la première prédiction sous forme d'entier

#### Variables de Configuration

```python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKING_DIR = os.path.join(BASE_DIR, "working_data")
MODEL_DIR = os.path.join(BASE_DIR, "model")
```

Ces variables garantissent que les chemins sont relatifs au projet local, assurant la portabilité du code.

## Dataset : Advertising.csv

### Description

Le dataset contient des informations sur le comportement des utilisateurs face aux publicités en ligne. Il est utilisé pour prédire si un utilisateur va cliquer sur une publicité.

### Colonnes du Dataset

| Colonne | Type | Description | Utilisation |
|---------|------|-------------|-------------|
| **Daily Time Spent on Site** | Numérique | Temps quotidien passé sur le site (minutes) | Feature (normalisée) |
| **Age** | Numérique | Âge de l'utilisateur (années) | Feature (normalisée) |
| **Area Income** | Numérique | Revenu moyen de la zone géographique | Feature (normalisée) |
| **Daily Internet Usage** | Numérique | Utilisation quotidienne d'Internet (minutes) | Feature (normalisée) |
| **Male** | Binaire | Genre de l'utilisateur (1=Homme, 0=Femme) | Feature (normalisée) |
| **Timestamp** | Temporel | Horodatage de l'événement | Supprimée (non pertinente) |
| **Clicked on Ad** | Binaire | L'utilisateur a cliqué sur la publicité (0/1) | Variable cible |
| **Ad Topic Line** | Texte | Sujet de la publicité | Supprimée (texte) |
| **City** | Texte | Ville de l'utilisateur | Supprimée (texte) |
| **Country** | Texte | Pays de l'utilisateur | Supprimée (texte) |

### Prétraitement Appliqué

1. **Suppression des colonnes** : Timestamp, Ad Topic Line, City, Country
2. **Normalisation** : Application de MinMaxScaler et StandardScaler sur les features numériques
3. **Division** : 70% entraînement, 30% test (stratification non spécifiée)

## Dépendances et Technologies

### Dépendances Python (requirements.txt)

```
apache-airflow          # Orchestration de workflows
dvc[gs]                 # Gestion de versions de données avec support Google Cloud Storage
scikit-learn            # Bibliothèque de Machine Learning
scipy                   # Calculs scientifiques
pandas                  # Manipulation de données tabulaires
numpy                   # Calculs numériques
fastapi                 # Framework API moderne (non utilisé dans ce projet)
uvicorn                 # Serveur ASGI pour FastAPI
httpx                   # Client HTTP asynchrone
pydantic                # Validation de données
python-multipart        # Parsing de formulaires multipart
joblib                  # Sérialisation d'objets Python
```

### Technologies Utilisées

- **Apache Airflow** : Orchestration et planification des tâches
- **Flask** : API web pour la visualisation des résultats
- **scikit-learn** : Algorithmes de Machine Learning
- **pandas** : Manipulation et analyse de données
- **pickle** : Sérialisation des données et modèles
- **SMTP** : Envoi de notifications par email

## Installation et Configuration

### Prérequis

- Python 3.8 ou supérieur
- Apache Airflow 2.0 ou supérieur
- Accès SMTP pour l'envoi d'emails (Gmail configuré)
- Docker (optionnel, si utilisation de setup.sh)

### Installation Locale

#### Étape 1 : Cloner le Projet

```bash
git clone <URL_DU_REPOSITORY>
cd airflowML
```

#### Étape 2 : Créer un Environnement Virtuel

```bash
python3 -m venv .venv
source .venv/bin/activate  # Sur Linux/Mac
# ou
.venv\Scripts\activate     # Sur Windows
```

#### Étape 3 : Installer les Dépendances

```bash
pip install -r requirements.txt
```

#### Étape 4 : Configurer Airflow

```bash
# Initialiser la base de données Airflow
airflow db init

# Créer un utilisateur admin
airflow users create \
    --username airflow \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password airflow
```

#### Étape 5 : Configurer la Connexion SMTP

Dans l'interface web d'Airflow (Admin > Connections), créer une connexion nommée `smtp_gmail` :

- **Conn Id** : `smtp_gmail`
- **Conn Type** : `Email`
- **Host** : `smtp.gmail.com`
- **Login** : Votre adresse Gmail
- **Password** : Mot de passe d'application Gmail
- **Port** : `587`
- **Extra** : `{"use_tls": true}`

### Installation avec Docker

#### Étape 1 : Exécuter le Script de Configuration

```bash
chmod +x setup.sh
./setup.sh
```

Ce script effectue les opérations suivantes :
- Supprime les anciens conteneurs et volumes
- Crée les répertoires nécessaires (logs, plugins, config)
- Configure l'UID utilisateur dans `.env`
- Affiche la configuration Airflow

#### Étape 2 : Démarrer les Conteneurs

```bash
docker compose up -d
```

## Utilisation

### Démarrage d'Airflow

#### Mode Local

```bash
# Terminal 1 : Scheduler
airflow scheduler

# Terminal 2 : Webserver
airflow webserver --port 8080
```

#### Mode Docker

```bash
docker compose up -d
```

### Exécution du Pipeline

#### Interface Web

1. Accéder à l'interface Airflow : `http://localhost:8080`
2. Se connecter avec les identifiants (airflow/airflow)
3. Activer le DAG `Airflow_Lab2`
4. Déclencher l'exécution manuellement ou attendre la planification quotidienne

#### Ligne de Commande

```bash
# Déclencher manuellement le DAG principal
airflow dags trigger Airflow_Lab2

# Vérifier l'état d'exécution
airflow dags list-runs -d Airflow_Lab2

# Consulter les logs d'une tâche spécifique
airflow tasks test Airflow_Lab2 load_data_task 2024-01-01
```

### Accès à l'API Flask

Une fois le pipeline exécuté et l'API démarrée :

```bash
# Vérifier l'état de santé de l'API
curl http://localhost:5555/health

# Accéder à la page principale (redirection automatique)
curl -L http://localhost:5555/

# Consulter directement la page de succès
curl http://localhost:5555/success

# Consulter directement la page d'échec
curl http://localhost:5555/failure
```

Ou ouvrir dans un navigateur : `http://localhost:5555`

### Arrêt du Système

#### Mode Local

```bash
# Arrêter Airflow (Ctrl+C dans chaque terminal)
# Puis :
airflow db reset  # (optionnel) Réinitialiser la base de données
```

#### Mode Docker

```bash
# Arrêter les conteneurs
docker compose down

# Arrêter et supprimer les volumes
docker compose down -v
```

## Gestion des Erreurs et Notifications

### Callback d'Échec

La fonction `envoyer_email_echec(context)` est automatiquement appelée en cas d'échec d'une tâche :

```python
def envoyer_email_echec(context):
    """
    Fonction callback pour envoyer un email en cas d'échec du DAG.

    Args:
        context: Contexte Airflow contenant les informations de l'exécution
    """
    # Récupération des informations du contexte
    task_instance = context.get('task_instance')
    dag_run = context.get('dag_run')

    # Envoi d'un email détaillé avec :
    # - Nom du DAG
    # - Tâche échouée
    # - Date d'exécution
    # - Lien vers les logs
```

### Notifications Email

Deux types de notifications sont envoyés :

1. **Email de succès** : Après l'exécution réussie de `load_model_task`
   - Sujet : "Test Airflow MailDev"
   - Contenu : Confirmation de l'exécution

2. **Email d'échec** : En cas d'erreur dans n'importe quelle tâche
   - Sujet : "Échec du Pipeline ML - Airflow_Lab2"
   - Contenu : Détails de l'erreur et informations de débogage

### Logs

Les logs sont stockés dans le répertoire `logs/` avec la structure suivante :

```
logs/
└── dag_id=Airflow_Lab2/
    └── run_id=manual__2024-01-01T00:00:00+00:00/
        └── task_id=load_data_task/
            └── attempt=1.log
```

Consultation des logs :
- Interface web : Cliquer sur une tâche puis "Log"
- Ligne de commande : `airflow tasks logs Airflow_Lab2 load_data_task 2024-01-01`

## Métriques et Performances

### Évaluation du Modèle

Le modèle de régression logistique est évalué sur l'ensemble de test avec la métrique par défaut de scikit-learn (accuracy pour la classification).

```python
score = model.score(X_test, y_test)
print(f"Model score on test data: {score}")
```

Le score est affiché dans les logs de la tâche `load_model_task`.

### Amélioration Potentielle des Métriques

Pour un projet de production, il serait recommandé d'ajouter :
- **Précision** : Proportion de prédictions positives correctes
- **Rappel** : Proportion de cas positifs correctement identifiés
- **F1-Score** : Moyenne harmonique de la précision et du rappel
- **Matrice de confusion** : Visualisation des vrais/faux positifs/négatifs
- **Courbe ROC et AUC** : Évaluation de la capacité de discrimination

## Architecture Technique

### Flux de Données

```
advertising.csv (CSV brut)
    ↓
raw.pkl (DataFrame sérialisé)
    ↓
[Prétraitement + Division + Normalisation]
    ↓
preprocessed.pkl (X_train, X_test, y_train, y_test)
    ↓
[Entraînement Régression Logistique]
    ↓
model.sav (Modèle sérialisé)
    ↓
[Évaluation + Prédictions]
    ↓
API Flask + Logs + Email
```

### Sérialisation

Le projet utilise **pickle** pour la sérialisation :
- **Avantages** : Simple, natif Python, rapide
- **Inconvénients** : Non sécurisé, dépendant de la version Python
- **Alternative recommandée** : joblib pour les modèles scikit-learn (plus efficace)

### Gestion de la Concurrence

Le DAG principal est configuré avec `max_active_runs=1`, ce qui signifie :
- Une seule exécution à la fois
- Les nouvelles exécutions attendent la fin de l'exécution en cours
- Évite les conflits d'accès aux fichiers (pickle)

## Bonnes Pratiques Implémentées

### Clean Code

Le code respecte les principes du Clean Code :

1. **Responsabilité unique** : Chaque fonction a un rôle unique et bien défini
2. **Nommage explicite** : Les noms de fonctions et variables sont clairs
3. **Pas de logique cachée** : Le flux d'exécution est transparent
4. **Découpage en petites briques** : Fonctions modulaires et réutilisables

### Gestion des Chemins

Utilisation de chemins relatifs au projet :

```python
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

Cela garantit la portabilité du code entre différents environnements.

### Création Automatique des Répertoires

```python
os.makedirs(WORKING_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
```

Évite les erreurs de fichiers manquants lors de la première exécution.

### Isolation des Environnements

Utilisation d'un environnement virtuel Python (`.venv/`) pour isoler les dépendances du projet.

## Limitations et Améliorations Futures

### Limitations Actuelles

1. **Modèle simple** : Régression logistique basique sans optimisation des hyperparamètres
2. **Pas de validation croisée** : Division unique train/test
3. **Pas de feature engineering avancé** : Suppression directe des colonnes textuelles
4. **Sérialisation pickle** : Moins efficace que joblib pour les modèles ML
5. **API Flask bloquante** : L'API utilise le serveur de développement Flask
6. **Pas de tests unitaires** : Absence de tests automatisés
7. **Pas de monitoring des performances** : Absence de tableaux de bord de métriques

### Améliorations Proposées

#### Court Terme

1. **Validation croisée** : Implémenter une validation croisée k-fold
   ```python
   from sklearn.model_selection import cross_val_score
   scores = cross_val_score(model, X, y, cv=5)
   ```

2. **Optimisation des hyperparamètres** : Utiliser GridSearchCV ou RandomizedSearchCV
   ```python
   from sklearn.model_selection import GridSearchCV
   param_grid = {'C': [0.1, 1, 10], 'penalty': ['l1', 'l2']}
   grid = GridSearchCV(LogisticRegression(), param_grid, cv=5)
   ```

3. **Métriques complètes** : Ajouter précision, rappel, F1-score
   ```python
   from sklearn.metrics import classification_report
   print(classification_report(y_test, predictions))
   ```

4. **Tests unitaires** : Créer des tests pour chaque fonction
   ```python
   import pytest
   def test_load_data():
       path = load_data()
       assert os.path.exists(path)
   ```

#### Moyen Terme

5. **Feature engineering** : Traiter les colonnes textuelles (NLP, embeddings)
6. **Modèles alternatifs** : Tester Random Forest, XGBoost, LightGBM
7. **API de production** : Remplacer Flask dev par Gunicorn/uWSGI
8. **Monitoring** : Intégrer Prometheus + Grafana pour le suivi des métriques
9. **CI/CD** : Mise en place de pipelines d'intégration continue

#### Long Terme

10. **MLOps** : Intégrer MLflow pour le suivi des expérimentations
11. **Déploiement cloud** : Migration vers AWS/GCP/Azure
12. **Scalabilité** : Utilisation de Spark pour le traitement de gros volumes
13. **Model versioning** : Gestion des versions de modèles avec DVC ou MLflow
14. **A/B Testing** : Comparaison de modèles en production

## Sécurité

### Bonnes Pratiques

- **Pas de credentials en dur** : Utilisation de connexions Airflow
- **Environnement virtuel** : Isolation des dépendances
- **Gitignore** : Exclusion des fichiers sensibles (.env, logs, .venv)

### Points d'Attention

- **SMTP Gmail** : Utiliser des mots de passe d'application, pas le mot de passe principal
- **API Flask** : En production, ajouter une authentification
- **Airflow API** : Sécuriser avec Basic Auth ou OAuth

## Contributeurs

- **Elvis MESSIAEN** - Développeur principal
  - GitHub : [elvis-messiaen/airflowML](https://github.com/elvis-messiaen/airflowML)
  - Email : elvism72@gmail.com

## Licence

Ce projet est un projet éducatif développé dans le cadre d'une formation. Veuillez consulter l'auteur pour toute utilisation commerciale.

## Ressources et Documentation

### Documentation Officielle

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [scikit-learn Documentation](https://scikit-learn.org/stable/documentation.html)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [pandas Documentation](https://pandas.pydata.org/docs/)

### Tutoriels Recommandés

- [Airflow Tutorial](https://airflow.apache.org/docs/apache-airflow/stable/tutorial.html)
- [scikit-learn Tutorials](https://scikit-learn.org/stable/tutorial/index.html)
- [Machine Learning with Python](https://www.coursera.org/learn/machine-learning-with-python)

### Communautés

- [Apache Airflow Slack](https://apache-airflow-slack.herokuapp.com/)
- [Stack Overflow - Airflow](https://stackoverflow.com/questions/tagged/airflow)
- [Reddit - Machine Learning](https://www.reddit.com/r/MachineLearning/)

## Support

Pour toute question ou problème :

1. Consulter les logs Airflow
2. Vérifier la configuration SMTP
3. Consulter les issues GitHub
4. Contacter le développeur : elvism72@gmail.com

## Changelog

### Version 1.0.0 (2024-01-01)

- Implémentation initiale du pipeline ML
- Intégration de l'API Flask
- Configuration des notifications email
- Documentation complète du projet