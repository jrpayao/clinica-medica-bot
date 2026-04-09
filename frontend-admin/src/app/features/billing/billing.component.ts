import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  computed,
  inject,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';

import { Chart, registerables } from 'chart.js';

import { BillingService } from './billing.service';
import { BillingConfigComponent } from './billing-config.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { localDateString } from '../../core/utils/date.utils';
import { AuthAdminService } from '../../core/services/auth-admin.service';

Chart.register(...registerables);

@Component({
  selector: 'app-billing',
  standalone: true,
  imports: [
    DecimalPipe, ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule, MatTabsModule,
    MatProgressBarModule, MatTableModule, MatFormFieldModule,
    MatInputModule, MatDatepickerModule, MatNativeDateModule,
    MatProgressSpinnerModule, MatSelectModule, MatTooltipModule,
    MatChipsModule,
    BillingConfigComponent, PageHeaderComponent,
  ],
  templateUrl: './billing.component.html',
  styleUrl: './billing.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BillingComponent implements OnInit, AfterViewInit {
  readonly svc  = inject(BillingService);
  readonly auth = inject(AuthAdminService);

  readonly dataCtrl          = new FormControl<Date>(new Date());
  readonly estabelecimentoCtrl = new FormControl<number | null>(null);

  readonly colunasModelo    = ['modelo', 'chamadas', 'tokens', 'custo'];
  readonly colunasRanking   = ['nome', 'chamadas', 'tokens', 'custo'];

  readonly isAdminGlobal = computed(() => this.auth.usuario()?.role === 'ADMIN_GLOBAL');

  @ViewChild('modelChart')   modelChartRef!: ElementRef<HTMLCanvasElement>;
  @ViewChild('featureChart') featureChartRef!: ElementRef<HTMLCanvasElement>;

  private charts: Chart[] = [];

  async ngOnInit(): Promise<void> {
    await this._carregar();
    if (this.isAdminGlobal()) {
      await this.svc.carregarRanking(this.dataISO());
    }
  }

  ngAfterViewInit(): void {
    this.renderCharts();
  }

  async filtrar(): Promise<void> {
    await this._carregar();
    if (this.isAdminGlobal()) {
      await this.svc.carregarRanking(this.dataISO());
    }
    this.renderCharts();
  }

  private async _carregar(): Promise<void> {
    const estId = this.isAdminGlobal()
      ? this.estabelecimentoCtrl.value
      : null; // ADMIN_ESTABELECIMENTO: backend resolve pelo JWT
    await this.svc.carregar(this.dataISO(), estId);
  }

  private dataISO(): string {
    return localDateString(this.dataCtrl.value ?? new Date());
  }

  private renderCharts(): void {
    this.charts.forEach((c) => c.destroy());
    this.charts = [];

    const d = this.svc.dashboard();
    if (!d) return;

    if (this.modelChartRef?.nativeElement && d.por_modelo.length) {
      this.charts.push(
        new Chart(this.modelChartRef.nativeElement, {
          type: 'bar',
          data: {
            labels: d.por_modelo.map((m) => m.modelo),
            datasets: [
              {
                label: 'Custo (USD)',
                data: d.por_modelo.map((m) => m.custo_total),
                backgroundColor: 'rgba(37,99,235,0.8)',
                borderRadius: 6,
                yAxisID: 'y',
              },
              {
                label: 'Chamadas',
                data: d.por_modelo.map((m) => m.total_chamadas),
                backgroundColor: 'rgba(22,163,74,0.8)',
                borderRadius: 6,
                yAxisID: 'y1',
              },
            ],
          },
          options: {
            responsive: true,
            plugins: { legend: { position: 'top' } },
            scales: {
              y:  { position: 'left',  title: { display: true, text: 'USD' } },
              y1: { position: 'right', title: { display: true, text: 'Chamadas' }, grid: { drawOnChartArea: false } },
            },
          },
        })
      );
    }

    if (this.featureChartRef?.nativeElement && d.por_feature.length) {
      this.charts.push(
        new Chart(this.featureChartRef.nativeElement, {
          type: 'doughnut',
          data: {
            labels: d.por_feature.map((f) => f.feature),
            datasets: [{
              data: d.por_feature.map((f) => f.custo_total),
              backgroundColor: ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2'],
              borderWidth: 2,
            }],
          },
          options: {
            responsive: true,
            plugins: { legend: { position: 'right' } },
          },
        })
      );
    }
  }

  get percentual(): number {
    return this.svc.dashboard()?.limites.percentual_usado ?? 0;
  }

  get corProgressBar(): string {
    if (this.percentual >= 90) return 'warn';
    if (this.percentual >= 70) return 'accent';
    return 'primary';
  }

  baixarCsv(): void {
    const estId = this.isAdminGlobal() ? this.estabelecimentoCtrl.value : null;
    const link = document.createElement('a');
    link.href = this.svc.exportarCsvUrl(this.dataISO(), this.dataISO(), estId);
    link.download = `billing-${this.dataISO()}.csv`;
    link.click();
  }

  nomeEstabelecimentoSelecionado(): string {
    const id = this.estabelecimentoCtrl.value;
    if (!id) return 'Todos os estabelecimentos';
    const found = this.svc.ranking().find((r) => r.estabelecimento_id === id);
    return found?.nome ?? `Estabelecimento #${id}`;
  }
}
