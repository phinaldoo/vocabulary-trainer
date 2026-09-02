import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminPage } from './AdminPage';
import { I18nProvider } from '../i18n';

const mockApi = vi.hoisted(() => vi.fn());

const initialUserPage = {
  items: [
    {
      id: 'admin-1',
      email: 'admin@example.com',
      display_name: 'Admin',
      role: 'admin',
      created_at: '2026-08-31T10:00:00Z',
    },
    {
      id: 'user-2',
      email: 'learner@example.com',
      display_name: 'Learner',
      role: 'user',
      created_at: '2026-09-01T10:00:00Z',
    },
  ],
  page: 1,
  page_size: 25,
  total: 2,
  pages: 1,
};

let currentUserPage = initialUserPage;

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, api: mockApi };
});

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'admin-1',
      email: 'admin@example.com',
      display_name: 'Admin',
      role: 'admin',
      language: 'en',
      daily_goal: 12,
      direction: 'forward',
      input_mode: 'typing',
      selected_deck_id: null,
      selected_section_id: null,
      created_at: '2026-08-31T10:00:00Z',
    },
  }),
}));

describe('Adminbereich', () => {
  beforeEach(() => {
    mockApi.mockReset();
    currentUserPage = {
      ...initialUserPage,
      items: initialUserPage.items.map((account) => ({ ...account })),
    };
    mockApi.mockImplementation((path: string) => {
      if (path === '/admin/decks') return Promise.resolve([]);
      if (path === '/admin/users?page=1&page_size=25&q=') return Promise.resolve(currentUserPage);
      if (path === '/admin/users/user-2/promote') {
        const promoted = { ...currentUserPage.items[1]!, role: 'admin' };
        currentUserPage = {
          ...currentUserPage,
          items: currentUserPage.items.map((account) => account.id === promoted.id ? promoted : account),
        };
        return Promise.resolve(promoted);
      }
      throw new Error(`Unerwarteter API-Aufruf: ${path}`);
    });
  });

  it('bietet den Deck-Import auch in einer leeren Installation an', async () => {
    render(
      <I18nProvider><MemoryRouter>
        <AdminPage />
      </MemoryRouter></I18nProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Administration' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Users' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Import deck' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Validate and import/ })).toBeDisabled();
  });

  it('allows an administrator to promote a learner', async () => {
    const actor = userEvent.setup();
    render(
      <I18nProvider><MemoryRouter>
        <AdminPage />
      </MemoryRouter></I18nProvider>,
    );

    await actor.click(await screen.findByRole('button', { name: 'Make Learner an administrator' }));

    expect(mockApi).toHaveBeenCalledWith('/admin/users/user-2/promote', { method: 'POST' });
    expect(await screen.findByText('Learner is now an administrator.')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Make Learner an administrator' })).not.toBeInTheDocument();
    });
  });
});
