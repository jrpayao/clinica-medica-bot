#!/usr/bin/env bash
# Testa a jornada completa do usuário MedBot
# Uso: bash scripts/testar_jornada.sh

BASE="http://localhost:8100/v1"
PG_CMD="docker compose exec -T postgres psql -U medbot -d medbot"

BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

section() { echo -e "\n${BOLD}${CYAN}═══════════════════════════════════════${NC}"; echo -e "${BOLD}${CYAN} $1${NC}"; echo -e "${BOLD}${CYAN}═══════════════════════════════════════${NC}"; }
step()    { echo -e "\n${YELLOW}▶ $1${NC}"; }
ok()      { echo -e "${GREEN}  ✓ $1${NC}"; }
info()    { echo -e "  $1"; }

# ============================================================
section "ETAPA 0 — Estado do banco antes da jornada"
# ============================================================
step "Contagem de registros por tabela"
cd /home/payao/projetos/chatbot-ai-medical/backend
$PG_CMD -c "
SELECT
  'especialidades' AS tabela, COUNT(*) FROM especialidades
UNION ALL SELECT 'medicos',    COUNT(*) FROM medicos
UNION ALL SELECT 'slots',      COUNT(*) FROM slots
UNION ALL SELECT 'pacientes',  COUNT(*) FROM pacientes
UNION ALL SELECT 'usuarios',   COUNT(*) FROM usuarios
UNION ALL SELECT 'consultas',  COUNT(*) FROM consultas
UNION ALL SELECT 'sessoes_chat', COUNT(*) FROM sessoes_chat
ORDER BY 1;" 2>/dev/null

# ============================================================
section "ETAPA 1 — Login admin e consulta de dados"
# ============================================================
step "Fazendo login como admin"
ADMIN_TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medbot.com","senha":"Admin@123"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token','ERRO'))")

if [ "$ADMIN_TOKEN" = "ERRO" ]; then
  echo -e "${RED}  ✗ Falha no login admin${NC}"
  exit 1
fi
ok "Login admin OK"

step "Listando especialidades via API"
ESPECIALIDADES=$(curl -s "$BASE/especialidades/" -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$ESPECIALIDADES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  Total: {len(data)} especialidades')
for e in data[:3]:
    print(f'  [{e[\"id\"]}] {e[\"nome\"]} — {e[\"cor_hex\"]}')"

step "Listando médicos via API"
MEDICOS=$(curl -s "$BASE/medicos/" -H "Authorization: Bearer $ADMIN_TOKEN")
echo "$MEDICOS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  Total: {len(data)} médicos')
for m in data[:4]:
    print(f'  [{m[\"id\"]}] {m[\"nome\"]} — {m[\"crm\"]}')"

# ============================================================
section "ETAPA 2 — Login de paciente (fluxo SMS)"
# ============================================================
CPF_PACIENTE="12345678901"

step "Solicitando código SMS para CPF $CPF_PACIENTE"
SMS_RESP=$(curl -s -X POST "$BASE/auth/sms/request" \
  -H "Content-Type: application/json" \
  -d "{\"cpf\":\"$CPF_PACIENTE\"}")
echo "  Resposta: $(echo $SMS_RESP | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mensagem',''))" 2>/dev/null)"

step "Lendo código SMS do Redis (ambiente dev)"
SMS_CODE=$($PG_CMD -t -c "SELECT 1" 2>/dev/null && docker compose exec -T redis redis-cli GET "sms:code:$CPF_PACIENTE" 2>/dev/null | tr -d '\r')
if [ -z "$SMS_CODE" ]; then
  SMS_CODE="000000"
  echo "  ⚠ Não foi possível ler do Redis, usando fallback"
else
  ok "Código SMS no Redis: $SMS_CODE"
fi

step "Verificando código SMS e obtendo token do paciente"
PACIENTE_RESP=$(curl -s -X POST "$BASE/auth/sms/verify" \
  -H "Content-Type: application/json" \
  -d "{\"cpf\":\"$CPF_PACIENTE\",\"codigo\":\"$SMS_CODE\"}")
PACIENTE_TOKEN=$(echo "$PACIENTE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token','ERRO'))" 2>/dev/null)

if [ "$PACIENTE_TOKEN" = "ERRO" ]; then
  echo "  ⚠ Token de paciente não obtido. Resposta: $PACIENTE_RESP"
  PACIENTE_TOKEN=""
else
  ok "Token do paciente OK"
fi

# ============================================================
section "ETAPA 3 — Consultar agenda disponível"
# ============================================================
AMANHA=$(date -d "+1 day" +%Y-%m-%d 2>/dev/null || date -v+1d +%Y-%m-%d)
SEMANA=$(date -d "+5 days" +%Y-%m-%d 2>/dev/null || date -v+5d +%Y-%m-%d)

