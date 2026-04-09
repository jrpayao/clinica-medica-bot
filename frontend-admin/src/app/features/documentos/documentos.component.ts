import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { ApiService } from '../../core/services/api.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';

interface RagHealth {
  status: string;
  vectors_count?: number;
  collection?: string;
}

interface IndexResult {
  documento_id: string;
  titulo: string;
  chunks_indexados: number;
}

@Component({
  selector: 'app-documentos',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    PageHeaderComponent,
  ],
  templateUrl: './documentos.component.html',
  styleUrl: './documentos.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DocumentosComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  readonly health = signal<RagHealth | null>(null);
  readonly indexando = signal(false);
  readonly ultimoResultado = signal<IndexResult | null>(null);

  readonly form = this.fb.group({
    titulo:       ['', Validators.required],
    documento_id: ['', Validators.required],
    texto:        ['', [Validators.required, Validators.minLength(50)]],
  });

  async ngOnInit(): Promise<void> {
    try {
      const h = await firstValueFrom(this.api.get<RagHealth>('/rag/health'));
      this.health.set(h);
    } catch {
      this.health.set({ status: 'error' });
    }
  }

  async indexar(): Promise<void> {
    if (this.form.invalid) return;
    this.indexando.set(true);
    this.ultimoResultado.set(null);
    try {
      const dados = this.form.getRawValue();
      const resultado = await firstValueFrom(
        this.api.post<IndexResult>('/rag/documentos', {
          titulo:       dados.titulo,
          documento_id: dados.documento_id,
          texto:        dados.texto,
        }),
      );
      this.ultimoResultado.set(resultado);
      this.form.reset();
      this.toast.sucesso(`Documento indexado! ${resultado.chunks_indexados} chunks criados.`);
    } catch {
      this.toast.erro('Erro ao indexar documento. Verifique o Qdrant.');
    } finally {
      this.indexando.set(false);
    }
  }
}
