import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '../i18n';
import { SpecialVerbsPage } from './SpecialVerbsPage';

const mockApi = vi.hoisted(() => vi.fn());
const auth = vi.hoisted(() => ({ user: { role: 'admin', language: 'en' } }));
vi.mock('../api/client', async () => ({ ...await vi.importActual('../api/client'), api: mockApi }));
vi.mock('../auth/AuthContext', () => ({ useAuth: () => auth }));
const deck = { id: 'verbs', title: 'Verbs', front_matcher: 'latin-principal-parts-v1', card_count: 1, section_count: 1, status: 'published' };
const row = { line: 3, infinitive: 'vetare', present: 'veto', perfect: 'vetui', supine: 'vetitum', meaning: 'verbieten' };
const csv = 'vetare;veto;vetui;vetitum;verbieten';
function setup() { return render(<I18nProvider><MemoryRouter><SpecialVerbsPage /></MemoryRouter></I18nProvider>); }
function file() {
  const upload = new File([csv], 'Verbs.csv', { type: 'text/csv' });
  Object.defineProperty(upload, 'arrayBuffer', { value: async () => new TextEncoder().encode(csv).buffer });
  return upload;
}

describe('special verbs', () => {
  beforeEach(() => {
    auth.user.role = 'admin';
    mockApi.mockReset();
    mockApi.mockImplementation((path: string) => {
      if (path === '/decks?kind=special_verbs') return Promise.resolve([deck, { id: 'normal', title: 'Ordinary vocabulary', front_matcher: 'latin-v1' }]);
      if (path.startsWith('/sections?')) return Promise.resolve([{ id: 'group1', title: 'u-Perfekt' }]);
      if (path.startsWith('/cards?')) return Promise.resolve({ items: [{ id: 'verb1', front_text: 'vetare, veto, vetui, vetitum', back_text: 'verbieten', section_title: 'u-Perfekt' }], pages: 1 });
      if (path.endsWith('/preview')) return Promise.resolve({ rows: [row], errors: [], duplicate_count: 0, section_count: 1 });
      if (path.endsWith('/import')) return Promise.resolve({ deck, unchanged: false });
      throw new Error(path);
    });
  });

  it('previews then publishes a CSV and refreshes the saved collections', async () => {
    const user = userEvent.setup(); setup();
    await user.upload(screen.getByLabelText('Choose CSV file'), file());
    expect(await screen.findByText('Preview · first 10 verbs')).toBeInTheDocument();
    expect(mockApi).not.toHaveBeenCalledWith('/admin/special-verbs/import', expect.anything());
    await user.click(screen.getByRole('button', { name: 'Import and publish' }));
    expect(await screen.findByText('1 verbs imported. Ready to practice.')).toBeInTheDocument();
    expect(mockApi).toHaveBeenCalledWith('/admin/special-verbs/import', {
      method: 'POST', body: JSON.stringify({ title: 'Verbs', csv_text: csv }),
    });
    expect(screen.queryByRole('button', { name: 'Import and publish' })).not.toBeInTheDocument();
    await waitFor(() => expect(mockApi.mock.calls.filter(([path]) => path === '/decks?kind=special_verbs').length).toBe(2));
  });

  it('shows row errors and blocks invalid imports', async () => {
    const original = mockApi.getMockImplementation()!;
    mockApi.mockImplementation((path: string) => path.endsWith('/preview') ? Promise.resolve({ rows: [], errors: [{ line: 4, code: 'columns' }] }) : original(path));
    const user = userEvent.setup(); setup();
    await user.upload(screen.getByLabelText('Choose CSV file'), file());
    expect(await screen.findByRole('alert')).toHaveTextContent('Line 4');
    expect(screen.queryByRole('button', { name: 'Import and publish' })).not.toBeInTheDocument();
  });

  it('filters special collections and carries the group and each direction into practice', async () => {
    const user = userEvent.setup(); setup();
    expect(await screen.findByText('vetitum')).toBeInTheDocument();
    expect(screen.queryByText('Ordinary vocabulary')).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Conjugation / perfect group' }), 'group1');
    expect(screen.getByRole('link', { name: 'Latin → German' })).toHaveAttribute('href', '/verben/lernen?deck=verbs&section=group1&direction=forward');
    expect(screen.getByRole('link', { name: 'German → Latin forms' })).toHaveAttribute('href', '/verben/lernen?deck=verbs&section=group1&direction=reverse');
    expect(screen.getByRole('link', { name: /Mixed/ })).toHaveAttribute('href', '/verben/lernen?deck=verbs&section=group1&direction=mixed');
    await user.type(screen.getByRole('textbox', { name: 'Search verbs or meanings' }), 'vetare');
    await waitFor(() => expect(mockApi).toHaveBeenCalledWith(expect.stringContaining('q=vetare')));
  });

  it('lets learners practice but keeps shared catalogue imports admin-only', async () => {
    auth.user.role = 'user'; setup();
    expect(await screen.findByText('vetitum')).toBeInTheDocument();
    expect(screen.queryByLabelText('Choose CSV file')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'German → Latin forms' })).toBeInTheDocument();
  });

  it('rejects oversized files before uploading', async () => {
    const upload = file(); Object.defineProperty(upload, 'size', { value: 1_000_001 });
    const user = userEvent.setup(); setup();
    await user.upload(screen.getByLabelText('Choose CSV file'), upload);
    expect(await screen.findByRole('alert')).toHaveTextContent('smaller than 1 MB');
    expect(mockApi.mock.calls.some(([path]) => path.endsWith('/preview'))).toBe(false);
  });
});
