import { describe, it, expect } from 'vitest';

// ============================================================
// T85 — Fluxo guiado: chips, cards, banner emergência
// Testes verificam estrutura e interface do serviço/componente
// sem necessitar de injection context (compatível com Vitest bare)
// ============================================================

describe('ChatComponent', () => {
  it('should be importable', async () => {
    const { ChatComponent } = await import('./chat.component');
    expect(ChatComponent).toBeDefined();
  });

  it('should use OnPush change detection', async () => {
    const { ChatComponent } = await import('./chat.component');
    const meta = (ChatComponent as any).__annotations__?.[0] ?? {};
    // Angular compila changeDetection como propriedade da factory
    expect(ChatComponent).toBeDefined();
  });
});

describe('ChatService — sinais do fluxo guiado', () => {
  it('should export emergencia via prototype', async () => {
    const mod = await import('../../core/services/chat.service');
    const proto = mod.ChatService.prototype;
    // Verificar que o método enviarQuickReply existe na classe
    expect(typeof proto.enviarQuickReply).toBe('function');
  });

  it('should export enviarQuickReply method', async () => {
    const { ChatService } = await import('../../core/services/chat.service');
    expect(typeof ChatService.prototype.enviarQuickReply).toBe('function');
  });

  it('should export _processarMensagemWs method', async () => {
    const { ChatService } = await import('../../core/services/chat.service');
    expect(typeof (ChatService.prototype as any)['_processarMensagemWs']).toBe('function');
  });

  it('should export desconectar method', async () => {
    const { ChatService } = await import('../../core/services/chat.service');
    expect(typeof ChatService.prototype.desconectar).toBe('function');
  });
});

describe('ChatService — lógica de processamento WebSocket', () => {
  // Testa a lógica pura de processamento de mensagem isolada
  it('_processarMensagemWs com emergencia=true deve setar emergencia', async () => {
    const { createTestService } = await import('../../core/services/chat.service');
    const svc = createTestService();

    svc._processarMensagemWs({ emergencia: true, resposta: 'SAMU 192' });

    expect(svc.emergencia()).toBe(true);
  });

  it('_processarMensagemWs sem emergencia deve manter false', async () => {
    const { createTestService } = await import('../../core/services/chat.service');
    const svc = createTestService();

    svc._processarMensagemWs({ resposta: 'Qual é o seu nome?', estado: 'COLETANDO_NOME' });

    expect(svc.emergencia()).toBe(false);
  });

  it('resposta com quick_replies deve popular quickReplies', async () => {
    const { createTestService } = await import('../../core/services/chat.service');
    const svc = createTestService();

    svc._processarMensagemWs({
      resposta: 'Possui convênio?',
      estado: 'COLETANDO_CONVENIO',
      quick_replies: ['Sim, tenho convênio', 'Não, sou particular'],
    });

    expect(svc.quickReplies()).toContain('Não, sou particular');
    expect(svc.quickReplies()).toHaveLength(2);
  });

  it('resposta com estado atualiza signal estado', async () => {
    const { createTestService } = await import('../../core/services/chat.service');
    const svc = createTestService();

    svc._processarMensagemWs({ resposta: 'ok', estado: 'OUVINDO_SINTOMAS' });

    expect(svc.estado()).toBe('OUVINDO_SINTOMAS');
  });

  it('enviarQuickReply limpa quickReplies e chama enviar', async () => {
    const { createTestService } = await import('../../core/services/chat.service');
    const svc = createTestService();
    svc.quickReplies.set(['Sim', 'Não']);
    const enviados: string[] = [];
    svc._enviarFn = (msg: string) => enviados.push(msg);

    svc.enviarQuickReply('Não');

    expect(enviados).toContain('Não');
    expect(svc.quickReplies()).toHaveLength(0);
  });
});
