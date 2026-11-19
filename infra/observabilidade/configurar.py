"""Prepara a observabilidade (Prometheus + Grafana) do MedBot.

Uso (local):
    python infra/observabilidade/configurar.py --aplicar-banco --apontar-backend
    cd infra/observabilidade && docker compose up -d

O que faz:
- gera `infra/observabilidade/.env` (senha do admin do Grafana e do usuário de leitura do banco) e
  `segredos/metrics_token` (token que o Prometheus usa para ler GET /metrics da API);
- com --aplicar-banco: cria ou atualiza no Postgres o usuário `grafana_leitura`, que só lê colunas sem dado
  de paciente (nada de nome, CPF, telefone ou relato de sintomas);
- com --apontar-backend: grava METRICS_TOKEN no backend/.env (reinicie o backend depois).

Rodar de novo mantém as senhas e o token já gerados, a menos que se passe --novas-senhas.
Os arquivos gerados têm segredos e ficam fora do git.
"""

import argparse
import re
import secrets
import subprocess
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ARQUIVO = AQUI / ".env"
TOKEN = AQUI / "segredos" / "metrics_token"
BACKEND_ENV = AQUI.parents[1] / "backend" / ".env"

# Colunas que o Grafana pode ler. Qualquer coisa fora daqui (nome do paciente, CPF, telefone,
# relato de sintomas, observações) fica inacessível ao usuário de leitura.
COLUNAS_LIBERADAS = {
    "token_usage": ["id", "estabelecimento_id", "modelo", "feature", "prompt_tokens", "completion_tokens",
                    "total_tokens", "cost_usd", "created_at"],
    "estabelecimentos": ["id", "nome", "ativo"],
    "atendimentos": ["id", "estabelecimento_id", "status", "canal_origem", "modalidade", "motivo_cancelamento",
                     "created_at"],
}


def atuais() -> dict[str, str]:
    if not ARQUIVO.exists():
        return {}
    linhas = ARQUIVO.read_text(encoding="utf-8").splitlines()
    return dict(linha.split("=", 1) for linha in linhas if "=" in linha and not linha.startswith("#"))


def sql_usuario_leitura(senha: str, banco: str) -> str:
    concessoes = "\n".join(
        f"GRANT SELECT ({', '.join(colunas)}) ON {tabela} TO grafana_leitura;"
        for tabela, colunas in COLUNAS_LIBERADAS.items()
    )
    return f"""
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana_leitura') THEN
        CREATE ROLE grafana_leitura LOGIN;
    END IF;
END $$;
ALTER ROLE grafana_leitura WITH LOGIN PASSWORD '{senha}' CONNECTION LIMIT 5;
ALTER ROLE grafana_leitura SET default_transaction_read_only = on;
ALTER ROLE grafana_leitura SET statement_timeout = '10s';
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM grafana_leitura;
GRANT CONNECT ON DATABASE {banco} TO grafana_leitura;
GRANT USAGE ON SCHEMA public TO grafana_leitura;
{concessoes}
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--banco-endereco", default="host.docker.internal:5432",
                   help="host:porta do Postgres visto de dentro do Grafana (padrão: o da máquina local)")
    p.add_argument("--banco-nome", default="medbot")
    p.add_argument("--grafana-url", default="http://localhost:3000")
    p.add_argument("--retencao", default="30d", help="por quanto tempo o Prometheus guarda as métricas")
    p.add_argument("--aplicar-banco", action="store_true", help="cria/atualiza o usuário de leitura no Postgres")
    p.add_argument("--container-banco", default="medbot-postgres", help="container do Postgres (para --aplicar-banco)")
    p.add_argument("--usuario-banco", default="medbot", help="dono do banco (para --aplicar-banco)")
    p.add_argument("--apontar-backend", action="store_true", help="grava METRICS_TOKEN no backend/.env")
    p.add_argument("--novas-senhas", action="store_true")
    args = p.parse_args()

    antes = {} if args.novas_senhas else atuais()
    senha_admin = antes.get("GRAFANA_SENHA_ADMIN") or secrets.token_urlsafe(18)
    senha_leitura = antes.get("BANCO_LEITURA_SENHA") or secrets.token_hex(20)
    token = (not args.novas_senhas and TOKEN.exists() and TOKEN.read_text(encoding="utf-8").strip()) or secrets.token_hex(24)

    ARQUIVO.write_text("\n".join([
        "# Gerado por infra/observabilidade/configurar.py. Não versionar.",
        f"GRAFANA_SENHA_ADMIN={senha_admin}",
        f"GRAFANA_URL={args.grafana_url}",
        f"BANCO_ENDERECO={args.banco_endereco}",
        f"BANCO_NOME={args.banco_nome}",
        f"BANCO_LEITURA_SENHA={senha_leitura}",
        f"RETENCAO_METRICAS={args.retencao}",
        "",
    ]), encoding="utf-8")
    TOKEN.parent.mkdir(exist_ok=True)
    TOKEN.write_text(token, encoding="utf-8")
    print(f"Gerado: {ARQUIVO} e {TOKEN}")

    if args.aplicar_banco:
        subprocess.run(
            ["docker", "exec", "-i", args.container_banco, "psql", "-v", "ON_ERROR_STOP=1", "-q",
             "-U", args.usuario_banco, "-d", args.banco_nome],
            input=sql_usuario_leitura(senha_leitura, args.banco_nome), text=True, check=True,
        )
        print("Usuário de leitura grafana_leitura pronto no banco.")

    if args.apontar_backend:
        texto = BACKEND_ENV.read_bytes().decode("utf-8") if BACKEND_ENV.exists() else ""
        quebra = "\r\n" if "\r\n" in texto else "\n"
        if re.search(r"^METRICS_TOKEN=.*$", texto, flags=re.M):
            texto = re.sub(r"^METRICS_TOKEN=[^\r\n]*", lambda _m: f"METRICS_TOKEN={token}", texto, flags=re.M)
        else:
            texto = texto.rstrip("\r\n") + quebra + f"METRICS_TOKEN={token}" + quebra
        BACKEND_ENV.write_bytes(texto.encode("utf-8"))
        print(f"{BACKEND_ENV}: METRICS_TOKEN gravado (oculto). Reinicie o backend.")

    print()
    print("Suba os serviços:  cd infra/observabilidade && docker compose up -d")
    print(f"Grafana: {args.grafana_url}  (usuário admin; a senha está em GRAFANA_SENHA_ADMIN no .env gerado)")


if __name__ == "__main__":
    main()
