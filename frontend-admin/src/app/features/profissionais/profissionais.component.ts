import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';

import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDialog } from '@angular/material/dialog';

import { ProfissionaisService, Medico } from './profissionais.service';
import { ProfissionalDialogComponent, ProfissionalDialogData } from './profissional-dialog.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';
import { VocabularioService } from '../../core/services/vocabulario.service';

import { AuthAdminService } from '../../core/services/auth-admin.service';
import { perfilSomenteLeituraDeCadastros } from '../../core/services/perfil';

@Component({
  selector: 'app-profissionais',
  standalone: true,
  imports: [
    MatTableModule, MatButtonModule, MatIconModule,
    MatChipsModule, MatTooltipModule, MatProgressSpinnerModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './profissionais.component.html',
  styleUrl: './profissionais.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfissionaisComponent implements OnInit {
  readonly vocab = inject(VocabularioService);
  readonly svc = inject(ProfissionaisService);
  private readonly dialog = inject(MatDialog);
  private readonly toast = inject(ToastService);

  /** Recepção consulta o cadastro, mas não altera (a API também recusa). */
  readonly somenteLeitura = perfilSomenteLeituraDeCadastros(inject(AuthAdminService).usuario()?.role);

  readonly colunas = [
    'avatar', 'nome', 'registro_profissional', 'especialidade', 'duracao', 'status',
    ...(this.somenteLeitura ? [] : ['acoes']),
  ];

  async ngOnInit(): Promise<void> {
    await this.svc.listar();
  }

  abrirNovo(): void {
    const ref = this.dialog.open(ProfissionalDialogComponent, {
      data: {
        medico: null,
        especialidades: this.svc.especialidades(),
      } satisfies ProfissionalDialogData,
      width: '520px',
    });

    ref.afterClosed().subscribe(async (dados) => {
      if (!dados) return;
      try {
        await this.svc.criar(dados);
        this.toast.sucesso(`${this.vocab.profissional()}: cadastro criado.`);
      } catch {
        this.toast.erro('Erro ao criar o cadastro. Verifique as informações.');
      }
    });
  }

  abrirEditar(medico: Medico): void {
    const ref = this.dialog.open(ProfissionalDialogComponent, {
      data: {
        medico,
        especialidades: this.svc.especialidades(),
      } satisfies ProfissionalDialogData,
      width: '520px',
    });

    ref.afterClosed().subscribe(async (dados) => {
      if (!dados) return;
      try {
        await this.svc.atualizar(medico.id, {
          nome: dados.nome,
          email: dados.email || undefined,
          telefone: dados.telefone || undefined,
          duracao_atendimento_min: dados.duracao_atendimento_min,
        });
        this.toast.sucesso('Cadastro atualizado.');
      } catch {
        this.toast.erro('Erro ao atualizar o cadastro.');
      }
    });
  }

  confirmarDesativar(medico: Medico): void {
    const ref = this.dialog.open(ConfirmDialogComponent, {
      data: {
        titulo: `Desativar ${this.vocab.profissional().toLowerCase()}`,
        mensagem: `Tem certeza que deseja desativar ${medico.nome}? O cadastro não aparecerá mais na agenda.`,
        confirmLabel: 'Desativar',
        confirmColor: 'warn',
      },
    });

    ref.afterClosed().subscribe(async (confirmado) => {
      if (!confirmado) return;
      try {
        await this.svc.desativar(medico.id);
        this.toast.sucesso('Cadastro desativado.');
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
