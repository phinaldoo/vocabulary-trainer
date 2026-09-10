import { afterEach, describe, expect, it, vi } from 'vitest';
import { createIdempotencyKey } from './client';

describe('createIdempotencyKey', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('uses randomUUID when the browser provides it', () => {
    vi.stubGlobal('crypto', { randomUUID: () => '11111111-2222-4333-8444-555555555555' });

    expect(createIdempotencyKey()).toBe('11111111-2222-4333-8444-555555555555');
  });

  it('creates a UUID over HTTP when randomUUID is unavailable', () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => {
      bytes.fill(0);
      return bytes;
    });
    vi.stubGlobal('crypto', { getRandomValues });

    expect(createIdempotencyKey()).toBe('00000000-0000-4000-8000-000000000000');
    expect(getRandomValues).toHaveBeenCalledOnce();
  });
});
