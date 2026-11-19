import {
  ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { VocabularioService } from '../../core/services/vocabulario.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ROTULO_STATUS, rotuloDaAcao } from '../recepcao/recepcao.model';
import {
  DocumentoEmitido, ItemReceita, ROTULO_SITUACAO_PACIENTE, SalaAtendimento, erroDaReceita, erroDoAtestado,
  idade, itensValidos, podeEmitirDocumento, podeRegistrar, resumoDoDocumento, situacaoDoPaciente,
} from './atender.model';

const ATUALIZACAO_MS = 5_000;
const SALVAR_APOS_MS = 1_500;

type Formulario = 'receita' | 'atestado' | null;

/** Atendimento do profissional: paciente, triagem, sala de vídeo (se online), registro e documentos. */
@Component({
  selector: 'app-atender',
  standalone: true,
  imports: [
    FormsModule, RouterLink,
    MatButtonModule, MatFormFieldModule, MatIconModule, MatInputModule, MatProgressSpinnerModule, MatTooltipModule,
    EmptyStateComponent,
  ],
  templateUrl: './atender.component.html',
  styleUrl: './atender.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AtenderComponent implements OnInit {
  readonly vocab = inject(VocabularioService);
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly destroyRef = inject(DestroyRef);
  private readonly router = inject(Router);
  private readonly id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));
  private readonly base = `/profissional/atendimentos/${this.id}`;

  readonly sala = signal<SalaAtendimento | null>(null);
  readonly carregando = signal(true);
  readonly naoEncontrado = signal(false);
  readonly mudandoStatus = signal(false);

  // Vídeo: só carrega quando o profissional pede (câmera e microfone são solicitados nesse momento)
  readonly videoAberto = signal(false);
  readonly videoUrl = signal<SafeResourceUrl | null>(null);

  // Registro
  readonly queixa = signal('');
  readonly evolucao = signal('');
  readonly conduta = signal('');
  readonly estadoRegistro = signal<'salvo' | 'pendente' | 'salvando' | 'erro'>('salvo');
  private temporizadorRegistro: ReturnType<typeof setTimeout> | null = null;

  // Documentos
  readonly formulario = signal<Formulario>(null);
  readonly itens = signal<ItemReceita[]>([{ medicamento: '', posologia: '' }]);
  readonly observacoesReceita = signal('');
  readonly dias = signal<number | null>(1);
  readonly cid = signal('');
  readonly emitindo = signal(false);
  readonly erroFormulario = signal<string | null>(null);

  readonly rotuloStatus = ROTULO_STATUS;
  readonly resumoDoc = resumoDoDocumento;
  readonly idade = computed(() => idade(this.sala()?.cliente_nascimento ?? null));
  readonly podeEmitir = computed(() => podeEmitirDocumento(this.sala()?.status ?? ''));
  readonly podeRegistrar = computed(() => podeRegistrar(this.sala()?.status ?? ''));
  readonly acao = computed(() => {
    const proxima = this.sala()?.acoes[0];
    return proxima ? { status: proxima, ...rotuloDaAcao(proxima, 'profissional') } : null;
  });
  readonly paciente = computed(() => {
    const t = this.sala()?.teleconsulta;
    if (!t) return null;
    const situacao = situacaoDoPaciente(t);
    const naChamada = situacao === 'na_sala' && this.sala()?.status === 'EM_ATENDIMENTO';
    return { situacao, rotulo: naChamada ? 'Paciente na chamada' : ROTULO_SITUACAO_PACIENTE[situacao] };
  });

  ngOnInit(): void {
    void this.carregar(true);
    const timer = setInterval(() => void this.carregar(false), ATUALIZACAO_MS);
    this.destroyRef.onDestroy(() => {
      clearInterval(timer);
      if (this.temporizadorRegistro) clearTimeout(this.temporizadorRegistro);
      if (this.estadoRegistro() === 'pendente') void this.salvarRegistro();
    });
  }

  /** Carrega a tela. Nas atualizações periódicas, o texto que o profissional está digitando não é trocado. */
  async carregar(primeira: boolean): Promise<void> {
    try {
      const dados = await firstValueFrom(this.api.get<SalaAtendimento>(`${this.base}/sala`));
      this.sala.set(dados);
      if (primeira) {
        this.queixa.set(dados.registro.queixa ?? '');
        this.evolucao.set(dados.registro.evolucao ?? '');
        this.conduta.set(dados.registro.conduta ?? '');
      }
    } catch {
      // falha em atualizacao periodica nao derruba a tela ja carregada
      if (primeira) this.naoEncontrado.set(true);
    } finally {
      this.carregando.set(false);
    }
  }

  voltarParaMeuDia(): void {
    void this.router.navigateByUrl('/meu-dia');
  }

  async mudarStatus(status: string): Promise<void> {
    if (this.estadoRegistro() === 'pendente') await this.salvarRegistro();
    this.mudandoStatus.set(true);
    try {
      await firstValueFrom(this.api.patch(`${this.base}/status`, { status_novo: status }));
      await this.carregar(false);
      if (status === 'REALIZADA') this.fecharVideo();
    } catch (e: unknown) {
      this.toast.erro((e as { error?: { detail?: string } })?.error?.detail ?? 'Não foi possível atualizar o atendimento.');
    } finally {
      this.mudandoStatus.set(false);
    }
  }

  // ── Vídeo ──────────────────────────────────────────────────────
  abrirVideo(): void {
    const url = this.sala()?.teleconsulta?.sala_url;
    if (!url) return;
    this.videoUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
    this.videoAberto.set(true);
  }

  fecharVideo(): void {
    this.videoAberto.set(false);
    this.videoUrl.set(null);
  }

  abrirVideoEmNovaAba(): void {
    const url = this.sala()?.teleconsulta?.sala_url;
    if (url) window.open(url, '_blank', 'noopener');
  }

  async copiarLink(): Promise<void> {
    const link = this.sala()?.teleconsulta?.link_paciente;
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      this.toast.sucesso('Link do paciente copiado.');
    } catch {
      this.toast.erro('Não foi possível copiar. Selecione o link e copie manualmente.');
    }
  }

  async reenviarLink(): Promise<void> {
    try {
      const r = await firstValueFrom(this.api.post<{ enviado: boolean }>(`${this.base}/enviar-link`, {}));
      if (r.enviado) this.toast.sucesso('Link reenviado ao paciente.');
      else this.toast.erro('O envio falhou (WhatsApp e e-mail). Copie o link e envie por outro meio.');
    } catch {
      this.toast.erro('Não foi possível reenviar o link.');
    }
  }

  // ── Registro ───────────────────────────────────────────────────
  editarRegistro(campo: 'queixa' | 'evolucao' | 'conduta', valor: string): void {
    this[campo].set(valor);
    this.estadoRegistro.set('pendente');
    if (this.temporizadorRegistro) clearTimeout(this.temporizadorRegistro);
    this.temporizadorRegistro = setTimeout(() => void this.salvarRegistro(), SALVAR_APOS_MS);
  }

  async salvarRegistro(): Promise<void> {
    if (this.temporizadorRegistro) clearTimeout(this.temporizadorRegistro);
    this.estadoRegistro.set('salvando');
    const enviado = { queixa: this.queixa(), evolucao: this.evolucao(), conduta: this.conduta() };
    try {
      await firstValueFrom(this.api.put(`${this.base}/registro`, enviado));
      // se o profissional continuou digitando durante o envio, ainda há o que salvar
      const mudou = enviado.queixa !== this.queixa() || enviado.evolucao !== this.evolucao() || enviado.conduta !== this.conduta();
      this.estadoRegistro.set(mudou ? 'pendente' : 'salvo');
      if (mudou) this.temporizadorRegistro = setTimeout(() => void this.salvarRegistro(), SALVAR_APOS_MS);
    } catch {
      this.estadoRegistro.set('erro');
    }
  }

  // ── Documentos ─────────────────────────────────────────────────
  abrirFormulario(tipo: Formulario): void {
    this.formulario.set(tipo);
    this.erroFormulario.set(null);
    this.itens.set([{ medicamento: '', posologia: '' }]);
    this.observacoesReceita.set('');
    this.dias.set(1);
    this.cid.set('');
  }

  editarItem(indice: number, campo: keyof ItemReceita, valor: string): void {
    this.itens.update((lista) => lista.map((item, i) => (i === indice ? { ...item, [campo]: valor } : item)));
  }

  adicionarItem(): void {
    this.itens.update((lista) => [...lista, { medicamento: '', posologia: '' }]);
  }

  removerItem(indice: number): void {
    this.itens.update((lista) => (lista.length > 1 ? lista.filter((_, i) => i !== indice) : lista));
  }

  async emitir(): Promise<void> {
    const tipo = this.formulario();
    if (!tipo) return;
    const erro = tipo === 'receita' ? erroDaReceita(this.itens()) : erroDoAtestado(this.dias());
    this.erroFormulario.set(erro);
    if (erro) return;

    const corpo = tipo === 'receita'
      ? { tipo: 'RECEITA', conteudo: { itens: itensValidos(this.itens()), observacoes: this.observacoesReceita().trim() || null } }
      : { tipo: 'ATESTADO', conteudo: { dias: this.dias(), cid: this.cid().trim() || null } };
    this.emitindo.set(true);
    try {
      const doc = await firstValueFrom(this.api.post<DocumentoEmitido>(`${this.base}/documentos`, corpo));
      this.formulario.set(null);
      await this.carregar(false);
      this.toast.sucesso(tipo === 'receita' ? 'Receita emitida.' : 'Atestado emitido.');
      await this.abrirPdf(doc.id);
    } catch (e: unknown) {
      this.erroFormulario.set((e as { error?: { detail?: string } })?.error?.detail ?? 'Não foi possível emitir o documento.');
    } finally {
      this.emitindo.set(false);
    }
  }

  /** O PDF exige o token de acesso, então é baixado pela aplicação e aberto como arquivo local. */
  async abrirPdf(documentoId: number): Promise<void> {
    try {
      const arquivo = await firstValueFrom(this.api.getBlob(`${this.base}/documentos/${documentoId}.pdf`));
      const url = URL.createObjectURL(arquivo);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      this.toast.erro('Não foi possível abrir o PDF.');
    }
  }
}
