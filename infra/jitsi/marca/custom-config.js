// Identidade e comportamento da sala de teleconsulta do MedBot (T157).
// Anexado ao fim do config.js gerado pela imagem oficial: só sobrescreve o que está aqui.

// Cores, fundo e logo vêm da API do MedBot (logo da unidade dona da sala) ou, sem API, de
// /static/medbot-branding.json. O endereço é definido no .env por configurar.py.

// Só o que uma consulta por vídeo precisa. Sem convite, gravação, transmissão, quadro, enquete etc.
config.toolbarButtons = [
    'microphone',
    'camera',
    'desktop',            // mostrar exame ou documento na tela
    'chat',
    'select-background',  // desfocar ou trocar o fundo: privacidade de quem atende de casa
    'tileview',
    'fullscreen',
    'settings',           // escolher câmera, microfone e alto-falante
    'hangup'
];

// O nome técnico da sala (medbot-<código>) não aparece para ninguém
config.hideConferenceSubject = true;
config.hideConferenceTimer = false;

// Teleconsulta é entre profissional e paciente: ninguém convida terceiros
config.disableInviteFunctions = true;
config.disableProfile = true;        // o nome vem do agendamento e não pode ser trocado na sala
config.readOnlyName = true;
config.doNotStoreRoom = true;

// Privacidade (LGPD): nada de avatar, estatística ou pesquisa enviados a serviços de terceiros
config.disableThirdPartyRequests = true;
config.feedbackPercentage = 0;
config.analytics = Object.assign(config.analytics || {}, { disabled: true, rtcstatsEnabled: false });
config.giphy = { enabled: false };
config.disableReactions = true;
config.disablePolls = true;

// Sem telas de aviso que não fazem sentido para salas criadas pelo sistema
config.enableInsecureRoomNameWarning = false;
config.disableDeepLinking = true;
