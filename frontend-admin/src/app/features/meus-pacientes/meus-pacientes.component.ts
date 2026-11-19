import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';

import { ApiService } from '../../core/services/api.service';
import { VocabularioService } from '../../core/services/vocabulario.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';

interface MeuPaciente {
  cliente_id: number;
  nome: string;
  cpf_mascarado: string;
  telefone: string | null;
  total_atendimentos: number;
  ultimo_atendimento: string | null;
  convenio_nome: string | null;
}

/** Pacientes que o profissional logado já atendeu (ou tem agendados) nesta unidade. */
@Component({
  selector: 'app-meus-pacientes',
  standalone: true,
  imports: [
    DatePipe, FormsModule,
    MatFormFieldModule, MatIconModule, MatInputModule, MatProgressSpinnerModule, MatTableModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './meus-pacientes.component.html',
  styleUrl: './meus-pacientes.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MeusPacientesComponent implements OnInit {
  readonly vocab = inject(VocabularioService);
  private readonly api = inject(ApiService);

  readonly pacientes = signal<MeuPaciente[]>([]);
  readonly carregando = signal(true);
  readonly falhou = signal(false);
  readonly busca = signal('');

  readonly colunas = ['nome', 'cpf', 'telefone', 'convenio', 'total', 'ultimo'];

  readonly filtrados = computed(() => {
    const termo = this.busca().trim().toLowerCase();
    if (!termo) return this.pacientes();
    return this.pacientes().filter((p) => p.nome.toLowerCase().includes(termo));
  });

  async ngOnInit(): Promise<void> {
    try {
      this.pacientes.set(await firstValueFrom(this.api.get<MeuPaciente[]>('/profissional/clientes')));
    } catch {
      this.falhou.set(true);
    } finally {
      this.carregando.set(false);
    }
  }
}
