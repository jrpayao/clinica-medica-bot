import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatDialog } from '@angular/material/dialog';

import { ApiService } from '../../core/services/api.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { PacienteEditDialogComponent } from './paciente-edit-dialog.component';
import { ToastService } from '../../core/services/toast.service';

interface Paciente {
  id: number;
  nome: string;
  cpf: string; // mascarado pela API
  data_nascimento: string | null;
  telefone: string | null;
  email: string | null;
  convenio: string | null;
  numero_carteirinha: string | null;
  ativo: boolean;
  created_at: string;
}

@Component({
  selector: 'app-pacientes',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    MatTooltipModule, MatPaginatorModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './pacientes.component.html',
  styleUrl: './pacientes.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PacientesComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog);
  private readonly toast = inject(ToastService);

  readonly pacientes = signal<Paciente[]>([]);
  readonly carregando = signal(false);
  readonly busca = new FormControl('');
  readonly pagina = signal(0);
  readonly tamanhoPagina = signal(20);

  readonly colunas = ['nome', 'cpf', 'telefone', 'email', 'convenio', 'acoes'];

  get pacientesFiltrados(): Paciente[] {
    const termo = (this.busca.value ?? '').toLowerCase();
    if (!termo) return this.pacientes();
    return this.pacientes().filter(
      (p) =>
        p.nome.toLowerCase().includes(termo) ||
        p.cpf.toLowerCase().includes(termo),
    );
  }

  get pacientesPaginados(): Paciente[] {
    const inicio = this.pagina() * this.tamanhoPagina();
    return this.pacientesFiltrados.slice(inicio, inicio + this.tamanhoPagina());
  }

  async ngOnInit(): Promise<void> {
    this.carregando.set(true);
    try {
      const lista = await firstValueFrom(this.api.get<Paciente[]>('/pacientes/'));
      this.pacientes.set(lista);
    } catch {
      this.toast.erro('Erro ao carregar pacientes.');
    } finally {
      this.carregando.set(false);
    }
  }

  abrirEditar(paciente: Paciente): void {
    const ref = this.dialog.open(PacienteEditDialogComponent, {
      data: paciente,
      width: '480px',
    });
    ref.afterClosed().subscribe(async (dados) => {
      if (!dados) return;
      try {
        const atualizado = await firstValueFrom(
          this.api.patch<Paciente>(`/pacientes/${paciente.id}`, dados),
        );
        this.pacientes.update((l) => l.map((p) => (p.id === paciente.id ? atualizado : p)));
        this.toast.sucesso('Paciente atualizado!');
      } catch {
        this.toast.erro('Erro ao atualizar paciente.');
      }
    });
  }

  onPageChange(e: PageEvent): void {
    this.pagina.set(e.pageIndex);
    this.tamanhoPagina.set(e.pageSize);
  }
}
