import { ChangeDetectionStrategy, Component, OnInit, inject, signal, computed } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/services/api.service';

interface Licenca {
  id: number;
  estabelecimento_id: number;
  estabelecimento_nome: string;
  plano: string;
  status: string;
  expira_em: string | null;
  criada_em: string | null;
}

@Component({
  selector: 'app-licencas',
  standalone: true,
  imports: [
    DatePipe,
    MatTableModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatFormFieldModule,
    FormsModule,
  ],
  templateUrl: './licencas.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LicencasComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly licencas = signal<Licenca[]>([]);
  readonly loading = signal(false);
  readonly filtroStatus = signal<string>('');

  readonly colunas = ['estabelecimento_nome', 'plano', 'status', 'expira_em', 'criada_em'];

  readonly licencasFiltradas = computed(() => {
    const f = this.filtroStatus();
    return f ? this.licencas().filter((l) => l.status === f) : this.licencas();
  });

  async ngOnInit(): Promise<void> {
    this.loading.set(true);
    try {
      const data = await firstValueFrom(this.api.get<Licenca[]>('/admin/licencas'));
      this.licencas.set(data);
    } finally {
      this.loading.set(false);
    }
  }

  corStatus(status: string): string {
    const map: Record<string, string> = {
      ATIVA: 'primary',
      TRIAL: 'accent',
      EXPIRADA: 'warn',
      SUSPENSA: 'warn',
    };
    return map[status] ?? 'default';
  }
}
