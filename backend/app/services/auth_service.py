import secrets

import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
)
from app.models.cliente import Cliente
from app.models.usuario import Usuario

log = structlog.get_logger(__name__)

SMS_CODE_TTL = 300  # 5 minutos
SMS_RATE_LIMIT_TTL = 60  # 1 minuto entre envios


class AuthService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis

    async def solicitar_codigo_sms(self, cpf: str) -> dict[str, str | int]:
        """Gera e armazena codigo SMS de 6 digitos no Redis.

        Rate limit: 1 envio por minuto por CPF.
        TTL do codigo: 5 minutos.
        """
        rate_key = f"sms:rate:{cpf}"
        code_key = f"sms:code:{cpf}"

        # Verificar rate limit
        if await self.redis.exists(rate_key):
            log.warning("sms_rate_limit_atingido", cpf_prefixo=cpf[:3] + "***")
            raise RateLimitError("Aguarde 1 minuto antes de solicitar novo codigo")

        # Gerar codigo de 6 digitos
        codigo = f"{secrets.randbelow(1000000):06d}"

        # Armazenar no Redis com TTL
        await self.redis.set(code_key, codigo, ex=SMS_CODE_TTL)
        await self.redis.set(rate_key, "1", ex=SMS_RATE_LIMIT_TTL)

        log.info(
            "sms_codigo_gerado",
            cpf_prefixo=cpf[:3] + "***",
            ttl=SMS_CODE_TTL,
        )

        # TODO T30: Integrar com Twilio/Evolution API para envio real
        # Em dev, retorna o codigo para facilitar testes sem SMS real
        resposta: dict[str, str | int] = {
            "mensagem": "Codigo SMS enviado com sucesso",
            "ttl_segundos": SMS_CODE_TTL,
        }
        if settings.debug:
            resposta["dev_codigo"] = codigo

        return resposta

    async def verificar_codigo_sms(self, cpf: str, codigo: str) -> dict[str, str]:
        """Verifica codigo SMS e retorna tokens JWT.

        Se o paciente nao existe, sera criado em T10.
        """
        code_key = f"sms:code:{cpf}"

        codigo_armazenado = await self.redis.get(code_key)
        if codigo_armazenado is None:
            log.warning("sms_codigo_expirado", cpf_prefixo=cpf[:3] + "***")
            raise CodigoInvalidoError("Codigo expirado ou inexistente")

        if codigo_armazenado != codigo:
            log.warning("sms_codigo_incorreto", cpf_prefixo=cpf[:3] + "***")
            raise CodigoInvalidoError("Codigo incorreto")

        # Remover codigo apos uso
        await self.redis.delete(code_key)

        # Buscar cliente — criar automaticamente se não existir (auto-registro)
        result = await self.db.execute(
            select(Cliente).where(Cliente.cpf == cpf)
        )
        cliente = result.scalar_one_or_none()

        if not cliente:
            from app.models.estabelecimento import EstabelecimentoSaude
            est_result = await self.db.execute(
                select(EstabelecimentoSaude.id).order_by(EstabelecimentoSaude.id).limit(1)
            )
            est_id = est_result.scalar_one_or_none() or 1

            cliente = Cliente(
                cpf=cpf,
                nome=f"Cliente {cpf[:3]}***",
                estabelecimento_id=est_id,
            )
            self.db.add(cliente)
            await self.db.flush()
            await self.db.refresh(cliente)
            log.info("cliente_auto_registrado", cpf_prefixo=cpf[:3] + "***", estabelecimento_id=est_id)

        token_data: dict[str, str | int] = {
            "sub": cpf,
            "role": "PACIENTE_EXTERNO",
            "cliente_id": cliente.id,
            "estabelecimento_id": cliente.estabelecimento_id,
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        log.info("sms_autenticacao_sucesso", cpf_prefixo=cpf[:3] + "***")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def login_interno(self, email: str, senha: str) -> dict[str, str]:
        """Autentica usuario interno (recepcionista, medico, admin) via email + senha."""
        result = await self.db.execute(
            select(Usuario).where(Usuario.email == email, Usuario.ativo == True)  # noqa: E712
        )
        usuario = result.scalar_one_or_none()

        if not usuario or not verify_password(senha, usuario.senha_hash):
            log.warning("login_interno_falhou", email=email)
            raise CredenciaisInvalidasError("Email ou senha incorretos")

        token_data: dict[str, str | int] = {
            "sub": str(usuario.id),
            "email": usuario.email,
            "role": usuario.role.value,
        }

        if usuario.medico_id:
            token_data["medico_id"] = usuario.medico_id

        # ADMIN_GLOBAL opera cross-tenant — sem estabelecimento_id no token base
        if usuario.estabelecimento_id is not None:
            token_data["estabelecimento_id"] = usuario.estabelecimento_id

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        log.info("login_interno_sucesso", email=email, role=usuario.role.value)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def renovar_token(self, refresh_token_str: str) -> dict[str, str]:
        """Renova access token a partir de um refresh token valido."""
        payload = verify_token(refresh_token_str)

        if payload is None or payload.get("type") != "refresh":
            raise TokenInvalidoError("Refresh token invalido ou expirado")

        # Criar novo par de tokens mantendo os dados originais
        token_data = {
            k: v for k, v in payload.items() if k not in ("exp", "type", "iat")
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }


# Excecoes de dominio
class RateLimitError(Exception):
    pass


class CodigoInvalidoError(Exception):
    pass


class CredenciaisInvalidasError(Exception):
    pass


class TokenInvalidoError(Exception):
    pass
