import { describe, it, expect } from 'vitest';

describe('AuthComponent', () => {
  it('should be importable', async () => {
    const { AuthComponent } = await import('./auth.component');
    expect(AuthComponent).toBeDefined();
  });
});

describe('AuthService', () => {
  it('should be importable', async () => {
    const { AuthService } = await import('../../core/services/auth.service');
    expect(AuthService).toBeDefined();
  });

  it('should have required methods', async () => {
    const { AuthService } = await import('../../core/services/auth.service');
    expect(AuthService.prototype.solicitarSms).toBeDefined();
    expect(AuthService.prototype.verificarSms).toBeDefined();
    expect(AuthService.prototype.getToken).toBeDefined();
    expect(AuthService.prototype.logout).toBeDefined();
  });
});
