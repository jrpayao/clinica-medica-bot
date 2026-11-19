# Jitsi Meet próprio para a telemedicina

Servidor de vídeo das teleconsultas do MedBot. O servidor público `meet.jit.si` não serve para uso real
(exige login de quem abre a sala e limita chamadas embutidas), por isso o MedBot roda o seu.

O `docker-compose.yml` desta pasta é o oficial do projeto
[jitsi/docker-jitsi-meet](https://github.com/jitsi/docker-jitsi-meet) (versão `stable-11509`, licença Apache 2.0), sem alterações.
Toda a configuração do MedBot fica no `.env`, gerado por `configurar.py`.

## O que a configuração garante

- **Só entra quem o MedBot autoriza.** Cada entrada em sala leva um acesso assinado (JWT) que vale para uma sala só e expira em 3 horas. Sem ele, ou com o de outra sala, a entrada é recusada.
- **Só o profissional é moderador.** O paciente entra como participante e não consegue silenciar nem remover ninguém.
- **Sem página inicial.** Ninguém cria sala avulsa no servidor.

## Na sua máquina

```bash
python infra/jitsi/configurar.py          # gera infra/jitsi/.env (https://localhost:8443)
cd infra/jitsi && docker compose up -d    # sobe os 4 serviços
python infra/jitsi/apontar_backend.py     # grava endereço e segredo no backend/.env
```

Reinicie o backend depois.

O certificado local é autoassinado. **Abra `https://localhost:8443` uma vez em cada navegador e aceite o aviso de segurança**;
sem isso, o vídeo embutido na tela do atendimento fica em branco (o botão "Abrir em nova aba" mostra o aviso para aceitar).

Para testar com outro aparelho da mesma rede (celular do "paciente", por exemplo), gere com o IP da máquina e use esse
endereço também no `PORTAL_URL` do backend:

```bash
python infra/jitsi/configurar.py --url https://192.168.0.10:8443
```

Teste de uma chamada real entre dois participantes, com câmera e microfone simulados:

```bash
cd backend && uv run python -c "from app.services.telemedicina_service import url_da_sala as u; import json; print(json.dumps({'medico': u('medbot-teste', 'Dr. Teste', moderador=True), 'paciente': u('medbot-teste', 'Paciente'), 'outra': u('medbot-outra', 'Paciente')}))" > ../tools/video/out/salas.json
cd ../tools/video && node sonda-jitsi.mjs out/salas.json
```

## No servidor (VPS)

Pré-requisitos: um subdomínio apontando para o servidor (ex.: `video.suaclinica.com.br`) e estas portas abertas no firewall:

| Porta | Protocolo | Para quê |
|---|---|---|
| 80 | TCP | emissão do certificado (Let's Encrypt) e redirecionamento |
| 443 | TCP | página e sinalização da chamada |
| 10000 | **UDP** | áudio e vídeo. Sem ela, a chamada conecta mas fica sem imagem e som |

```bash
python infra/jitsi/configurar.py \
  --url https://video.suaclinica.com.br \
  --ip <IP público do servidor> \
  --letsencrypt voce@suaclinica.com.br
cd infra/jitsi && docker compose up -d
```

No `.env` do backend em produção:

```
JITSI_BASE_URL=https://video.suaclinica.com.br
JITSI_APP_ID=medbot
JITSI_APP_SECRET=<valor de JWT_APP_SECRET em infra/jitsi/.env>
PORTAL_URL=https://portal.suaclinica.com.br
```

Observações para o deploy com CapRover:

- O Jitsi precisa das portas 80/443 **ou** ficar atrás do proxy do CapRover. Atrás do proxy, publique só o serviço `web`
  (porta interna 8000, HTTP) como um app do CapRover com HTTPS e WebSocket habilitados, e gere o `.env` sem `--letsencrypt`.
- A porta **10000/UDP não passa pelo proxy**: tem de ser exposta direto no host pelo serviço `jvb`.
- O `--ip` precisa ser o IP público; é ele que os navegadores usam para o áudio e o vídeo.

## Manutenção

- **Trocar o segredo** (suspeita de vazamento): `python infra/jitsi/configurar.py --novo-segredo`, `docker compose up -d`,
  `python infra/jitsi/apontar_backend.py` e reiniciar o backend. Links de sala já abertos deixam de valer.
- **Atualizar o Jitsi:** baixar o `docker-compose.yml` da versão nova do projeto oficial, `docker compose pull && docker compose up -d`.
- **Registros:** `docker compose logs -f prosody` (entrada em salas) e `docker compose logs -f jvb` (áudio e vídeo).
- A pasta `config/` e o arquivo `.env` são gerados e ficam fora do git: têm chaves e senhas.

## Limites conhecidos

- Chamada com mais de duas pessoas, gravação e compartilhamento de tela não foram testados (a teleconsulta usa dois participantes).
- Redes muito restritas, que bloqueiam UDP, precisam de um servidor TURN; ele não está configurado.
