/**
 * ConfirmDialogComponent — diálogo de confirmação genérico.
 *
 * Uso:
 *   const ref = this.dialog.open(ConfirmDialogComponent, {
 *     data: {
 *       titulo: 'Desativar médico',
 *       mensagem: 'Tem certeza? O médico não aparecerá mais na agenda.',
 *       confirmLabel: 'Desativar',
 *       confirmColor: 'warn',
 *     },
 *   });
 *   ref.afterClosed().subscribe(confirmado => { if (confirmado) { ... } });
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

export interface ConfirmDialogData {
  titulo: string;
  mensagem: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmColor?: 'primary' | 'accent' | 'warn';
}

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.titulo }}</h2>
    <mat-dialog-content>
      <p>{{ data.mensagem }}</p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button [mat-dialog-close]="false">
        {{ data.cancelLabel ?? 'Cancelar' }}
      </button>
      <button
        mat-raised-button
        [color]="data.confirmColor ?? 'warn'"
        [mat-dialog-close]="true">
        {{ data.confirmLabel ?? 'Confirmar' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content p {
      margin: 0;
      color: var(--color-text-secondary);
      font-size: 15px;
      line-height: 1.6;
    }
    mat-dialog-actions { padding-bottom: 16px !important; gap: 8px; }
  `],
})
export class ConfirmDialogComponent {
  readonly data = inject<ConfirmDialogData>(MAT_DIALOG_DATA);
  readonly dialogRef = inject(MatDialogRef<ConfirmDialogComponent>);
}
