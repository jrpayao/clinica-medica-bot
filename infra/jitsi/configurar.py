"""Gera o `.env` do Jitsi Meet próprio do MedBot e mostra o que colocar no `backend/.env`.

Uso (local, na própria máquina):
    python infra/jitsi/configurar.py

Uso (servidor, com domínio e HTTPS):
    python infra/jitsi/configurar.py --url https://video.suaclinica.com.br --ip 203.0.113.10 --letsencrypt voce@suaclinica.com.br

O endereço é sempre https: a imagem oficial do Jitsi monta os endereços internos assim, e o navegador
só libera câmera e microfone em página segura.

O arquivo gerado tem senhas e o segredo que assina o acesso às salas: não vai para o git.
Rodar de novo mantém o segredo e as senhas já gerados, a menos que se passe --novo-segredo.
"""

import argparse
import secrets
import socket
from pathlib import Path
from urllib.parse import urlparse

AQUI = Path(__file__).resolve().parent
ARQUIVO = AQUI / ".env"
APP_ID = "medbot"
SENHAS = (
    "JICOFO_AUTH_PASSWORD", "JVB_AUTH_PASSWORD", "JIGASI_XMPP_PASSWORD", "JIGASI_TRANSCRIBER_PASSWORD",
    "JIBRI_RECORDER_PASSWORD", "JIBRI_XMPP_PASSWORD",
)


def ip_da_rede() -> str:
    """Endereço desta máquina na rede local (para outros aparelhos da mesma rede entrarem na chamada)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # não envia nada: só descobre a interface de saída
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def atuais() -> dict[str, str]:
    if not ARQUIVO.exists():
        return {}
    linhas = ARQUIVO.read_text(encoding="utf-8").splitlines()
    pares = (linha.split("=", 1) for linha in linhas if "=" in linha and not linha.startswith("#"))
    return {chave.strip(): valor.strip() for chave, valor in pares}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="https://localhost:8443",
                   help="endereço público do Jitsi, sempre https (padrão: https://localhost:8443)")
    p.add_argument("--ip", action="append",
                   help="IP que os participantes alcançam (pode repetir). Padrão: 127.0.0.1 e o IP da rede local")
    p.add_argument("--letsencrypt", metavar="EMAIL",
                   help="emite certificado HTTPS para o domínio da --url (exige portas 80 e 443 abertas)")
    p.add_argument("--api", default="http://localhost:8100",
                   help="endereço público da API do MedBot, de onde a sala busca o logo da unidade (padrão: http://localhost:8100)")
    p.add_argument("--sem-api", action="store_true",
                   help="usa só a marca do MedBot, sem buscar o logo da unidade (ex.: Jitsi sem backend)")
    p.add_argument("--fuso", default="America/Sao_Paulo")
    p.add_argument("--novo-segredo", action="store_true",
                   help="troca o segredo das salas (o backend precisa ser atualizado junto)")
    args = p.parse_args()

    url = urlparse(args.url)
    if url.scheme != "https":
        raise SystemExit("O Jitsi só funciona em https. Use, por exemplo, https://localhost:8443.")
    endereco = args.url.rstrip("/")
    local = url.port is not None  # com porta explícita: uso local, com certificado autoassinado

    antes = atuais()
    segredo = (not args.novo_segredo and antes.get("JWT_APP_SECRET")) or secrets.token_hex(32)
    ips = args.ip or sorted({"127.0.0.1", ip_da_rede()})

    linhas = [
        "# Gerado por infra/jitsi/configurar.py. Não versionar.",
        "CONFIG=./config",
        f"TZ={args.fuso}",
        f"PUBLIC_URL={endereco}",
        f"JVB_ADVERTISE_IPS={','.join(ips)}",
        "",
        "# Portas",
        f"HTTP_PORT={8000 if local else 80}",
        f"HTTPS_PORT={url.port or 443}",
        f"ENABLE_HTTP_REDIRECT={0 if local else 1}",
        "# portas de diagnóstico (só em 127.0.0.1), fora das faixas mais disputadas",
        "JVB_COLIBRI_PORT=18080",
        "JICOFO_REST_PORT=18888",
    ]
    if args.letsencrypt:
        linhas += ["ENABLE_LETSENCRYPT=1", f"LETSENCRYPT_DOMAIN={url.hostname}", f"LETSENCRYPT_EMAIL={args.letsencrypt}"]
    linhas += [
        "",
        "# Só entra em sala quem chega com acesso assinado pelo MedBot",
        "ENABLE_AUTH=1",
        "ENABLE_GUESTS=0",
        "AUTH_TYPE=jwt",
        f"JWT_APP_ID={APP_ID}",
        f"JWT_APP_SECRET={segredo}",
        f"JWT_ACCEPTED_ISSUERS={APP_ID}",
        "JWT_ACCEPTED_AUDIENCES=jitsi",
        # Moderador é só quem o MedBot indica no acesso assinado (o profissional), não todo participante
        "XMPP_MUC_MODULES=token_affiliation",
        "ENABLE_AUTO_OWNER=0",
        # o acesso assinado é conferido pelo servidor de salas; se o controlador de conferência também
        # autenticar, ele promove todo participante a moderador
        "JICOFO_ENABLE_AUTH=0",
        "",
        "# Marca da sala: logo da unidade dona do atendimento, buscado na API do MedBot (T158)",
        ("DYNAMIC_BRANDING_URL=/static/medbot-branding.json" if args.sem_api
         else f"BRANDING_DATA_URL={args.api.rstrip('/')}/v1/salas/marca"),
        "",
        "# Chamada entra direto, sem tela de boas-vindas nem convite para criar salas",
        "ENABLE_WELCOME_PAGE=0",
        "ENABLE_CLOSE_PAGE=1",  # quem sai vai para a tela de encerramento do MedBot (marca/encerramento.html)
        "ENABLE_PREJOIN_PAGE=0",
        "DISABLE_DEEP_LINKING=1",
        "DEFAULT_LANGUAGE=pt-BR",  # código desta versão do Jitsi (arquivo lang/main-pt-BR.json)
        "",
        "# Senhas internas entre os serviços do Jitsi",
        *[f"{nome}={antes.get(nome) or secrets.token_hex(16)}" for nome in SENHAS],
        "",
    ]
    ARQUIVO.write_text("\n".join(linhas), encoding="utf-8")

    print(f"Gerado: {ARQUIVO}")
    print()
    print("Suba o Jitsi:")
    print("    cd infra/jitsi && docker compose up -d")
    print()
    print("No backend/.env, deixe estas linhas (o segredo está no arquivo gerado, na linha JWT_APP_SECRET):")
    print(f"    JITSI_BASE_URL={endereco}")
    print(f"    JITSI_APP_ID={APP_ID}")
    print("    JITSI_APP_SECRET=<valor de JWT_APP_SECRET>")
    print()
    print("Depois reinicie o backend.")
    if local and not args.letsencrypt:
        print()
        print(f"Certificado autoassinado: abra {endereco} uma vez em cada navegador e aceite o aviso de segurança.")
        print("Sem isso, o vídeo embutido na tela do atendimento fica em branco.")


if __name__ == "__main__":
    main()
