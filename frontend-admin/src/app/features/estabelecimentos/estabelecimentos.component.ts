import {
  ChangeDetectionStrategy, Component, OnInit, inject, signal,
} from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { DatePipe, UpperCasePipe } from '@angular/common';
import { firstValueFrom } from 'rxjs';

import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';

import { ApiService } from '../../core/services/api.service';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';

interface Estabelecimento {
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
  timezone: string;
  created_at: string;
}

/** Fusos do Brasil, um por deslocamento em relação a Brasília. */
export const FUSOS_BRASIL = [
  { valor: 'America/Sao_Paulo',  rotulo: 'Horário de Brasília' },
  { valor: 'America/Manaus',     rotulo: 'Amazonas, Roraima e Rondônia (1h a menos)' },
  { valor: 'America/Cuiaba',     rotulo: 'Mato Grosso e Mato Grosso do Sul (1h a menos)' },
  { valor: 'America/Rio_Branco', rotulo: 'Acre (2h a menos)' },
  { valor: 'America/Noronha',    rotulo: 'Fernando de Noronha (1h a mais)' },
] as const;

/** Campos que só existem na criação: na edição ficam ocultos e não podem invalidar o formulário. */
const CAMPOS_SO_NA_CRIACAO = [
  'cnpj', 'slug', 'tipo', 'cep', 'endereco',
  'responsavel_nome', 'responsavel_cpf', 'responsavel_email', 'responsavel_telefone', 'responsavel_cargo',
] as const;

@Component({
  selector: 'app-estabelecimentos',
  standalone: true,
  imports: [
    DatePipe, UpperCasePipe, ReactiveFormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatProgressSpinnerModule, MatTooltipModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './estabelecimentos.component.html',
  styleUrl: './estabelecimentos.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EstabelecimentosComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly dialog = inject(MatDialog);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly estabelecimentos = signal<Estabelecimento[]>([]);
  readonly carregando = signal(false);
  readonly mostrarForm = signal(false);
  readonly editando = signal<Estabelecimento | null>(null);

  readonly colunas = ['nome', 'tipo', 'plano', 'localizacao', 'status', 'criado', 'acoes'];

  readonly form = this.fb.group({
    nome:     ['', Validators.required],
    cnpj:     ['', Validators.required],
    slug:     ['', Validators.required],
    tipo:     ['CLINICA', Validators.required],
    plano:    ['basico', Validators.required],
    email:    ['', Validators.email],
    telefone: [''],
    cidade:   [''],
    estado:   [''],
    timezone: ['America/Sao_Paulo', Validators.required],
    cep:      [''],
    endereco: [''],
    responsavel_nome:     ['', Validators.required],
    responsavel_cpf:      ['', Validators.required],
    responsavel_email:    ['', [Validators.required, Validators.email]],
    responsavel_telefone: [''],
    responsavel_cargo:    [''],
  });

  readonly fusos = FUSOS_BRASIL;

  async ngOnInit(): Promise<void> {
    await this.carregar();
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    try {
      const lista = await firstValueFrom(this.api.get<Estabelecimento[]>('/estabelecimentos/'));
      this.estabelecimentos.set(lista);
    } finally {
      this.carregando.set(false);
    }
  }

  abrirNovo(): void {
    this.editando.set(null);
    for (const campo of CAMPOS_SO_NA_CRIACAO) this.form.controls[campo].enable();
    this.form.reset({ tipo: 'CLINICA', plano: 'basico', timezone: 'America/Sao_Paulo' });
    this.mostrarForm.set(true);
  }

  abrirEditar(est: Estabelecimento): void {
    this.editando.set(est);
    for (const campo of CAMPOS_SO_NA_CRIACAO) this.form.controls[campo].disable();
    this.form.patchValue({
      nome:     est.nome,
      slug:     est.slug,
      timezone: est.timezone ?? 'America/Sao_Paulo',
      tipo:     est.tipo,
      plano:    est.plano,
      email:    est.email ?? '',
      telefone: est.telefone ?? '',
      cidade:   est.cidade ?? '',
      estado:   est.estado ?? '',
    });
    this.mostrarForm.set(true);
  }

  fecharForm(): void {
    this.mostrarForm.set(false);
  }

  async salvar(): Promise<void> {
    if (this.form.invalid) return;
    try {
      const ed = this.editando();
      // Na edição vão só os campos habilitados e preenchidos; na criação, o formulário inteiro
      const dados = ed
        ? Object.fromEntries(Object.entries(this.form.value).filter(([, v]) => v !== '' && v != null))
        : this.form.getRawValue();
      if (ed) {
        const atualizado = await firstValueFrom(
          this.api.patch<Estabelecimento>(`/estabelecimentos/${ed.id}`, dados),
        );
        this.estabelecimentos.update((l) =>
          l.map((e) => (e.id === ed.id ? atualizado : e)),
        );
        this.toast.sucesso('Estabelecimento atualizado!');
      } else {
        const novo = await firstValueFrom(
          this.api.post<Estabelecimento>('/estabelecimentos/', dados),
        );
        this.estabelecimentos.update((l) => [...l, novo]);
        this.toast.sucesso('Estabelecimento criado!');
      }
      this.mostrarForm.set(false);
    } catch {
      this.toast.erro('Erro ao salvar estabelecimento. Verifique os campos.');
    }
  }

  confirmarDesativar(est: Estabelecimento): void {
    const ref = this.dialog.open(ConfirmDialogComponent, {
      data: {
        titulo: 'Desativar estabelecimento',
        mensagem: `Desativar "${est.nome}"? O acesso ao painel será bloqueado.`,
        confirmLabel: 'Desativar',
        confirmColor: 'warn',
      },
    });
    ref.afterClosed().subscribe(async (ok) => {
      if (!ok) return;
      try {
        await firstValueFrom(this.api.delete(`/estabelecimentos/${est.id}`));
        this.estabelecimentos.update((l) =>
          l.map((e) => (e.id === est.id ? { ...e, ativo: false } : e)),
        );
        this.toast.sucesso('Estabelecimento desativado.');
      } catch {
        this.toast.erro('Erro ao desativar.');
      }
    });
  }
}
