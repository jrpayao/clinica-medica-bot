import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { VocabularioService } from '../../core/services/vocabulario.service';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import {
  EntradaFila, RemarcacaoPendente, ROTULO_PENDENCIA, ROTULO_STATUS_FILA, buscarClientes, semComoAvisar,
  tempoDeEspera,
} from './fila-espera.model';

interface ClienteOpcao { id: number; nome: string; telefone: string | null; }
interface EspecialidadeOpcao { id: number; nome: string; }

/** Lista de espera da unidade e remarcações (canceladas pela unidade) que ainda pedem contato. */
@Component({
  selector: 'app-fila-espera',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule, MatFormFieldModule, MatIconModule, MatInputModule, MatProgressSpinnerModule,
    MatSelectModule, MatTooltipModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './fila-espera.component.html',
  styleUrl: './fila-espera.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FilaEsperaComponent implements OnInit {
  readonly vocab = inject(VocabularioService);
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly dialog = inject(MatDialog);

  readonly fila = signal<EntradaFila[]>([]);
  readonly pendencias = signal<RemarcacaoPendente[]>([]);
  readonly carregando = signal(true);
  readonly falhou = signal(false);

  // Formulário de inclusão
  readonly incluindo = signal(false);
  readonly salvando = signal(false);
  readonly clientes = signal<ClienteOpcao[]>([]);
  readonly especialidades = signal<EspecialidadeOpcao[]>([]);
  readonly busca = signal('');
  readonly clienteEscolhido = signal<ClienteOpcao | null>(null);
  readonly especialidadeId = signal<number | null>(null);
  readonly sugestoes = computed(() =>
    this.clienteEscolhido() ? [] : buscarClientes(this.clientes(), this.busca()),
  );

  readonly rotuloStatus = ROTULO_STATUS_FILA;
  readonly rotuloPendencia = ROTULO_PENDENCIA;
  readonly espera = tempoDeEspera;
  readonly semComoAvisar = semComoAvisar;

  ngOnInit(): void {
    void this.carregar();
  }

  async carregar(): Promise<void> {
    this.carregando.set(true);
    try {
      const [fila, pendencias] = await Promise.all([
        firstValueFrom(this.api.get<EntradaFila[]>('/fila-espera')),
        firstValueFrom(this.api.get<RemarcacaoPendente[]>('/reagendamentos/pendencias')),
      ]);
      this.fila.set(fila);
      this.pendencias.set(pendencias);
      this.falhou.set(false);
    } catch {
      this.falhou.set(true);
    } finally {
      this.carregando.set(false);
    }
  }

  async abrirInclusao(): Promise<void> {
    this.incluindo.set(true);
    this.busca.set('');
    this.clienteEscolhido.set(null);
    this.especialidadeId.set(null);
    if (this.clientes().length) return;
    try {
      const [clientes, especialidades] = await Promise.all([
        firstValueFrom(this.api.get<ClienteOpcao[]>('/clientes/')),
        firstValueFrom(this.api.get<EspecialidadeOpcao[]>('/especialidades/')),
      ]);
      this.clientes.set(clientes);
      this.especialidades.set(especialidades);
    } catch {
      this.toast.erro('Não foi possível carregar os cadastros. Tente de novo.');
      this.incluindo.set(false);
    }
  }

  escolherCliente(cliente: ClienteOpcao): void {
    this.clienteEscolhido.set(cliente);
    this.busca.set(cliente.nome);
  }

  mudarBusca(texto: string): void {
    this.busca.set(texto);
    if (this.clienteEscolhido()?.nome !== texto) this.clienteEscolhido.set(null);
  }

  async incluir(): Promise<void> {
    const cliente = this.clienteEscolhido();
    if (!cliente) return;
    this.salvando.set(true);
    try {
      await firstValueFrom(
        this.api.post('/fila-espera', { cliente_id: cliente.id, especialidade_id: this.especialidadeId() }),
      );
      this.toast.sucesso(`${cliente.nome} está na lista de espera.`);
      this.incluindo.set(false);
      await this.carregar();
    } catch (e: unknown) {
      this.toast.erro((e as { error?: { detail?: string } })?.error?.detail ?? 'Não foi possível incluir na lista.');
    } finally {
      this.salvando.set(false);
    }
  }

  remover(entrada: EntradaFila): void {
    const ref = this.dialog.open(ConfirmDialogComponent, {
      data: {
        titulo: 'Tirar da lista de espera',
        mensagem: entrada.status === 'NOTIFICADO'
          ? `${entrada.cliente_nome} recebeu a oferta de um horário e ainda pode responder. Ao tirar da lista, esse horário volta para a agenda.`
          : `${entrada.cliente_nome} deixará de ser avisado quando abrir um horário.`,
        confirmLabel: 'Tirar da lista',
        cancelLabel: 'Manter',
        confirmColor: 'warn',
      },
    });
    ref.afterClosed().subscribe(async (ok) => {
      if (!ok) return;
      try {
        await firstValueFrom(this.api.delete(`/fila-espera/${entrada.id}`));
        this.fila.update((lista) => lista.filter((e) => e.id !== entrada.id));
        this.toast.sucesso(`${entrada.cliente_nome} saiu da lista de espera.`);
      } catch {
        this.toast.erro('Não foi possível tirar da lista. Atualize e tente de novo.');
      }
    });
  }

  async resolver(p: RemarcacaoPendente): Promise<void> {
    try {
      await firstValueFrom(this.api.post(`/reagendamentos/${p.id}/resolver`, {}));
      this.pendencias.update((lista) => lista.filter((x) => x.id !== p.id));
      this.toast.sucesso(`Remarcação de ${p.cliente_nome} marcada como resolvida.`);
    } catch {
      this.toast.erro('Não foi possível concluir. Atualize e tente de novo.');
    }
  }
}
