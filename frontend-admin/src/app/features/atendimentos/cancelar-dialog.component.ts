import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatRadioModule } from '@angular/material/radio';

export type OrigemCancelamento = 'PACIENTE' | 'MEDICO' | 'ESTABELECIMENTO';

export interface CancelarDialogData {
  clienteNome: string;
  rotuloCliente: string;
  rotuloProfissional: string;
}

export interface CancelarDialogResultado {
  origem: OrigemCancelamento;
  motivo: string;
}

/** Texto gravado quando quem cancela não escreve um motivo. */
export const MOTIVO_PADRAO: Record<OrigemCancelamento, string> = {
  PACIENTE: 'Cancelado a pedido do cliente',
  MEDICO: 'Profissional indisponível',
  ESTABELECIMENTO: 'Cancelado pela unidade',
};

/** Pergunta quem pediu o cancelamento: é isso que decide se o cliente recebe novos horários. */
@Component({
  selector: 'app-cancelar-dialog',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatRadioModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Cancelar o horário de {{ data.clienteNome }}</h2>
    <mat-dialog-content>
      <p class="pergunta" id="origem-rotulo">Quem pediu o cancelamento?</p>
      <mat-radio-group aria-labelledby="origem-rotulo" [ngModel]="origem()" (ngModelChange)="origem.set($event)">
        <mat-radio-button value="PACIENTE">O próprio {{ data.rotuloCliente.toLowerCase() }}</mat-radio-button>
        <mat-radio-button value="MEDICO">O {{ data.rotuloProfissional.toLowerCase() }} não poderá atender</mat-radio-button>
        <mat-radio-button value="ESTABELECIMENTO">A unidade</mat-radio-button>
      </mat-radio-group>

      <p class="efeito">{{ efeito() }}</p>

      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Motivo (opcional)</mat-label>
        <input matInput maxlength="500" [ngModel]="motivo()" (ngModelChange)="motivo.set($event)" />
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button [mat-dialog-close]="null">Voltar</button>
      <button mat-raised-button color="warn" [disabled]="!origem()" (click)="confirmar()">Cancelar horário</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .pergunta { margin: 0 0 4px; font-size: 14px; font-weight: 600; color: var(--color-text); }
    mat-radio-group { display: flex; flex-direction: column; }
    .efeito { margin: 8px 0 16px; min-height: 40px; font-size: 13px; line-height: 1.5; color: var(--color-text-secondary); }
    mat-form-field { width: 100%; }
    mat-dialog-actions { padding-bottom: 16px !important; gap: 8px; }
  `],
})
export class CancelarDialogComponent {
  readonly data = inject<CancelarDialogData>(MAT_DIALOG_DATA);
  private readonly ref = inject<MatDialogRef<CancelarDialogComponent, CancelarDialogResultado | null>>(MatDialogRef);

  readonly origem = signal<OrigemCancelamento | null>(null);
  readonly motivo = signal('');

  readonly efeito = computed(() => {
    switch (this.origem()) {
      case 'PACIENTE': return 'O horário volta para a agenda. Nenhuma mensagem é enviada.';
      case 'MEDICO': return 'O horário fica bloqueado e a pessoa recebe por WhatsApp até três novos horários para escolher.';
      case 'ESTABELECIMENTO': return 'O horário volta para a agenda e a pessoa recebe por WhatsApp até três novos horários para escolher.';
      default: return '';
    }
  });

  confirmar(): void {
    const origem = this.origem();
    if (!origem) return;
    const motivo = this.motivo().trim();
    this.ref.close({ origem, motivo: motivo.length >= 3 ? motivo : MOTIVO_PADRAO[origem] });
  }
}
