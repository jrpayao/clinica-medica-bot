import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './auth.component.html',
  styleUrls: ['./auth.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AuthComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  // Modo: paciente (CPF+SMS) ou equipe (email+senha)
  readonly modo = signal<'paciente' | 'equipe'>('paciente');

  // Fluxo paciente
  readonly etapa = signal<'cpf' | 'codigo'>('cpf');
  readonly cpf = signal('');
  readonly codigo = signal('');
  readonly devCodigo = signal(''); // mostrado em dev

  // Fluxo equipe
  readonly email = signal('');
  readonly senha = signal('');

  readonly carregando = signal(false);
  readonly erro = signal('');

  // ── CPF helpers ──────────────────────────────────────────────────────────
  get cpfNumerosOnly(): string {
    return this.cpf().replace(/\D/g, '');
  }

  onCpfInput(event: Event): void {
    this.formatarCpf((event.target as HTMLInputElement).value);
  }

  onCodigoInput(event: Event): void {
    this.codigo.set((event.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 6));
  }

  onEmailInput(event: Event): void {
    this.email.set((event.target as HTMLInputElement).value);
  }

  onSenhaInput(event: Event): void {
    this.senha.set((event.target as HTMLInputElement).value);
  }

  formatarCpf(valor: string): void {
    const nums = valor.replace(/\D/g, '').slice(0, 11);
    let fmt = nums;
    if (nums.length > 9) fmt = `${nums.slice(0, 3)}.${nums.slice(3, 6)}.${nums.slice(6, 9)}-${nums.slice(9)}`;
    else if (nums.length > 6) fmt = `${nums.slice(0, 3)}.${nums.slice(3, 6)}.${nums.slice(6)}`;
    else if (nums.length > 3) fmt = `${nums.slice(0, 3)}.${nums.slice(3)}`;
    this.cpf.set(fmt);
  }

  // ── Paciente: solicitar SMS ───────────────────────────────────────────────
  async solicitarSms(): Promise<void> {
    this.carregando.set(true);
    this.erro.set('');
    try {
      const res = await this.auth.solicitarSms(this.cpfNumerosOnly);
      this.devCodigo.set(res.dev_codigo ?? '');
      this.etapa.set('codigo');
    } catch {
      this.erro.set('CPF não encontrado ou erro ao enviar código. Verifique e tente novamente.');
    } finally {
      this.carregando.set(false);
    }
  }

  async verificarCodigo(): Promise<void> {
    this.carregando.set(true);
    this.erro.set('');
    try {
      await this.auth.verificarSms(this.cpfNumerosOnly, this.codigo());
      await this.router.navigate(['/chat']);
    } catch {
      this.erro.set('Código inválido ou expirado. Tente novamente.');
    } finally {
      this.carregando.set(false);
    }
  }

  // ── Equipe: login com email e senha ───────────────────────────────────────
  async loginEquipe(): Promise<void> {
    this.carregando.set(true);
    this.erro.set('');
    try {
      await this.auth.loginInterno(this.email(), this.senha());
      await this.router.navigate(['/chat']);
    } catch {
      this.erro.set('E-mail ou senha incorretos.');
    } finally {
      this.carregando.set(false);
    }
  }

  trocarModo(novo: 'paciente' | 'equipe'): void {
    this.modo.set(novo);
    this.etapa.set('cpf');
    this.erro.set('');
  }
}
