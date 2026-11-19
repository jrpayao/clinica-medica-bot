import {
  ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { VocabularioService } from '../../core/services/vocabulario.service';
import { localDateString } from '../../core/utils/date.utils';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import {
  AtendimentoRecepcao, FiltroEtapa, ModoPainel, PainelRecepcao, RESUMO_VAZIO, ROTULO_ACAO, ROTULO_STATUS,
  ROTULO_URGENCIA, etapaDoStatus, filtrarPorEtapa, proximoAChegar, rotuloDaAcao,
} from './recepcao.model';

const ATUALIZACAO_MS = 60_000;

@Component({
  selector: 'app-recepcao',
  standalone: true,
  imports: [
    DatePipe, RouterLink,
    MatButtonModule, MatIconModule, MatMenuModule, MatProgressSpinnerModule, MatTooltipModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './recepcao.component.html',
  styleUrl: './recepcao.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RecepcaoComponent implements OnInit {
  readonly vocab = inject(VocabularioService);
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);

  /** A mesma fila serve à recepção (unidade inteira) e ao profissional (só os atendimentos dele). */
  readonly modo: ModoPainel = inject(ActivatedRoute).snapshot.data['modo'] ?? 'recepcao';
  private readonly base = this.modo === 'profissional' ? '/profissional' : '/recepcao';
  readonly titulo = this.modo === 'profissional' ? 'Meu dia' : 'Recepção';

  readonly hoje = new Date();
  readonly painel = signal<PainelRecepcao | null>(null);
  readonly carregando = signal(true);
  readonly falhou = signal(false);
  readonly filtro = signal<FiltroEtapa>('todos');
  /** Atendimento com alteração de status em andamento (bloqueia os botões da linha). */
  readonly salvandoId = signal<number | null>(null);
  private readonly agora = signal(this.horaAtual());

  readonly resumo = computed(() => this.painel()?.resumo ?? RESUMO_VAZIO);
  readonly atendimentos = computed(() => this.painel()?.atendimentos ?? []);
  readonly lista = computed(() => filtrarPorEtapa(this.atendimentos(), this.filtro()));
  readonly proximo = computed(() => proximoAChegar(this.atendimentos(), this.agora()));

  readonly rotuloStatus = ROTULO_STATUS;
  readonly rotuloUrgencia = ROTULO_URGENCIA;
  readonly rotuloAcao: Record<string, { texto: string; icone: string; principal: boolean }> = Object.fromEntries(
    Object.keys(ROTULO_ACAO).map((acao) => [acao, rotuloDaAcao(acao, this.modo)]),
  );
  readonly etapa = etapaDoStatus;

  readonly cartoes = computed(() => {
    const r = this.resumo();
    return [
      { filtro: 'a_chegar' as FiltroEtapa,       rotulo: 'A chegar',       valor: r.a_chegar,       icone: 'schedule' },
      { filtro: 'na_recepcao' as FiltroEtapa,    rotulo: 'Na recepção',    valor: r.na_recepcao,    icone: 'chair' },
      { filtro: 'em_atendimento' as FiltroEtapa, rotulo: 'Em atendimento', valor: r.em_atendimento, icone: 'medical_services' },
      { filtro: 'encerrados' as FiltroEtapa,     rotulo: 'Encerrados',     valor: r.realizados + r.faltas + r.cancelados, icone: 'task_alt' },
    ];
  });

  ngOnInit(): void {
    void this.carregar();
    const timer = setInterval(() => {
      this.agora.set(this.horaAtual());
      if (this.salvandoId() === null) void this.carregar(true);
    }, ATUALIZACAO_MS);
    this.destroyRef.onDestroy(() => clearInterval(timer));
  }

  async carregar(silencioso = false): Promise<void> {
    if (!silencioso) this.carregando.set(true);
    try {
      const dados = await firstValueFrom(
        this.api.get<PainelRecepcao>(`${this.base}/painel?data=${localDateString(this.hoje)}`),
      );
      this.painel.set(dados);
      this.falhou.set(false);
    } catch {
      // atualização automática que falha não apaga a fila já exibida
      if (!silencioso) this.falhou.set(true);
    } finally {
      this.carregando.set(false);
    }
  }

  alternarFiltro(filtro: FiltroEtapa): void {
    this.filtro.update((atual) => (atual === filtro ? 'todos' : filtro));
  }

  acaoPrincipal(a: AtendimentoRecepcao): string | null {
    return a.acoes.find((acao) => this.rotuloAcao[acao]?.principal) ?? null;
  }

  acoesSecundarias(a: AtendimentoRecepcao): string[] {
    const principal = this.acaoPrincipal(a);
    return a.acoes.filter((acao) => acao !== principal && this.rotuloAcao[acao]);
  }

  async mudarStatus(a: AtendimentoRecepcao, statusNovo: string): Promise<void> {
    this.salvandoId.set(a.atendimento_id);
    try {
      await firstValueFrom(
        this.api.patch(`${this.base}/atendimentos/${a.atendimento_id}/status`, { status_novo: statusNovo }),
      );
      this.toast.sucesso(`${a.cliente_nome}: ${this.rotuloStatus[statusNovo]?.toLowerCase() ?? statusNovo}.`);
      await this.carregar(true);
    } catch (e: unknown) {
      const detalhe = (e as { error?: { detail?: string } })?.error?.detail;
      this.toast.erro(detalhe ?? 'Não foi possível atualizar. Recarregue a fila e tente de novo.');
      await this.carregar(true);
    } finally {
      this.salvandoId.set(null);
    }
  }

  private horaAtual(): string {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  }
}
