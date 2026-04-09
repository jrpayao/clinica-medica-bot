import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.auth_service import (
    AuthService,
    CodigoInvalidoError,
    CredenciaisInvalidasError,
    RateLimitError,
    TokenInvalidoError,
)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    # execute() retorna AsyncMock, mas scalar_one_or_none() e sync no Result
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock
    return db


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def service(mock_db, mock_redis):
    return AuthService(mock_db, mock_redis)


# ============================================================
# T05: Auth SMS
# ============================================================

async def test_solicitar_codigo_sms_gera_codigo_6_digitos(service, mock_redis):
    """RF: QUANDO o paciente solicita SMS, O SISTEMA DEVE gerar codigo de 6 digitos."""
    resultado = await service.solicitar_codigo_sms("12345678901")

    assert resultado["mensagem"] == "Codigo SMS enviado com sucesso"
    assert resultado["ttl_segundos"] == 300

    # Verificar que set foi chamado para code e rate
    assert mock_redis.set.call_count == 2

    # Primeiro call: codigo (6 digitos, TTL 300s)
    code_call = mock_redis.set.call_args_list[0]
    assert code_call[0][0] == "sms:code:12345678901"
    assert len(code_call[0][1]) == 6
    assert code_call[0][1].isdigit()
    assert code_call[1]["ex"] == 300

    # Segundo call: rate limit (TTL 60s)
    rate_call = mock_redis.set.call_args_list[1]
    assert rate_call[0][0] == "sms:rate:12345678901"
    assert rate_call[1]["ex"] == 60


async def test_solicitar_codigo_sms_rate_limit(service, mock_redis):
    """RF: SE o codigo SMS expirar, rate limit de 1/min."""
    mock_redis.exists.return_value = True

    with pytest.raises(RateLimitError, match="Aguarde 1 minuto"):
        await service.solicitar_codigo_sms("12345678901")


async def test_verificar_codigo_sms_correto(service, mock_redis, mock_db):
    """RF: QUANDO o codigo correto e informado, retornar JWT."""
    mock_redis.get.return_value = "123456"

    resultado = await service.verificar_codigo_sms("12345678901", "123456")

    assert "access_token" in resultado
    assert "refresh_token" in resultado
    assert resultado["token_type"] == "bearer"
    mock_redis.delete.assert_called_once_with("sms:code:12345678901")


async def test_verificar_codigo_sms_com_paciente_existente(service, mock_redis, mock_db):
    """RF: Se paciente existe, incluir cliente_id no token."""
    mock_redis.get.return_value = "123456"
    paciente_mock = MagicMock()
    paciente_mock.id = 42
    paciente_mock.estabelecimento_id = 1
    mock_db.execute.return_value.scalar_one_or_none.return_value = paciente_mock

    resultado = await service.verificar_codigo_sms("12345678901", "123456")

    assert "access_token" in resultado
    from app.core.security import verify_token
    payload = verify_token(resultado["access_token"])
    assert payload["cliente_id"] == 42
    assert payload["role"] == "PACIENTE_EXTERNO"


async def test_verificar_codigo_sms_expirado(service, mock_redis):
    """Edge case: codigo expirado retorna erro."""
    mock_redis.get.return_value = None

    with pytest.raises(CodigoInvalidoError, match="expirado"):
        await service.verificar_codigo_sms("12345678901", "123456")


async def test_verificar_codigo_sms_incorreto(service, mock_redis):
    """Edge case: codigo incorreto retorna erro."""
    mock_redis.get.return_value = "654321"

    with pytest.raises(CodigoInvalidoError, match="incorreto"):
        await service.verificar_codigo_sms("12345678901", "123456")


async def test_sms_nao_expoe_cpf_completo_em_log(service, mock_redis, caplog):
    """Seguranca: CPF completo nao deve aparecer nos logs."""
    await service.solicitar_codigo_sms("98765432100")

    assert "98765432100" not in caplog.text


