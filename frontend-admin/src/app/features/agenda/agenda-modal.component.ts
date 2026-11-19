import { itensDaTriagem } from '../../core/utils/triagem.utils';
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
} from '@angular/core';
import { DatePipe, SlicePipe } from '@angular/common';
import { SlotAdmin } from '../../core/services/agenda-admin.service';

@Component({
  selector: 'app-agenda-modal',
  standalone: true,
  imports: [DatePipe, SlicePipe],
  templateUrl: './agenda-modal.component.html',
  styleUrls: ['./agenda-modal.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AgendaModalComponent {
  @Input({ required: true }) slot!: SlotAdmin;
  @Output() fechar = new EventEmitter<void>();

  get urgenciaClass(): string {
    const u = this.slot.atendimento?.urgencia ?? '';
    return u.toLowerCase();
  }

  get triagemItens(): { chave: string; valor: string }[] {
    return itensDaTriagem(this.slot.atendimento?.triagem_resumo);
  }
}
