from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "medbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    beat_schedule={
        "cleanup-slots-expirados": {
            "task": "app.workers.slot_cleanup.limpar_slots_expirados",
            "schedule": 300.0,  # a cada 5 minutos
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
