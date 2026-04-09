import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';

import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialog } from '@angular/material/dialog';

import { MedicosService, Medico } from './medicos.service';
import { MedicoDialogComponent, MedicoDialogData } from './medico-dialog.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';

@Component({
  selector: 'app-medicos',
  standalone: true,
  imports: [
    MatTableModule, MatButtonModule, MatIconModule,
    MatChipsModule, MatTooltipModule, MatProgressSpinnerModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './medicos.component.html',
  styleUrl: './medicos.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MedicosComponent implements OnInit {
  readonly svc = inject(MedicosService);
  private readonly dialog = inject(MatDialog);
  private readonly toast = inject(ToastService);

  readonly colunas = ['avatar', 'nome', 'crm', 'especialidade', 'duracao', 'status', 'acoes'];

  async ngOnInit(): Promise<void> {
    await this.svc.listar();
  }

  abrirNovo(): void {
    const ref = this.dialog.open(MedicoDialogComponent, {
      data: {
        medico: null,
        especialidades: this.svc.especialidades(),
      } satisfies MedicoDialogData,
      width: '520px',
    });

    ref.afterClosed().subscribe(async (dados) => {
      if (!dados) return;
      try {
        await this.svc.criar(dados);
        this.toast.sucesso('Médico criado com sucesso!');
      } catch {
        this.toast.erro('Erro ao criar médico. Verifique as informações.');
      }
    });
  }

  abrirEditar(medico: Medico): void {
    const ref = this.dialog.open(MedicoDialogComponent, {
      data: {
        medico,
        especialidades: this.svc.especialidades(),
      } satisfies MedicoDialogData,
      width: '520px',
    });

    ref.afterClosed().subscribe(async (dados) => {
      if (!dados) return;
      try {
        await this.svc.atualizar(medico.id, {
          nome: dados.nome,
          email: dados.email || undefined,
          telefone: dados.telefone || undefined,
          duracao_consulta_min: dados.duracao_consulta_min,
        });
        this.toast.sucesso('Médico atualizado!');
      } catch {
        this.toast.erro('Erro ao atualizar médico.');
      }
    });
  }

  confirmarDesativar(medico: Medico): void {
    const ref = this.dialog.open(ConfirmDialogComponent, {
      data: {
        titulo: 'Desativar médico',
        mensagem: `Tem certeza que deseja desativar ${medico.nome}? O médico não aparecerá mais na agenda.`,
        confirmLabel: 'Desativar',
        confirmColor: 'warn',
      },
    });

    ref.afterClosed().subscribe(async (confirmado) => {
      if (!confirmado) return;
      try {
        await this.svc.desativar(medico.id);
        this.toast.sucesso('Médico desativado.');
      } catch {
        this.toast.erro('Erro ao desativar médico.');
      }
    });
  }

  corEspecialidade(id: number): string {
    return this.svc.especialidades().find((e) => e.id === id)?.cor_hex ?? '#64748b';
  }

  iniciais(nome: string): string {
    return nome.split(' ').slice(0, 2).map((n) => n[0]).join('').toUpperCase();
  }
}
