import { describe, it, expect } from 'vitest';

describe('AgendamentosComponent', () => {
  it('should be importable', async () => {
    const { AgendamentosComponent } = await import('./agendamentos.component');
    expect(AgendamentosComponent).toBeDefined();
  });
});

describe('AgendamentoService', () => {
  it('should be importable', async () => {
    const { AgendamentoService } = await import('../../core/services/agendamento.service');
    expect(AgendamentoService).toBeDefined();
  });
});
