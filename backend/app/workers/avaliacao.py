"""Job: pede a avaliação 24 horas depois do atendimento realizado (T100). Roda a cada hora."""

from app.services.avaliacao_service import solicitar_avaliacoes
from app.workers.base import executar
from app.workers.celery_app import celery_app


@celery_app.task(name="solicitar_avaliacoes")
def solicitar_avaliacoes_task() -> dict:
    return executar(lambda db, redis: solicitar_avaliacoes(db, redis))
