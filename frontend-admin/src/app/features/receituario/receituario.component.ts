import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeUrl } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';

import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';

import { ApiService } from '../../core/services/api.service';
import { ToastService } from '../../core/services/toast.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { PapelTimbrado, TAMANHO_RODAPE, erroDoArquivo, marcaDaguaAtiva } from './receituario.model';

const BASE = '/estabelecimentos/meu/papel-timbrado';

/** Personalização de receitas e atestados da unidade: logo, marca-d'água e rodapé. */
@Component({
  selector: 'app-receituario',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule, MatFormFieldModule, MatIconModule, MatInputModule, MatProgressSpinnerModule, MatSlideToggleModule,
    EmptyStateComponent, PageHeaderComponent,
  ],
  templateUrl: './receituario.component.html',
  styleUrl: './receituario.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReceituarioComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly toast = inject(ToastService);
  private readonly sanitizer = inject(DomSanitizer);

  readonly config = signal<PapelTimbrado | null>(null);
  readonly carregando = signal(true);
  readonly falhou = signal(false);
  readonly enviando = signal(false);
  readonly salvando = signal(false);
  readonly erroArquivo = signal<string | null>(null);
  readonly logoUrl = signal<SafeUrl | null>(null);
  private urlDoLogo: string | null = null;

  readonly marcaDagua = signal(true);
  readonly rodape = signal('');
  readonly tamanhoRodape = TAMANHO_RODAPE;
  readonly alterado = computed(() => {
    const c = this.config();
    return !!c && (c.marca_dagua !== this.marcaDagua() || (c.rodape ?? '') !== this.rodape().trim());
  });
  readonly marcaAtiva = computed(() =>
    marcaDaguaAtiva({ tem_logo: this.config()?.tem_logo ?? false, marca_dagua: this.marcaDagua() }),
  );

  constructor() {
    inject(DestroyRef).onDestroy(() => this.liberarLogo());
  }

  async ngOnInit(): Promise<void> {
    try {
      await this.aplicar(await firstValueFrom(this.api.get<PapelTimbrado>(BASE)));
    } catch {
      this.falhou.set(true);
    } finally {
      this.carregando.set(false);
    }
  }

  async escolherArquivo(evento: Event): Promise<void> {
    const campo = evento.target as HTMLInputElement;
    const arquivo = campo.files?.[0];
    campo.value = ''; // permite escolher o mesmo arquivo de novo
    if (!arquivo) return;

    const erro = erroDoArquivo(arquivo);
    this.erroArquivo.set(erro);
    if (erro) return;

    const formulario = new FormData();
    formulario.append('arquivo', arquivo);
    this.enviando.set(true);
    try {
      await this.aplicar(await firstValueFrom(this.api.post<PapelTimbrado>(`${BASE}/logo`, formulario)));
      this.toast.sucesso('Logo atualizado. Ele já vale para as próximas receitas e atestados.');
    } catch (e: unknown) {
      this.erroArquivo.set((e as { error?: { detail?: string } })?.error?.detail ?? 'Não foi possível enviar a imagem.');
    } finally {
      this.enviando.set(false);
    }
  }

  async removerLogo(): Promise<void> {
    this.enviando.set(true);
    try {
      await firstValueFrom(this.api.delete(`${BASE}/logo`));
      await this.aplicar({ ...this.config()!, tem_logo: false });
      this.toast.sucesso('Logo removido.');
    } catch {
      this.toast.erro('Não foi possível remover o logo.');
    } finally {
      this.enviando.set(false);
    }
  }

  async salvar(): Promise<void> {
    this.salvando.set(true);
    try {
      const salvo = await firstValueFrom(
        this.api.put<PapelTimbrado>(BASE, { marca_dagua: this.marcaDagua(), rodape: this.rodape().trim() || null }),
      );
      this.config.set(salvo);
      this.rodape.set(salvo.rodape ?? '');
      this.toast.sucesso('Opções salvas.');
    } catch {
      this.toast.erro('Não foi possível salvar as opções.');
    } finally {
      this.salvando.set(false);
    }
  }

  /** Abre uma receita de exemplo com o que está salvo (alterações pendentes são salvas antes). */
  async verExemplo(): Promise<void> {
    if (this.alterado()) await this.salvar();
    try {
      const url = URL.createObjectURL(await firstValueFrom(this.api.getBlob(`${BASE}/exemplo.pdf`)));
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      this.toast.erro('Não foi possível gerar o exemplo.');
    }
  }

  private async aplicar(config: PapelTimbrado): Promise<void> {
    this.config.set(config);
    this.marcaDagua.set(config.marca_dagua);
    this.rodape.set(config.rodape ?? '');
    this.liberarLogo();
    if (!config.tem_logo) return;
    try {
      this.urlDoLogo = URL.createObjectURL(await firstValueFrom(this.api.getBlob(`${BASE}/logo`)));
      this.logoUrl.set(this.sanitizer.bypassSecurityTrustUrl(this.urlDoLogo));
    } catch {
      // o logo existe, só a prévia não carregou
    }
  }

  private liberarLogo(): void {
    if (this.urlDoLogo) URL.revokeObjectURL(this.urlDoLogo);
    this.urlDoLogo = null;
    this.logoUrl.set(null);
  }
}
