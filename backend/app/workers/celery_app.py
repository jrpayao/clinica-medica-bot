from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "medbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Sem isto o worker sobe sem conhecer as tasks e o beat agenda nomes que ninguém executa
    include=[
        "app.workers.slot_cleanup",
        "app.workers.billing_alert",
        "app.workers.lembretes",
        "app.workers.fila_espera",
        "app.workers.reagendamento",
        "app.workers.avaliacao",
        "app.workers.resumo_medico",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    beat_schedule={
        # `limpar_slots_expirados` saiu do agendamento: cancelava todo atendimento AGENDADA com mais
        # de 10 minutos, ou seja, qualquer agendamento ainda não confirmado pela recepção.
        "fila-espera": {
            "task": "processar_fila_espera",
            "schedule": 300.0,  # a cada 5 minutos
        },
        "reagendamento-expirar": {
            "task": "expirar_ofertas_reagendamento",
            "schedule": 300.0,
        },
        "resumo-triagem-profissional": {
            "task": "enviar_resumos_triagem",
            "schedule": 900.0,  # a cada 15 minutos
        },
        "avaliacoes": {
            "task": "solicitar_avaliacoes",
            "schedule": 3600.0,  # a cada hora
        },
        "verificar-billing-diario": {
            "task": "verificar_billing_diario",
            "schedule": 600.0,  # a cada 10 minutos
        },
        "lembretes-d1": {
            "task": "enviar_lembretes_d1",
            "schedule": 3600.0,  # a cada 1 hora
        },
        "lembretes-h2": {
            "task": "enviar_lembretes_h2",
            "schedule": 1800.0,  # a cada 30 minutos
        },
    },
)
