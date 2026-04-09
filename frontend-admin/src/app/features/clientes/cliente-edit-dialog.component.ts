import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';

interface Paciente {
  id: number; nome: string; cpf: string; telefone: string | null;
  email: string | null; convenio: string | null; numero_carteirinha: string | null;
}

@Component({
  selector: 'app-cliente-edit-dialog',
  standalone: true,
  imports: [ReactiveFormsModule, MatDialogModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>Editar Paciente</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline">
          <mat-label>Nome</mat-label>
          <input matInput formControlName="nome" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>CPF (mascarado)</mat-label>
          <input matInput [value]="data.cpf" disabled />
          <mat-hint>CPF não pode ser alterado</mat-hint>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Telefone</mat-label>
          <input matInput formControlName="telefone" type="tel" />
          <mat-icon matPrefix>phone</mat-icon>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>E-mail</mat-label>
          <input matInput formControlName="email" type="email" />
          <mat-icon matPrefix>email</mat-icon>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Convênio</mat-label>
          <input matInput formControlName="convenio" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Nº Carteirinha</mat-label>
          <input matInput formControlName="numero_carteirinha" />
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button [mat-dialog-close]="null">Cancelar</button>
      <button mat-raised-button color="primary" (click)="salvar()">
        <mat-icon>save</mat-icon> Salvar
      </button>
    </mat-dialog-actions>
  `,
  styles: [`.dialog-form { display: flex; flex-direction: column; gap: 4px; min-width: 380px; padding-top: 8px; }
            mat-dialog-actions { padding-bottom: 16px !important; gap: 8px; }`],
})
export class ClienteEditDialogComponent {
  readonly data = inject<Paciente>(MAT_DIALOG_DATA);
  readonly dialogRef = inject(MatDialogRef<ClienteEditDialogComponent>);
  private readonly fb = inject(FormBuilder);

  readonly form = this.fb.group({
    nome:               [this.data.nome],
    telefone:           [this.data.telefone ?? ''],
    email:              [this.data.email ?? ''],
    convenio:           [this.data.convenio ?? ''],
    numero_carteirinha: [this.data.numero_carteirinha ?? ''],
  });

  salvar(): void {
    const v = this.form.getRawValue();
    this.dialogRef.close({
      nome:               v.nome || undefined,
      telefone:           v.telefone || undefined,
      email:              v.email || undefined,
      convenio:           v.convenio || undefined,
      numero_carteirinha: v.numero_carteirinha || undefined,
    });
  }
}
