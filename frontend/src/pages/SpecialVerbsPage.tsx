import { ArrowLeft, ArrowRight, FileUp, Search, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { PageError, PageLoading } from '../components/PageState';
import { useI18n } from '../i18n';
import type { MessageKey } from '../i18n/messages';
import type { CardPage, Deck, ImportResult, Section } from '../types';

const matcher = 'latin-principal-parts-v1';
type VerbRow = { line: number; infinitive: string; present: string; perfect: string; supine: string; meaning: string; conjugation: string; perfect_group: string };
type CsvPreview = { rows: VerbRow[]; errors: { line: number; code: string }[]; duplicate_count: number; section_count: number };
const columns = ['infinitive', 'present', 'perfect', 'supine', 'meaning'] as const;
const issueKeys: Record<string, MessageKey> = {
  columns: 'verbs.error.columns', required: 'verbs.error.required', length: 'verbs.error.length',
  heading: 'verbs.error.heading', duplicate: 'verbs.error.duplicate', syntax: 'verbs.error.syntax',
  empty: 'verbs.error.empty', too_large: 'verbs.error.tooLarge', too_many: 'verbs.error.tooMany',
  encoding: 'verbs.error.encoding', answer: 'verbs.error.answer',
};

function CsvImport({ onImported }: { onImported(deck: Deck): void }) {
  const { t, number } = useI18n();
  const [title, setTitle] = useState('');
  const [csv, setCsv] = useState('');
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function readFile(file?: File) {
    setPreview(null); setResult(null); setError(''); setCsv('');
    if (!file) return;
    if (file.size > 1_000_000) { setError(t('verbs.error.tooLarge')); return; }
    setBusy(true);
    try {
      const bytes = await file.arrayBuffer();
      let text: string;
      try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
      catch { text = new TextDecoder('windows-1252').decode(bytes); }
      const nextTitle = file.name.replace(/\.csv$/i, '').slice(0, 120).trim() || t('verbs.title');
      setTitle(nextTitle);
      const parsed = await api<CsvPreview>('/admin/special-verbs/preview', {
        method: 'POST', body: JSON.stringify({ title: nextTitle, csv_text: text }),
      });
      setCsv(text); setPreview(parsed);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t('verbs.readError'));
    } finally { setBusy(false); }
  }

  async function importCsv() {
    if (!preview || preview.errors.length || !title.trim() || busy) return;
    setBusy(true); setError('');
    try {
      const imported = await api<ImportResult>('/admin/special-verbs/import', {
        method: 'POST', body: JSON.stringify({ title: title.trim(), csv_text: csv }),
      });
      setResult(imported); setPreview(null); setCsv(''); onImported(imported.deck);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t('common.genericError'));
    } finally { setBusy(false); }
  }

  return <section className="panel admin-editor verb-import">
    <header><div><h2>{t('verbs.import')}</h2><p>{t('verbs.format')}</p><p>{t('verbs.shared')}</p></div><FileUp aria-hidden="true" /></header>
    <label className="file-field"><span>{t('verbs.file')}</span><input type="file" accept=".csv,text/csv" disabled={busy} onChange={(event) => { void readFile(event.target.files?.[0]); event.target.value = ''; }} /></label>
    {busy && <p role="status">{t('common.loading')}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {preview && <div className="verb-preview">
      {preview.errors.length > 0 ? <div className="form-error" role="alert"><strong>{t('verbs.fixErrors')}</strong><ul>{preview.errors.map((issue, index) => <li key={index}>{t('verbs.line', { line: number(issue.line) })}: {t(issueKeys[issue.code] ?? 'verbs.error.answer')}</li>)}</ul></div> : <>
        <p>{t('verbs.previewCount', { count: number(preview.rows.length), groups: number(preview.section_count) })}</p>
        {preview.duplicate_count > 0 && <p>{t('verbs.duplicates', { count: number(preview.duplicate_count) })}</p>}
        <div className="admin-form-grid"><label><span>{t('admin.titleField')}</span><input value={title} maxLength={120} disabled={busy} onChange={(event) => setTitle(event.target.value)} /></label></div>
        <div className="vocabulary-table-scroll" role="region" aria-label={t('verbs.preview')} tabIndex={0}><table className="vocabulary-table"><caption>{t('verbs.preview')}</caption><thead><tr>{columns.map((key) => <th scope="col" key={key}>{t(`verbs.${key}`)}</th>)}</tr></thead><tbody>{preview.rows.slice(0, 10).map((row) => <tr key={row.line}>{columns.map((key) => <td key={key} lang={key === 'meaning' ? 'de' : 'la'}>{row[key]}</td>)}</tr>)}</tbody></table></div>
        <button className="button primary" disabled={busy || !title.trim()} onClick={() => void importCsv()}><FileUp />{t('verbs.publish')}</button>
      </>}
    </div>}
    {result && <p role="status">{t(result.unchanged ? 'verbs.alreadyImported' : 'verbs.imported', { count: number(result.deck.card_count) })} {result.deck.status !== 'published' && <Link to="/admin">{t('verbs.unpublished')}</Link>}</p>}
  </section>;
}

