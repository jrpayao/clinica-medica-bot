import { describe, it, expect } from 'vitest';

describe('App', () => {
  it('should be importable', async () => {
    const { App } = await import('./app');
    expect(App).toBeDefined();
  });
});
