// Roteiro MedBot — narração e legendas por cena.
// Público: gestor(a) de clínica / estabelecimento de saúde avaliando a contratação.
// Duração-alvo: ~3 min (≈ 440 palavras). Legendas: no máximo ~110 caracteres cada.
export const CENAS = [
  {
    id: '01', nome: 'abertura', // cartaz c1
    falas: [{
      texto: 'Telefone que não para, agenda com buracos e paciente que desiste de esperar. O MedBot coloca uma inteligência artificial para agendar por você, vinte e quatro horas por dia.',
      legendas: [
        'Telefone que não para, agenda com buracos e paciente que desiste de esperar.',
        'O MedBot coloca uma inteligência artificial para agendar por você, 24 horas por dia.',
      ],
    }],
  },
  {
    id: '02', nome: 'chat-paciente', // portal :4200/chat
    falas: [
      { // 0 — nome, convênio e sintomas (a IA pode fazer uma ou duas perguntas a mais)
        texto: 'O paciente conversa como em qualquer aplicativo de mensagens. O assistente pergunta o nome, o convênio e o que ele está sentindo. Se precisar, faz mais perguntas para entender melhor o caso.',
        legendas: [
          'O paciente conversa como em qualquer aplicativo de mensagens.',
          'O assistente pergunta o nome, o convênio e o que ele está sentindo.',
          'Se precisar, faz mais perguntas para entender melhor o caso.',
        ],
      },
      { // 1 — só começa quando os horários aparecem na tela
        texto: 'Com base nos sintomas, a inteligência artificial indica a especialidade e mostra os horários livres da agenda.',
        legendas: [
          'Com base nos sintomas, a inteligência artificial indica a especialidade',
          'e mostra os horários livres da agenda.',
        ],
      },
      { // 2 — escolhe o horário, informa contato, confirma
        texto: 'O paciente escolhe o horário, informa documento e contato, e confirma. Pronto: consulta marcada, com número de protocolo, sem ninguém da equipe precisar atender.',
        legendas: [
          'O paciente escolhe o horário, informa documento e contato, e confirma.',
          'Pronto: consulta marcada, com número de protocolo,',
          'sem ninguém da equipe precisar atender.',
        ],
      },
      { // 3 — nova conversa: emergência
        texto: 'E em caso de emergência, ele não agenda: orienta ligar imediatamente para o SAMU, um nove dois.',
        legendas: [
          'E em caso de emergência, ele não agenda:',
          'orienta ligar imediatamente para o SAMU, 192.',
        ],
      },
    ],
  },
  {
    id: '03', nome: 'plataforma', // qa-01 login → qa-03 dashboard → qa-04 estabelecimentos → qa-05 licenças
    falas: [{
      texto: 'Do outro lado fica o painel de gestão. Quem administra a plataforma enxerga todas as unidades em um só lugar: estabelecimentos cadastrados, licenças de cada um e o plano contratado.',
      legendas: [
        'Do outro lado fica o painel de gestão.',
        'Quem administra a plataforma enxerga todas as unidades em um só lugar:',
        'estabelecimentos cadastrados, licenças de cada um e o plano contratado.',
      ],
    }],
  },
  {
    id: '04', nome: 'controle', // qa-06 usuários → qa-07 billing → qa-08 auditoria
    falas: [{
      texto: 'Cada pessoa da equipe tem o seu acesso. O custo da inteligência artificial aparece em tempo real, com limite diário e alerta. E toda ação sensível fica registrada na auditoria.',
      legendas: [
        'Cada pessoa da equipe tem o seu acesso.',
        'O custo da inteligência artificial aparece em tempo real, com limite diário e alerta.',
        'E toda ação sensível fica registrada na auditoria.',
      ],
    }],
  },
  {
    id: '05', nome: 'clinica-agenda', // qa-02 selecionar → qa-09 dashboard clínica → qa-18 agenda
    falas: [{
      texto: 'Ao entrar em uma clínica, o painel muda para o dia a dia dela. Consultas de hoje, ocupação da agenda e próximos atendimentos. Na agenda, cada horário de cada profissional, com filtro por especialidade.',
      legendas: [
        'Ao entrar em uma clínica, o painel muda para o dia a dia dela.',
        'Consultas de hoje, ocupação da agenda e próximos atendimentos.',
        'Na agenda, cada horário de cada profissional, com filtro por especialidade.',
      ],
    }],
  },
  {
    id: '06', nome: 'convenios', // qa-10 → qa-11 → qa-12 → qa-13
    falas: [{
      texto: 'Os convênios aceitos são cadastrados com os seus planos. Assim o assistente só oferece ao paciente os horários de quem atende o plano dele.',
      legendas: [
        'Os convênios aceitos são cadastrados com os seus planos.',
        'Assim o assistente só oferece ao paciente os horários de quem atende o plano dele.',
      ],
    }],
  },
  {
    id: '07', nome: 'catalogo', // qa-14 → qa-15
    falas: [{
      texto: 'No catálogo ficam os serviços que a clínica oferece: consultas, exames, procedimentos. Cada um com a sua duração e o seu preço.',
      legendas: [
        'No catálogo ficam os serviços que a clínica oferece: consultas, exames, procedimentos.',
        'Cada um com a sua duração e o seu preço.',
      ],
    }],
  },
  {
    id: '08', nome: 'cadastros', // qa-19 clientes → qa-20 profissionais → qa-21 especialidades → qa-22 atendimentos
    falas: [{
      texto: 'Clientes, profissionais, especialidades e atendimentos ficam organizados por unidade. Os dados de uma clínica nunca aparecem para outra, e o documento do paciente é sempre exibido mascarado.',
      legendas: [
        'Clientes, profissionais, especialidades e atendimentos ficam organizados por unidade.',
        'Os dados de uma clínica nunca aparecem para outra,',
        'e o documento do paciente é sempre exibido mascarado.',
      ],
    }],
  },
  {
    id: '09', nome: 'vocabulario', // qa-16 → qa-17
    falas: [{
      texto: 'E o sistema fala a língua do seu negócio. Em uma clínica de estética, médico vira esteticista e consulta vira sessão. Você troca os termos e o sistema inteiro acompanha.',
      legendas: [
        'E o sistema fala a língua do seu negócio.',
        'Em uma clínica de estética, médico vira esteticista e consulta vira sessão.',
        'Você troca os termos e o sistema inteiro acompanha.',
      ],
    }],
  },
  {
    id: '10', nome: 'encerramento', // cartaz c2
    falas: [{
      texto: 'MedBot. Sua agenda cheia, sua equipe livre para cuidar de quem já chegou.',
      legendas: ['MedBot.', 'Sua agenda cheia, sua equipe livre para cuidar de quem já chegou.'],
    }],
  },
]

// Termos internos que não devem aparecer na tela gravada.
export const PROIBIDAS = /ADMIN_GLOBAL|ADMIN_ESTABELECIMENTO|Documentos RAG|localhost/i

// Trocas de texto aplicadas só à página gravada (não alteram a aplicação).
export const TROCAS = [
  [/ADMIN_GLOBAL/g, 'Administrador'],
  [/ADMIN_ESTABELECIMENTO/g, 'Gestor da clínica'],
  [/Documentos RAG/g, 'Protocolos'],
]
