# File: main.py
from __future__ import annotations

import pendulum
from airflow._shared.timezones.timezone import datetime

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.task.trigger_rule import TriggerRule

from src.model_development import (
    load_data,
    data_preprocessing,
    separate_data_outputs,
    build_model,
    load_model,
)

def envoyer_email_echec(context):
    """
    Fonction callback pour envoyer un email en cas d'échec du DAG.
    Protégée avec try/except pour éviter les boucles d'échec.

    Args:
        context: Contexte Airflow contenant les informations de l'exécution
    """
    from airflow.providers.smtp.operators.smtp import EmailOperator

    task_instance = context.get('task_instance')
    dag_run = context.get('dag_run')

    try:
        email = EmailOperator(
            task_id='echec_notification',
            to='elvism72@gmail.com',
            subject=f"Échec du Pipeline ML - {dag_run.dag_id}",
            html_content=f"""
            <h2>Pipeline ML - Échec détecté</h2>
            <p>Une erreur s'est produite lors de l'exécution du pipeline.</p>
            <h3>Détails de l'erreur :</h3>
            <ul>
                <li><strong>DAG :</strong> {dag_run.dag_id}</li>
                <li><strong>Tâche échouée :</strong> {task_instance.task_id}</li>
                <li><strong>Date d'exécution :</strong> {dag_run.execution_date}</li>
            </ul>
            <p>Consultez les logs Airflow pour plus de détails.</p>
            """,
        )
        email.execute(context)
        print("Email d'échec envoyé avec succès", flush=True)
    except Exception as e:
        # Si l'email échoue, on log l'erreur mais on ne bloque pas
        print(f"Impossible d'envoyer l'email d'échec: {e}", flush=True)

# ---------- Arguments par défaut ----------
default_args = {
    "start_date": pendulum.datetime(2024, 1, 1, tz="UTC"),
    "retries": 0,
}

# ---------- Configuration du DAG ----------
dag = DAG(
    dag_id="Airflow_Lab2",
    default_args=default_args,
    description="Pipeline ML pour la prédiction de clics publicitaires avec régression logistique",
    schedule="@daily",
    catchup=False,
    tags=["machine-learning", "pipeline", "production"],
    owner_links={"Elvis MESSIAEN": "https://github.com/elvis-messiaen/airflowML"},
    max_active_runs=1,
    on_failure_callback=envoyer_email_echec,
)

# ---------- Définition des tâches ----------
owner_task = BashOperator(
    task_id="task_using_linked_owner",
    bash_command="echo 1",
    owner="Elvis MESSIAEN",
    dag=dag,
)

send_email = EmailOperator(
    task_id='send_email',
    to='elvism72@gmail.com',
    subject='Test Airflow MailDev',
    html_content='<h1>Hello from Airflow!</h1><p>Ceci est un test d\'envoi d\'email via Airflow</p>',
    conn_id='smtp_gmail',
    mime_subtype='mixed',
    dag=dag,
    # Cette tâche est optionnelle : si elle échoue, le DAG ne sera pas marqué comme échoué
    trigger_rule=TriggerRule.ALL_DONE,  # S'exécute quoi qu'il arrive
)

load_data_task = PythonOperator(
    task_id="load_data_task",
    python_callable=load_data,
    dag=dag,
)

data_preprocessing_task = PythonOperator(
    task_id="data_preprocessing_task",
    python_callable=data_preprocessing,
    op_args=[load_data_task.output],
    dag=dag,
)

separate_data_outputs_task = PythonOperator(
    task_id="separate_data_outputs_task",
    python_callable=separate_data_outputs,
    op_args=[data_preprocessing_task.output],
    dag=dag,
)

build_save_model_task = PythonOperator(
    task_id="build_save_model_task",
    python_callable=build_model,
    op_args=[separate_data_outputs_task.output, "model.sav"],
    dag=dag,
)

load_model_task = PythonOperator(
    task_id="load_model_task",
    python_callable=load_model,
    op_args=[separate_data_outputs_task.output, "model.sav"],
    dag=dag,
)

# Déclenchement de l'API Flask sans bloquer l'exécution du DAG
trigger_dag_task = TriggerDagRunOperator(
    task_id="my_trigger_task",
    trigger_dag_id="Airflow_Lab2_Flask",
    conf={"message": "Données provenant du DAG principal"},
    reset_dag_run=False,
    wait_for_completion=False,          # Ne bloque pas l'exécution
    trigger_rule=TriggerRule.ALL_DONE,  # S'exécute même si des tâches précédentes échouent
    dag=dag,
)

# ---------- Dépendances entre les tâches ----------
owner_task >> load_data_task >> data_preprocessing_task >> \
    separate_data_outputs_task >> build_save_model_task >> \
    load_model_task >> trigger_dag_task

# Email de notification après le chargement du modèle (branche indépendante)
load_model_task >> send_email
