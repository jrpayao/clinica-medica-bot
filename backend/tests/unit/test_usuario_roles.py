"""Testes TDAD para novos roles e campo estabelecimento_id no Usuario."""

import pytest

from app.models.usuario import Usuario, UsuarioRole


# ============================================================
# T58-A: Novos roles
# ============================================================


def test_role_admin_global_existe() -> None:
    """ADMIN_GLOBAL deve existir no enum para acesso cross-tenant."""
    assert UsuarioRole.ADMIN_GLOBAL == "ADMIN_GLOBAL"


def test_role_admin_estabelecimento_existe() -> None:
    """ADMIN_ESTABELECIMENTO substitui ADMIN limitado a 1 tenant."""
    assert UsuarioRole.ADMIN_ESTABELECIMENTO == "ADMIN_ESTABELECIMENTO"


def test_roles_existentes_preservados() -> None:
    """Roles anteriores devem continuar existindo (sem breaking change)."""
    assert UsuarioRole.RECEPCIONISTA == "RECEPCIONISTA"
    assert UsuarioRole.MEDICO == "MEDICO"


def test_role_admin_antigo_removido() -> None:
    """Role 'ADMIN' simples não deve mais existir — foi renomeado."""
    roles = {r.value for r in UsuarioRole}
    assert "ADMIN" not in roles, (
        "Role 'ADMIN' foi substituído por ADMIN_GLOBAL e ADMIN_ESTABELECIMENTO"
    )


def test_todos_roles_sao_string() -> None:
    """Todos os roles devem ser StrEnum para serialização JWT."""
    for role in UsuarioRole:
        assert isinstance(role.value, str)


# ============================================================
# T58-B: Campo estabelecimento_id no Usuario
# ============================================================


def test_usuario_tem_campo_estabelecimento_id() -> None:
    """Usuario deve ter o campo estabelecimento_id."""
    assert hasattr(Usuario, "estabelecimento_id")


def test_usuario_admin_global_pode_ter_estabelecimento_id_nulo() -> None:
    """ADMIN_GLOBAL não pertence a nenhum estabelecimento específico."""
    u = Usuario(
        nome="Admin Master",
        email="admin@plataforma.com",
        senha_hash="hash",
        role=UsuarioRole.ADMIN_GLOBAL,
        estabelecimento_id=None,
    )
    assert u.estabelecimento_id is None
    assert u.role == UsuarioRole.ADMIN_GLOBAL


def test_usuario_recepcionista_tem_estabelecimento_id() -> None:
    """Recepcionista deve estar vinculada a um estabelecimento."""
    u = Usuario(
        nome="Carla Recepção",
        email="carla@clinica.com",
        senha_hash="hash",
        role=UsuarioRole.RECEPCIONISTA,
        estabelecimento_id=3,
    )
    assert u.estabelecimento_id == 3


def test_usuario_medico_tem_estabelecimento_id_principal() -> None:
    """Médico tem estabelecimento_id principal (pode atender em outros via junction)."""
    u = Usuario(
        nome="Dr. Carlos",
        email="carlos@clinica.com",
        senha_hash="hash",
        role=UsuarioRole.MEDICO,
        medico_id=1,
        estabelecimento_id=1,
    )
    assert u.estabelecimento_id == 1
    assert u.medico_id == 1
