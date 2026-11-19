"""Papel timbrado da unidade (G29): logo, marca-d'água e rodapé usados em receitas e atestados.

O arquivo enviado nunca é guardado como veio: é aberto, conferido, reduzido e regravado como PNG,
o que descarta metadados e qualquer coisa que não seja imagem.
"""

import io
from datetime import datetime, timezone

import structlog
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teleconsulta import PapelTimbrado

log = structlog.get_logger(__name__)

TAMANHO_MAXIMO_BYTES = 2 * 1024 * 1024
LADO_MAXIMO = 1200
FORMATOS_ACEITOS = ("PNG", "JPEG")
CLAREAMENTO = 0.90          # quanto do branco entra na marca-d'água
TAMANHO_RODAPE = 300


class LogoInvalidoError(Exception):
    pass


def preparar_logo(bruto: bytes) -> bytes:
    """Confere o arquivo e devolve o logo em PNG, com o maior lado em até LADO_MAXIMO pixels."""
    if not bruto:
        raise LogoInvalidoError("Envie um arquivo de imagem.")
    if len(bruto) > TAMANHO_MAXIMO_BYTES:
        raise LogoInvalidoError("A imagem precisa ter até 2 MB.")
    try:
        with Image.open(io.BytesIO(bruto)) as conferida:
            conferida.verify()
        imagem = Image.open(io.BytesIO(bruto))
        if imagem.format not in FORMATOS_ACEITOS:
            raise LogoInvalidoError("Use uma imagem PNG ou JPEG.")
        imagem = imagem.convert("RGBA")
    except LogoInvalidoError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as erro:
        raise LogoInvalidoError("O arquivo não é uma imagem PNG ou JPEG válida.") from erro

    imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    saida = io.BytesIO()
    imagem.save(saida, "PNG", optimize=True)
    return saida.getvalue()


def versao_marca_dagua(logo: bytes) -> bytes:
    """Logo sobre fundo branco, bem claro, para ficar atrás do texto sem atrapalhar a leitura."""
    imagem = Image.open(io.BytesIO(logo)).convert("RGBA")
    fundo = Image.new("RGBA", imagem.size, (255, 255, 255, 255))
    fundo.alpha_composite(imagem)
    clara = Image.blend(fundo.convert("RGB"), Image.new("RGB", imagem.size, (255, 255, 255)), CLAREAMENTO)
    saida = io.BytesIO()
    clara.save(saida, "PNG", optimize=True)
    return saida.getvalue()


async def _registro(db: AsyncSession, estabelecimento_id: int) -> PapelTimbrado | None:
    return (
        await db.execute(select(PapelTimbrado).where(PapelTimbrado.estabelecimento_id == estabelecimento_id))
    ).scalar_one_or_none()


async def _registro_ou_novo(db: AsyncSession, estabelecimento_id: int) -> PapelTimbrado:
    registro = await _registro(db, estabelecimento_id)
    if registro is None:
        registro = PapelTimbrado(estabelecimento_id=estabelecimento_id, marca_dagua=True)
        db.add(registro)
    registro.updated_at = datetime.now(timezone.utc)
    return registro


async def obter(db: AsyncSession, estabelecimento_id: int) -> dict:
    """Configuração da unidade, sem os bytes do logo."""
    registro = await _registro(db, estabelecimento_id)
    if registro is None:
        return {"tem_logo": False, "marca_dagua": True, "rodape": None, "atualizado_em": None}
    return {
        "tem_logo": registro.logo is not None,
        "marca_dagua": registro.marca_dagua,
        "rodape": registro.rodape,
        "atualizado_em": registro.updated_at.isoformat() if registro.updated_at else None,
    }


async def logo(db: AsyncSession, estabelecimento_id: int) -> bytes | None:
    registro = await _registro(db, estabelecimento_id)
    return registro.logo if registro else None


async def para_o_pdf(db: AsyncSession, estabelecimento_id: int) -> dict | None:
    """O que o gerador de PDF precisa: logo, se usa marca-d'água e o rodapé."""
    registro = await _registro(db, estabelecimento_id)
    if registro is None or (registro.logo is None and not registro.rodape):
        return None
    return {"logo": registro.logo, "marca_dagua": registro.marca_dagua, "rodape": registro.rodape}


async def salvar_logo(db: AsyncSession, estabelecimento_id: int, bruto: bytes) -> None:
    preparado = preparar_logo(bruto)
    registro = await _registro_ou_novo(db, estabelecimento_id)
    registro.logo = preparado
    await db.flush()
    log.info("papel_timbrado_logo_salvo", estabelecimento_id=estabelecimento_id, bytes=len(preparado))


async def remover_logo(db: AsyncSession, estabelecimento_id: int) -> None:
    registro = await _registro(db, estabelecimento_id)
    if registro is not None:
        registro.logo = None
        registro.updated_at = datetime.now(timezone.utc)
        await db.flush()


async def salvar_opcoes(db: AsyncSession, estabelecimento_id: int, marca_dagua: bool, rodape: str | None) -> None:
    registro = await _registro_ou_novo(db, estabelecimento_id)
    registro.marca_dagua = marca_dagua
    registro.rodape = ((rodape or "").strip()[:TAMANHO_RODAPE]) or None
    await db.flush()