function VerbCollection({ deck }: { deck: Deck }) {
  const { t, number } = useI18n();
  const [query, setQuery] = useState('');
  const [sectionId, setSectionId] = useState('');
  const [page, setPage] = useState(1);
  const sections = useResource(() => api<Section[]>(`/sections?deck_id=${deck.id}`), deck.id);
  const search = new URLSearchParams({ deck_id: deck.id, q: query, page: String(page), page_size: '50' });
  if (sectionId) search.set('section_id', sectionId);
  const cards = useResource(() => api<CardPage>(`/cards?${search}`), search.toString());
  const learn = new URLSearchParams({ deck: deck.id });
  if (sectionId) learn.set('section', sectionId);

  return <section className="verb-collection">
    <div className="panel admin-editor">
      <header><div><h2>{deck.title}</h2><p>{t('verbs.previewCount', { count: number(deck.card_count), groups: number(deck.section_count) })}</p></div><Sparkles aria-hidden="true" /></header>
      <p className="verb-hint">{t('verbs.practiceHelp')}</p>
      <div className="verb-filters">
        <label className="search-field"><Search aria-hidden="true" /><input aria-label={t('verbs.search')} placeholder={t('verbs.search')} maxLength={100} value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} /></label>
        <label><span className="sr-only">{t('verbs.group')}</span><select value={sectionId} disabled={sections.loading || Boolean(sections.error)} onChange={(event) => { setSectionId(event.target.value); setPage(1); }}><option value="">{t('common.allSections')}</option>{sections.data?.map((section) => <option key={section.id} value={section.id}>{section.title}</option>)}</select></label>
      </div>
      {sections.error && <PageError message={sections.error} retry={sections.reload} />}
      <div className="verb-practice-actions">
        <Link className="button primary" to={`/lernen?${learn}&direction=forward`}>{t('verbs.forward')} <ArrowRight /></Link>
        <Link className="button secondary" to={`/lernen?${learn}&direction=reverse`}>{t('verbs.reverse')} <ArrowRight /></Link>
        <Link className="button secondary" to={`/lernen?${learn}&direction=mixed`}>{t('settings.mixed')}</Link>
        <Link className="button subtle" to={`/vokabeln?deck=${deck.id}`}>{t('verbs.manageProgress')}</Link>
      </div>
      <p className="verb-hint">{t('verbs.practiceScope')}</p>
    </div>
    {cards.loading ? <PageLoading label={t('common.cardsLoading')} /> : cards.error || !cards.data ? <PageError message={cards.error} retry={cards.reload} /> : <>
      <div className="vocabulary-table-scroll panel" role="region" aria-label={t('verbs.title')} tabIndex={0}><table className="vocabulary-table verb-table"><caption className="sr-only">{t('verbs.title')}</caption><thead><tr>{columns.map((key) => <th scope="col" key={key}>{t(`verbs.${key}`)}</th>)}<th scope="col">{t('verbs.group')}</th></tr></thead><tbody>{cards.data.items.map((card) => <tr key={card.id}><td lang="la">{card.front_text.split(',')[0]}</td><td lang="la">{card.front_text.split(',')[1]}</td><td lang="la">{card.front_text.split(',')[2]}</td><td lang="la">{card.front_text.split(',')[3]}</td><td lang="de">{card.back_text}</td><td>{card.section_title}</td></tr>)}</tbody></table></div>
      {cards.data.items.length === 0 && <p className="empty-state">{t('verbs.noResults')}</p>}
      {cards.data.pages > 1 && <nav className="pagination" aria-label={t('cards.pagination')}><button disabled={page <= 1} onClick={() => setPage(page - 1)}><ArrowLeft />{t('common.back')}</button><span>{t('common.pageOf', { page: number(page), pages: number(cards.data.pages) })}</span><button disabled={page >= cards.data.pages} onClick={() => setPage(page + 1)}>{t('common.next')}<ArrowRight /></button></nav>}
    </>}
  </section>;
}

export function SpecialVerbsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const decks = useResource(() => api<Deck[]>('/decks'));
  const collections = decks.data?.filter((deck) => deck.front_matcher === matcher) ?? [];
  const selected = collections.find((deck) => deck.id === params.get('deck')) ?? collections[0];

  return <main className="page-wrap special-verbs-page">
    <header className="page-header"><p className="section-kicker">{t('verbs.kicker')}</p><h1>{t('verbs.title')}</h1><p>{t('verbs.intro')}</p></header>
    {user?.role === 'admin' ? <CsvImport onImported={(deck) => { decks.reload(); setParams({ deck: deck.id }, { replace: true }); }} /> : <p className="verb-hint">{t('verbs.adminOnly')}</p>}
    {decks.loading ? <PageLoading label={t('common.decksLoading')} /> : decks.error ? <PageError message={decks.error} retry={decks.reload} /> : !selected ? <section className="empty-state panel"><Sparkles /><h2>{t('verbs.empty')}</h2><p>{t('verbs.emptyHelp')}</p></section> : <>
      <label className="deck-select"><span>{t('common.deck')}</span><div className="select-wrap"><select value={selected.id} onChange={(event) => setParams({ deck: event.target.value })}>{collections.map((deck) => <option key={deck.id} value={deck.id}>{deck.title}</option>)}</select></div></label>
      <VerbCollection key={selected.id} deck={selected} />
    </>}
  </main>;
}