# ============================================================
# T06: Auth interna JWT
# ============================================================

async def test_login_interno_sucesso(service, mock_db):
    """RF: QUANDO credenciais validas, retornar JWT com role."""
    from app.core.security import hash_password
    from app.models.usuario import UsuarioRole

    usuario_mock = MagicMock()
    usuario_mock.id = 1
    usuario_mock.email = "recep@clinica.com"
    usuario_mock.senha_hash = hash_password("senha123")
    usuario_mock.role = UsuarioRole.RECEPCIONISTA
    usuario_mock.profissional_id = None
    usuario_mock.estabelecimento_id = 1
    usuario_mock.ativo = True

    mock_db.execute.return_value.scalar_one_or_none.return_value = usuario_mock

    resultado = await service.login_interno("recep@clinica.com", "senha123")

    assert "access_token" in resultado
    assert "refresh_token" in resultado
    assert resultado["token_type"] == "bearer"

    from app.core.security import verify_token
    payload = verify_token(resultado["access_token"])
    assert payload["role"] == "RECEPCIONISTA"
    assert payload["email"] == "recep@clinica.com"


async def test_login_interno_email_inexistente(service, mock_db):
    """Edge case: email nao cadastrado."""
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(CredenciaisInvalidasError):
        await service.login_interno("naoexiste@clinica.com", "senha123")


async def test_login_interno_senha_incorreta(service, mock_db):
    """Edge case: senha incorreta."""
    from app.core.security import hash_password
    from app.models.usuario import UsuarioRole

    usuario_mock = MagicMock()
    usuario_mock.id = 1
    usuario_mock.email = "admin@clinica.com"
    usuario_mock.senha_hash = hash_password("correta123")
    usuario_mock.role = UsuarioRole.ADMIN_ESTABELECIMENTO
    usuario_mock.profissional_id = None
    usuario_mock.estabelecimento_id = 1
    usuario_mock.ativo = True

    mock_db.execute.return_value.scalar_one_or_none.return_value = usuario_mock

    with pytest.raises(CredenciaisInvalidasError):
        await service.login_interno("admin@clinica.com", "errada123")


async def test_login_medico_inclui_profissional_id(service, mock_db):
    """RF: SE role MEDICO, token inclui profissional_id."""
    from app.core.security import hash_password
    from app.models.usuario import UsuarioRole

    usuario_mock = MagicMock()
    usuario_mock.id = 5
    usuario_mock.email = "dr@clinica.com"
    usuario_mock.senha_hash = hash_password("senha123")
    usuario_mock.role = UsuarioRole.MEDICO
    usuario_mock.profissional_id = 10
    usuario_mock.estabelecimento_id = 1
    usuario_mock.ativo = True

    mock_db.execute.return_value.scalar_one_or_none.return_value = usuario_mock

    resultado = await service.login_interno("dr@clinica.com", "senha123")

    from app.core.security import verify_token
    payload = verify_token(resultado["access_token"])
    assert payload["profissional_id"] == 10
    assert payload["role"] == "MEDICO"


async def test_renovar_token_sucesso(service):
    """RF: QUANDO refresh token valido, retornar novo par de tokens."""
    from app.core.security import create_refresh_token

    refresh = create_refresh_token({"sub": "1", "role": "ADMIN"})
    resultado = await service.renovar_token(refresh)

    assert "access_token" in resultado
    assert "refresh_token" in resultado


async def test_renovar_token_invalido(service):
    """Edge case: refresh token invalido/expirado."""
    with pytest.raises(TokenInvalidoError):
        await service.renovar_token("token.invalido.aqui")


async def test_renovar_token_access_nao_aceito(service):
    """Seguranca: access token nao deve ser aceito como refresh."""
    from app.core.security import create_access_token

    access = create_access_token({"sub": "1", "role": "ADMIN"})

    with pytest.raises(TokenInvalidoError):
        await service.renovar_token(access)
