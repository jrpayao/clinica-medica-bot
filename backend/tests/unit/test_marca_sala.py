"""Testes — Marca da sala de vídeo por unidade (T158).

O Jitsi pede a marca ao entrar na sala (`brandingDataUrl?conferenceFqn=<sala>@<domínio>`).
A sala de um atendimento mostra o logo da unidade dona do atendimento; o resto é a marca do MedBot.
"""

import io

import pytest
from PIL import Image

from app.core.config import settings
from app.models.teleconsulta import Modalidade
from app.services import marca_sala_service as marca
from app.services import papel_timbrado_service as timbre
from app.services import telemedicina_service as tele
from tests.fabrica import (
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)


def _logo(cor=(30, 30, 30, 255), tamanho=(400, 200)) -> bytes:
    saida = io.BytesIO()
    Image.new("RGBA", tamanho, cor).save(saida, "PNG")
    return saida.getvalue()


async def _sala(db, com_logo=True):
    est = await criar_estabelecimento(db, nome="Clínica Vida")
    esp = await criar_especialidade(db, est)
    prof = await criar_profissional(db, est, esp)
    paciente = await criar_cliente(db, est)
    atendimento = await criar_atendimento(
        db, await criar_slot(db, est, prof), paciente, prof, modalidade=Modalidade.ONLINE
    )
    sala = await tele.criar_teleconsulta(db, atendimento)
    if com_logo:
        await timbre.salvar_logo(db, est.id, _logo())
    return est, sala


# ── Nome da sala ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("fqn", "sala"),
    [
        ("medbot-0a1b2c3d4e5f60718293a4b5@muc.meet.jitsi", "medbot-0a1b2c3d4e5f60718293a4b5"),
        ("medbot-0a1b2c3d4e5f60718293a4b5", "medbot-0a1b2c3d4e5f60718293a4b5"),
        ("MEDBOT-ABC@muc.meet.jitsi", "medbot-abc"),
    ],
)
def test_nome_da_sala_vem_da_parte_antes_do_dominio(fqn, sala):
    assert marca.nome_da_sala(fqn) == sala


@pytest.mark.parametrize("fqn", [None, "", "@muc.meet.jitsi", "sala com espaço@x", "../../etc/passwd", "a" * 200])
def test_nome_de_sala_invalido_e_ignorado(fqn):
    assert marca.nome_da_sala(fqn) is None


# ── Marca ───────────────────────────────────────────────────────────────────

def test_marca_da_plataforma_tem_fundo_logo_e_cores_do_medbot():
    m = marca.marca_da_plataforma()
    assert m["backgroundColor"] == "#0f172a"
    assert m["logoImageUrl"] == "/images/medbot-logo.svg"
    assert m["customTheme"]["palette"]["action01"] == "#2563eb"
    assert len(m["avatarBackgrounds"]) >= 4


async def test_sala_de_unidade_com_logo_usa_o_logo_da_unidade(db_session):
    _, sala = await _sala(db_session)

    m = await marca.marca_da_sala(db_session, f"{sala.sala}@muc.meet.jitsi", base_url="https://api.medbot.test/")

    assert m["logoImageUrl"] == f"https://api.medbot.test/v1/salas/{sala.sala}/logo.png"
    assert m["backgroundColor"] == "#0f172a"            # cores continuam as da plataforma


async def test_unidade_sem_logo_fica_com_a_marca_do_medbot(db_session):
    _, sala = await _sala(db_session, com_logo=False)

    m = await marca.marca_da_sala(db_session, sala.sala, base_url="https://api.medbot.test/")

    assert m == marca.marca_da_plataforma()


@pytest.mark.parametrize("fqn", [None, "medbot-nao-existe@muc.meet.jitsi", "../x"])
async def test_sala_desconhecida_fica_com_a_marca_do_medbot(db_session, fqn):
    assert await marca.marca_da_sala(db_session, fqn, base_url="https://api.medbot.test/") == marca.marca_da_plataforma()


# ── Logo em selo ────────────────────────────────────────────────────────────

def test_selo_poe_o_logo_sobre_fundo_branco_com_altura_fixa():
    selo = Image.open(io.BytesIO(marca.selo_do_logo(timbre.preparar_logo(_logo()))))

    assert selo.format == "PNG"
    assert selo.height == marca.ALTURA_SELO
    assert selo.width <= marca.LARGURA_MAXIMA_SELO
    centro = selo.convert("RGBA").getpixel((selo.width // 2, selo.height // 2))
    canto_interno = selo.convert("RGBA").getpixel((6, selo.height // 2))
    assert centro[:3] == (30, 30, 30)                   # o logo
    assert canto_interno[:3] == (255, 255, 255)         # a margem branca em volta


def test_selo_de_logo_muito_largo_respeita_a_largura_maxima():
    selo = Image.open(io.BytesIO(marca.selo_do_logo(timbre.preparar_logo(_logo(tamanho=(1200, 60))))))
    assert selo.width == marca.LARGURA_MAXIMA_SELO


async def test_logo_da_sala_devolve_o_selo_da_unidade(db_session):
    _, sala = await _sala(db_session)
    png = await marca.logo_da_sala(db_session, sala.sala)
    assert png.startswith(b"\x89PNG")
    assert Image.open(io.BytesIO(png)).height == marca.ALTURA_SELO


async def test_logo_de_sala_sem_logo_ou_desconhecida_e_none(db_session):
    _, sala = await _sala(db_session, com_logo=False)
    assert await marca.logo_da_sala(db_session, sala.sala) is None
    assert await marca.logo_da_sala(db_session, "medbot-nao-existe") is None


# ── API ─────────────────────────────────────────────────────────────────────

async def test_api_publica_entrega_a_marca_ao_jitsi_com_cors(db_session, async_client):
    from app.main import app

    _, sala = await _sala(db_session)
    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    origem = cors.kwargs["allow_origins"][-1]            # o servidor de vídeo é a última origem liberada

    resposta = await async_client.get(
        "/v1/salas/marca", params={"conferenceFqn": f"{sala.sala}@muc.meet.jitsi"}, headers={"Origin": origem}
    )
    logo = await async_client.get(f"/v1/salas/{sala.sala}/logo.png")

    assert resposta.status_code == 200
    assert resposta.json()["logoImageUrl"].endswith(f"/v1/salas/{sala.sala}/logo.png")
    assert resposta.headers.get("access-control-allow-origin") == origem
    assert logo.status_code == 200 and logo.headers["content-type"] == "image/png"


async def test_api_de_sala_desconhecida_responde_a_marca_do_medbot(db_session, async_client):
    resposta = await async_client.get("/v1/salas/marca", params={"conferenceFqn": "medbot-x@muc.meet.jitsi"})
    assert resposta.json() == marca.marca_da_plataforma()
    assert (await async_client.get("/v1/salas/medbot-x/logo.png")).status_code == 404


def test_origens_liberadas_incluem_o_servidor_de_video():
    from app.main import origens_permitidas

    origens = origens_permitidas()                       # conftest aponta o Jitsi para https://meet.jit.si
    assert origens[-1] == "https://meet.jit.si"
    assert set(settings.allowed_origins) <= set(origens)
