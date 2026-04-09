import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { DatePipe, DecimalPipe, LowerCasePipe, PercentPipe } from '@angular/common';
import { Router, RouterModule } from '@angular/router';

import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatNativeDateModule } from '@angular/material/core';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatListModule } from '@angular/material/list';
import { ReactiveFormsModule, FormControl } from '@angular/forms';

import { Chart, registerables } from 'chart.js';
import { DashboardService } from '../../core/services/dashboard.service';
import { AuthAdminService } from '../../core/services/auth-admin.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { localDateString } from '../../core/utils/date.utils';

Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DatePipe, DecimalPipe, LowerCasePipe, PercentPipe,
    RouterModule, ReactiveFormsModule,
    MatCardModule, MatIconModule, MatButtonModule,
    MatProgressBarModule, MatProgressSpinnerModule,
    MatDatepickerModule, MatInputModule, MatFormFieldModule,
    MatNativeDateModule, MatTooltipModule, MatSelectModule,
    MatChipsModule, MatListModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent implements OnInit, AfterViewInit {
  readonly ds     = inject(DashboardService);
  readonly auth   = inject(AuthAdminService);
  private  router = inject(Router);

  readonly hoje     = signal(new Date());
  readonly dataCtrl = new FormControl<Date>(new Date());

  readonly isAdminGlobal = computed(() => this.auth.usuario()?.role === 'ADMIN_GLOBAL');

  @ViewChild('modelChart', { static: false }) modelChartRef!: ElementRef<HTMLCanvasElement>;
  private chart: Chart | null = null;
  private viewReady = false;

  constructor() {
    effect(() => {
      // Recarregar quando o filtro muda — inclusive quando volta para "todas as clínicas" (null)
      // Só bloqueia quando o usuário ainda não escolheu modo (precisaSelecionarEstabelecimento)
      this.auth.estabelecimentoAtivoId(); // rastrear signal
      if (!this.auth.precisaSelecionarEstabelecimento()) {
        untracked(() => { void this._carregar(); });
      }
    });
  }

  async ngOnInit(): Promise<void> {
    this.dataCtrl.valueChanges.subscribe(async (data) => {
      if (!data || this.auth.precisaSelecionarEstabelecimento()) return;
      this.hoje.set(data);
      await this._carregar();
    });
  }

  ngAfterViewInit(): void {
    this.viewReady = true;
    this._renderChart();
  }

  private async _carregar(): Promise<void> {
    const iso = localDateString(this.dataCtrl.value ?? new Date());
    await this.ds.carregar(iso);   // interceptor adiciona X-Estabelecimento-ID automaticamente
    this._renderChart();
  }

  private _renderChart(): void {
    if (!this.viewReady || !this.modelChartRef) return;
    const modelos = this.ds.usoModelos();
    if (!modelos.length) return;

    if (this.chart) this.chart.destroy();

    this.chart = new Chart(this.modelChartRef.nativeElement, {
      type: 'bar',
      data: {
        labels: modelos.map((m) => m.modelo),
        datasets: [
          {
            label: 'Custo (USD)',
            data: modelos.map((m) => m.custo_total),
            backgroundColor: '#2563eb',
            borderRadius: 6,
            yAxisID: 'y',
          },
          {
            label: 'Chamadas',
            data: modelos.map((m) => m.total_chamadas),
            backgroundColor: '#16a34a',
            borderRadius: 6,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'top' } },
        scales: {
          y:  { position: 'left',  beginAtZero: true, title: { display: true, text: 'USD' } },
          y1: { position: 'right', beginAtZero: true, title: { display: true, text: 'Chamadas' }, grid: { drawOnChartArea: false } },
        },
      },
    });
  }

  irParaConsultas(status?: string): void {
    const data = localDateString(this.dataCtrl.value ?? new Date());
    const qp: Record<string, string> = { data };
    if (status) qp['status'] = status;
    this.router.navigate(['/atendimentos'], { queryParams: qp });
  }

  get percentualCusto(): number {
    const kpi = this.ds.kpi();
    if (!kpi?.limite_diario) return 0;
    return Math.min(kpi.custo_ia_total / kpi.limite_diario, 1);
  }

  get corProgressBar(): string {
    const p = this.percentualCusto;
    if (p >= 0.9) return 'warn';
    if (p >= 0.7) return 'accent';
    return 'primary';
  }

  corAlerta(tipo: string): string {
    if (tipo === 'urgencia_alta') return 'danger';
    if (tipo === 'custo_alto')    return 'warning';
    return 'info';
  }

  iconeAlerta(tipo: string): string {
    if (tipo === 'urgencia_alta')       return 'emergency';
    if (tipo === 'custo_alto')          return 'payments';
    if (tipo === 'pendente_confirmacao') return 'pending_actions';
    return 'info';
  }

}
