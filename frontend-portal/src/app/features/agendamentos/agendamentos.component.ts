import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AgendamentoService } from '../../core/services/agendamento.service';

@Component({
  selector: 'app-agendamentos',
  standalone: true,
  imports: [DatePipe, FormsModule],
  templateUrl: './agendamentos.component.html',
  styleUrls: ['./agendamentos.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AgendamentosComponent {
  readonly agendamentos = inject(AgendamentoService);
  readonly motivoCancelar = signal('');
  readonly cancelandoId = signal<number | null>(null);
  readonly confirmarCancelarId = signal<number | null>(null);

  onMotivoInput(event: Event): void {
    this.motivoCancelar.set((event.target as HTMLInputElement).value);
  }

  abrirCancelamento(consultaId: number): void {
    this.confirmarCancelarId.set(consultaId);
    this.motivoCancelar.set('');
  }

  fecharCancelamento(): void {
    this.confirmarCancelarId.set(null);
    this.motivoCancelar.set('');
  }

  async confirmarCancelamento(consultaId: number): Promise<void> {
    const motivo = this.motivoCancelar().trim();
    if (!motivo) return;

    this.cancelandoId.set(consultaId);
    this.confirmarCancelarId.set(null);
    try {
      await this.agendamentos.cancelar(consultaId, motivo);
    } finally {
      this.cancelandoId.set(null);
      this.motivoCancelar.set('');
    }
  }
}
