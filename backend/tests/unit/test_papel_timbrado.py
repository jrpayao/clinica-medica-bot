"""Testes — Papel timbrado da unidade (G29): logo, marca-d'água e rodapé nos documentos clínicos."""

import io
import re

import pytest
from PIL import Image

from app.models.atendimento import AtendimentoStatus
from app.models.teleconsulta import Modalidade, TipoDocumento
from app.services import papel_timbrado_service as timbre
from app.services import telemedicina_service as tele
from app.services.documentos_pdf import gerar_pdf
from tests.fabrica import (
    cabecalho,
    criar_atendimento,
    criar_cliente,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
)

BASE_PDF = {
    "tipo": "RECEITA",
    "codigo": "AB12CD34",
    "emitido_em": "10/05/2030",
    "unidade": {"nome": "Clínica Vida", "endereco": "Rua das Flores, 100", "telefone": "(11) 3333-4444"},
    "profissional": {"nome": "Dra. Ana Lima", "registro": "CRM 12345"},
    "paciente": {"nome": "João Souza"},
    "conteudo": {"itens": [{"medicamento": "Dipirona 500 mg", "posologia": "1 comprimido a cada 6 horas"}]},
}


def _imagem(formato="PNG", tamanho=(400, 200), modo="RGBA") -> bytes:
    saida = io.BytesIO()
    Image.new(modo, tamanho, (30, 90, 200, 255) if modo == "RGBA" else (30, 90, 200)).save(saida, formato)
    return saida.getvalue()


def _imagens_no_pdf(pdf: bytes) -> int:
    return len(re.findall(rb"/Subtype /Image", pdf))


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b(?!s)", pdf))


# ── Preparo do logo ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(("formato", "modo"), [("PNG", "RGBA"), ("JPEG", "RGB")])
def test_logo_png_ou_jpeg_e_aceito_e_regravado_como_png(formato, modo):
    preparado = timbre.preparar_logo(_imagem(formato, modo=modo))
    imagem = Image.open(io.BytesIO(preparado))
    assert imagem.format == "PNG"
    assert imagem.size == (400, 200)


