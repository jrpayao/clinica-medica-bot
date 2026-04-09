/**
 * ProfissionalDialogComponent — formulário de criação/edição de médico.
 * Aberto via MatDialog. Retorna os dados ao fechar com "Salvar".
 */
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';

import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { Medico, Especialidade } from './profissionais.service';

export interface ProfissionalDialogData {
  medico: Medico | null;
  especialidades: Especialidade[];
}

@Component({
  selector: 'app-profissional-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatDialogModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h2 mat-dialog-title>{{ data.medico ? 'Editar Médico' : 'Novo Médico' }}</h2>

    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">

        <!-- Nome -->
        <mat-form-field appearance="outline">
          <mat-label>Nome completo *</mat-label>
          <input matInput formControlName="nome" placeholder="Dr. João Silva" />
          @if (form.controls.nome.hasError('required') && form.controls.nome.touched) {
            <mat-error>Nome é obrigatório.</mat-error>
          }
        </mat-form-field>

        <!-- CRM (apenas criação) -->
        @if (!data.medico) {
          <mat-form-field appearance="outline">
            <mat-label>CRM *</mat-label>
            <input matInput formControlName="crm" placeholder="123456" />
            <mat-hint>Somente números, sem estado</mat-hint>
            @if (form.controls.crm.hasError('required') && form.controls.crm.touched) {
              <mat-error>CRM é obrigatório.</mat-error>
            }
          </mat-form-field>

          <!-- Especialidade (apenas criação) -->
          <mat-form-field appearance="outline">
            <mat-label>Especialidade *</mat-label>
            <mat-select formControlName="especialidade_id">
              @for (esp of data.especialidades; track esp.id) {
                <mat-option [value]="esp.id">{{ esp.nome }}</mat-option>
              }
            </mat-select>
            @if (form.controls.especialidade_id.hasError('required') && form.controls.especialidade_id.touched) {
              <mat-error>Selecione uma especialidade.</mat-error>
            }
          </mat-form-field>
        }

        <!-- E-mail -->
        <mat-form-field appearance="outline">
          <mat-label>E-mail</mat-label>
          <input matInput type="email" formControlName="email" placeholder="medico@clinica.com" />
          <mat-icon matPrefix>email</mat-icon>
          @if (form.controls.email.hasError('email') && form.controls.email.touched) {
            <mat-error>Informe um e-mail válido.</mat-error>
          }
        </mat-form-field>

        <!-- Telefone -->
        <mat-form-field appearance="outline">
          <mat-label>Telefone</mat-label>
          <input matInput type="tel" formControlName="telefone" placeholder="(11) 9 9999-9999" />
          <mat-icon matPrefix>phone</mat-icon>
        </mat-form-field>

        <!-- Duração -->
        <mat-form-field appearance="outline">
          <mat-label>Duração da consulta (minutos)</mat-label>
          <input matInput type="number" formControlName="duracao_consulta_min" min="10" max="120" />
          <mat-hint>Entre 10 e 120 minutos</mat-hint>
        </mat-form-field>

      </form>
    </mat-dialog-content>

    <mat-dialog-actions align="end">
      <button mat-button [mat-dialog-close]="null">Cancelar</button>
      <button
        mat-raised-button
        color="primary"
        [disabled]="form.invalid"
        (click)="salvar()">
        <mat-icon>save</mat-icon>
        Salvar
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-form {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 420px;
      padding-top: 8px;
    }
    @media (max-width: 480px) {
      .dialog-form { min-width: unset; }
    }
    mat-dialog-actions { padding-bottom: 16px !important; gap: 8px; }
  `],
})
export class ProfissionalDialogComponent {
  readonly data = inject<ProfissionalDialogData>(MAT_DIALOG_DATA);
  readonly dialogRef = inject(MatDialogRef<ProfissionalDialogComponent>);
  private readonly fb = inject(FormBuilder);

  readonly form = this.fb.group({
    nome:                 [this.data.medico?.nome ?? '', Validators.required],
    crm:                  [this.data.medico?.crm ?? '', this.data.medico ? [] : [Validators.required]],
    especialidade_id:     [this.data.medico?.especialidade_id ?? null, this.data.medico ? [] : [Validators.required]],
    email:                [this.data.medico?.email ?? '', Validators.email],
    telefone:             [this.data.medico?.telefone ?? ''],
    duracao_consulta_min: [this.data.medico?.duracao_consulta_min ?? 30, [Validators.min(10), Validators.max(120)]],
  });

  salvar(): void {
    if (this.form.invalid) return;
    this.dialogRef.close(this.form.getRawValue());
  }
}
