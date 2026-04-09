import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  ViewChild,
  afterNextRender,
  inject,
  signal,
  OnInit,
  OnDestroy,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { ChatService, Convenio } from '../../core/services/chat.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [FormsModule, DatePipe],
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatComponent implements OnInit, OnDestroy {
  readonly chat = inject(ChatService);
  readonly inputMensagem = signal('');
  readonly erroSessao = signal('');
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly sanitizer = inject(DomSanitizer);

  @ViewChild('messagesContainer') messagesContainer!: ElementRef<HTMLDivElement>;

  async ngOnInit(): Promise<void> {
    try {
      const token = await this.chat.criarSessao();
      this.chat.conectar(token);
      this._watchMensagens();
    } catch (err: any) {
      const detail = err?.error?.detail ?? 'Erro ao iniciar sessão de chat.';
      this.erroSessao.set(detail);
    }
  }

  ngOnDestroy(): void {
    this.chat.desconectar();
  }

  private _watchMensagens(): void {
    // Observar mudanças nas mensagens para auto-scroll
    let count = 0;
    const check = () => {
      const current = this.chat.mensagens().length;
      if (current !== count) {
        count = current;
        this.cdr.markForCheck();
        setTimeout(() => this._scrollToBottom(), 50);
      }
      if (!this.chat.conectado() && this.chat.mensagens().length === 0) return;
      requestAnimationFrame(check);
    };
    requestAnimationFrame(check);
  }

  private _scrollToBottom(): void {
    const el = this.messagesContainer?.nativeElement;
    if (el) el.scrollTop = el.scrollHeight;
  }

  enviar(): void {
    const msg = this.inputMensagem().trim();
    if (!msg) return;
    this.chat.enviar(msg);
    this.inputMensagem.set('');
    setTimeout(() => this._scrollToBottom(), 100);
  }

  async reconectar(): Promise<void> {
    this.erroSessao.set('');
    try {
      const token = await this.chat.criarSessao();
      this.chat.conectar(token);
      this._watchMensagens();
    } catch (err: any) {
      const detail = err?.error?.detail ?? 'Erro ao reconectar.';
      this.erroSessao.set(detail);
    }
  }

  selecionarConvenio(conv: Convenio): void {
    this.chat.convenios.set([]);
    this.chat.enviarQuickReply(`Sim, meu convênio é ${conv.nome}`);
  }

  formatarMensagem(texto: string): SafeHtml {
    const html = texto
      // Negrito **texto**
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      // Bullet points: linhas começando com "* " ou "- "
      .replace(/^[\*\-] (.+)$/gm, '• $1')
      // Quebras de linha
      .replace(/\n/g, '<br>');
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }
}
