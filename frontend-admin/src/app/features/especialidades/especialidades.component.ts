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
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from '../../core/services/api.service';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';

interface Especialidade {
  id: number;
  nome: string;
  descricao: string | null;
  cor_hex: string | null;
  icone: string | null;
  ativo: boolean;
}

@Component({
  selector: 'app-especialidades',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule, MatDialogModule,
    MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    MatTooltipModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './especialidades.component.html',
  styleUrl: './especialidades.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EspecialidadesComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly especialidades = signal<Especialidade[]>([]);
  readonly carregando = signal(false);
  readonly mostrarForm = signal(false);
  readonly editando = signal<Especialidade | null>(null);

  readonly form = this.fb.group({
    nome:     ['', Validators.required],
    descricao:[''],
    cor_hex:  ['#2563eb'],
    icone:    ['stethoscope'],
  });

  async ngOnInit(): Promise<void> {
    await this.carregar();
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    try {
      const lista = await firstValueFrom(this.api.get<Especialidade[]>('/especialidades/'));
      this.especialidades.set(lista);
    } finally {
      this.carregando.set(false);
    }
  }

  abrirNova(): void {
    this.editando.set(null);
    this.form.reset({ nome: '', descricao: '', cor_hex: '#2563eb', icone: 'stethoscope' });
    this.mostrarForm.set(true);
  }

  abrirEditar(esp: Especialidade): void {
    this.editando.set(esp);
    this.form.patchValue({
      nome:      esp.nome,
      descricao: esp.descricao ?? '',
      cor_hex:   esp.cor_hex ?? '#2563eb',
      icone:     esp.icone ?? 'stethoscope',
    });
    this.mostrarForm.set(true);
  }

  fecharForm(): void {
    this.mostrarForm.set(false);
  }

  async salvar(): Promise<void> {
    if (this.form.invalid) return;
    const dados = this.form.getRawValue();
    try {
      const ed = this.editando();
      if (ed) {
        const atualizada = await firstValueFrom(
          this.api.patch<Especialidade>(`/especialidades/${ed.id}`, dados),
        );
        this.especialidades.update((l) => l.map((e) => (e.id === ed.id ? atualizada : e)));
        this.toast.sucesso('Especialidade atualizada!');
      } else {
        const nova = await firstValueFrom(
          this.api.post<Especialidade>('/especialidades/', dados),
        );
        this.especialidades.update((l) => [...l, nova]);
        this.toast.sucesso('Especialidade criada!');
      }
      this.mostrarForm.set(false);
    } catch {
      this.toast.erro('Erro ao salvar especialidade.');
    }
  }

  confirmarDesativar(esp: Especialidade): void {
    const ref = this.dialog.open(ConfirmDialogComponent, {
      data: {
        titulo: 'Desativar especialidade',
        mensagem: `Deseja desativar "${esp.nome}"? Os médicos desta especialidade não serão afetados.`,
        confirmLabel: 'Desativar',
        confirmColor: 'warn',
      },
    });
    ref.afterClosed().subscribe(async (ok) => {
      if (!ok) return;
      try {
        await firstValueFrom(this.api.patch(`/especialidades/${esp.id}`, { ativo: false }));
        this.especialidades.update((l) => l.map((e) => (e.id === esp.id ? { ...e, ativo: false } : e)));
        this.toast.sucesso('Especialidade desativada.');
      } catch {
        this.toast.erro('Erro ao desativar.');
      }
    });
  }

  textColor(hex: string | null): string {
    if (!hex) return '#fff';
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? '#1e293b' : '#fff';
  }
}
