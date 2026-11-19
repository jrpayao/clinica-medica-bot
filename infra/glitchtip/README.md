# GlitchTip: erros com aviso

Recebe os erros da API e do worker do Celery e avisa por e-mail. É compatível com o SDK do Sentry: para usar o
Sentry pago no lugar, basta trocar o `SENTRY_DSN` do backend.

Imagem oficial `glitchtip/glitchtip:7.0.0`, num contêiner só (páginas, recebimento e tarefas), com Postgres e Valkey
próprios. Consumo aproximado: 400 a 700 MB de memória.

## Subir na sua máquina

```bash
python infra/glitchtip/configurar.py
cd infra/glitchtip && docker compose up -d
# quando http://localhost:8020 responder:
python infra/glitchtip/configurar.py --preparar --apontar-backend
```

Reinicie o backend e o worker depois. O `--preparar` cria:

- administrador `admin@medbot.local` (senha em `ADMIN_SENHA` no `infra/glitchtip/.env`);
- organização **MedBot** e projeto **medbot-api**;
- alerta **Erro novo**: e-mail para a equipe a cada erro novo.

Sem SMTP, o e-mail do alerta só aparece no log (`docker compose logs web`). Para enviar de verdade:

```bash
python infra/glitchtip/configurar.py --email-url "smtp+tls://usuario:senha@smtp.servidor.com:587" --email-remetente alertas@suaclinica.com.br
cd infra/glitchtip && docker compose up -d
```

## O que sai do servidor (LGPD)

Antes de enviar qualquer erro, o backend (`app/core/erros.py`) oculta em todo o evento:

- CPF, e-mail e telefone;
- o código do link da teleconsulta (`/teleconsulta/[oculto]`) e tokens de acesso (JWT, `jwt=`, `token=`, `senha=`);
- os valores das consultas ao banco que aparecem nos erros do SQLAlchemy (`[parameters: [oculto]]`).

Também não envia corpo de requisição, cookies, cabeçalho `Authorization`, variáveis locais nem identificação do usuário.
O que segue: tipo do erro, mensagem já limpa, rota, linha do código e versão (commit).

Limite: um nome de paciente escrito à mão numa mensagem de erro não tem como ser reconhecido. As mensagens de erro do
código não devem citar nome de pessoa.

## No servidor

```bash
python infra/glitchtip/configurar.py --url https://erros.suaclinica.com.br --ambiente producao \
  --admin-email voce@suaclinica.com.br --email-url "smtp+tls://..." 
```

- Publique a porta 8020 atrás do HTTPS do CapRover; o `ALLOWED_HOSTS` já fica restrito ao domínio da `--url`.
- O backend precisa alcançar o endereço do GlitchTip (rede interna ou domínio público).
- Retenção padrão: 30 dias (`--retencao-dias`).

## Conferir

Um erro de teste, pelo mesmo caminho da API:

```bash
cd backend && uv run python -c "from app.core import erros; import sentry_sdk; erros.iniciar('api'); sentry_sdk.capture_message('teste de envio'); sentry_sdk.flush()"
```

Ele aparece em <http://localhost:8020> no projeto medbot-api, e o alerta sai em até um minuto.
