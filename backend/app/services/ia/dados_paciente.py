"""Leitura dos dados que o paciente digita no chat: CPF e convênio/plano em texto livre."""

import re
import unicodedata


def _digito_verificador(digitos: str) -> int:
    peso_inicial = len(digitos) + 1
    soma = sum(int(d) * (peso_inicial - i) for i, d in enumerate(digitos))
    resto = (soma * 10) % 11
    return 0 if resto == 10 else resto


def normalizar_cpf(texto: str | None) -> str | None:
    """Devolve o CPF com 11 dígitos se o texto contiver um CPF válido; senão None."""
    digitos = re.sub(r"\D", "", texto or "")
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return None
    if _digito_verificador(digitos[:9]) != int(digitos[9]):
        return None
    if _digito_verificador(digitos[:10]) != int(digitos[10]):
        return None
    return digitos


def mascarar_cpf(cpf: str | None) -> str:
    """CPF para exibir na conversa. Sem asteriscos: no chat e no WhatsApp eles viram negrito."""
    if not cpf or len(cpf) < 11:
        return "***"
    return f"{cpf[:3]}.XXX.XXX-{cpf[-2:]}"


def _simplificar(texto: str) -> str:
    """Minúsculas, sem acento e sem pontuação/espaço: 'Sul América' → 'sulamerica'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def localizar_por_nome(texto: str | None, opcoes: list[dict]) -> dict | None:
    """Acha em `opcoes` (dicts com 'nome') aquela cujo nome aparece no texto digitado.

    Só casa quando o nome cadastrado está contido no texto — não tenta adivinhar grafias parecidas.
    Entre várias candidatas, vence o nome mais longo.
    """
    alvo = _simplificar(texto or "")
    if not alvo:
        return None
    candidatas = [o for o in opcoes if _simplificar(o["nome"]) and _simplificar(o["nome"]) in alvo]
    return max(candidatas, key=lambda o: len(o["nome"]), default=None)
