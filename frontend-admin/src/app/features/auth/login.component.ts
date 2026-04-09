import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { AuthAdminService } from '../../core/services/auth-admin.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule, MatProgressSpinnerModule,
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginComponent {
  private readonly auth = inject(AuthAdminService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);

  readonly form = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    senha: ['', [Validators.required, Validators.minLength(4)]],
  });

  readonly carregando = signal(false);
  readonly erro = signal('');
  readonly mostrarSenha = signal(false);

  async login(): Promise<void> {
    if (this.form.invalid) return;
    this.carregando.set(true);
    this.erro.set('');
    try {
      const { email, senha } = this.form.getRawValue();
      await this.auth.login(email!, senha!);
      if (this.auth.precisaSelecionarEstabelecimento()) {
        await this.router.navigate(['/selecionar-estabelecimento']);
      } else {
        await this.router.navigate(['/']);
      }
    } catch {
      this.erro.set('Email ou senha inválidos. Verifique suas credenciais.');
    } finally {
      this.carregando.set(false);
    }
  }
}
