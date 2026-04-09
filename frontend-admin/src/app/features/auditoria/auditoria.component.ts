import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/services/api.service';

interface EventoAuditoria {
  id: number;
  usuario_id: number;
  usuario_role: string;
  acao: string;
  estabelecimento_id: number | null;
  entidade: string | null;
  entidade_id: number | null;
  ip_origem: string | null;
  created_at: string;
}

@Component({
  selector: 'app-auditoria',
  standalone: true,
  imports: [
    DatePipe,
    FormsModule,
    MatTableModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatSelectModule,
    MatInputModule,
  ],
  templateUrl: './auditoria.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuditoriaComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly eventos = signal<EventoAuditoria[]>([]);
  readonly loading = signal(false);
  readonly offset = signal(0);
  readonly limit = 50;
  readonly filtroAcao = signal('');

  readonly colunas = ['created_at', 'usuario_role', 'acao', 'estabelecimento_id', 'ip_origem'];

  async ngOnInit(): Promise<void> {
    await this._carregar();
  }

  private async _carregar(): Promise<void> {
    this.loading.set(true);
    const params = new URLSearchParams({
      limit: String(this.limit),
      offset: String(this.offset()),
    });
    if (this.filtroAcao()) params.set('acao', this.filtroAcao());
    try {
      const data = await firstValueFrom(
        this.api.get<EventoAuditoria[]>(`/admin/auditoria?${params}`),
      );
      this.eventos.set(data);
    } finally {
      this.loading.set(false);
    }
  }

  async aplicarFiltro(): Promise<void> {
    this.offset.set(0);
    await this._carregar();
  }

  async proxima(): Promise<void> {
    this.offset.update((v) => v + this.limit);
    await this._carregar();
  }

  async anterior(): Promise<void> {
    this.offset.update((v) => Math.max(0, v - this.limit));
    await this._carregar();
  }
}
