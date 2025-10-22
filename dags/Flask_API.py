# File: Flask_API.py
from __future__ import annotations

import os
import time
import socket
import pendulum
import requests
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from flask import Flask, redirect, render_template

# ---------- Config (Airflow 3: use REST with Basic Auth via FAB API backend) ----------
WEBSERVER = os.getenv("AIRFLOW_WEBSERVER", "http://localhost:8080")
AF_USER   = os.getenv("AIRFLOW_USERNAME", os.getenv("_AIRFLOW_WWW_USER_USERNAME", "airflow"))
AF_PASS   = os.getenv("AIRFLOW_PASSWORD", os.getenv("_AIRFLOW_WWW_USER_PASSWORD", "airflow"))
TARGET_DAG_ID = os.getenv("TARGET_DAG_ID", "Airflow_Lab2")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5555"))

# ---------- Default args ----------
default_args = {
    "start_date": pendulum.datetime(2024, 1, 1, tz="UTC"),
    "retries": 0,
}

# ---------- Flask app ----------
app = Flask(__name__, template_folder="templates")

def get_latest_run_info():
    """
    Query Airflow stable REST API (/api/v2) using Basic Auth.
    Requires Airflow to be configured with:
      AIRFLOW__FAB__AUTH_BACKENDS=airflow.providers.fab.auth_manager.api.auth.backend.basic_auth
    """
    url = f"{WEBSERVER}/api/v2/dags/{TARGET_DAG_ID}/dagRuns?order_by=-logical_date&limit=1"
    try:
        r = requests.get(url, auth=(AF_USER, AF_PASS), timeout=5)
    except Exception as e:
        return False, {"note": f"Exception calling Airflow API: {e}"}

    # If auth/backend is not set correctly you'll get 401 here.
    if r.status_code != 200:
        # Surface a short note (kept small to avoid template overflow)
        snippet = r.text[:200].replace("\n", " ")
        return False, {"note": f"API status {r.status_code}: {snippet}"}

    runs = r.json().get("dag_runs", [])
    if not runs:
        return False, {"note": "No DagRuns found yet."}

    run = runs[0]
    state = run.get("state")
    info = {
        "state": state,
        "run_id": run.get("dag_run_id"),
        "logical_date": run.get("logical_date"),
        "start_date": run.get("start_date"),
        "end_date": run.get("end_date"),
        "note": "",
    }
    return state == "success", info


@app.route("/")
def index():
    ok, _ = get_latest_run_info()
    return redirect("/success" if ok else "/failure")

@app.route("/success")
def success():
    ok, info = get_latest_run_info()
    return render_template("success.html", **info)

@app.route("/failure")
def failure():
    ok, info = get_latest_run_info()
    return render_template("failure.html", **info)

@app.route("/health")
def health():
    return "ok", 200


def verifier_port_disponible(port):
    """
    Vérifie si un port est disponible pour écouter.

    Args:
        port (int): Numéro du port à vérifier

    Returns:
        bool: True si le port est disponible, False sinon
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)

    try:
        # Tente de se connecter au port
        resultat = sock.connect_ex(('localhost', port))
        sock.close()

        # Si la connexion réussit (code 0), le port est occupé
        return resultat != 0
    except Exception as e:
        print(f"Erreur lors de la vérification du port {port}: {e}", flush=True)
        return False


def tester_api_existante(port):
    """
    Teste si une API Flask est déjà en cours d'exécution sur le port.

    Args:
        port (int): Numéro du port à tester

    Returns:
        bool: True si l'API répond correctement, False sinon
    """
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        return response.status_code == 200 and response.text == "ok"
    except Exception:
        return False


def start_flask_app():
    """
    Démarre le serveur Flask en gérant les cas où le port est déjà utilisé.

    Cette fonction :
    - Vérifie si le port est disponible
    - Si le port est occupé, teste si c'est notre API qui tourne déjà
    - Si notre API tourne, maintient la tâche active sans redémarrer
    - Sinon, affiche une erreur claire
    - Démarre Flask si le port est libre
    """
    print(f"Vérification de la disponibilité du port {FLASK_PORT}...", flush=True)

    if not verifier_port_disponible(FLASK_PORT):
        print(f"Le port {FLASK_PORT} est déjà utilisé.", flush=True)

        # Vérifie si c'est notre API qui tourne déjà
        if tester_api_existante(FLASK_PORT):
            print(f"L'API Flask est déjà en cours d'exécution sur le port {FLASK_PORT}.", flush=True)
            print("La tâche va maintenir l'exécution active.", flush=True)

            # Maintient la tâche active tant que l'API répond
            while True:
                time.sleep(30)
                if not tester_api_existante(FLASK_PORT):
                    print("L'API Flask ne répond plus. Arrêt de la tâche.", flush=True)
                    raise RuntimeError("L'API Flask s'est arrêtée de manière inattendue")
        else:
            erreur_msg = (
                f"Le port {FLASK_PORT} est occupé par un autre processus.\n"
                f"Utilisez 'lsof -i :{FLASK_PORT}' pour identifier le processus,\n"
                f"puis 'kill -9 <PID>' pour l'arrêter."
            )
            print(erreur_msg, flush=True)
            raise RuntimeError(erreur_msg)

    print(f"Démarrage de Flask sur 0.0.0.0:{FLASK_PORT}...", flush=True)

    try:
        app.run(host="0.0.0.0", port=FLASK_PORT, use_reloader=False)
    except Exception as e:
        print(f"Erreur lors du démarrage de Flask: {e}", flush=True)
        raise

    # Si app.run retourne (normalement il ne devrait jamais), maintient la tâche active
    print("Flask s'est arrêté de manière inattendue. Maintien de la tâche active...", flush=True)
    while True:
        time.sleep(60)

# ---------- DAG ----------
flask_api_dag = DAG(
    dag_id="Airflow_Lab2_Flask",
    default_args=default_args,
    description="DAG to manage Flask API lifecycle",
    schedule=None,                 # trigger-only
    catchup=False,
    is_paused_upon_creation=False,
    tags=["Flask_Api"],
    max_active_runs=1,
)

start_flask_API = PythonOperator(
    task_id="start_Flask_API",
    python_callable=start_flask_app,
    dag=flask_api_dag,
)

start_flask_API

if __name__ == "__main__":
    start_flask_API.cli()
