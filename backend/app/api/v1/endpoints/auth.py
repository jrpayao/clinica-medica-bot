import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.schemas.auth import (
    LoginSchema,
    RefreshTokenSchema,
    SMSRequestSchema,
    SMSResponse,
    SMSVerifySchema,
    TokenResponse,
)
from app.services.auth_service import (
    AuthService,
    CodigoInvalidoError,
    CredenciaisInvalidasError,
    RateLimitError,
    TokenInvalidoError,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticacao"])


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> AuthService:
    return AuthService(db, redis)


@router.post(
    "/sms/request",
    response_model=SMSResponse,
    status_code=status.HTTP_200_OK,
    summary="Solicitar codigo SMS",
)
async def solicitar_sms(
    dados: SMSRequestSchema,
    service: AuthService = Depends(get_auth_service),
) -> SMSResponse:
    """Envia codigo SMS de 6 digitos para o CPF informado. Rate limit: 1/min."""
    try:
        resultado = await service.solicitar_codigo_sms(dados.cpf)
        return SMSResponse(**resultado)
    except RateLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )


@router.post(
    "/sms/verify",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar codigo SMS",
)
async def verificar_sms(
    dados: SMSVerifySchema,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Verifica codigo SMS e retorna tokens JWT."""
    try:
        resultado = await service.verificar_codigo_sms(dados.cpf, dados.codigo)
        await service.db.commit()
        return TokenResponse(**resultado)
    except CodigoInvalidoError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login interno (email + senha)",
)
async def login_interno(
    dados: LoginSchema,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Autentica usuario interno e retorna tokens JWT com role."""
    try:
        resultado = await service.login_interno(dados.email, dados.senha)
        return TokenResponse(**resultado)
    except CredenciaisInvalidasError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Renovar token",
)
async def renovar_token(
    dados: RefreshTokenSchema,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Renova access token a partir de refresh token valido."""
    try:
        resultado = await service.renovar_token(dados.refresh_token)
        return TokenResponse(**resultado)
    except TokenInvalidoError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