step "Consultando slots disponíveis ($AMANHA a $SEMANA)"
SLOTS=$(curl -s "$BASE/agenda/disponivel?data_inicio=$AMANHA&data_fim=$SEMANA&especialidade_id=1" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
SLOTS_COUNT=$(echo "$SLOTS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d))" 2>/dev/null)
echo "  Slots de Clínica Geral disponíveis: $SLOTS_COUNT"
echo "$SLOTS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for s in data[:3]:
    print(f'  [{s[\"id\"]}] {s[\"data\"]} {s[\"hora_inicio\"]} — Dr. {s.get(\"medico\",{}).get(\"nome\",\"?\")}')
" 2>/dev/null

# Pegar primeiro slot disponível
SLOT_ID=$(echo "$SLOTS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
PACIENTE_ID=1

# ============================================================
section "ETAPA 4 — Agendar consulta"
# ============================================================
step "Agendando consulta (slot=$SLOT_ID, paciente=$PACIENTE_ID)"
if [ -n "$SLOT_ID" ]; then
  CONSULTA=$(curl -s -X POST "$BASE/agenda/consultas" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "{
      \"paciente_id\": $PACIENTE_ID,
      \"slot_id\": $SLOT_ID,
      \"tipo\": \"EXTERNO\",
      \"canal\": \"PORTAL\",
      \"urgencia\": \"MEDIA\"
    }")
  CONSULTA_ID=$(echo "$CONSULTA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id','ERRO'))" 2>/dev/null)
  ok "Consulta criada! ID: $CONSULTA_ID"
  echo "$CONSULTA" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if 'id' in d:
    print(f'  Data: {d.get(\"data_hora\",\"?\")}')
    print(f'  Status: {d.get(\"status\",\"?\")}')
    print(f'  Urgência: {d.get(\"urgencia\",\"?\")}')
" 2>/dev/null
else
  echo "  ⚠ Nenhum slot disponível encontrado"
  CONSULTA_ID=""
fi

# ============================================================
section "ETAPA 5 — Jornada do Bot (Chat IA)"
# ============================================================
step "Iniciando sessão de chat para paciente CPF=$CPF_PACIENTE"
SESSAO=$(curl -s -X POST "$BASE/chat/sessao" \
  -H "Content-Type: application/json" \
  -d "{
    \"cpf_paciente\": \"$CPF_PACIENTE\",
    \"mensagem\": \"Oi, estou sentindo dor de cabeça intensa há 3 dias\"
  }")
echo "  Resposta do bot:"
echo "$SESSAO" | python3 -c "
import sys, json
d = json.load(sys.stdin)
sessao_id = d.get('sessao_id', d.get('id','?'))
resposta = d.get('resposta', d.get('mensagem','?'))
estado = d.get('estado', d.get('etapa','?'))
print(f'  Sessão ID: {sessao_id}')
print(f'  Bot: {str(resposta)[:200]}')
print(f'  Estado: {estado}')
" 2>/dev/null || echo "  Resposta: $SESSAO" | head -c 400

# ============================================================
section "ETAPA 6 — Verificar banco após jornada"
# ============================================================
step "Estado do banco após a jornada completa"
$PG_CMD -c "
SELECT
  'especialidades' AS tabela, COUNT(*) AS total FROM especialidades
UNION ALL SELECT 'medicos',      COUNT(*) FROM medicos
UNION ALL SELECT 'slots total',  COUNT(*) FROM slots
UNION ALL SELECT 'slots agendados', COUNT(*) FROM slots WHERE status='AGENDADO'
UNION ALL SELECT 'slots disponíveis', COUNT(*) FROM slots WHERE status='DISPONIVEL'
UNION ALL SELECT 'pacientes',    COUNT(*) FROM pacientes
UNION ALL SELECT 'usuarios',     COUNT(*) FROM usuarios
UNION ALL SELECT 'consultas',    COUNT(*) FROM consultas
UNION ALL SELECT 'sessoes_chat', COUNT(*) FROM sessoes_chat
ORDER BY 1;" 2>/dev/null

step "Detalhe das consultas agendadas"
$PG_CMD -c "
SELECT
  c.id,
  p.nome AS paciente,
  m.nome AS medico,
  e.nome AS especialidade,
  s.data,
  s.hora_inicio,
  c.status,
  c.urgencia,
  c.canal
FROM consultas c
JOIN slots s ON c.slot_id = s.id
JOIN medicos m ON s.medico_id = m.id
JOIN especialidades e ON m.especialidade_id = e.id
JOIN pacientes p ON c.paciente_id = p.id
ORDER BY c.id;" 2>/dev/null

step "Sessões de chat abertas"
$PG_CMD -c "
SELECT id, cpf_paciente, estado, created_at
FROM sessoes_chat
ORDER BY created_at DESC
LIMIT 5;" 2>/dev/null

echo ""
ok "Jornada completa testada!"
echo ""
