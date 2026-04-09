import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  effect,
  inject,
  signal,
  computed,
  untracked,
} from '@angular/core';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { DatePipe } from '@angular/common';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatInputModule } from '@angular/material/input';
import { MatNativeDateModule } from '@angular/material/core';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';

import { AgendaAdminService, SlotAdmin } from '../../core/services/agenda-admin.service';
import { MedicosService } from '../medicos/medicos.service';
import { AuthAdminService } from '../../core/services/auth-admin.service';
import { SlotDetalheDialogComponent } from './slot-detalhe-dialog.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { localDateString } from '../../core/utils/date.utils';

@Component({
  selector: 'app-agenda',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule,
    MatSelectModule, MatFormFieldModule, MatDatepickerModule,
    MatInputModule, MatNativeDateModule, MatChipsModule,
    MatProgressSpinnerModule, MatTooltipModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './agenda.component.html',
  styleUrl: './agenda.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AgendaComponent implements OnInit {
  readonly agenda    = inject(AgendaAdminService);
  readonly medicosSvc = inject(MedicosService);
  readonly auth      = inject(AuthAdminService);
  private readonly dialog = inject(MatDialog);

  readonly dataCtrl                = new FormControl<Date>(new Date());
  readonly filtroEspecialidadeCtrl = new FormControl<number | null>(null);
  readonly filtroMedicoCtrl        = new FormControl<number | null>(null);

  readonly dataSelecionada       = signal(localDateString());
  readonly filtroEspecialidadeId = signal<number | null>(null);
  readonly filtroMedicoId        = signal<number | null>(null);

  /** Admin Global sem estabelecimento ativo (nem JWT nem filtro global no toolbar) */
  readonly semEstabelecimento = computed(() => this.auth.semEstabelecimento());

  /** Médicos disponíveis no dropdown — filtrado pela especialidade selecionada */
  readonly medicosFiltrados = computed(() => {
    const espId = this.filtroEspecialidadeId();
    return espId
      ? this.medicosSvc.medicos().filter((m) => m.especialidade_id === espId)
      : this.medicosSvc.medicos();
  });

  /** Slots exibidos — filtro client-side reativo (especialidade → médico) */
  readonly slotsFiltrados = computed(() => {
    const medicoId = this.filtroMedicoId();
    const espId    = this.filtroEspecialidadeId();

    let slots = this.agenda.slots();

    if (medicoId) {
      slots = slots.filter((s) => s.medico_id === medicoId);
    } else if (espId) {
      const ids = new Set(this.medicosFiltrados().map((m) => m.id));
      slots = slots.filter((s) => ids.has(s.medico_id));
    }

    return slots;
  });

  constructor() {
    effect(() => {
      const id = this.auth.estabelecimentoAtivoId();
      if (id !== null) {
        untracked(() => {
          void Promise.all([
            this.agenda.carregarPorData(this.dataSelecionada()),
            this.medicosSvc.listar(),
          ]);
        });
      }
    });
  }

  async ngOnInit(): Promise<void> {
    // Muda data → recarrega backend
    this.dataCtrl.valueChanges.subscribe(async (data) => {
      if (!data || this.semEstabelecimento()) return;
      const iso = localDateString(data);
      this.dataSelecionada.set(iso);
      await this._recarregar(iso);
    });

    // Muda especialidade → reseta médico (client-side, sem reload)
    this.filtroEspecialidadeCtrl.valueChanges.subscribe((espId) => {
      this.filtroEspecialidadeId.set(espId);
      this.filtroMedicoCtrl.setValue(null, { emitEvent: false });
      this.filtroMedicoId.set(null);
      this.agenda.filtroMedicoId.set(null);
    });

    // Muda médico → recarrega backend com ?medico_id=N
    this.filtroMedicoCtrl.valueChanges.subscribe(async (id) => {
      this.filtroMedicoId.set(id);
      if (this.semEstabelecimento()) return;
      this.agenda.filtroMedicoId.set(id);
      await this._recarregar(this.dataSelecionada());
    });
  }

  private async _recarregar(data: string): Promise<void> {
    await this.agenda.carregarPorData(data);
  }


  slotsPorHora(): Map<string, SlotAdmin[]> {
    const map = new Map<string, SlotAdmin[]>();
    for (const slot of this.slotsFiltrados()) {
      const hora = slot.hora_inicio.slice(0, 5);
      if (!map.has(hora)) map.set(hora, []);
      map.get(hora)!.push(slot);
    }
    return map;
  }

  horas(): string[] {
    return Array.from(this.slotsPorHora().keys()).sort();
  }

  abrirDetalhe(slot: SlotAdmin): void {
    this.dialog.open(SlotDetalheDialogComponent, {
      data: slot,
      width: '540px',
    });
  }

  corSlot(status: string): string {
    const mapa: Record<string, string> = {
      DISPONIVEL: '#16a34a',
      AGENDADO:   '#2563eb',
      BLOQUEADO:  '#9ca3af',
      ENCAIXE:    '#d97706',
      RESERVADO:  '#7c3aed',
    };
    return mapa[status] ?? '#64748b';
  }

  iconSlot(status: string): string {
    const mapa: Record<string, string> = {
      DISPONIVEL: 'event_available',
      AGENDADO:   'person',
      BLOQUEADO:  'block',
      ENCAIXE:    'add_circle',
      RESERVADO:  'lock',
    };
    return mapa[status] ?? 'circle';
  }

  diaAnterior(): void {
    const atual = this.dataCtrl.value ?? new Date();
    const nova = new Date(atual.getTime() - 86400000);
    this.dataCtrl.setValue(nova);
  }

  proximoDia(): void {
    const atual = this.dataCtrl.value ?? new Date();
    const nova = new Date(atual.getTime() + 86400000);
    this.dataCtrl.setValue(nova);
  }
}
