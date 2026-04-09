/**
 * SlotDetalheDialogComponent — detalhe do slot/consulta.
 * Substitui o AgendaModalComponent inline por um mat-dialog.
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDividerModule } from '@angular/material/divider';
import { MatChipsModule } from '@angular/material/chips';

import { SlotAdmin } from '../../core/services/agenda-admin.service';

@Component({
  selector: 'app-slot-detalhe-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule, MatDividerModule, MatChipsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="dialog-header" [style.borderColor]="corUrgencia">
      <div>
        <h2 mat-dialog-title>{{ slot.hora_inicio.slice(0,5) }} — {{ slot.profissional_nome }}</h2>
        <p class="dialog-esp">{{ slot.especialidade_nome }}</p>
      </div>
      <span class="badge badge--{{ slot.status.toLowerCase() }}">{{ slot.status }}</span>
    </div>

    <mat-dialog-content>

      @if (slot.consulta; as c) {
        <!-- Paciente -->
        <section class="section">
          <h4 class="section-title"><mat-icon>person</mat-icon> Paciente</h4>
          <p class="info-row"><strong>Nome:</strong> {{ c.cliente_nome }}</p>
          @if (c.paciente_cpf_mascarado) {
            <p class="info-row"><strong>CPF:</strong> {{ c.paciente_cpf_mascarado }}</p>
          }
          <p class="info-row"><strong>Canal:</strong> {{ c.canal_origem }}</p>
          <p class="info-row">
            <strong>Urgência:</strong>
            <span class="badge badge--{{ c.urgencia.toLowerCase() }}">{{ c.urgencia }}</span>
          </p>
          @if (c.observacoes) {
            <p class="info-row"><strong>Observações:</strong> {{ c.observacoes }}</p>
          }
        </section>

        <!-- Triagem IA -->
        @if (triagemItens.length) {
          <mat-divider />
          <section class="section">
            <h4 class="section-title"><mat-icon>psychology</mat-icon> Triagem IA</h4>
            @for (item of triagemItens; track item.chave) {
              <p class="info-row">
                <strong>{{ item.chave }}:</strong> {{ item.valor }}
              </p>
            }
          </section>
        }
      } @else {
        <div class="disponivel-info">
          <mat-icon>event_available</mat-icon>
          <p>Slot disponível para agendamento.</p>
        </div>
      }

    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Fechar</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      padding: 20px 24px 0;
      border-top: 4px solid #2563eb;
    }
    h2[mat-dialog-title] { margin: 0 0 2px; font-size: 18px !important; }
    .dialog-esp { color: var(--color-text-secondary); font-size: 13px; margin: 0; }
    .section { padding: 16px 0 8px; }
    .section-title {
      display: flex; align-items: center; gap: 6px;
      font-size: 13px; font-weight: 600; color: var(--color-text-secondary);
      text-transform: uppercase; letter-spacing: .5px; margin: 0 0 10px;
      mat-icon { font-size: 16px; width: 16px; height: 16px; }
    }
    .info-row { margin: 4px 0; font-size: 14px; display: flex; gap: 6px; align-items: center; }
    .disponivel-info {
      display: flex; flex-direction: column; align-items: center;
      padding: 32px; color: var(--color-text-secondary);
      mat-icon { font-size: 48px; width: 48px; height: 48px; opacity: .3; margin-bottom: 8px; }
    }
    mat-dialog-actions { padding-bottom: 16px !important; }
  `],
})
export class SlotDetalheDialogComponent {
  readonly slot = inject<SlotAdmin>(MAT_DIALOG_DATA);

  get corUrgencia(): string {
    const mapa: Record<string, string> = {
      BAIXA: '#64748b', MEDIA: '#d97706', ALTA: '#ea580c', EMERGENCIA: '#dc2626',
    };
    return mapa[this.slot.consulta?.urgencia ?? ''] ?? '#2563eb';
  }

  get triagemItens(): { chave: string; valor: string }[] {
    const resumo = this.slot.consulta?.triagem_resumo;
    if (!resumo || typeof resumo !== 'object') return [];
    return Object.entries(resumo as Record<string, unknown>).map(([chave, valor]) => ({
      chave,
      valor: String(valor),
    }));
  }
}
