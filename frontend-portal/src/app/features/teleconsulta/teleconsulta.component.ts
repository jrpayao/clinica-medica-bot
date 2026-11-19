import {
  ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal,
} from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/services/api.service';
import { environment } from '../../environments/environment';
import {
  ROTULO_DOCUMENTO, TeleconsultaPaciente, blocosDoTermo, deveAcompanhar, intervaloMs,
} from './teleconsulta.model';

/** Teleconsulta do paciente: aceite do termo, sala de espera, chamada de vídeo e documentos. */
@Component({
  selector: 'app-teleconsulta',
  standalone: true,
  templateUrl: './teleconsulta.component.html',
  styleUrl: './teleconsulta.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TeleconsultaComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly destroyRef = inject(DestroyRef);
  private readonly token = inject(ActivatedRoute).snapshot.paramMap.get('token') ?? '';
  private readonly base = `/teleconsulta/${encodeURIComponent(this.token)}`;

  readonly dados = signal<TeleconsultaPaciente | null>(null);
  readonly carregando = signal(true);
  readonly linkInvalido = signal(false);
  readonly semConexao = signal(false);
  readonly aceito = signal(false);
  readonly enviando = signal(false);

  // A sala só é montada uma vez: recriar o quadro a cada consulta derrubaria a chamada
  readonly salaUrl = signal<SafeResourceUrl | null>(null);
  private salaAtual: string | null = null;

  readonly rotuloDocumento = ROTULO_DOCUMENTO;
  readonly termo = computed(() => {
    const t = this.dados()?.termo;
    return t ? blocosDoTermo(t.texto) : null;
  });

  private temporizador: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.destroyRef.onDestroy(() => this.temporizador && clearTimeout(this.temporizador));
    void this.atualizar(true);
  }

  urlDoDocumento(id: number): string {
    return `${environment.apiUrl}${this.base}/documentos/${id}.pdf`;
  }

  async aceitar(): Promise<void> {
    if (!this.aceito() || this.enviando()) return;
    this.enviando.set(true);
    try {
      this.aplicar(await firstValueFrom(this.api.post<TeleconsultaPaciente>(`${this.base}/consentimento`, {})));
    } catch {
      this.semConexao.set(true);
    } finally {
      this.enviando.set(false);
    }
  }

  /** Primeira carga só lê; depois do termo aceito, cada consulta também avisa que o paciente está na página. */
  private async atualizar(primeira = false): Promise<void> {
    try {
      const acompanha = !primeira && this.dados() && deveAcompanhar(this.dados()!.situacao);
      const resposta = acompanha
        ? await firstValueFrom(this.api.post<TeleconsultaPaciente>(`${this.base}/presenca`, {}))
        : await firstValueFrom(this.api.get<TeleconsultaPaciente>(this.base));
      this.semConexao.set(false);
      this.aplicar(resposta);
      // quem volta à página com o termo já aceito entra na sala de espera na hora
      if (primeira && deveAcompanhar(resposta.situacao)) this.agendar(0);
    } catch (e: unknown) {
      const status = (e as { status?: number })?.status;
      if (status === 404) this.linkInvalido.set(true);
      else {
        this.semConexao.set(true);
        this.agendar(10_000);
      }
    } finally {
      this.carregando.set(false);
    }
  }

  private aplicar(resposta: TeleconsultaPaciente): void {
    this.dados.set(resposta);
    if (resposta.sala_url !== this.salaAtual) {
      this.salaAtual = resposta.sala_url;
      this.salaUrl.set(resposta.sala_url ? this.sanitizer.bypassSecurityTrustResourceUrl(resposta.sala_url) : null);
    }
    if (deveAcompanhar(resposta.situacao)) this.agendar(intervaloMs(resposta.situacao));
  }

  private agendar(ms: number): void {
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = setTimeout(() => void this.atualizar(), ms);
  }
}
