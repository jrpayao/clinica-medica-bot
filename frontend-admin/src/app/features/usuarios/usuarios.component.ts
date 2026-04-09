import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
  computed,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatCardModule } from '@angular/material/card';
import { firstValueFrom } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { AuthAdminService } from '../../core/services/auth-admin.service';

interface UsuarioInterno {
  id: number;
  nome: string;
  email: string;
  role: string;
  ativo: boolean;
}

@Component({
  selector: 'app-usuarios',
  standalone: true,
  imports: [
    FormsModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTooltipModule,
    MatCardModule,
  ],
  templateUrl: './usuarios.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UsuariosComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthAdminService);

  readonly usuarios = signal<UsuarioInterno[]>([]);
  readonly loading = signal(false);
  readonly isGlobal = computed(() => this.auth.usuario()?.role === 'ADMIN_GLOBAL');

  readonly novoNome = signal('');
  readonly novoEmail = signal('');
  readonly novaSenha = signal('');
  readonly novoRole = signal('RECEPCIONISTA');
  readonly criando = signal(false);
  readonly erroForm = signal<string | null>(null);

  readonly colunas = ['nome', 'email', 'role', 'ativo', 'acoes'];

  async ngOnInit(): Promise<void> {
    await this._carregar();
  }

  private async _carregar(): Promise<void> {
    this.loading.set(true);
    try {
      const data = await firstValueFrom(this.api.get<UsuarioInterno[]>('/admin/usuarios'));
      this.usuarios.set(data);
    } finally {
      this.loading.set(false);
    }
  }

  async criarUsuario(): Promise<void> {
    this.erroForm.set(null);
    this.criando.set(true);
    try {
      await firstValueFrom(
        this.api.post('/admin/usuarios', {
          nome: this.novoNome(),
          email: this.novoEmail(),
          senha: this.novaSenha(),
          role: this.novoRole(),
        }),
      );
      this.novoNome.set('');
      this.novoEmail.set('');
      this.novaSenha.set('');
      this.novoRole.set('RECEPCIONISTA');
      await this._carregar();
    } catch {
      this.erroForm.set('Erro ao criar usuário. Verifique os dados.');
    } finally {
      this.criando.set(false);
    }
  }

  async desativar(id: number): Promise<void> {
    await firstValueFrom(this.api.patch(`/admin/usuarios/${id}`, { ativo: false }));
    await this._carregar();
  }

  async reativar(id: number): Promise<void> {
    await firstValueFrom(this.api.patch(`/admin/usuarios/${id}`, { ativo: true }));
    await this._carregar();
  }
}
