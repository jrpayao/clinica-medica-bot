import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormControl, FormGroup, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { firstValueFrom } from 'rxjs';

import { CatalogoService, TipoAtendimento } from './catalogo.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ToastService } from '../../core/services/toast.service';

@Component({
  selector: 'app-catalogo',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule, MatTableModule,
    MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    PageHeaderComponent, EmptyStateComponent,
  ],
  templateUrl: './catalogo.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogoComponent implements OnInit {
  private svc   = inject(CatalogoService);
  private toast = inject(ToastService);

  readonly tipos   = signal<TipoAtendimento[]>([]);
  readonly loading = signal(false);
  readonly colunas = ['nome', 'duracao_min', 'preco', 'ativo', 'acoes'];

  readonly form = new FormGroup({
    nome:        new FormControl('', [Validators.required]),
    descricao:   new FormControl(''),
    duracao_min: new FormControl(30, [Validators.required, Validators.min(5)]),
    preco:       new FormControl<number | null>(null),
  });

  ngOnInit(): void {
    this.carregar();
  }

  async carregar(): Promise<void> {
    this.loading.set(true);
    try {
      const lista = await firstValueFrom(this.svc.listar());
      this.tipos.set(lista ?? []);
    } finally {
      this.loading.set(false);
    }
  }

  async salvar(): Promise<void> {
    if (this.form.invalid) return;
    try {
      await firstValueFrom(this.svc.criar(this.form.value as Partial<TipoAtendimento>));
      this.toast.sucesso('Serviço criado');
      this.form.reset({ duracao_min: 30 });
      await this.carregar();
    } catch {
      this.toast.erro('Erro ao criar serviço');
    }
  }

  async toggle(tipo: TipoAtendimento): Promise<void> {
    try {
      await firstValueFrom(this.svc.atualizar(tipo.id, { ativo: !tipo.ativo }));
      await this.carregar();
    } catch {
      this.toast.erro('Erro ao atualizar');
    }
  }
}
