import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';

interface BillingConfig {
  daily_limit_usd: number;
  monthly_limit_usd: number;
  alert_threshold: number;
}

@Component({
  selector: 'app-billing-config',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule, MatProgressSpinnerModule,
  ],
  templateUrl: './billing-config.component.html',
  styleUrl: './billing-config.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BillingConfigComponent implements OnInit {
  private readonly api   = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly fb    = inject(FormBuilder);

  readonly salvando = signal(false);

  readonly form = this.fb.group({
    daily_limit_usd:   [10,  [Validators.required, Validators.min(0.01)]],
    monthly_limit_usd: [200, [Validators.required, Validators.min(0.01)]],
    alert_threshold:   [80,  [Validators.required, Validators.min(1), Validators.max(100)]],
  });

  async ngOnInit(): Promise<void> {
    try {
      const res = await firstValueFrom(this.api.get<BillingConfig>('/billing/config'));
      this.form.patchValue({
        daily_limit_usd:   res.daily_limit_usd,
        monthly_limit_usd: res.monthly_limit_usd,
        alert_threshold:   res.alert_threshold * 100,
      });
    } catch {
      // usa valores padrão se API falhar
    }
  }

  async salvar(): Promise<void> {
    if (this.form.invalid) return;
    this.salvando.set(true);
    try {
      const raw = this.form.getRawValue();
      const payload: BillingConfig = {
        daily_limit_usd:   raw.daily_limit_usd!,
        monthly_limit_usd: raw.monthly_limit_usd!,
        alert_threshold:   raw.alert_threshold! / 100,
      };
      await firstValueFrom(this.api.patch<BillingConfig>('/billing/config', payload));
      this.toast.sucesso('Configurações de billing salvas com sucesso.');
    } catch {
      this.toast.erro('Erro ao salvar configurações de billing.');
    } finally {
      this.salvando.set(false);
    }
  }
}
