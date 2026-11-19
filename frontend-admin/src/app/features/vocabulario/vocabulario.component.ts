import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormControl, FormGroup } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../../core/services/api.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { ToastService } from '../../core/services/toast.service';
import { Vocabulario, VocabularioService } from '../../core/services/vocabulario.service';


@Component({
  selector: 'app-vocabulario',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatProgressSpinnerModule,
    PageHeaderComponent,
  ],
  templateUrl: './vocabulario.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VocabularioComponent implements OnInit {
  private api   = inject(ApiService);
  private toast = inject(ToastService);
  private vocab = inject(VocabularioService);

  readonly loading = signal(false);
  readonly salvando = signal(false);

  readonly form = new FormGroup({
    label_profissional:  new FormControl(''),
    label_atendimento:   new FormControl(''),
    label_cliente:       new FormControl(''),
    label_especialidade: new FormControl(''),
  });

  ngOnInit(): void {
    this.carregar();
  }

  async carregar(): Promise<void> {
    this.loading.set(true);
    try {
      const vocab = await firstValueFrom(this.api.get<Vocabulario>('/estabelecimentos/meu/vocabulario'));
      this.form.patchValue(vocab);
    } finally {
      this.loading.set(false);
    }
  }

  async salvar(): Promise<void> {
    this.salvando.set(true);
    try {
      const salvo = await firstValueFrom(
        this.api.patch<Vocabulario>('/estabelecimentos/meu/vocabulario', this.form.value),
      );
      this.vocab.definir(salvo);
      this.toast.sucesso('Vocabulário atualizado');
    } catch {
      this.toast.erro('Erro ao salvar');
    } finally {
      this.salvando.set(false);
    }
  }
}
