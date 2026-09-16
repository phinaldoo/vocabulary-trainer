import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LearnPage } from './LearnPage';
import { I18nProvider } from '../i18n';

const mockApi = vi.hoisted(() => vi.fn());
const mockUpdateUser = vi.hoisted(() => vi.fn());

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, api: mockApi };
});

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'lerner@example.test',
      display_name: 'Lerner',
      role: 'user',
      language: 'en',
      daily_goal: 12,
      direction: 'forward',
      input_mode: 'typing',
      selected_deck_id: 'deck-1',
      selected_section_id: null,
      created_at: '2026-08-30T10:00:00Z',
    },
    refresh: vi.fn().mockResolvedValue(undefined),
    updateUser: mockUpdateUser,
  }),
}));

const deck = {
  id: 'deck-1', slug: 'synthetic-test', title: 'Synthetic test deck', description: null,
  front_label: 'Prompt', back_label: 'Answer', front_language: 'zxx', back_language: 'zxx',
  front_matcher: 'generic-v1', back_matcher: 'generic-v1', status: 'published', version: 1,
  license: null, attribution: null, sort_order: 1, section_count: 1, card_count: 1,
};

const section = {
  id: 'section-49', deck_id: 'deck-1', stable_key: 'generated', title: 'Generated samples',
  sort_order: 1, active: true, total: 1, learned: 0, mastered: 0, due: 0,
  progress_percent: 0,
};

const session = {
  id: 'session-1', deck_id: 'deck-1', deck_title: 'Synthetic test deck', section_id: 'section-49',
  section_title: 'Generated samples', front_label: 'Prompt', back_label: 'Answer',
  front_language: 'zxx', back_language: 'zxx', direction: 'forward', input_mode: 'reveal',
  total: 1, reviewed: 0, correct_reviewed: 0, complete: false,
  cards: [{
    item_id: 'item-1', card_id: 'word-1', section_id: 'section-49', section_title: 'Lektion 49',
    ordinal: 1, direction: 'forward', prompt: 'nuvexa-47', prompt_language: 'zxx',
    answer_language: 'zxx', metadata: { kind: 'synthetic' }, state_version: 0, is_new: true,
  }],
};

