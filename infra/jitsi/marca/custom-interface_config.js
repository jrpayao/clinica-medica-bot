// Identidade da interface da sala de teleconsulta do MedBot (T157).
// Anexado ao fim do interface_config.js da imagem oficial.

interfaceConfig.APP_NAME = 'MedBot Teleconsulta';
interfaceConfig.NATIVE_APP_NAME = 'MedBot';
interfaceConfig.PROVIDER_NAME = 'MedBot';

// Logo do MedBot no lugar do Jitsi (o arquivo de marca também o define)
interfaceConfig.SHOW_JITSI_WATERMARK = true;
interfaceConfig.JITSI_WATERMARK_LINK = '';
interfaceConfig.DEFAULT_LOGO_URL = 'images/medbot-logo.svg';
interfaceConfig.DEFAULT_WELCOME_PAGE_LOGO_URL = 'images/medbot-logo.svg';
interfaceConfig.SHOW_BRAND_WATERMARK = false;
interfaceConfig.SHOW_POWERED_BY = false;
interfaceConfig.DEFAULT_BACKGROUND = '#0f172a';

// Sempre em português, qualquer que seja o idioma do navegador
interfaceConfig.LANG_DETECTION = false;

// Sem propaganda de aplicativo nem página de agradecimento do Jitsi
interfaceConfig.MOBILE_APP_PROMO = false;
interfaceConfig.SHOW_PROMOTIONAL_CLOSE_PAGE = false;
interfaceConfig.HIDE_INVITE_MORE_HEADER = true;

// Configurações acessíveis na sala: só aparelhos e opções de vídeo
interfaceConfig.SETTINGS_SECTIONS = ['devices', 'more'];
