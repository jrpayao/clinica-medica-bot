"""Prepara o GlitchTip do MedBot (erros da API e do worker, com aviso por e-mail).

Uso (local):
    python infra/glitchtip/configurar.py
    cd infra/glitchtip && docker compose up -d
    python infra/glitchtip/configurar.py --preparar --apontar-backend      # quando o GlitchTip estiver no ar

O que faz:
- gera `infra/glitchtip/.env` (chave secreta, senha do banco e do administrador);
- com --preparar: cria o administrador, a organização "MedBot", o projeto "medbot-api" e um alerta que
  avisa por e-mail a cada erro novo; mostra onde ficou o DSN;
- com --apontar-backend: grava SENTRY_DSN e SENTRY_AMBIENTE no backend/.env (reinicie o backend e o worker).

O e-mail do administrador recebe os avisos. Para eles saírem de verdade, informe --email-url (SMTP).
Rodar de novo mantém as senhas já geradas. Os arquivos gerados têm segredos e ficam fora do git.
"""

import argparse
import json
import re
import secrets
import subprocess
from pathlib import Path
from urllib.parse import urlparse

AQUI = Path(__file__).resolve().parent
ARQUIVO = AQUI / ".env"
BACKEND_ENV = AQUI.parents[1] / "backend" / ".env"

# Executado dentro do contêiner do GlitchTip (manage.py shell). Idempotente.
PREPARO = r"""
import json
from allauth.account.models import EmailAddress
from apps.alerts.constants import RecipientType
from apps.alerts.models import AlertRecipient, ProjectAlert
from apps.organizations_ext.models import Organization
from apps.projects.models import Project, ProjectKey
from apps.teams.models import Team
from apps.users.models import User

email, senha = {email!r}, {senha!r}
usuario = User.objects.filter(email=email).first()
if usuario is None:
    usuario = User.objects.create_superuser(email=email, password=senha)
else:
    usuario.set_password(senha)
    usuario.save()
EmailAddress.objects.get_or_create(user=usuario, email=email, defaults={{"primary": True, "verified": True}})

org, _ = Organization.objects.get_or_create(slug="medbot", defaults={{"name": "MedBot"}})
if not org.users.filter(pk=usuario.pk).exists():
    org.add_user(usuario)
projeto, _ = Project.objects.get_or_create(slug="medbot-api", organization=org, defaults={{"name": "medbot-api"}})
equipe, _ = Team.objects.get_or_create(slug="medbot", organization=org)
equipe.members.add(org.organization_users.get(user=usuario))
equipe.projects.add(projeto)

alerta, _ = ProjectAlert.objects.get_or_create(
    project=projeto, name="Erro novo", defaults={{"timespan_minutes": 1, "quantity": 1}}
)
AlertRecipient.objects.get_or_create(alert=alerta, recipient_type=RecipientType.EMAIL, url="")

chave = ProjectKey.objects.filter(project=projeto).first() or ProjectKey.objects.create(project=projeto)
print("RESULTADO=" + json.dumps({{"dsn": chave.get_dsn()}}))
"""


def atuais() -> dict[str, str]:
    if not ARQUIVO.exists():
        return {}
    linhas = ARQUIVO.read_text(encoding="utf-8").splitlines()
    return dict(linha.split("=", 1) for linha in linhas if "=" in linha and not linha.startswith("#"))


def gravar_no_backend(valores: dict[str, str]) -> None:
    texto = BACKEND_ENV.read_bytes().decode("utf-8") if BACKEND_ENV.exists() else ""
    quebra = "\r\n" if "\r\n" in texto else "\n"
    for chave, valor in valores.items():
        linha = f"{chave}={valor}"
        if re.search(rf"^{chave}=.*$", texto, flags=re.M):
            texto = re.sub(rf"^{chave}=[^\r\n]*", lambda _m, nova=linha: nova, texto, flags=re.M)
        else:
            texto = texto.rstrip("\r\n") + quebra + linha + quebra
    BACKEND_ENV.write_bytes(texto.encode("utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8020", help="endereço público do GlitchTip")
    p.add_argument("--porta", default="8020")
    p.add_argument("--admin-email", default="admin@medbot.local", help="login do administrador e destino dos avisos")
    p.add_argument("--email-url", default="", help="SMTP para os avisos, ex.: smtp+tls://usuario:senha@host:587")
    p.add_argument("--email-remetente", default="glitchtip@medbot.local")
    p.add_argument("--retencao-dias", default="30")
    p.add_argument("--ambiente", default="desenvolvimento", help="nome do ambiente nos erros (SENTRY_AMBIENTE)")
    p.add_argument("--preparar", action="store_true", help="cria administrador, organização, projeto e alerta")
    p.add_argument("--apontar-backend", action="store_true", help="grava SENTRY_DSN no backend/.env")
    p.add_argument("--novas-senhas", action="store_true")
    args = p.parse_args()

    antes = {} if args.novas_senhas else atuais()
    valores = {
        "SECRET_KEY": antes.get("SECRET_KEY") or secrets.token_urlsafe(48),
        "POSTGRES_SENHA": antes.get("POSTGRES_SENHA") or secrets.token_hex(20),
        "ADMIN_EMAIL": args.admin_email,
        "ADMIN_SENHA": antes.get("ADMIN_SENHA") or secrets.token_urlsafe(18),
        "GLITCHTIP_URL": args.url.rstrip("/"),
        # só responde pelo próprio endereço (e pela máquina local)
        "ALLOWED_HOSTS": ",".join(dict.fromkeys([urlparse(args.url).hostname or "localhost", "localhost", "127.0.0.1"])),
        "PORTA": args.porta,
        "EMAIL_URL": args.email_url or antes.get("EMAIL_URL", ""),
        "EMAIL_REMETENTE": args.email_remetente,
        "RETENCAO_DIAS": args.retencao_dias,
    }
    ARQUIVO.write_text(
        "# Gerado por infra/glitchtip/configurar.py. Não versionar.\n"
        + "\n".join(f"{chave}={valor}" for chave, valor in valores.items()) + "\n",
        encoding="utf-8",
    )
    print(f"Gerado: {ARQUIVO}")

    if args.preparar:
        script = PREPARO.format(email=valores["ADMIN_EMAIL"], senha=valores["ADMIN_SENHA"])
        saida = subprocess.run(
            ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "shell"],
            cwd=AQUI, input=script, text=True, capture_output=True, check=False,
        )
        linha = next((l for l in saida.stdout.splitlines() if l.startswith("RESULTADO=")), None)
        if linha is None:
            raise SystemExit(f"Não foi possível preparar o GlitchTip:\n{saida.stderr[-2000:]}")
        dsn = json.loads(linha.removeprefix("RESULTADO="))["dsn"]
        (AQUI / "segredos").mkdir(exist_ok=True)
        (AQUI / "segredos" / "dsn").write_text(dsn, encoding="utf-8")
        print("GlitchTip pronto: organização MedBot, projeto medbot-api, alerta \"Erro novo\" por e-mail.")
        print(f"DSN gravado em {AQUI / 'segredos' / 'dsn'}")

        if args.apontar_backend:
            gravar_no_backend({"SENTRY_DSN": dsn, "SENTRY_AMBIENTE": args.ambiente})
            print(f"{BACKEND_ENV}: SENTRY_DSN e SENTRY_AMBIENTE gravados. Reinicie o backend e o worker.")

    print()
    print(f"GlitchTip: {valores['GLITCHTIP_URL']}  (login {valores['ADMIN_EMAIL']}; senha em ADMIN_SENHA no .env gerado)")


if __name__ == "__main__":
    main()
