import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, BookOpen, ChevronDown, Heart, LayoutGrid, List, Search, Sparkles, X } from 'lucide-react';
import { useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { CardMetadata } from '../components/CardMetadata';
import { PageError, PageLoading } from '../components/PageState';
import { useModalDialog } from '../hooks/useModalDialog';
import { useI18n } from '../i18n';
import type { MessageKey } from '../i18n/messages';
import { metadataFields, metadataValue } from '../lib/vocabularyMetadata';
import type { Card, CardPage, CardStatus, Deck, Difficulty, Section } from '../types';

const filters: Array<{ value: 'all' | CardStatus | 'favorites'; label: MessageKey }> = [
  { value: 'all', label: 'cards.filterAll' },
  { value: 'new', label: 'cards.statusNew' },
  { value: 'learning', label: 'cards.statusLearning' },
  { value: 'familiar', label: 'cards.statusFamiliar' },
  { value: 'mastered', label: 'cards.statusMastered' },
  { value: 'difficult', label: 'cards.statusDifficult' },
  { value: 'favorites', label: 'cards.favorites' },
];
const statusLabels: Record<CardStatus, MessageKey> = {
  new: 'cards.statusNew', learning: 'cards.statusLearning', familiar: 'cards.statusFamiliar',
  mastered: 'cards.statusMastered', difficult: 'cards.statusDifficult',
};
const sortKeys = ['original', 'front', 'back', 'gender', 'part_of_speech', 'additional_info', 'additional_info_2', 'section', 'difficulty', 'status'] as const;
type SortKey = typeof sortKeys[number];
const difficultyOptions: Difficulty[] = ['auto', 'easy', 'normal', 'hard'];
const emptyPage: CardPage = { items: [], page: 1, page_size: 36, total: 0, pages: 1 };

export function VocabularyPage() {
  const { user } = useAuth();
  const { number, t } = useI18n();
  const [params, setParams] = useSearchParams();
  const decks = useResource(() => api<Deck[]>('/decks'));
  const requestedDeck = params.get('deck');
  const fallbackDeckId = decks.data?.find((deck) => deck.id === user?.selected_deck_id)?.id ?? decks.data?.[0]?.id ?? '';
  const deckId = decks.data?.some((deck) => deck.id === requestedDeck) ? requestedDeck! : fallbackDeckId;
  const deck = decks.data?.find((entry) => entry.id === deckId) ?? null;
  const sectionId = params.get('section') ?? '';
  const query = params.get('q') ?? '';
  const filter = filters.some(({ value }) => value === params.get('state')) ? params.get('state')! : 'all';
  const requestedPage = Number(params.get('page') ?? 1);
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const sortBy = sortKeys.includes(params.get('sort') as SortKey) ? params.get('sort') as SortKey : 'original';
  const sortDirection = params.get('order') === 'desc' ? 'desc' : 'asc';
  const view = params.get('view') === 'list' ? 'list' : 'grid';
  const [selected, setSelected] = useState<Card | null>(null);
  const [actionError, setActionError] = useState('');
  const [saving, setSaving] = useState<string[]>([]);
  const pending = useRef(new Set<string>());
  const closeDialog = () => setSelected(null);
  const dialogRef = useModalDialog<HTMLElement>(Boolean(selected), closeDialog);
  const sections = useResource(() => deckId ? api<Section[]>(`/sections?deck_id=${deckId}`) : Promise.resolve([]), deckId);
  const search = new URLSearchParams({ deck_id: deckId, page: String(page), page_size: '36', state: filter, sort_by: sortBy, sort_direction: sortDirection });
  if (query.trim()) search.set('q', query.trim());
  if (sectionId) search.set('section_id', sectionId);
  const cards = useResource(() => deckId ? api<CardPage>(`/cards?${search}`) : Promise.resolve(emptyPage), search.toString());
  const data = cards.data;

  function updateParams(changes: Record<string, string | null>, resetPage = true) {
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (resetPage) next.delete('page');
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value); else next.delete(key);
      }
      return next;
    }, { replace: true });
  }

  function updateCard(id: string, changes: Partial<Card>) {
    cards.setData((current) => current ? { ...current, items: current.items.map((card) => card.id === id ? { ...card, ...changes } : card) } : current);
    setSelected((current) => current?.id === id ? { ...current, ...changes } : current);
  }

  async function saveCardPreference(card: Card, difficulty?: Difficulty) {
    if (pending.current.has(card.id)) return;
    pending.current.add(card.id); setSaving([...pending.current]); setActionError('');
    const favorite = !card.favorite;
    try {
      if (difficulty !== undefined) {
        await api(`/cards/${card.id}/difficulty`, { method: 'PUT', body: JSON.stringify({ difficulty }) });
        updateCard(card.id, { difficulty });
      } else {
        await api(`/favorites/${card.id}`, { method: favorite ? 'PUT' : 'DELETE' });
        updateCard(card.id, { favorite });
      }
      cards.reload();
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : t('common.genericError'));
    } finally {
      pending.current.delete(card.id); setSaving([...pending.current]);
    }
  }

  function difficultyControl(card: Card) {
    return <label className="difficulty-control"><span>{t('cards.difficulty')}</span><select aria-label={t('cards.difficultyFor', { card: card.front_text })} value={card.difficulty ?? 'auto'} disabled={saving.includes(card.id)} onChange={(event) => void saveCardPreference(card, event.target.value as Difficulty)}>
      {difficultyOptions.map((value) => <option key={value} value={value}>{t(`cards.difficulty.${value}`)}</option>)}
    </select></label>;
  }

  function favoriteControl(card: Card, className = 'icon-button') {
    return <button type="button" className={`${className} ${card.favorite ? 'active' : ''}`} disabled={saving.includes(card.id)} onClick={() => void saveCardPreference(card)} aria-label={t(card.favorite ? 'cards.removeFavorite' : 'cards.addFavorite', { card: card.front_text })}><Heart fill={card.favorite ? 'currentColor' : 'none'} /></button>;
  }

  function sortLabel(key: SortKey) {
    if (key === 'front') return deck?.front_label ?? '';
    if (key === 'back') return deck?.back_label ?? '';
    const metadata = metadataFields.find(({ key: field }) => field === key);
    return metadata ? t(metadata.label) : t(`cards.sort.${key}` as MessageKey);
  }

  function columnHeader(key: SortKey) {
    const active = sortBy === key;
    return <th key={key} scope="col" aria-sort={active ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}><button type="button" onClick={() => updateParams({ sort: key, order: active && sortDirection === 'asc' ? 'desc' : 'asc' })}>{sortLabel(key)}{active && (sortDirection === 'asc' ? <ArrowUp /> : <ArrowDown />)}</button></th>;
  }

  if (decks.loading) return <PageLoading label={t('common.decksLoading')} />;
  if (!decks.data) return <PageError message={decks.error} retry={decks.reload} />;
  if (!deck) return <main className="page-wrap"><section className="empty-state panel"><BookOpen /><h2>{t('cards.noDeck')}</h2><p>{t('cards.noDeckText')}</p></section></main>;

  return <main className="page-wrap vocabulary-page">
    <header className="page-header"><p className="section-kicker">{t('cards.kicker')}</p><h1>{t('cards.title')}</h1><p>{t('cards.intro', { deck: deck.title, count: number(deck.card_count) })}</p></header>
    <section className="catalog-controls panel">
      <label className="search-field"><Search /><input value={query} onChange={(event) => updateParams({ q: event.target.value })} placeholder={t('cards.searchPlaceholder', { front: deck.front_label, back: deck.back_label })} aria-label={t('cards.searchLabel')} /></label>
      <div className="select-wrap"><select aria-label={t('cards.chooseDeck')} value={deck.id} onChange={(event) => { setSelected(null); updateParams({ deck: event.target.value, section: null }); }}>{decks.data.map((entry) => <option key={entry.id} value={entry.id}>{entry.title}</option>)}</select><ChevronDown /></div>
      <div className="select-wrap"><select aria-label={t('cards.filterSection')} value={sectionId} onChange={(event) => updateParams({ section: event.target.value })}><option value="">{t('common.allSections')}</option>{sections.data?.map((section) => <option key={section.id} value={section.id}>{section.title}</option>)}</select><ChevronDown /></div>
      <div className="filter-row">{filters.map((item) => <button type="button" key={item.value} aria-pressed={filter === item.value} className={filter === item.value ? 'selected' : ''} onClick={() => updateParams({ state: item.value })}>{t(item.label)}</button>)}</div>
      <div className="catalog-view-controls">
        <div className="view-toggle" role="group" aria-label={t('cards.view')}>
          <button type="button" aria-pressed={view === 'grid'} onClick={() => updateParams({ view: 'grid' }, false)}><LayoutGrid /> {t('cards.viewGrid')}</button>
          <button type="button" aria-pressed={view === 'list'} onClick={() => updateParams({ view: 'list' }, false)}><List /> {t('cards.viewList')}</button>
        </div>
        <label>{t('cards.sortBy')}<select value={sortBy} onChange={(event) => updateParams({ sort: event.target.value })}>{sortKeys.map((key) => <option key={key} value={key}>{sortLabel(key)}</option>)}</select></label>
        <label>{t('cards.sortDirection')}<select value={sortDirection} onChange={(event) => updateParams({ order: event.target.value })}><option value="asc">{t('cards.ascending')}</option><option value="desc">{t('cards.descending')}</option></select></label>
      </div>
      <p className="difficulty-hint">{t('cards.difficultyHint')}</p>
    </section>
    {sections.error && <PageError message={sections.error} retry={sections.reload} />}
    {actionError && <p className="form-error" role="alert">{actionError}</p>}
    <div className="catalog-summary"><p>{data ? t(data.total === 1 ? 'cards.foundOne' : 'cards.foundMany', { count: number(data.total) }) : t('common.cardsLoading')}</p>{cards.loading && <span className="spinner mini-loader" />}</div>
    {cards.error ? <PageError message={cards.error} retry={cards.reload} /> : data && <div aria-busy={cards.loading}>
      {data.items.length > 0 ? view === 'list' ? <div className="vocabulary-table-scroll panel" role="region" aria-label={t('cards.viewList')} tabIndex={0}>
        <table className="vocabulary-table"><caption className="sr-only">{t('cards.title')}</caption><thead><tr>{sortKeys.filter((key) => key !== 'original').map(columnHeader)}<th scope="col">{t('cards.favorites')}</th></tr></thead>
          <tbody>{data.items.map((card) => <tr key={card.id}>
            <th scope="row"><button type="button" className="word-detail-link" lang={deck.front_language} onClick={() => setSelected(card)}>{card.front_text}</button></th>
            <td lang={deck.back_language}>{card.back_text}</td>
            {metadataFields.map(({ key }) => <td key={key}>{metadataValue(card.metadata, key) || '—'}</td>)}
            <td>{card.section_title ?? '—'}</td><td>{difficultyControl(card)}</td><td><em className={`status ${card.status}`}>{t(statusLabels[card.status])}</em></td>
            <td>{favoriteControl(card)}</td>
          </tr>)}</tbody>
        </table>
      </div> : <section className="vocabulary-grid">{data.items.map((card) => <article key={card.id} className="vocabulary-card panel">
        <button className="card-open" onClick={() => setSelected(card)}><div><span>{card.section_title ?? deck.title}</span><em className={`status ${card.status}`}>{t(statusLabels[card.status])}</em></div><h2 lang={deck.front_language}>{card.front_text}</h2><p lang={deck.back_language}>{card.back_text}</p></button>
        <CardMetadata metadata={card.metadata} />{difficultyControl(card)}{favoriteControl(card, 'favorite')}
      </article>)}</section> : <section className="empty-state panel"><BookOpen /><h2>{t('cards.noneFound')}</h2><p>{t('cards.noneFoundText')}</p><button className="button secondary" onClick={() => updateParams({ q: null, state: null, section: null })}>{t('cards.resetFilters')}</button></section>}
      {data.pages > 1 && <nav className="pagination" aria-label={t('cards.pagination')}><button disabled={page <= 1 || cards.loading} onClick={() => updateParams({ page: String(page - 1) }, false)}><ArrowLeft /> {t('common.back')}</button><span>{t('common.pageOf', { page: number(data.page), pages: number(data.pages) })}</span><button disabled={page >= data.pages || cards.loading} onClick={() => updateParams({ page: String(page + 1) }, false)}>{t('common.next')} <ArrowRight /></button></nav>}
    </div>}
    {selected && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}><section ref={dialogRef} tabIndex={-1} className="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="card-title">
      <button data-autofocus className="icon-button close" onClick={closeDialog} aria-label={t('common.close')}><X /></button><p className="section-kicker">{selected.section_title ?? deck.title}</p><h2 id="card-title" lang={deck.front_language}>{selected.front_text}</h2><p className="detail-translation" lang={deck.back_language}>{selected.back_text}</p><CardMetadata metadata={selected.metadata} />
      {difficultyControl(selected)}{actionError && <p className="form-error" role="alert">{actionError}</p>}
      <div className="dialog-actions">{favoriteControl(selected)}<Link className="button primary" to={`/lernen?deck=${deck.id}${selected.section_id ? `&section=${selected.section_id}` : ''}`}><Sparkles /> {t('cards.studySection')}</Link></div>
    </section></div>}
  </main>;
}