def test_logo_grande_e_reduzido_mantendo_a_proporcao():
    preparado = timbre.preparar_logo(_imagem(tamanho=(3000, 1500)))
    assert Image.open(io.BytesIO(preparado)).size == (timbre.LADO_MAXIMO, timbre.LADO_MAXIMO // 2)


@pytest.mark.parametrize(
    "bruto",
    [b"", b"isto nao e uma imagem", b"%PDF-1.4 arquivo", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"],
)
def test_arquivo_que_nao_e_imagem_e_recusado(bruto):
    with pytest.raises(timbre.LogoInvalidoError):
        timbre.preparar_logo(bruto)


def test_logo_acima_do_tamanho_maximo_e_recusado():
    with pytest.raises(timbre.LogoInvalidoError):
        timbre.preparar_logo(b"\x89PNG" + b"0" * (timbre.TAMANHO_MAXIMO_BYTES + 1))


def test_formato_que_nao_e_png_nem_jpeg_e_recusado():
    with pytest.raises(timbre.LogoInvalidoError):
        timbre.preparar_logo(_imagem("GIF", modo="RGB"))


def test_marca_dagua_e_uma_versao_clara_do_logo():
    original = Image.open(io.BytesIO(timbre.preparar_logo(_imagem()))).convert("RGB").getpixel((10, 10))
    clara = Image.open(io.BytesIO(timbre.versao_marca_dagua(timbre.preparar_logo(_imagem())))).convert("RGB").getpixel((10, 10))

    assert all(c > 225 for c in clara)            # quase branco: não atrapalha a leitura
    assert clara != (255, 255, 255)               # mas ainda visível
    assert sum(clara) > sum(original)


# ── PDF ─────────────────────────────────────────────────────────────────────

def test_pdf_sem_timbre_nao_tem_imagem():
    assert _imagens_no_pdf(gerar_pdf(BASE_PDF)) == 0


def test_pdf_com_logo_e_marca_dagua_traz_as_duas_imagens():
    logo = timbre.preparar_logo(_imagem())
    so_logo = gerar_pdf({**BASE_PDF, "timbre": {"logo": logo, "marca_dagua": False, "rodape": None}})
    completo = gerar_pdf({**BASE_PDF, "timbre": {"logo": logo, "marca_dagua": True, "rodape": None}})

    assert _imagens_no_pdf(so_logo) == 1
    assert _imagens_no_pdf(completo) == 2
    assert completo.startswith(b"%PDF")


def test_marca_dagua_aparece_em_todas_as_paginas():
    logo = timbre.preparar_logo(_imagem())
    itens = [
        {"medicamento": f"Medicamento {n}", "posologia": "Tomar 1 comprimido a cada 8 horas, " * 6}
        for n in range(1, 11)
    ]
    pdf = gerar_pdf({
        **BASE_PDF, "conteudo": {"itens": itens},
        "timbre": {"logo": logo, "marca_dagua": True, "rodape": None},
    })

    assert _paginas(pdf) >= 2
    # a mesma imagem é reutilizada: cada página desenha a marca-d'água e o logo do cabeçalho
    desenhos = len(re.findall(rb"/I\d+ Do", b"".join(_fluxos(pdf))))
    assert desenhos == 2 * _paginas(pdf)


def test_rodape_personalizado_entra_no_pdf():
    pdf = gerar_pdf({**BASE_PDF, "timbre": {"logo": None, "marca_dagua": False, "rodape": "Atendimento de segunda a sexta, 8h às 18h"}})
    assert "Atendimento de segunda a sexta" in b" ".join(_fluxos(pdf)).decode("latin-1")


def _fluxos(pdf: bytes) -> list[bytes]:
    import zlib

    saida = []
    for bruto in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            saida.append(zlib.decompress(bruto))
        except zlib.error:
            continue
    return saida


# ── Configuração por unidade ────────────────────────────────────────────────

async def test_configuracao_padrao_da_unidade_e_sem_logo(db_session):
    est = await criar_estabelecimento(db_session)
    assert await timbre.obter(db_session, est.id) == {
        "tem_logo": False, "marca_dagua": True, "rodape": None, "atualizado_em": None,
    }


async def test_logo_e_opcoes_sao_por_unidade(db_session):
    est = await criar_estabelecimento(db_session)
    outra = await criar_estabelecimento(db_session)

    await timbre.salvar_logo(db_session, est.id, _imagem())
    await timbre.salvar_opcoes(db_session, est.id, marca_dagua=False, rodape="  Rua A, 10  ")

    config = await timbre.obter(db_session, est.id)
    assert (config["tem_logo"], config["marca_dagua"], config["rodape"]) == (True, False, "Rua A, 10")
    assert (await timbre.obter(db_session, outra.id))["tem_logo"] is False
    assert await timbre.logo(db_session, outra.id) is None
    assert (await timbre.logo(db_session, est.id)).startswith(b"\x89PNG")


async def test_remover_o_logo_mantem_as_outras_opcoes(db_session):
    est = await criar_estabelecimento(db_session)
    await timbre.salvar_logo(db_session, est.id, _imagem())
    await timbre.salvar_opcoes(db_session, est.id, marca_dagua=True, rodape="Rodapé")

    await timbre.remover_logo(db_session, est.id)

    config = await timbre.obter(db_session, est.id)
    assert (config["tem_logo"], config["rodape"]) == (False, "Rodapé")


async def test_receita_emitida_usa_o_timbre_da_unidade(db_session):
    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    paciente = await criar_cliente(db_session, est)
    atendimento = await criar_atendimento(
        db_session, await criar_slot(db_session, est, prof), paciente, prof,
        status=AtendimentoStatus.EM_ATENDIMENTO, modalidade=Modalidade.ONLINE,
    )
    doc = await tele.emitir_documento(db_session, atendimento.id, prof.id, est.id, TipoDocumento.ATESTADO, {"dias": 1})

    antes, _ = await tele.pdf_do_documento(db_session, doc.id, atendimento.id, prof.id, est.id)
    await timbre.salvar_logo(db_session, est.id, _imagem())
    depois, _ = await tele.pdf_do_documento(db_session, doc.id, atendimento.id, prof.id, est.id)

    assert _imagens_no_pdf(antes) == 0
    assert _imagens_no_pdf(depois) == 2          # logo no cabeçalho + marca-d'água (ligada por padrão)


# ── API ─────────────────────────────────────────────────────────────────────

async def test_gestor_configura_o_papel_timbrado_e_ve_o_exemplo(db_session, async_client):
    est = await criar_estabelecimento(db_session)
    gestor = cabecalho(est)
    base = "/v1/estabelecimentos/meu/papel-timbrado"

    envio = await async_client.post(f"{base}/logo", headers=gestor, files={"arquivo": ("logo.png", _imagem(), "image/png")})
    opcoes = await async_client.put(base, headers=gestor, json={"marca_dagua": True, "rodape": "Rua A, 10"})
    config = (await async_client.get(base, headers=gestor)).json()
    imagem = await async_client.get(f"{base}/logo", headers=gestor)
    exemplo = await async_client.get(f"{base}/exemplo.pdf", headers=gestor)
    invalido = await async_client.post(f"{base}/logo", headers=gestor, files={"arquivo": ("x.png", b"nao e imagem", "image/png")})
    removido = await async_client.delete(f"{base}/logo", headers=gestor)

    assert (envio.status_code, opcoes.status_code) == (200, 200)
    assert (config["tem_logo"], config["marca_dagua"], config["rodape"]) == (True, True, "Rua A, 10")
    assert imagem.headers["content-type"] == "image/png"
    assert exemplo.content.startswith(b"%PDF") and _imagens_no_pdf(exemplo.content) == 2
    assert invalido.status_code == 422
    assert removido.status_code == 204
    assert (await async_client.get(base, headers=gestor)).json()["tem_logo"] is False
    assert (await async_client.get(f"{base}/logo", headers=gestor)).status_code == 404


@pytest.mark.parametrize("role", ["RECEPCIONISTA", "MEDICO"])
async def test_so_o_gestor_altera_o_papel_timbrado(db_session, async_client, role):
    est = await criar_estabelecimento(db_session)
    extras = {"profissional_id": 1} if role == "MEDICO" else {}

    resposta = await async_client.put(
        "/v1/estabelecimentos/meu/papel-timbrado", headers=cabecalho(est, role=role, **extras),
        json={"marca_dagua": False, "rodape": None},
    )

    assert resposta.status_code == 403
