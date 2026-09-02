import { ArrowLeft, ArrowRight, BookOpen, ChevronDown, Heart, Search, Sparkles, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { PageError, PageLoading } from '../components/PageState';
import { useModalDialog } from '../hooks/useModalDialog';
import type { Card, CardPage, CardStatus, Deck, Section } from '../types';
import { useI18n } from '../i18n';
import type { MessageKey } from '../i18n/messages';

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
  new: 'cards.statusNew',
  learning: 'cards.statusLearning',
  familiar: 'cards.statusFamiliar',
  mastered: 'cards.statusMastered',
  difficult: 'cards.statusDifficult',
};

export function VocabularyPage() {
  const { user } = useAuth();
  const { number, t } = useI18n();
  const [params, setParams] = useSearchParams();
  const decks = useResource(() => api<Deck[]>('/decks'));
  const requestedDeck = params.get('deck');
  const fallbackDeckId = decks.data?.find((deck) => deck.id === user?.selected_deck_id)?.id ?? decks.data?.[0]?.id ?? '';
  const deckId = decks.data?.some((deck) => deck.id === requestedDeck) ? requestedDeck! : fallbackDeckId;
  const sectionId = params.get('section') ?? '';
  const [query, setQuery] = useState(params.get('q') ?? '');
  const [filter, setFilter] = useState(params.get('state') ?? 'all');
  const [page, setPage] = useState(Number(params.get('page') ?? 1));
  const [data, setData] = useState<CardPage | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<Card | null>(null);
  const closeDialog = () => setSelected(null);
  const dialogRef = useModalDialog<HTMLElement>(Boolean(selected), closeDialog);
  const deck = decks.data?.find((entry) => entry.id === deckId) ?? null;

  useEffect(() => {
    if (!deckId) { setSections([]); return; }
    let active = true;
    void api<Section[]>(`/sections?deck_id=${deckId}`).then((value) => { if (active) setSections(value); });
    return () => { active = false; };
  }, [deckId]);

  useEffect(() => {
    if (!deckId) { setData(null); return; }
    let active = true;
    const search = new URLSearchParams({ deck_id: deckId, page: String(page), page_size: '36', state: filter });
    if (query.trim()) search.set('q', query.trim());
    if (sectionId) search.set('section_id', sectionId);
    setLoading(true); setError('');
    void api<CardPage>(`/cards?${search}`)
      .then((value) => { if (active) setData(value); })
      .catch((caught: unknown) => { if (active) setError(caught instanceof ApiError ? caught.message : t('cards.loadError')); })
      .finally(() => { if (active) setLoading(false); });
    const next = new URLSearchParams();
    next.set('deck', deckId);
    if (query.trim()) next.set('q', query.trim());
    if (sectionId) next.set('section', sectionId);
    if (filter !== 'all') next.set('state', filter);
    if (page > 1) next.set('page', String(page));
    setParams(next, { replace: true });
    return () => { active = false; };
  }, [deckId, filter, page, query, revision, sectionId, setParams]);

  function chooseDeck(value: string) {
    const next = new URLSearchParams(params);
    next.set('deck', value); next.delete('section'); next.delete('page');
    setPage(1); setParams(next);
  }

  function chooseSection(value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set('section', value); else next.delete('section');
    next.delete('page'); setPage(1); setParams(next);
  }

  async function toggleFavorite(card: Card) {
    const favorite = !card.favorite;
    setData((current) => current ? { ...current, items: current.items.map((item) => item.id === card.id ? { ...item, favorite } : item) } : current);
    setSelected((current) => current?.id === card.id ? { ...current, favorite } : current);
    try {
      await api(`/favorites/${card.id}`, { method: favorite ? 'PUT' : 'DELETE' });
      if (filter === 'favorites' && !favorite) setRevision((value) => value + 1);
    } catch {
      setRevision((value) => value + 1);
    }
  }

  if (decks.loading) return <PageLoading label={t('common.decksLoading')} />;
  if (!decks.data) return <PageError message={decks.error} retry={() => void decks.reload()} />;
  if (!deck) return <main className="page-wrap"><section className="empty-state panel"><BookOpen /><h2>{t('cards.noDeck')}</h2><p>{t('cards.noDeckText')}</p></section></main>;

  const metadataEntries = selected
    ? Object.entries(selected.metadata).filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
    : [];

  return (
    <main className="page-wrap vocabulary-page">
      <header className="page-header"><p className="section-kicker">{t('cards.kicker')}</p><h1>{t('cards.title')}</h1><p>{t('cards.intro', { deck: deck.title, count: number(deck.card_count) })}</p></header>
      <section className="catalog-controls panel">
        <label className="search-field"><Search /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder={t('cards.searchPlaceholder', { front: deck.front_label, back: deck.back_label })} aria-label={t('cards.searchLabel')} /></label>
        <div className="select-wrap"><select aria-label={t('cards.chooseDeck')} value={deck.id} onChange={(event) => chooseDeck(event.target.value)}>{decks.data.map((entry) => <option key={entry.id} value={entry.id}>{entry.title}</option>)}</select><ChevronDown /></div>
        <div className="select-wrap"><select aria-label={t('cards.filterSection')} value={sectionId} onChange={(event) => chooseSection(event.target.value)}><option value="">{t('common.allSections')}</option>{sections.map((section) => <option key={section.id} value={section.id}>{section.title}</option>)}</select><ChevronDown /></div>
        <div className="filter-row">{filters.map((item) => <button type="button" key={item.value} className={filter === item.value ? 'selected' : ''} onClick={() => { setFilter(item.value); setPage(1); }}>{t(item.label)}</button>)}</div>
      </section>
      <div className="catalog-summary"><p>{data ? t(data.total === 1 ? 'cards.foundOne' : 'cards.foundMany', { count: number(data.total) }) : t('common.cardsLoading')}</p>{loading && <span className="spinner mini-loader" />}</div>
      {error ? <PageError message={error} retry={() => setRevision((value) => value + 1)} /> : data && (
        <>
          {data.items.length ? <section className="vocabulary-grid">{data.items.map((card) => <article key={card.id} className="vocabulary-card panel"><button className="card-open" onClick={() => setSelected(card)}><div><span>{card.section_title ?? deck.title}</span><em className={`status ${card.status}`}>{t(statusLabels[card.status])}</em></div><h2 lang={deck.front_language}>{card.front_text}</h2><p lang={deck.back_language}>{card.back_text}</p></button><button className={card.favorite ? 'favorite active' : 'favorite'} onClick={() => void toggleFavorite(card)} aria-label={t(card.favorite ? 'cards.removeFavorite' : 'cards.addFavorite', { card: card.front_text })}><Heart fill={card.favorite ? 'currentColor' : 'none'} /></button></article>)}</section> : <section className="empty-state panel"><BookOpen /><h2>{t('cards.noneFound')}</h2><p>{t('cards.noneFoundText')}</p><button className="button secondary" onClick={() => { setQuery(''); setFilter('all'); chooseSection(''); }}>{t('cards.resetFilters')}</button></section>}
          {data.pages > 1 && <nav className="pagination" aria-label={t('cards.pagination')}><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ArrowLeft /> {t('common.back')}</button><span>{t('common.pageOf', { page: number(data.page), pages: number(data.pages) })}</span><button disabled={page >= data.pages} onClick={() => setPage((value) => value + 1)}>{t('common.next')} <ArrowRight /></button></nav>}
        </>
      )}

      {selected && <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}><section ref={dialogRef} tabIndex={-1} className="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="card-title"><button data-autofocus className="icon-button close" onClick={closeDialog} aria-label={t('common.close')}><X /></button><p className="section-kicker">{selected.section_title ?? deck.title}</p><h2 id="card-title" lang={deck.front_language}>{selected.front_text}</h2><p className="detail-translation" lang={deck.back_language}>{selected.back_text}</p>{metadataEntries.length > 0 && <dl>{metadataEntries.map(([key, value]) => <div key={key} className="detail-row"><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>}<div className="dialog-actions"><button className={selected.favorite ? 'button secondary active-favorite' : 'button secondary'} onClick={() => void toggleFavorite(selected)}><Heart fill={selected.favorite ? 'currentColor' : 'none'} /> {selected.favorite ? t('cards.favorited') : t('cards.favorite')}</button><Link className="button primary" to={`/lernen?deck=${deck.id}${selected.section_id ? `&section=${selected.section_id}` : ''}`}><Sparkles /> {t('cards.studySection')}</Link></div></section></div>}
    </main>
  );
}
