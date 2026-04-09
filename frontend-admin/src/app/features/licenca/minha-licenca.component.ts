import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { PercentPipe, UpperCasePipe } from '@angular/common';
import { firstValueFrom } from 'rxjs';

import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { ApiService } from '../../core/services/api.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';

interface QuotaInfo {
  max_medicos: number;
  max_consultas_mes: number;
  whatsapp: boolean;
  medicos_ativos: number;
  consultas_mes_atual: number;
}

interface LicencaResponse {
  id: number;
  plano: string;
  status: string;
  modalidade: string;
  trial_expira_em: string | null;
  licenca_expira_em: string | null;
  dias_restantes: number;
  quota_info: QuotaInfo;
}

@Component({
  selector: 'app-minha-licenca',
  standalone: true,
  imports: [
    PercentPipe, UpperCasePipe,
    MatCardModule, MatIconModule, MatProgressBarModule,
    MatButtonModule, MatProgressSpinnerModule,
    PageHeaderComponent,
  ],
  templateUrl: './minha-licenca.component.html',
  styleUrl: './minha-licenca.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MinhaLicencaComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);

  readonly licenca = signal<LicencaResponse | null>(null);
  readonly carregando = signal(false);

  async ngOnInit(): Promise<void> {
    this.carregando.set(true);
    try {
      const res = await firstValueFrom(this.api.get<LicencaResponse>('/licenca/minha'));
      this.licenca.set(res);
    } catch {
      this.toast.erro('Erro ao carregar informações da licença.');
    } finally {
      this.carregando.set(false);
    }
  }

  get quotaMedicos(): number {
    const q = this.licenca()?.quota_info;
    if (!q?.max_medicos) return 0;
    return q.medicos_ativos / q.max_medicos;
  }

  get quotaConsultas(): number {
    const q = this.licenca()?.quota_info;
    if (!q?.max_consultas_mes) return 0;
    return q.consultas_mes_atual / q.max_consultas_mes;
  }

  get corLicenca(): string {
    const status = this.licenca()?.status ?? '';
    const mapa: Record<string, string> = {
      TRIAL: 'var(--licenca-trial)',
      ATIVA: 'var(--licenca-ativa)',
      EXPIRADA: 'var(--licenca-expirada)',
      SUSPENSA: 'var(--licenca-suspensa)',
    };
    return mapa[status] ?? 'var(--color-text-secondary)';
  }

  get alertaExpiracao(): boolean {
    const dias = this.licenca()?.dias_restantes ?? 999;
    return dias <= 7 && dias >= 0;
  }
}
