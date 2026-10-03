import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VocabularyPage } from './VocabularyPage';
import { I18nProvider } from '../i18n';

const mockApi = vi.hoisted(() => vi.fn());
vi.mock('../api/client', async () => ({ ...await vi.importActual('../api/client'), api: mockApi }));
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: { selected_deck_id: 'deck-1', language: 'en' } }) }));
const deck = { id: 'deck-1', title: 'Latin', front_label: 'Latin', back_label: 'German', front_language: 'la', back_language: 'de', card_count: 40 };
let card = { id: 'card-1', front_text: 'rosa', back_text: 'Rose', section_title: 'Chapter 1', section_id: 'section-1', status: 'new', favorite: false, difficulty: 'auto', metadata: { gender: 'f.', part_of_speech: 'noun', additional_info: 'First', additional_info_2: 'Second' } };
function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function setup(url = '/vokabeln') {
  return render(<I18nProvider><MemoryRouter initialEntries={[url]}><VocabularyPage /><Location /></MemoryRouter></I18nProvider>);
}

describe('all vocabulary', () => {
  beforeEach(() => {
    mockApi.mockReset();
    card = { ...card, difficulty: 'auto', favorite: false };
    mockApi.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/decks') return Promise.resolve([deck]);
      if (path.startsWith('/sections?')) return Promise.resolve([{ id: 'section-1', title: 'Chapter 1' }]);
      if (path.startsWith('/cards?')) return Promise.resolve({ items: [card], total: 40, pages: 2, page: Number(new URLSearchParams(path.split('?')[1]).get('page')), page_size: 36 });
      if (path === '/cards/card-1/difficulty') { card = { ...card, ...JSON.parse(String(options?.body)) }; return Promise.resolve({ difficulty: card.difficulty }); }
      throw new Error(path);
    });
  });

  it('restores list sorting and sorts the entire catalogue before pagination', async () => {
    const user = userEvent.setup();
    setup('/vokabeln?view=list&sort=front&order=desc&page=2');
    const table = await screen.findByRole('table');
    expect(screen.getByRole('heading', { name: 'All vocabulary' })).toBeInTheDocument();
    expect(within(table).getByText('Second')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Latin' })).toHaveAttribute('aria-sort', 'descending');
    await user.click(within(table).getByRole('button', { name: 'Part of speech' }));
    await waitFor(() => expect(mockApi).toHaveBeenCalledWith(expect.stringContaining('sort_by=part_of_speech')));
    expect(screen.getByTestId('location').textContent).not.toContain('page=');
    expect(screen.getByRole('columnheader', { name: 'Part of speech' })).toHaveAttribute('aria-sort', 'ascending');
    await user.click(screen.getByRole('button', { name: /Next/ }));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('page=2'));
    await user.click(screen.getByRole('button', { name: 'Cards' }));
    expect(await screen.findByRole('heading', { name: 'rosa' })).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('sort=part_of_speech');
  });

  it('edits difficulty in the list and restores it in card details', async () => {
    const user = userEvent.setup(); setup('/vokabeln?view=list');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Difficulty for rosa' }), 'hard');
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Difficulty for rosa' })).toHaveValue('hard'));
    expect(mockApi).toHaveBeenCalledWith('/cards/card-1/difficulty', { method: 'PUT', body: '{"difficulty":"hard"}' });
    await user.click(screen.getByRole('button', { name: 'rosa' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('combobox')).toHaveValue('hard');
    await user.selectOptions(within(dialog).getByRole('combobox'), 'auto');
    await waitFor(() => expect(within(dialog).getByRole('combobox')).toHaveValue('auto'));
  });

  it('keeps the saved difficulty when an update fails', async () => {
    const original = mockApi.getMockImplementation()!;
    mockApi.mockImplementation((path: string, options?: RequestInit) => path.endsWith('/difficulty') ? Promise.reject(new Error('offline')) : original(path, options));
    const user = userEvent.setup(); setup();
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Difficulty for rosa' }), 'hard');
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Difficulty for rosa' })).toHaveValue('auto');
    expect(screen.getByRole('combobox', { name: 'Difficulty for rosa' })).toBeEnabled();
  });
});
