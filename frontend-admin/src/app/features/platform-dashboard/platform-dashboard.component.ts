import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { PlataformaService } from '../../core/services/plataforma.service';

@Component({
  selector: 'app-platform-dashboard',
  standalone: true,
  imports: [MatCardModule, MatIconModule, MatProgressSpinnerModule, MatChipsModule],
  templateUrl: './platform-dashboard.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PlatformDashboardComponent implements OnInit {
  readonly ps = inject(PlataformaService);
  readonly objectEntries = Object.entries;

  async ngOnInit(): Promise<void> {
    await this.ps.carregar();
  }

  statusColor(status: string): string {
    const map: Record<string, string> = {
      ATIVA: 'primary', TRIAL: 'accent', EXPIRADA: 'warn', SUSPENSA: 'warn',
    };
    return map[status] ?? 'default';
  }
}
