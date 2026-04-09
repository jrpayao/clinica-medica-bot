/**
 * EmptyStateComponent — estado vazio reutilizável.
 *
 * Uso:
 *   <app-empty-state
 *     icon="group"
 *     title="Nenhum paciente cadastrado"
 *     description="Adicione o primeiro paciente para começar."
 *     ctaLabel="Novo Paciente"
 *     (ctaClick)="abrirNovo()" />
 */
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
} from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  imports: [MatIconModule, MatButtonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="empty-state">
      <mat-icon class="empty-state__icon">{{ icon }}</mat-icon>
      <h3 class="empty-state__title">{{ title }}</h3>
      @if (description) {
        <p class="empty-state__desc">{{ description }}</p>
      }
      @if (ctaLabel) {
        <button mat-raised-button color="primary" (click)="ctaClick.emit()">
          {{ ctaLabel }}
        </button>
      }
    </div>
  `,
  styles: [`
    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 64px 32px;
      text-align: center;
      color: var(--color-text-secondary);

      &__icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        opacity: .35;
        margin-bottom: 16px;
      }

      &__title {
        font-size: 18px;
        font-weight: 600;
        color: var(--color-text);
        margin: 0 0 8px;
      }

      &__desc {
        font-size: 14px;
        margin: 0 0 24px;
        max-width: 360px;
      }
    }
  `],
})
export class EmptyStateComponent {
  @Input() icon = 'inbox';
  @Input() title = 'Nenhum registro encontrado';
  @Input() description = '';
  @Input() ctaLabel = '';
  @Output() ctaClick = new EventEmitter<void>();
}
