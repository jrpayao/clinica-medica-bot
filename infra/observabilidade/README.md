# Observabilidade do MedBot

Prometheus coleta as métricas da API; o Grafana mostra o painel **MedBot — visão geral**, que também lê o
banco (custo de IA por unidade, agendamentos por canal) com um usuário que só enxerga colunas sem dado de paciente.

## Subir na sua máquina

```bash
python infra/observabilidade/configurar.py --aplicar-banco --apontar-backend
cd infra/observabilidade && docker compose up -d
```

Reinicie o backend depois (o `--apontar-backend` grava `METRICS_TOKEN` no `backend/.env`).

- Grafana: <http://localhost:3000>, usuário `admin`, senha em `GRAFANA_SENHA_ADMIN` no `infra/observabilidade/.env`.
- Prometheus: <http://localhost:9090> (só nesta máquina).
- A API não precisa escutar fora do `127.0.0.1`: no Docker Desktop, `host.docker.internal` chega ao `127.0.0.1` da máquina.

Conferência automática (consulta de cada painel na última hora e captura de tela):

```bash
cd tools/video && node sonda-grafana.mjs
```

## O que o painel mostra

| Bloco | Painéis | De onde vem |
|---|---|---|
| API | requisições por minuto, erros (5xx e 4xx), tempo de resposta (mediana e 95%), rotas mais lentas | Prometheus |
| Inteligência artificial | custo, tokens e chamadas no período; chamadas a modelos sem preço; tokens por hora por modelo; tempo de resposta da IA; uso por unidade | banco e Prometheus |
| Cache e fila | acerto do cache por área, falhas do Redis, fila do Celery | Prometheus |
| Operação | agendamentos criados por dia, por canal | banco |

Métricas publicadas pela API (`backend/app/core/metricas.py`):

| Métrica | O que conta |
|---|---|
| `http_requests_total`, `http_request_duration_*` | requisições por rota, método e faixa de status; tempo de resposta |
| `medbot_ia_tokens_total{modelo,feature,tipo}` | tokens de entrada e de saída |
| `medbot_ia_chamadas_total`, `medbot_ia_custo_usd_total` | chamadas e custo estimado |
| `medbot_ia_latencia_segundos{feature}` | tempo de resposta do modelo |
| `medbot_ia_modelo_sem_preco_total{modelo}` | chamadas a modelo sem preço cadastrado (custo zerado) |
| `medbot_cache_total{area,resultado}` | acerto, falta e erro do cache (hoje só a licença) |
| `medbot_celery_fila_tamanho` | tarefas esperando na fila do Celery (-1: Redis fora do ar) |

## Preço dos modelos de produção

O custo só sai certo se o modelo tiver preço. Os locais (Ollama) custam zero; os de produção vão no `backend/.env`,
em dólares por token:

```
PRECOS_MODELOS={"openai/gpt-4o-mini": {"input": 0.00000015, "output": 0.0000006}}
```

Modelo sem preço aparece no painel "Chamadas a modelos sem preço" (fica vermelho acima de zero).

## Privacidade

O usuário `grafana_leitura` é só de leitura e só vê estas colunas (lista em `configurar.py`):

- `token_usage`: modelo, tipo de uso, tokens, custo, data e unidade;
- `estabelecimentos`: nome e se está ativo;
- `atendimentos`: status, canal, modalidade, motivo de cancelamento, data e unidade.

Nome, CPF, telefone, relato de sintomas e observações ficam inacessíveis.

## No servidor

- Gere com os endereços do servidor: `--banco-endereco postgres:5432` (nome do serviço na rede interna) e
  `--grafana-url https://grafana.suaclinica.com.br`. Aplique o usuário de leitura com `--container-banco <container>`.
- No `prometheus/prometheus.yml`, troque o alvo `host.docker.internal:8100` pelo serviço da API na rede interna.
- Publique só o Grafana (atrás do HTTPS do CapRover). O Prometheus e o `/metrics` da API ficam na rede interna;
  o `METRICS_TOKEN` protege o `/metrics` caso ele acabe exposto.
- Consumo aproximado: 300 a 500 MB de memória para os dois serviços, com 30 dias de métricas.

## Limites conhecidos

- Os contadores ficam na memória da API: reiniciar a API zera os totais (o Prometheus lida com isso nas taxas),
  e com mais de um worker do uvicorn seria preciso o modo multiprocesso do `prometheus_client`.
- Sem alertas por e-mail ou mensagem ainda: o painel mostra, mas não avisa. Os avisos de erro vêm com o GlitchTip.
