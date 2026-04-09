import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';

import { AuthAdminService } from '../../core/services/auth-admin.service';
import { ApiService } from '../../core/services/api.service';
import { firstValueFrom } from 'rxjs';

export interface Estabelecimento {
  id: number;
  nome: string;
  slug: string;
  tipo: string;
  plano: string;
  ativo: boolean;
  cidade: string | null;
  estado: string | null;
  email: string | null;
  telefone: string | null;
  created_at: string;
}

const TIPO_ICON: Record<string, string> = {
  CLINICA:    'local_hospital',
  HOSPITAL:   'domain',
  LABORATORIO:'biotech',
  FARMACIA:   'medication',
  CONSULTORIO:'person',
  OUTRO:      'business',
};

const TIPO_LABEL: Record<string, string> = {
  CLINICA:    'Clínica',
  HOSPITAL:   'Hospital',
  LABORATORIO:'Laboratório',
  FARMACIA:   'Farmácia',
  CONSULTORIO:'Consultório',
  OUTRO:      'Outro',
};

@Component({
  selector: 'app-selecionar-estabelecimento',
  standalone: true,
  imports: [
    MatCardModule, MatButtonModule, MatIconModule,
    MatProgressSpinnerModule, MatTooltipModule,
  ],
  templateUrl: './selecionar-estabelecimento.component.html',
  styleUrl: './selecionar-estabelecimento.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SelecionarEstabelecimentoComponent implements OnInit {
  private readonly auth   = inject(AuthAdminService);
  private readonly api    = inject(ApiService);
  private readonly router = inject(Router);

  readonly estabelecimentos = signal<Estabelecimento[]>([]);
  readonly carregando       = signal(true);
  readonly selecionando     = signal<number | null>(null);
  readonly erro             = signal('');
  readonly usuario          = this.auth.usuario;

  async ngOnInit(): Promise<void> {
    try {
      const lista = await firstValueFrom(
        this.api.get<Estabelecimento[]>('/estabelecimentos/')
      );
      this.estabelecimentos.set(lista);
    } catch {
      this.erro.set('Erro ao carregar estabelecimentos. Verifique sua conexão.');
    } finally {
      this.carregando.set(false);
    }
  }

  async selecionar(id: number): Promise<void> {
    this.selecionando.set(id);
    this.erro.set('');
    try {
      await this.auth.selecionarEstabelecimento(id);
      await this.router.navigate(['/dashboard']);
    } catch {
      this.erro.set('Erro ao selecionar estabelecimento. Tente novamente.');
      this.selecionando.set(null);
    }
  }

  tipoIcon(tipo: string): string  { return TIPO_ICON[tipo]  ?? 'business'; }
  tipoLabel(tipo: string): string { return TIPO_LABEL[tipo] ?? tipo; }

  planoLabel(plano: string): string {
    return plano.charAt(0).toUpperCase() + plano.slice(1);
  }

  formatarLocalizacao(est: Estabelecimento): string {
    if (est.cidade && est.estado) return `${est.cidade} — ${est.estado}`;
    return est.cidade ?? est.estado ?? '—';
  }

  iniciais(): string {
    return (this.usuario()?.nome ?? 'A').charAt(0).toUpperCase();
  }

  async continuarComoSuperAdmin(): Promise<void> {
    try {
      await this.auth.voltarModoGlobal();
    } catch {
      // Se falhar (ex: token já global), só seta a flag
      this.auth.continuarComoSuperAdmin();
    }
    await this.router.navigate(['/dashboard']);
  }

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/login']);
  }
}
