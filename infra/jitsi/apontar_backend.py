"""Copia para o `backend/.env` o endereço, o identificador e o segredo do Jitsi gerados em `infra/jitsi/.env`.

Uso:
    python infra/jitsi/apontar_backend.py

O segredo não é impresso. Reinicie o backend depois.
"""

import re
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ORIGEM = AQUI / ".env"
DESTINO = AQUI.parents[1] / "backend" / ".env"


def main() -> None:
    if not ORIGEM.exists():
        raise SystemExit("Rode antes: python infra/jitsi/configurar.py")
    jitsi = dict(
        linha.split("=", 1)
        for linha in ORIGEM.read_text(encoding="utf-8").splitlines()
        if "=" in linha and not linha.startswith("#")
    )
    novos = {
        "JITSI_BASE_URL": jitsi["PUBLIC_URL"],
        "JITSI_APP_ID": jitsi["JWT_APP_ID"],
        "JITSI_APP_SECRET": jitsi["JWT_APP_SECRET"],
    }
    texto = DESTINO.read_bytes().decode("utf-8") if DESTINO.exists() else ""
    quebra = "\r\n" if "\r\n" in texto else "\n"
    for chave, valor in novos.items():
        linha = f"{chave}={valor}"
        if re.search(rf"^{chave}=.*$", texto, flags=re.M):
            texto = re.sub(rf"^{chave}=[^\r\n]*", lambda _m, nova=linha: nova, texto, flags=re.M)
        else:
            texto = texto.rstrip("\r\n") + quebra + linha + quebra
    DESTINO.write_bytes(texto.encode("utf-8"))
    print(f"{DESTINO} atualizado: JITSI_BASE_URL={novos['JITSI_BASE_URL']}, JITSI_APP_ID={novos['JITSI_APP_ID']}, JITSI_APP_SECRET=(oculto)")


if __name__ == "__main__":
    main()
