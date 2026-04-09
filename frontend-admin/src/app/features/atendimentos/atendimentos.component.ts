import {
  ChangeDetectionStrategy, Component, OnInit, inject, signal,
} from '@angular/core';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatDialog } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';

import { ApiService } from '../../core/services/api.service';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';
import { localDateString } from '../../core/utils/date.utils';

interface Consulta {
  id: number;
  slot_id: number;
  cliente_id: number;
  profissional_id: number;
  status: string;
  urgencia: string;
  canal_origem: string;
  tipo: string;
  triagem_resumo: Record<string, unknown> | null;
  observacoes: string | null;
  created_at: string;
}

interface SlotComConsulta {
  id: number;
  profissional_id: number;
  profissional_nome: string;
  especialidade_nome: string;
  data: string;
  hora_inicio: string;
  hora_fim: string;
  status: string;
  consulta: {
    id: number;
    cliente_nome: string;
    paciente_cpf_mascarado: string;
    status: string;
    urgencia: string;
    canal_origem: string;
    triagem_resumo: Record<string, unknown> | null;
    observacoes: string | null;
    created_at: string;
  } | null;
}

@Component({
  selector: 'app-atendimentos',
  standalone: true,
  imports: [
    DatePipe, ReactiveFormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatProgressSpinnerModule, MatTooltipModule, MatPaginatorModule,
    MatExpansionModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './atendimentos.component.html',
  styleUrl: './atendimentos.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AtendimentosComponent implements OnInit {
  private readonly api    = inject(ApiService);
  private readonly dialog = inject(MatDialog);
  private readonly toast  = inject(ToastService);
  private readonly route  = inject(ActivatedRoute);

  readonly slots = signal<SlotComConsulta[]>([]);
  readonly carregando = signal(false);
  readonly filtroStatus = new FormControl('');
  readonly filtroUrgencia = new FormControl('');
  readonly pagina = signal(0);
  readonly tamanhoPagina = signal(20);

  readonly colunas = ['data', 'medico', 'paciente', 'urgencia', 'status', 'canal', 'acoes'];

  get slotsFiltrados(): SlotComConsulta[] {
    let lista = this.slots().filter((s) => s.consulta);
    const status = this.filtroStatus.value;
    const urgencia = this.filtroUrgencia.value;
    if (status) lista = lista.filter((s) => s.consulta!.status === status);
    if (urgencia) lista = lista.filter((s) => s.consulta!.urgencia === urgencia);
    return lista;
  }

  get slotsPaginados(): SlotComConsulta[] {
    const inicio = this.pagina() * this.tamanhoPagina();
    return this.slotsFiltrados.slice(inicio, inicio + this.tamanhoPagina());
  }

  async ngOnInit(): Promise<void> {
    // Aplica filtros vindos de query params (ex: /atendimentos?status=AGENDADA&data=2026-04-08)
    const qp = this.route.snapshot.queryParamMap;
    const statusParam = qp.get('status');
    const dataParam   = qp.get('data');
    if (statusParam) this.filtroStatus.setValue(statusParam, { emitEvent: false });

    this.carregando.set(true);
    try {
      const hoje = dataParam ?? localDateString();
      const lista = await firstValueFrom(
        this.api.get<SlotComConsulta[]>(`/agenda/slots/dia/${hoje}`),
      );
      this.slots.set(lista);
    } catch {
      this.toast.erro('Erro ao carregar atendimentos.');
    } finally {
      this.carregando.set(false);
    }
  }

  confirmarCancelar(slot: SlotComConsulta): void {
    const ref = this.dialog.open(ConfirmDialogComponent, {
      data: {
        titulo: 'Cancelar consulta',
        mensagem: `Cancelar a consulta de ${slot.consulta!.cliente_nome}?`,
        confirmLabel: 'Cancelar consulta',
        confirmColor: 'warn',
      },
    });

    ref.afterClosed().subscribe(async (ok) => {
      if (!ok) return;
      try {
        await firstValueFrom(
          this.api.patch(`/agenda/atendimentos/${slot.consulta!.id}/cancelar`, {
            motivo: 'Cancelado pelo administrador',
          }),
        );
        this.slots.update((l) =>
          l.map((s) =>
            s.id === slot.id && s.consulta
              ? { ...s, consulta: { ...s.consulta, status: 'CANCELADA' } }
              : s,
          ),
        );
        this.toast.sucesso('Consulta cancelada.');
      } catch {
        this.toast.erro('Erro ao cancelar consulta.');
      }
    });
  }

  onPageChange(e: PageEvent): void {
    this.pagina.set(e.pageIndex);
    this.tamanhoPagina.set(e.pageSize);
  }

  triagemItens(resumo: Record<string, unknown> | null): { chave: string; valor: string }[] {
    if (!resumo) return [];
    return Object.entries(resumo).map(([chave, valor]) => ({ chave, valor: String(valor) }));
  }
}
