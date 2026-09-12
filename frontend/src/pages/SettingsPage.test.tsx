import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '../i18n';
import type { User } from '../types';
import { SettingsPage } from './SettingsPage';

const mockApi = vi.hoisted(() => vi.fn());
const mockUpdateUser = vi.hoisted(() => vi.fn());

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, api: mockApi };
});

const account: User = {
  id: 'user-1',
  email: 'learner@example.test',
  display_name: 'Learner',
  role: 'user',
  language: 'en',
  daily_goal: 12,
  direction: 'forward',
  input_mode: 'typing',
  selected_deck_id: null,
  selected_section_id: null,
  created_at: '2026-08-31T10:00:00Z',
};

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    user: account,
    updateUser: mockUpdateUser,
    clearUser: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}));

describe('SettingsPage language preference', () => {
  afterEach(cleanup);

  beforeEach(() => {
    mockApi.mockReset();
    mockUpdateUser.mockReset();
    mockApi.mockImplementation((path: string) => {
      if (path === '/decks') return Promise.resolve([]);
      if (path === '/account/settings') return Promise.resolve({ ...account, language: 'zh-Hans' });
      if (path === '/account/profile') return Promise.resolve({
        ...account,
        email: 'updated@example.test',
        display_name: 'Updated Learner',
      });
      throw new Error(`Unexpected API call: ${path}`);
    });
  });

  it('previews and persists the selected account language', async () => {
    const event = userEvent.setup();
    render(
      <I18nProvider><MemoryRouter><SettingsPage /></MemoryRouter></I18nProvider>,
    );

    const selector = await screen.findByRole('combobox', { name: 'Interface language' });
    await event.selectOptions(selector, 'zh-Hans');

    expect(document.documentElement.lang).toBe('zh-Hans');
    expect(screen.getByRole('heading', { name: '设置' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '保存更改' })).not.toBeInTheDocument();

    await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/account/settings', expect.objectContaining({
      method: 'PATCH',
    })));
    const settingsCall = mockApi.mock.calls.find(([path]) => path === '/account/settings');
    expect(JSON.parse(String(settingsCall?.[1]?.body))).toMatchObject({ language: 'zh-Hans' });
    expect(mockUpdateUser).toHaveBeenCalledWith(expect.objectContaining({ language: 'zh-Hans' }));
  });

  it('automatically saves every expanded daily goal without saving on mount', async () => {
    const event = userEvent.setup();
    render(<I18nProvider><MemoryRouter><SettingsPage /></MemoryRouter></I18nProvider>);
    const selector = await screen.findByRole('combobox', { name: 'Daily goal' });
    expect(mockApi.mock.calls.some(([path]) => path === '/account/settings')).toBe(false);
    for (const goal of [100, 150, 200, 250, 500]) {
      await event.selectOptions(selector, String(goal));
      await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/account/settings', {
        method: 'PATCH',
        body: expect.stringContaining('"daily_goal":' + goal),
      }));
    }
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
  });

  it('updates the signed-in account name and email', async () => {
    const event = userEvent.setup();
    render(
      <I18nProvider><MemoryRouter><SettingsPage /></MemoryRouter></I18nProvider>,
    );

    const name = await screen.findByRole('textbox', { name: 'Name' });
    const email = screen.getByRole('textbox', { name: 'Email' });
    await event.clear(name);
    await event.type(name, 'Updated Learner');
    await event.clear(email);
    await event.type(email, 'updated@example.test');
    await event.click(screen.getByRole('button', { name: 'Save account' }));

    await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/account/profile', expect.objectContaining({
      method: 'PATCH',
    })));
    const profileCall = mockApi.mock.calls.find(([path]) => path === '/account/profile');
    expect(JSON.parse(String(profileCall?.[1]?.body))).toEqual({
      display_name: 'Updated Learner',
      email: 'updated@example.test',
    });
    expect(mockUpdateUser).toHaveBeenCalledWith(expect.objectContaining({
      display_name: 'Updated Learner',
      email: 'updated@example.test',
    }));
    expect(name).toHaveValue('Updated Learner');
    expect(email).toHaveValue('updated@example.test');
  });
});