describe('Lernmodus', () => {
  beforeEach(() => {
    cleanup();
    mockApi.mockReset();
    mockUpdateUser.mockReset();
    mockApi.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/decks') return Promise.resolve([deck]);
      if (path === '/sections?deck_id=deck-1') return Promise.resolve([section]);
      if (path === '/study-sessions' && options?.method === 'POST') return Promise.resolve(session);
      if (path === '/study-sessions/session-1') return Promise.resolve(session);
      if (path.endsWith('/reveal')) return Promise.resolve({ solution: 'qarilo-82' });
      throw new Error(`Unerwarteter API-Aufruf: ${path}`);
    });
  });

  it.each(['random', 'adaptive'] as const)('starts %s practice across all sections', async (selectionMode) => {
    const user = userEvent.setup();
    render(<I18nProvider><MemoryRouter initialEntries={['/lernen?deck=deck-1&section=section-49']}><LearnPage /></MemoryRouter></I18nProvider>);
    await screen.findByRole('button', { name: /All sections/ });
    await user.click(screen.getByRole('button', { name: /All sections/ }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Card selection' }), selectionMode);
    await user.click(screen.getByRole('button', { name: /Start learning/ }));
    await screen.findByRole('heading', { name: 'nuvexa-47' });
    const call = mockApi.mock.calls.find(([path]) => path === '/study-sessions');
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      deck_id: 'deck-1', section_id: null, selection_mode: selectionMode,
    });
  });

  it('toggles multiple sections, retains hidden selections, and starts their union', async () => {
    const original = mockApi.getMockImplementation()!;
    mockApi.mockImplementation((path: string, options?: RequestInit) => path === '/sections?deck_id=deck-1'
      ? Promise.resolve([section, { ...section, id: 'section-50', title: 'More samples' }])
      : original(path, options));
    const user = userEvent.setup();
    render(<I18nProvider><MemoryRouter initialEntries={['/lernen?deck=deck-1']}><LearnPage /></MemoryRouter></I18nProvider>);
    await user.click(await screen.findByRole('button', { name: /Generated samples/ }));
    await user.type(screen.getByPlaceholderText(/Search sections/), 'More');
    await user.click(screen.getByRole('button', { name: /More samples/ }));
    await user.clear(screen.getByPlaceholderText(/Search sections/));
    expect(screen.getByRole('button', { name: /Generated samples/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /More samples/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /All sections/ })).toHaveAttribute('aria-pressed', 'false');
    await user.click(screen.getByRole('button', { name: /Start learning/ }));
    await screen.findByRole('heading', { name: 'nuvexa-47' });
    const call = mockApi.mock.calls.find(([path]) => path === '/study-sessions');
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ section_id: null, section_ids: ['section-49', 'section-50'] });
    expect(mockUpdateUser).toHaveBeenCalledWith(expect.objectContaining({ selected_section_ids: ['section-49', 'section-50'] }));
  });

  it('restores repeated section links and resets to all when the last section is deselected', async () => {
    const original = mockApi.getMockImplementation()!;
    mockApi.mockImplementation((path: string, options?: RequestInit) => path === '/sections?deck_id=deck-1'
      ? Promise.resolve([section, { ...section, id: 'section-50', title: 'More samples' }])
      : original(path, options));
    const user = userEvent.setup();
    render(<I18nProvider><MemoryRouter initialEntries={['/lernen?deck=deck-1&section=section-49&section=section-50']}><LearnPage /></MemoryRouter></I18nProvider>);
    expect(await screen.findByRole('button', { name: /Generated samples/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /More samples/ })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: /Generated samples/ }));
    expect(screen.getByRole('button', { name: /More samples/ })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: /More samples/ }));
    expect(screen.getByRole('button', { name: /All sections/ })).toHaveAttribute('aria-pressed', 'true');
  });

  it('restores multiple sections after a completed session', async () => {
    const original = mockApi.getMockImplementation()!;
    mockApi.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/sections?deck_id=deck-1') return Promise.resolve([section, { ...section, id: 'section-50', title: 'More samples' }]);
      if (path === '/study-sessions/session-1') return Promise.resolve({ ...session, section_id: null, section_ids: ['section-49', 'section-50'], section_titles: ['Generated samples', 'More samples'], complete: true, cards: [] });
      return original(path, options);
    });
    const user = userEvent.setup();
    render(<I18nProvider><MemoryRouter initialEntries={['/lernen?session=session-1']}><LearnPage /></MemoryRouter></I18nProvider>);
    await user.click(await screen.findByRole('button', { name: /New session/ }));
    expect(await screen.findByRole('button', { name: /Generated samples/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /More samples/ })).toHaveAttribute('aria-pressed', 'true');
  });

  it('clears selected sections when switching decks', async () => {
    const original = mockApi.getMockImplementation()!;
    mockApi.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/decks') return Promise.resolve([deck, { ...deck, id: 'deck-2', title: 'Second deck' }]);
      if (path === '/sections?deck_id=deck-2') return Promise.resolve([{ ...section, deck_id: 'deck-2', id: 'section-60', title: 'Other section' }]);
      return original(path, options);
    });
    const user = userEvent.setup();
    render(<I18nProvider><MemoryRouter initialEntries={['/lernen?deck=deck-1&section=section-49']}><LearnPage /></MemoryRouter></I18nProvider>);
    await screen.findByRole('button', { name: /Generated samples/ });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Deck' }), 'deck-2');
    await screen.findByRole('button', { name: /Other section/ });
    expect(screen.getByRole('button', { name: /All sections/ })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: /Start learning/ }));
    await screen.findByRole('heading', { name: 'nuvexa-47' });
    const call = mockApi.mock.calls.find(([path]) => path === '/study-sessions');
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ deck_id: 'deck-2', section_ids: [] });
  });

  it('keeps adaptive selection when starting another session', async () => {
    mockApi.mockImplementation((path: string) => {
      if (path === '/decks') return Promise.resolve([deck]);
      if (path === '/sections?deck_id=deck-1') return Promise.resolve([section]);
      if (path === '/study-sessions/session-1') return Promise.resolve({ ...session, selection_mode: 'adaptive', complete: true, cards: [] });
      throw new Error(`Unexpected API call: ${path}`);
    });
    const user = userEvent.setup();
    render(<I18nProvider><MemoryRouter initialEntries={['/lernen?session=session-1']}><LearnPage /></MemoryRouter></I18nProvider>);
    await user.click(await screen.findByRole('button', { name: /New session/ }));
    expect(await screen.findByRole('combobox', { name: 'Card selection' })).toHaveValue('adaptive');
  });

  it('bindet Deck und Abschnitt an die Session und zeigt die Lösung erst nach dem Wenden', async () => {
    const user = userEvent.setup();
    render(
      <I18nProvider><MemoryRouter initialEntries={['/lernen?deck=deck-1&section=section-49']}>
        <LearnPage />
      </MemoryRouter></I18nProvider>,
    );

    await screen.findByRole('heading', { name: 'What would you like to study today?' });
    await user.click(screen.getByRole('button', { name: /Reveal the card/ }));
    await user.click(screen.getByRole('button', { name: /Start learning/ }));

    await screen.findByRole('heading', { name: 'nuvexa-47' });
    expect(screen.queryByText('qarilo-82')).not.toBeInTheDocument();

    const startCall = mockApi.mock.calls.find(([path]) => path === '/study-sessions');
    expect(JSON.parse(String(startCall?.[1]?.body))).toMatchObject({
      deck_id: 'deck-1',
      section_id: 'section-49',
      input_mode: 'reveal',
      direction: 'forward',
    });
    expect(mockUpdateUser).toHaveBeenCalledWith(expect.objectContaining({
      selected_deck_id: 'deck-1',
      selected_section_id: 'section-49',
      input_mode: 'reveal',
      direction: 'forward',
    }));

    await user.click(screen.getByRole('button', { name: /Reveal card/ }));
    expect(await screen.findByText('qarilo-82')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Did not know/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Knew it/ })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole('button', { name: /know|knew/i })).toHaveLength(2));
  });

  it('verwirft eine geladene Session, wenn die Session-ID aus der URL entfernt wird', async () => {
    const user = userEvent.setup();
    render(
      <I18nProvider><MemoryRouter initialEntries={['/lernen?session=session-1']}>
        <Link to="/lernen">Neue Konfiguration</Link>
        <LearnPage />
      </MemoryRouter></I18nProvider>,
    );

    await screen.findByRole('heading', { name: 'nuvexa-47' });
    await user.click(screen.getByRole('link', { name: 'Neue Konfiguration' }));

    expect(await screen.findByRole('heading', { name: 'What would you like to study today?' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'nuvexa-47' })).not.toBeInTheDocument();
  });
});
