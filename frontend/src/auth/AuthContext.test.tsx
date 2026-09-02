import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider, useI18n } from '../i18n';
import type { User } from '../types';
import { AuthProvider, useAuth } from './AuthContext';

const mockApi = vi.hoisted(() => vi.fn());
const mockEnsureCsrf = vi.hoisted(() => vi.fn());

vi.mock('../api/client', () => ({
  api: mockApi,
  ensureCsrf: mockEnsureCsrf,
}));

const user: User = {
  id: 'user-1',
  email: 'learner@example.test',
  display_name: 'Learner',
  role: 'user',
  language: null,
  daily_goal: 12,
  direction: 'forward',
  input_mode: 'typing',
  selected_deck_id: null,
  selected_section_id: null,
  created_at: '2026-08-31T10:00:00Z',
};

function Probe() {
  const auth = useAuth();
  const { language } = useI18n();
  return (
    <>
      <span data-testid="account-language">{auth.user?.language ?? 'none'}</span>
      <span data-testid="ui-language">{language}</span>
      <button type="button" onClick={() => void auth.login('learner@example.test', 'password123')}>
        Log in
      </button>
    </>
  );
}

function renderProvider() {
  return render(
    <I18nProvider>
      <AuthProvider><Probe /></AuthProvider>
    </I18nProvider>,
  );
}

describe('AuthProvider language handling', () => {
  afterEach(cleanup);

  beforeEach(() => {
    mockApi.mockReset();
    mockEnsureCsrf.mockReset().mockResolvedValue(undefined);
    Object.defineProperty(window.navigator, 'languages', {
      configurable: true,
      value: ['zh-CN', 'en-US'],
    });
  });

  it('initializes a legacy account once from the browser language', async () => {
    mockApi.mockImplementation((path: string) => {
      if (path === '/auth/me') return Promise.resolve(user);
      if (path === '/account/language/initialize') {
        return Promise.resolve({ ...user, language: 'zh-Hans' });
      }
      throw new Error(`Unexpected API call: ${path}`);
    });

    renderProvider();

    await waitFor(() => expect(screen.getByTestId('account-language')).toHaveTextContent('zh-Hans'));
    expect(screen.getByTestId('ui-language')).toHaveTextContent('zh-Hans');
    expect(mockApi).toHaveBeenCalledWith('/account/language/initialize', {
      method: 'POST',
      body: JSON.stringify({ language: 'zh-Hans' }),
    });
  });

  it('uses the saved account preference instead of a different browser language', async () => {
    mockApi.mockImplementation((path: string) => {
      if (path === '/auth/me') return Promise.resolve({ ...user, language: 'de' });
      throw new Error(`Unexpected API call: ${path}`);
    });

    renderProvider();

    await waitFor(() => expect(screen.getByTestId('ui-language')).toHaveTextContent('de'));
    expect(mockApi).not.toHaveBeenCalledWith('/account/language/initialize', expect.anything());
  });

  it('sends the detected browser language during login', async () => {
    mockApi.mockImplementation((path: string) => {
      if (path === '/auth/me') return Promise.reject(new Error('Unauthenticated'));
      if (path === '/auth/login') return Promise.resolve({ ...user, language: 'zh-Hans' });
      throw new Error(`Unexpected API call: ${path}`);
    });

    const event = userEvent.setup();
    renderProvider();
    await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/auth/me'));
    await event.click(screen.getByRole('button', { name: 'Log in' }));

    expect(mockApi).toHaveBeenCalledWith('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: 'learner@example.test',
        password: 'password123',
        language: 'zh-Hans',
      }),
    });
  });
});
