"""Testes — Envio de erros ao GlitchTip/Sentry, com dados pessoais removidos antes de sair do servidor."""

import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

from app.core import erros


class Caixa(Transport):
    """Transporte que guarda os eventos em vez de enviá-los."""

    eventos: list[dict] = []

    def __init__(self, options=None):
        super().__init__(options)

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                Caixa.eventos.append(item.payload.json)


@pytest.fixture
def sentry_de_teste(monkeypatch):
    Caixa.eventos = []
    monkeypatch.setattr(erros.settings, "sentry_dsn", "https://chave@glitchtip.teste/1")
    assert erros.iniciar("api", transporte=Caixa) is True
    yield Caixa.eventos
    sentry_sdk.init()  # desliga


# ── Limpeza de dados pessoais ───────────────────────────────────────────────

@pytest.mark.parametrize(
    ("texto", "nao_pode_sobrar"),
    [
        ("Cliente CPF 529.982.247-25 não encontrado", "529.982.247-25"),
        ("cpf=52998224725", "52998224725"),
        ("Falha ao enviar para maria.souza@gmail.com", "maria.souza@gmail.com"),
        ("WhatsApp (11) 98888-7777 recusou", "98888-7777"),
        ("telefone 5511988887777", "5511988887777"),
        ("GET /v1/teleconsulta/gc7qP5MjZQ2HllshJCNCsPbNLM7Hugkj4fE80cNEfw0", "gc7qP5MjZQ2HllshJCNCsPbNLM7Hugkj4fE80cNEfw0"),
        ("https://localhost:8443/medbot-sala?jwt=eyJhbGciOiJIUzI1NiJ9.eyJyb29tIjoieCJ9.assinatura", "eyJhbGciOiJIUzI1NiJ9"),
        ("Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc-def_123", "eyJzdWIiOiIxIn0"),
        ("?senha=Admin@123&x=1", "Admin@123"),
        ("(psycopg.errors.UniqueViolation) duplicate key\n[SQL: INSERT INTO clientes (nome, cpf) VALUES ($1, $2)]\n"
         "[parameters: ('Maria Aparecida Souza', '52998224725')]\n(Background on this error at: https://sqlalche.me/e/20/gkpj)",
         "Maria Aparecida Souza"),
    ],
)
def test_mascarar_remove_dado_pessoal_e_segredo(texto, nao_pode_sobrar):
    assert nao_pode_sobrar not in erros.mascarar(texto)


def test_mascarar_preserva_o_resto_da_mensagem():
    assert erros.mascarar("Slot 42 indisponível às 14:30") == "Slot 42 indisponível às 14:30"


def test_limpar_evento_percorre_todo_o_evento_e_remove_o_corpo_da_requisicao():
    evento = {
        "message": "erro com 529.982.247-25",
        "exception": {"values": [{"value": "maria@teste.com sem cadastro", "stacktrace": {"frames": []}}]},
        "request": {
            "url": "http://api/v1/teleconsulta/tokensecreto123456",
            "query_string": "jwt=eyJa.eyJb.c",
            "data": {"cpf": "52998224725", "senha": "x"},
            "cookies": {"sessao": "abc"},
            "headers": {"Authorization": "Bearer eyJa.eyJb.c", "User-Agent": "teste"},
        },
        "breadcrumbs": {"values": [{"message": "ligou para (11) 98888-7777"}]},
        "extra": {"lista": ["529.982.247-25", 7, None]},
    }

    limpo = erros.limpar_evento(evento, {})
    texto = str(limpo)

    for proibido in ("529.982.247-25", "52998224725", "maria@teste.com", "tokensecreto123456", "eyJb", "98888-7777"):
        assert proibido not in texto
    assert "data" not in limpo["request"] and "cookies" not in limpo["request"]
    assert "Authorization" not in limpo["request"]["headers"]
    assert limpo["request"]["headers"]["User-Agent"] == "teste"
    assert limpo["extra"]["lista"][1:] == [7, None]


# ── Inicialização ───────────────────────────────────────────────────────────

def test_sem_dsn_nao_liga_o_envio(monkeypatch):
    monkeypatch.setattr(erros.settings, "sentry_dsn", "")
    assert erros.iniciar("api") is False


def test_configuracao_nao_envia_dado_pessoal_por_padrao(sentry_de_teste):
    opcoes = sentry_sdk.get_client().options
    assert opcoes["send_default_pii"] is False
    assert opcoes["include_local_variables"] is False
    assert opcoes["max_request_body_size"] == "never"
    assert opcoes["environment"] == erros.settings.sentry_ambiente


async def test_erro_nao_tratado_na_api_chega_ao_glitchtip_sem_dado_pessoal(sentry_de_teste, async_client):
    from app.main import app

    async def falha(token: str):
        # mensagem no formato que aparece de verdade: endereço da sala e valores de uma consulta ao banco
        raise RuntimeError(
            f"Falha em /v1/teleconsulta/{token} para o CPF 529.982.247-25\n"
            "[parameters: ('Maria Aparecida Souza', 'segredoDoPaciente999')]"
        )

    app.add_api_route("/v1/_teste/teleconsulta/{token}", falha)
    try:
        with pytest.raises(RuntimeError):
            await async_client.get("/v1/_teste/teleconsulta/segredoDoPaciente999")
    finally:
        app.router.routes.pop()

    sentry_sdk.flush()
    assert len(sentry_de_teste) == 1
    capturado = sentry_de_teste[0]
    # onde os dados de verdade aparecem: mensagem do erro, endereço, cabeçalhos e rastros.
    # O trecho de código-fonte que acompanha o erro mostra só código (aqui, o deste teste).
    evento = str([
        [v.get("type"), v.get("value")] for v in capturado["exception"]["values"]
    ] + [capturado.get("request"), capturado.get("breadcrumbs"), capturado.get("transaction")])
    assert "RuntimeError" in evento
    assert "/teleconsulta/[oculto]" in evento
    assert "529.982.247-25" not in evento
    assert "segredoDoPaciente999" not in evento
    assert "Maria Aparecida Souza" not in evento
