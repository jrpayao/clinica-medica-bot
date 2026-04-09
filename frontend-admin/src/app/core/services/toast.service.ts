/**
 * ToastService — centralizador de notificações.
 *
 * Uso:
 *   toast.sucesso('Médico salvo com sucesso!');
 *   toast.erro('Falha ao salvar. Tente novamente.');
 *   toast.aviso('Limite de médicos atingido.');
 */
import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable({ providedIn: 'root' })
export class ToastService {
  private readonly snack = inject(MatSnackBar);

  sucesso(mensagem: string, duracao = 4000): void {
    this.snack.open(mensagem, 'Fechar', {
      duration: duracao,
      panelClass: ['snack-success'],
      horizontalPosition: 'end',
      verticalPosition: 'top',
    });
  }

  erro(mensagem: string, duracao = 5000): void {
    this.snack.open(mensagem, 'Fechar', {
      duration: duracao,
      panelClass: ['snack-erro'],
      horizontalPosition: 'end',
      verticalPosition: 'top',
    });
  }

  aviso(mensagem: string, duracao = 5000): void {
    this.snack.open(mensagem, 'Fechar', {
      duration: duracao,
      panelClass: ['snack-aviso'],
      horizontalPosition: 'end',
      verticalPosition: 'top',
    });
  }
}
