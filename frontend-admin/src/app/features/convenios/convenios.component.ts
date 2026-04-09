import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormControl, FormGroup, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatExpansionModule } from '@angular/material/expansion';
import { firstValueFrom } from 'rxjs';

import { ConveniosService, Convenio, ConvenioPlano } from './convenios.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ToastService } from '../../core/services/toast.service';

@Component({
  selector: 'app-convenios',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    MatExpansionModule,
    PageHeaderComponent, EmptyStateComponent,
  ],
  templateUrl: './convenios.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConveniosComponent implements OnInit {
  private svc   = inject(ConveniosService);
  private toast = inject(ToastService);

  readonly convenios = signal<Convenio[]>([]);
  readonly planos    = signal<Record<number, ConvenioPlano[]>>({});
  readonly loading   = signal(false);

  readonly form = new FormGroup({
    nome:                 new FormControl('', [Validators.required]),
    codigo_ans:           new FormControl(''),
    cnpj:                 new FormControl(''),
    telefone_autorizacao: new FormControl(''),
    email:                new FormControl(''),
    website:              new FormControl(''),
  });

  readonly formPlano = new FormGroup({
    nome: new FormControl('', [Validators.required]),
  });

  ngOnInit(): void {
    this.carregar();
  }

  async carregar(): Promise<void> {
    this.loading.set(true);
    try {
      const lista = await firstValueFrom(this.svc.listar());
      this.convenios.set(lista ?? []);
    } finally {
      this.loading.set(false);
    }
  }

  async carregarPlanos(convenioId: number): Promise<void> {
    const lista = await firstValueFrom(this.svc.listarPlanos(convenioId));
    this.planos.update(p => ({ ...p, [convenioId]: lista ?? [] }));
  }

  async salvarConvenio(): Promise<void> {
    if (this.form.invalid) return;
    try {
      await firstValueFrom(this.svc.criar(this.form.value as Partial<Convenio>));
      this.toast.sucesso('Convênio criado');
      this.form.reset();
      await this.carregar();
    } catch {
      this.toast.erro('Erro ao criar convênio.');
    }
  }

  async salvarPlano(convenioId: number): Promise<void> {
    if (this.formPlano.invalid) return;
    try {
      await firstValueFrom(this.svc.criarPlano(convenioId, { nome: this.formPlano.value.nome! }));
      this.toast.sucesso('Plano criado');
      this.formPlano.reset();
      await this.carregarPlanos(convenioId);
    } catch {
      this.toast.erro('Erro ao criar plano.');
    }
  }

  async toggleConvenio(convenio: Convenio): Promise<void> {
    try {
      await firstValueFrom(this.svc.atualizar(convenio.id, { ativo: !convenio.ativo }));
      await this.carregar();
    } catch {
      this.toast.erro('Erro ao atualizar convênio.');
    }
  }

  async togglePlano(convenioId: number, plano: ConvenioPlano): Promise<void> {
    try {
      await firstValueFrom(this.svc.atualizarPlano(convenioId, plano.id, { ativo: !plano.ativo }));
      await this.carregarPlanos(convenioId);
    } catch {
      this.toast.erro('Erro ao atualizar plano.');
    }
  }
}
