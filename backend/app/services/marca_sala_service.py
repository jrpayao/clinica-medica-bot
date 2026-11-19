"""Marca da sala de vídeo por unidade (T158).

O Jitsi, ao entrar numa sala, pede a marca ao endereço configurado em BRANDING_DATA_URL, passando
`conferenceFqn=<sala>@<domínio>`. A sala de um atendimento mostra o logo da unidade dona do atendimento
(o mesmo do Receituário), sobre um selo branco para ficar legível no fundo escuro. Sala desconhecida
ou unidade sem logo: marca do MedBot.

A resposta é pública (o Jitsi a busca do navegador, sem login) e não traz nenhum dado do atendimento.
"""

import copy
import io
import re

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento
from app.models.teleconsulta import PapelTimbrado, Teleconsulta

ALTURA_SELO = 86            # o Jitsi mostra o logo em 132x43 px: o selo tem o dobro, para telas de alta densidade
LARGURA_MAXIMA_SELO = 264
MARGEM_SELO = 12
_SALA_VALIDA = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")

# Cores e logo do MedBot (as mesmas de infra/jitsi/marca/medbot-branding.json)
_PLATAFORMA = {
    "backgroundColor": "#0f172a",
    "premeetingBackground": "#0f172a",
    "logoImageUrl": "/images/medbot-logo.svg",
    "logoClickUrl": "",
    "avatarBackgrounds": ["#2563eb", "#0891b2", "#0d9488", "#7c3aed", "#c2410c"],
    "customTheme": {
        "palette": {
            "action01": "#2563eb",
            "action01Hover": "#1d4ed8",
            "action01Active": "#1e40af",
            "link01": "#93c5fd",
            "link01Hover": "#bfdbfe",
            "link01Active": "#60a5fa",
            "focus01": "#60a5fa",
            "uiBackground": "#0f172a",
        }
    },
}


def marca_da_plataforma() -> dict:
    return copy.deepcopy(_PLATAFORMA)


def nome_da_sala(conference_fqn: str | None) -> str | None:
    """'medbot-abc@muc.meet.jitsi' → 'medbot-abc'. Qualquer coisa fora do formato das salas vira None."""
    if not conference_fqn:
        return None
    sala = conference_fqn.split("@", 1)[0].strip().lower()
    return sala if _SALA_VALIDA.match(sala) else None


async def _logo_da_unidade_da_sala(db: AsyncSession, sala: str) -> bytes | None:
    return (
        await db.execute(
            select(PapelTimbrado.logo)
            .join(Atendimento, Atendimento.estabelecimento_id == PapelTimbrado.estabelecimento_id)
            .join(Teleconsulta, Teleconsulta.atendimento_id == Atendimento.id)
            .where(Teleconsulta.sala == sala)
        )
    ).scalar_one_or_none()


async def marca_da_sala(db: AsyncSession, conference_fqn: str | None, base_url: str) -> dict:
    """Marca que o Jitsi aplica na sala. `base_url` é o endereço público desta API (para o link do logo)."""
    sala = nome_da_sala(conference_fqn)
    marca = marca_da_plataforma()
    if sala and await _logo_da_unidade_da_sala(db, sala):
        marca["logoImageUrl"] = f"{base_url.rstrip('/')}/v1/salas/{sala}/logo.png"
    return marca


def selo_do_logo(logo: bytes) -> bytes:
    """Logo da unidade centralizado num selo branco de cantos arredondados, com altura fixa."""
    imagem = Image.open(io.BytesIO(logo)).convert("RGBA")
    altura_util = ALTURA_SELO - 2 * MARGEM_SELO
    largura_util = LARGURA_MAXIMA_SELO - 2 * MARGEM_SELO
    escala = min(altura_util / imagem.height, largura_util / imagem.width)
    imagem = imagem.resize(
        (max(1, round(imagem.width * escala)), max(1, round(imagem.height * escala))), Image.LANCZOS
    )

    largura = min(LARGURA_MAXIMA_SELO, imagem.width + 2 * MARGEM_SELO)
    selo = Image.new("RGBA", (largura, ALTURA_SELO), (0, 0, 0, 0))
    fundo = Image.new("RGBA", selo.size, (255, 255, 255, 255))
    mascara = Image.new("L", selo.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, largura - 1, ALTURA_SELO - 1), radius=14, fill=255)
    selo.paste(fundo, (0, 0), mascara)
    selo.alpha_composite(imagem, ((largura - imagem.width) // 2, (ALTURA_SELO - imagem.height) // 2))

    saida = io.BytesIO()
    selo.save(saida, "PNG", optimize=True)
    return saida.getvalue()


async def logo_da_sala(db: AsyncSession, sala: str) -> bytes | None:
    nome = nome_da_sala(sala)
    if nome is None:
        return None
    logo = await _logo_da_unidade_da_sala(db, nome)
    return selo_do_logo(logo) if logo else None
