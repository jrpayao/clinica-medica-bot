"""Job: oferece horários livres a quem está na lista de espera (T91). Roda a cada 5 minutos."""

from app.services.fila_espera_service import processar_fila
from app.workers.base import executar
from app.workers.celery_app import celery_app


@celery_app.task(name="processar_fila_espera")
def processar_fila_espera() -> dict:
    return executar(lambda db, redis: processar_fila(db, redis))
