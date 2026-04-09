import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from './api.service';
import { environment } from '../../environments/environment';
import { firstValueFrom } from 'rxjs';


export interface Mensagem {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface SlotSugerido {
  id: number;
  data: string;
  hora_inicio: string;
  hora_fim: string;
  profissional_nome: string;
}

export interface Convenio {
  id: number;
  nome: string;
}

export interface WsMensagem {
  resposta?: string;
  estado?: string;
  emergencia?: boolean;
  slots_sugeridos?: SlotSugerido[];
  quick_replies?: string[];
  convenios?: Convenio[];
  confirmacao?: { mensagem?: string };
  sessao_expirada?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly api = inject(ApiService);
  private ws: WebSocket | null = null;

  // Sinais base
  readonly mensagens = signal<Mensagem[]>([]);
  readonly digitando = signal(false);
  readonly conectado = signal(false);
  readonly confirmando = signal(false);
  readonly sessionToken = signal<string | null>(null);

  // Sinais do fluxo guiado (T85)
  readonly emergencia = signal(false);
  readonly quickReplies = signal<string[]>([]);
  readonly convenios = signal<Convenio[]>([]);
  readonly estado = signal<string>('START');
  readonly slotsSugeridos = signal<SlotSugerido[]>([]);

  // Injetável em testes para interceptar o envio
  _enviarFn: ((msg: string) => void) | null = null;

  async criarSessao(): Promise<string> {
    const res = await firstValueFrom(
      this.api.post<{ session_token: string }>('/chat/sessao', {
        canal: 'PORTAL',
        estabelecimento_id: environment.estabelecimentoId,
      })
    );
    this.sessionToken.set(res.session_token);
    return res.session_token;
  }

  conectar(token: string): void {
    const url = `${environment.wsUrl}/${token}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => this.conectado.set(true);
    this.ws.onmessage = (event) => this._processarMensagemWs(JSON.parse(event.data));
    this.ws.onclose = () => this.conectado.set(false);
    this.ws.onerror = () => this.conectado.set(false);
  }

  _processarMensagemWs(data: WsMensagem): void {
    this.digitando.set(false);

    if (data.estado) {
      this.estado.set(data.estado);
    }

    if (data.emergencia) {
      this.emergencia.set(true);
    }

    // Quando há confirmação, ela já contém a mensagem completa — evitar duplicata
    if (data.resposta && !data.confirmacao) {
      this.mensagens.update((msgs) => [
        ...msgs,
        { role: 'assistant', content: data.resposta!, timestamp: new Date() },
      ]);
    }

    if (data.quick_replies) {
      this.quickReplies.set(data.quick_replies);
    }

    if (data.convenios) {
      this.convenios.set(data.convenios);
    }

    if (data.slots_sugeridos) {
      this.slotsSugeridos.set(data.slots_sugeridos);
    }

    if (data.confirmacao) {
      this.confirmando.set(false);
      this.slotsSugeridos.set([]);
      this.mensagens.update((msgs) => [
        ...msgs,
        {
          role: 'assistant',
          content: data.confirmacao!.mensagem ?? 'Agendamento confirmado!',
          timestamp: new Date(),
        },
      ]);
    }

    if (data.sessao_expirada) {
      this.conectado.set(false);
    }
  }

  enviar(mensagem: string): void {
    if (this._enviarFn) {
      this._enviarFn(mensagem);
      return;
    }
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    this.mensagens.update((msgs) => [
      ...msgs,
      { role: 'user', content: mensagem, timestamp: new Date() },
    ]);

    this.digitando.set(true);
    this.ws.send(JSON.stringify({ mensagem }));
  }

  enviarQuickReply(texto: string): void {
    this.quickReplies.set([]);
    this.enviar(texto);
  }

  confirmarSlot(slotId: number): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.confirmando.set(true);
    this.ws.send(JSON.stringify({ confirmar_slot_id: slotId }));
  }

  desconectar(): void {
    this.ws?.close();
    this.ws = null;
    this.conectado.set(false);
    this.mensagens.set([]);
    this.sessionToken.set(null);
    this.emergencia.set(false);
    this.quickReplies.set([]);
    this.convenios.set([]);
    this.estado.set('START');
  }
}

/** Factory para testes unitários sem injection context. */
export function createTestService(): ChatService & { _enviarFn: ((msg: string) => void) | null } {
  const svc = Object.create(ChatService.prototype) as ChatService & {
    _enviarFn: ((msg: string) => void) | null;
  };
  // Inicializar sinais manualmente
  (svc as any).mensagens = signal<Mensagem[]>([]);
  (svc as any).digitando = signal(false);
  (svc as any).conectado = signal(false);
  (svc as any).confirmando = signal(false);
  (svc as any).sessionToken = signal<string | null>(null);
  (svc as any).emergencia = signal(false);
  (svc as any).quickReplies = signal<string[]>([]);
  (svc as any).convenios = signal<Convenio[]>([]);
  (svc as any).estado = signal<string>('START');
  (svc as any).slotsSugeridos = signal<SlotSugerido[]>([]);
  svc._enviarFn = null;
  return svc;
}
