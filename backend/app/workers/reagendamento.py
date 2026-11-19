"""Job: ofertas de reagendamento sem resposta viram pendência da recepção (T97). Roda a cada 5 minutos."""

from app.services.reagendamento_service import expirar_ofertas
from app.workers.base import executar
from app.workers.celery_app import celery_app


@celery_app.task(name="expirar_ofertas_reagendamento")
def expirar_ofertas_reagendamento() -> int:
    return executar(lambda db, _redis: expirar_ofertas(db))
