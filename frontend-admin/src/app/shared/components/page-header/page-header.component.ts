/**
 * PageHeaderComponent — cabeçalho padrão de página.
 *
 * Uso:
 *   <app-page-header titulo="Médicos" subtitulo="Gerencie os médicos da clínica">
 *     <button mat-raised-button color="primary" (click)="novo()">
 *       <mat-icon>add</mat-icon> Novo Médico
 *     </button>
 *   </app-page-header>
 */
import {
  ChangeDetectionStrategy,
  Component,
  Input,
} from '@angular/core';

@Component({
  selector: 'app-page-header',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="page-header">
      <div class="page-header__text">
        <h1 class="page-header__title">{{ titulo }}</h1>
        @if (subtitulo) {
          <p class="page-header__subtitle">{{ subtitulo }}</p>
        }
      </div>
      <div class="page-header__actions">
        <ng-content />
      </div>
    </header>
  `,
  styles: [`
    .page-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 24px;
      flex-wrap: wrap;
      gap: 12px;

      &__text { flex: 1; min-width: 200px; }

      &__title {
        font-size: 22px;
        font-weight: 700;
        color: var(--color-text);
        margin: 0 0 2px;
        line-height: 1.3;
      }

      &__subtitle {
        font-size: 14px;
        color: var(--color-text-secondary);
        margin: 0;
      }

      &__actions {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
      }
    }
  `],
})
export class PageHeaderComponent {
  @Input({ required: true }) titulo!: string;
  @Input() subtitulo = '';
}
