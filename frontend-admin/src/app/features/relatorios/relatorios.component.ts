import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from '../../core/services/api.service';
import { VocabularioService } from '../../core/services/vocabulario.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import {
  AvaliacaoItem, Confirmacao, Custo, FilaRelatorio, Ocupacao, PERIODOS_RAPIDOS, Periodo, ResumoNps,
  ROTULO_FAIXA_NPS, ROTULO_MOTIVO_CANCELAMENTO, Sintomas, distribuicaoOrdenada, faixaNps, formatarTaxa,
  formatarUsd, larguraBarra, periodoDosUltimosDias, periodoValido,
} from './relatorios.model';

interface Dados {
  ocupacao: Ocupacao;
  confirmacao: Confirmacao;
  sintomas: Sintomas;
  custo: Custo;
  fila: FilaRelatorio;
  nps: ResumoNps;
  avaliacoes: AvaliacaoItem[];
}

/** Relatórios da unidade: ocupação, comparecimento, procura, lista de espera, custo de IA e satisfação. */
@Component({
  selector: 'app-relatorios',
  standalone: true,
  imports: [
    DatePipe, FormsModule,
    MatButtonModule, MatButtonToggleModule, MatFormFieldModule, MatIconModule, MatInputModule,
    MatProgressSpinnerModule, MatSelectModule, MatTooltipModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './relatorios.component.html',
  styleUrl: './relatorios.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RelatoriosComponent implements OnInit {
  readonly vocab = inject(VocabularioService);
  private readonly api = inject(ApiService);

  readonly periodosRapidos = PERIODOS_RAPIDOS;
  readonly diasRapidos = signal<number | null>(30);
  readonly periodo = signal<Periodo>(periodoDosUltimosDias(30));
  readonly profissionalId = signal<number | null>(null);
  readonly profissionais = signal<{ id: number; nome: string }[]>([]);

  readonly dados = signal<Dados | null>(null);
  readonly carregando = signal(true);
  readonly falhou = signal(false);

  readonly taxa = formatarTaxa;
  readonly usd = formatarUsd;
  readonly largura = larguraBarra;
  readonly rotuloMotivo = ROTULO_MOTIVO_CANCELAMENTO;
  readonly periodoOk = computed(() => periodoValido(this.periodo()));

  readonly indicadores = computed(() => {
    const d = this.dados();
    if (!d) return [];
    const profissional = this.vocab.atendimentos().toLowerCase();
    return [
      {
        rotulo: 'Ocupação da agenda', valor: formatarTaxa(d.ocupacao.geral.taxa), icone: 'event_available',
        detalhe: `${d.ocupacao.geral.ocupados} de ${d.ocupacao.geral.total_slots} horários`,
      },
      {
        rotulo: 'Comparecimento', valor: formatarTaxa(d.confirmacao.taxa_comparecimento), icone: 'how_to_reg',
        detalhe: `${d.confirmacao.realizados} realizados, ${d.confirmacao.faltas} ${d.confirmacao.faltas === 1 ? 'falta' : 'faltas'}`,
      },
      {
        rotulo: 'Cancelamentos', valor: formatarTaxa(d.confirmacao.taxa_cancelamento), icone: 'event_busy',
        detalhe: `${d.confirmacao.cancelados} de ${d.confirmacao.total} ${profissional}`,
      },
      {
        rotulo: 'Satisfação (NPS)', valor: d.nps.geral.nps === null ? '—' : String(d.nps.geral.nps), icone: 'sentiment_satisfied',
        detalhe: d.nps.geral.total
          ? `${d.nps.geral.total} ${d.nps.geral.total === 1 ? 'avaliação' : 'avaliações'}, média ${d.nps.geral.media?.toLocaleString('pt-BR')}`
          : 'Sem avaliações no período',
      },
    ];
  });

  readonly maxSintoma = computed(() => Math.max(0, ...(this.dados()?.sintomas.sintomas.map((s) => s.total) ?? [])));
  readonly maxEspecialidade = computed(() =>
    Math.max(0, ...(this.dados()?.sintomas.especialidades.map((e) => e.total) ?? [])),
  );
  readonly distribuicao = computed(() => distribuicaoOrdenada(this.dados()?.nps.distribuicao ?? {}));
  readonly maxNota = computed(() => Math.max(0, ...this.distribuicao().map((n) => n.total)));
  readonly motivos = computed(() =>
    Object.entries(this.dados()?.confirmacao.cancelamentos_por_motivo ?? {}).sort((a, b) => b[1] - a[1]),
  );
  readonly faixa = computed(() => {
    const f = faixaNps(this.dados()?.nps.geral.nps);
    return { chave: f, rotulo: ROTULO_FAIXA_NPS[f] };
  });

  async ngOnInit(): Promise<void> {
    void this.carregarProfissionais();
    await this.carregar();
  }

  escolherPeriodoRapido(dias: number): void {
    this.diasRapidos.set(dias);
    this.periodo.set(periodoDosUltimosDias(dias));
    void this.carregar();
  }

  mudarData(campo: keyof Periodo, valor: string): void {
    this.diasRapidos.set(null);
    this.periodo.update((p) => ({ ...p, [campo]: valor }));
    if (this.periodoOk()) void this.carregar();
  }

  mudarProfissional(id: number | null): void {
    this.profissionalId.set(id);
    void this.carregar();
  }

  /** `atualizar`: o botão Atualizar pede números recalculados, sem o cache de 1 minuto do servidor. */
  async carregar(atualizar = false): Promise<void> {
    if (!this.periodoOk()) return;
    this.carregando.set(true);
    const p = this.periodo();
    const filtro = `?inicio=${p.inicio}&fim=${p.fim}`
      + (this.profissionalId() !== null ? `&profissional_id=${this.profissionalId()}` : '')
      + (atualizar ? '&atualizar=true' : '');
    const buscar = <T>(caminho: string) => firstValueFrom(this.api.get<T>(`${caminho}${filtro}`));
    try {
      const [ocupacao, confirmacao, sintomas, custo, fila, nps, avaliacoes] = await Promise.all([
        buscar<Ocupacao>('/relatorios/ocupacao'),
        buscar<Confirmacao>('/relatorios/confirmacao'),
        buscar<Sintomas>('/relatorios/sintomas'),
        buscar<Custo>('/relatorios/custo-por-agendamento'),
        buscar<FilaRelatorio>('/relatorios/fila-espera'),
        buscar<ResumoNps>('/admin/avaliacoes/nps'),
        firstValueFrom(this.api.get<AvaliacaoItem[]>(`/admin/avaliacoes${filtro}&limite=10`)),
      ]);
      this.dados.set({ ocupacao, confirmacao, sintomas, custo, fila, nps, avaliacoes });
      this.falhou.set(false);
    } catch {
      this.falhou.set(true);
    } finally {
      this.carregando.set(false);
    }
  }

  estrelas(nota: number): string {
    return '★'.repeat(nota) + '☆'.repeat(5 - nota);
  }

  private async carregarProfissionais(): Promise<void> {
    try {
      const lista = await firstValueFrom(this.api.get<{ id: number; nome: string }[]>('/profissionais/'));
      this.profissionais.set(lista.map(({ id, nome }) => ({ id, nome })));
    } catch {
      // sem a lista, o relatório continua valendo para a unidade inteira
    }
  }
}
