import {
  Archive,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  FileUp,
  Layers3,
  Pencil,
  Plus,
  Save,
  Search,
  ShieldCheck,
  UsersRound,
} from 'lucide-react';
import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { PageError, PageLoading } from '../components/PageState';
import type {
  AdminUser,
  AdminUserPage,
  Card,
  CardPage,
  Deck,
  DeckStatus,
  ImportResult,
  MatcherProfile,
  Section,
} from '../types';
import { useI18n } from '../i18n';

type DeckForm = {
  slug: string;
  title: string;
  description: string;
  front_label: string;
  back_label: string;
  front_language: string;
  back_language: string;
  front_matcher: MatcherProfile;
  back_matcher: MatcherProfile;
  license: string;
  attribution: string;
};

const emptyDeck: DeckForm = {
  slug: '', title: '', description: '', front_label: '', back_label: '',
  front_language: '', back_language: '', front_matcher: 'generic-v1',
  back_matcher: 'generic-v1', license: '', attribution: '',
};

type CardForm = {
  stable_key: string;
  section_id: string;
  sort_order: number;
  front_text: string;
  back_text: string;
  front_answers: string;
  back_answers: string;
  metadata: string;
  active: boolean;
};

const emptyCard: CardForm = {
  stable_key: '', section_id: '', sort_order: 1, front_text: '', back_text: '',
  front_answers: '', back_answers: '', metadata: '{}', active: true,
};

function nullable(value: string) {
  return value.trim() || null;
}

function aliases(value: string) {
  return value.split('\n').map((entry) => entry.trim()).filter(Boolean);
}

function deckPayload(form: DeckForm, includeSlug: boolean) {
  return {
    ...(includeSlug ? { slug: form.slug } : {}),
    title: form.title,
    description: nullable(form.description),
    front_label: form.front_label,
    back_label: form.back_label,
    front_language: form.front_language,
    back_language: form.back_language,
    front_matcher: form.front_matcher,
    back_matcher: form.back_matcher,
    license: nullable(form.license),
    attribution: nullable(form.attribution),
  };
}

export function AdminPage() {
  const { user } = useAuth();
  const { date, number, t } = useI18n();
  const decks = useResource(() => api<Deck[]>('/admin/decks'));
  const [userPage, setUserPage] = useState(1);
  const [userQuery, setUserQuery] = useState('');
  const [promotingUserId, setPromotingUserId] = useState<string | null>(null);
  const [promotedUserIds, setPromotedUserIds] = useState<Record<string, true>>({});
  const users = useResource(
    () => api<AdminUserPage>(`/admin/users?page=${userPage}&page_size=25&q=${encodeURIComponent(userQuery)}`),
    `${userPage}:${userQuery}`,
  );
  const [selectedDeckId, setSelectedDeckId] = useState('');
  const [deckForm, setDeckForm] = useState<DeckForm>(emptyDeck);
  const [showCreateDeck, setShowCreateDeck] = useState(false);
  const [sectionEdit, setSectionEdit] = useState<Section | null>(null);
  const [sectionFormOpen, setSectionFormOpen] = useState(false);
  const [sectionKey, setSectionKey] = useState('');
  const [sectionTitle, setSectionTitle] = useState('');
  const [sectionOrder, setSectionOrder] = useState(1);
  const [cardEdit, setCardEdit] = useState<Card | null>(null);
  const [cardFormOpen, setCardFormOpen] = useState(false);
  const [cardForm, setCardForm] = useState<CardForm>(emptyCard);
  const [cardPage, setCardPage] = useState(1);
  const [cardQuery, setCardQuery] = useState('');
  const [importText, setImportText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const selectedDeck = decks.data?.find((deck) => deck.id === selectedDeckId) ?? decks.data?.[0] ?? null;
  const sections = useResource(
    () => selectedDeck ? api<Section[]>(`/admin/decks/${selectedDeck.id}/sections`) : Promise.resolve([]),
    selectedDeck?.id ?? 'none',
  );
  const cards = useResource(
    () => selectedDeck
      ? api<CardPage>(`/admin/decks/${selectedDeck.id}/cards?page=${cardPage}&page_size=50&q=${encodeURIComponent(cardQuery)}`)
      : Promise.resolve({ items: [], page: 1, page_size: 50, total: 0, pages: 1 }),
    `${selectedDeck?.id ?? 'none'}:${cardPage}:${cardQuery}`,
  );

  useEffect(() => {
    if (!selectedDeckId && decks.data?.[0]) setSelectedDeckId(decks.data[0].id);
  }, [decks.data, selectedDeckId]);

  useEffect(() => {
    if (!selectedDeck) return;
    setDeckForm({
      slug: selectedDeck.slug,
      title: selectedDeck.title,
      description: selectedDeck.description ?? '',
      front_label: selectedDeck.front_label,
      back_label: selectedDeck.back_label,
      front_language: selectedDeck.front_language,
      back_language: selectedDeck.back_language,
      front_matcher: selectedDeck.front_matcher,
      back_matcher: selectedDeck.back_matcher,
      license: selectedDeck.license ?? '',
      attribution: selectedDeck.attribution ?? '',
    });
    setCardEdit(null);
    setCardForm(emptyCard);
  }, [selectedDeck]);

  if (user?.role !== 'admin') return <Navigate to="/" replace />;
  if (decks.loading) return <PageLoading label={t('admin.loading')} />;
  if (!decks.data) return <PageError message={decks.error} retry={() => void decks.reload()} />;

  function showMessage(message: string) {
    setNotice(message); setError(''); window.setTimeout(() => setNotice(''), 3500);
  }

  function handleError(caught: unknown, fallback: string) {
    setError(caught instanceof ApiError ? caught.message : fallback); setNotice('');
  }

  async function promoteUser(account: AdminUser) {
    setPromotingUserId(account.id); setError('');
    try {
      const promoted = await api<AdminUser>(`/admin/users/${account.id}/promote`, {
        method: 'POST',
      });
      setPromotedUserIds((current) => ({ ...current, [promoted.id]: true }));
      users.reload();
      showMessage(t('admin.userPromoted', { name: promoted.display_name }));
    } catch (caught) {
      handleError(caught, t('admin.userPromoteError'));
    } finally {
      setPromotingUserId(null);
    }
  }

  async function createDeck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const created = await api<Deck>('/admin/decks', { method: 'POST', body: JSON.stringify(deckPayload(deckForm, true)) });
      setShowCreateDeck(false); setSelectedDeckId(created.id); await decks.reload(); showMessage(t('admin.deckCreated'));
    } catch (caught) { handleError(caught, t('admin.deckCreateError')); }
    finally { setBusy(false); }
  }

  async function saveDeck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedDeck) return; setBusy(true); setError('');
    try {
      await api(`/admin/decks/${selectedDeck.id}`, { method: 'PATCH', body: JSON.stringify(deckPayload(deckForm, false)) });
      await decks.reload(); showMessage(t('admin.deckSaved'));
    } catch (caught) { handleError(caught, t('admin.deckSaveError')); }
    finally { setBusy(false); }
  }

  async function setStatus(status: DeckStatus) {
    if (!selectedDeck) return; setBusy(true); setError('');
    try {
      await api(`/admin/decks/${selectedDeck.id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) });
      await decks.reload(); showMessage(status === 'published' ? t('admin.deckPublished') : t('admin.statusChanged'));
    } catch (caught) { handleError(caught, t('admin.statusError')); }
    finally { setBusy(false); }
  }

  function editSection(section?: Section) {
    setSectionFormOpen(true);
    setSectionEdit(section ?? null);
    setSectionKey(section?.stable_key ?? '');
    setSectionTitle(section?.title ?? '');
    setSectionOrder(section?.sort_order ?? ((sections.data?.length ?? 0) + 1));
  }

  async function saveSection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedDeck) return; setBusy(true); setError('');
    try {
      if (sectionEdit) {
        await api(`/admin/decks/${selectedDeck.id}/sections/${sectionEdit.id}`, { method: 'PATCH', body: JSON.stringify({ title: sectionTitle, sort_order: sectionOrder, active: sectionEdit.active }) });
      } else {
        await api(`/admin/decks/${selectedDeck.id}/sections`, { method: 'POST', body: JSON.stringify({ stable_key: sectionKey, title: sectionTitle, sort_order: sectionOrder }) });
      }
      setSectionFormOpen(false); setSectionEdit(null); setSectionKey(''); setSectionTitle('');
      await Promise.all([sections.reload(), decks.reload()]); showMessage(t('admin.sectionSaved'));
    } catch (caught) { handleError(caught, t('admin.sectionSaveError')); }
    finally { setBusy(false); }
  }

  function editCard(card?: Card) {
    setCardFormOpen(true);
    setCardEdit(card ?? null);
    setCardForm(card ? {
      stable_key: card.stable_key,
      section_id: card.section_id ?? '',
      sort_order: card.sort_order,
      front_text: card.front_text,
      back_text: card.back_text,
      front_answers: card.front_answers.join('\n'),
      back_answers: card.back_answers.join('\n'),
      metadata: JSON.stringify(card.metadata, null, 2),
      active: card.active,
    } : { ...emptyCard, sort_order: (cards.data?.total ?? 0) + 1, section_id: sections.data?.[0]?.id ?? '' });
  }

  async function saveCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedDeck) return; setBusy(true); setError('');
    try {
      const parsedMetadata = JSON.parse(cardForm.metadata) as unknown;
      if (!parsedMetadata || Array.isArray(parsedMetadata) || typeof parsedMetadata !== 'object') throw new Error('metadata');
      const body = {
        ...(!cardEdit ? { stable_key: cardForm.stable_key } : {}),
        section_id: cardForm.section_id || null,
        sort_order: cardForm.sort_order,
        front_text: cardForm.front_text,
        back_text: cardForm.back_text,
        front_answers: aliases(cardForm.front_answers),
        back_answers: aliases(cardForm.back_answers),
        metadata: parsedMetadata,
        ...(cardEdit ? { active: cardForm.active } : {}),
      };
      const path = cardEdit ? `/admin/decks/${selectedDeck.id}/cards/${cardEdit.id}` : `/admin/decks/${selectedDeck.id}/cards`;
      await api(path, { method: cardEdit ? 'PATCH' : 'POST', body: JSON.stringify(body) });
      setCardFormOpen(false); setCardEdit(null); setCardForm(emptyCard);
      await Promise.all([cards.reload(), decks.reload(), sections.reload()]); showMessage(t('admin.cardSaved'));
    } catch (caught) {
      if (caught instanceof SyntaxError || (caught instanceof Error && caught.message === 'metadata')) setError(t('admin.metadataError'));
      else handleError(caught, t('admin.cardSaveError'));
    } finally { setBusy(false); }
  }

  async function archiveCard(card: Card) {
    if (!selectedDeck) return; setBusy(true); setError('');
    try {
      await api(`/admin/decks/${selectedDeck.id}/cards/${card.id}`, { method: 'DELETE' });
      await Promise.all([cards.reload(), decks.reload(), sections.reload()]); showMessage(t('admin.cardArchived'));
    } catch (caught) { handleError(caught, t('admin.cardArchiveError')); }
    finally { setBusy(false); }
  }

  async function importDeck(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const manifest = JSON.parse(importText) as unknown;
      const result = await api<ImportResult>('/admin/import', { method: 'POST', body: JSON.stringify(manifest) });
      setImportText(''); setSelectedDeckId(result.deck.id); await decks.reload();
      showMessage(result.unchanged ? t('admin.importUnchanged') : t('admin.importResult', { created: number(result.created_cards), updated: number(result.updated_cards), archived: number(result.archived_cards) }));
    } catch (caught) {
      if (caught instanceof SyntaxError) setError(t('admin.importJsonError'));
      else handleError(caught, t('admin.importError'));
    } finally { setBusy(false); }
  }

  async function loadImportFile(file: File | undefined) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { setError(t('admin.importSizeError')); return; }
    setImportText(await file.text());
  }

  return <main className="page-wrap admin-page">
    <header className="page-header horizontal"><div><p className="section-kicker">{t('admin.kicker')}</p><h1>{t('admin.title')}</h1><p>{t('admin.intro')}</p></div><button className="button primary" onClick={() => { setDeckForm(emptyDeck); setShowCreateDeck(true); }}><Plus /> {t('admin.newDeck')}</button></header>
    {notice && <p className="admin-notice"><Check /> {notice}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}

    <section className="panel admin-editor admin-users">
      <header><div><h2>{t('admin.users')}</h2><p>{t('admin.usersText')}</p></div>{users.data && <span className="admin-total"><UsersRound /> {number(users.data.total)}</span>}</header>
      <label className="search-field"><Search /><input value={userQuery} onChange={(event) => { setUserQuery(event.target.value); setUserPage(1); }} placeholder={t('admin.searchUsers')} /></label>
      {users.loading ? <PageLoading /> : !users.data ? <PageError message={users.error} retry={() => void users.reload()} /> : users.data.items.length === 0 ? <p className="admin-users-empty">{t('admin.noUsers')}</p> : <div className="admin-user-list">
        {users.data.items.map((account) => {
          const isAdmin = account.role === 'admin' || promotedUserIds[account.id];
          return <article key={account.id}>
            <div className="admin-user-identity"><span className="admin-user-icon"><UsersRound /></span><div><strong>{account.display_name}{account.id === user.id && <em>{t('admin.you')}</em>}</strong><small>{account.email} · {t('admin.joined', { date: date(account.created_at) })}</small></div></div>
            <div className="admin-user-actions"><span className={`user-role ${isAdmin ? 'admin' : 'user'}`}>{isAdmin ? t('settings.roleAdmin') : t('settings.roleLearner')}</span>{!isAdmin && <button className="button secondary small" disabled={promotingUserId !== null} aria-label={t('admin.promoteUser', { name: account.display_name })} onClick={() => void promoteUser(account)}><ShieldCheck /> {t('admin.promote')}</button>}</div>
          </article>;
        })}
      </div>}
      {users.data && users.data.pages > 1 && <nav className="pagination"><button disabled={userPage <= 1} onClick={() => setUserPage((value) => value - 1)}><ArrowLeft /> {t('common.back')}</button><span>{t('common.pageOf', { page: number(users.data.page), pages: number(users.data.pages) })}</span><button disabled={userPage >= users.data.pages} onClick={() => setUserPage((value) => value + 1)}>{t('common.next')} <ArrowRight /></button></nav>}
    </section>

    {showCreateDeck && <section className="panel admin-editor admin-create-deck"><header><div><h2>{t('admin.newDeck')}</h2><p>{t('admin.newDeckText')}</p></div></header><form onSubmit={createDeck}><DeckFields form={deckForm} setForm={setDeckForm} includeSlug /><div className="admin-actions"><button type="button" className="button secondary" onClick={() => setShowCreateDeck(false)}>{t('common.cancel')}</button><button className="button primary" disabled={busy}><Plus /> {t('admin.createDeck')}</button></div></form></section>}

    <section className="admin-layout">
      <aside className="panel admin-deck-list"><header><h2>{t('admin.decks')}</h2><span>{number(decks.data.length)}</span></header>{decks.data.map((deck) => <button key={deck.id} className={selectedDeck?.id === deck.id ? 'selected' : ''} onClick={() => { setSelectedDeckId(deck.id); setCardPage(1); }}><span><strong>{deck.title}</strong><small>{deck.front_label} → {deck.back_label}</small></span><em className={`deck-status ${deck.status}`}>{t(deck.status === 'published' ? 'admin.statusPublished' : deck.status === 'draft' ? 'admin.statusDraft' : 'admin.statusArchived')}</em></button>)}</aside>

      <div className="admin-workspace">
        {!selectedDeck ? <section className="empty-state panel"><Layers3 /><h2>{t('admin.firstDeck')}</h2><p>{t('admin.firstDeckText')}</p></section> : <>
          <section className="panel admin-editor"><header><div><h2>{selectedDeck.title}</h2><p>{t('admin.versionCards', { version: number(selectedDeck.version), count: number(selectedDeck.card_count) })}</p></div><div className="status-actions">{selectedDeck.status !== 'published' && <button className="button primary" disabled={busy} onClick={() => void setStatus('published')}>{t('admin.publish')}</button>}{selectedDeck.status === 'published' && <button className="button secondary" disabled={busy} onClick={() => void setStatus('draft')}>{t('admin.makeDraft')}</button>}<button className="button secondary" disabled={busy} onClick={() => void setStatus('archived')}><Archive /> {t('admin.archive')}</button></div></header><form onSubmit={saveDeck}><DeckFields form={deckForm} setForm={setDeckForm} /><button className="button primary" disabled={busy}><Save /> {t('admin.saveDeck')}</button></form></section>

          <section className="panel admin-editor"><header><div><h2>{t('admin.sections')}</h2><p>{t('admin.sectionsText')}</p></div><button className="button secondary" onClick={() => editSection()}><Plus /> {t('admin.section')}</button></header><div className="admin-section-list">{sections.data?.map((section) => <button key={section.id} onClick={() => editSection(section)}><span><strong>{section.title}</strong><small>{section.stable_key} · {t(section.total === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: number(section.total) })}</small></span><Pencil /></button>)}</div>{sectionFormOpen && <form className="inline-admin-form" onSubmit={saveSection}><label><span>{t('admin.id')}</span><input value={sectionKey} disabled={Boolean(sectionEdit)} onChange={(event) => setSectionKey(event.target.value)} required pattern="[A-Za-z0-9][A-Za-z0-9._:-]*" /></label><label><span>{t('admin.titleField')}</span><input value={sectionTitle} onChange={(event) => setSectionTitle(event.target.value)} required /></label><label><span>{t('admin.order')}</span><input type="number" min={1} value={sectionOrder} onChange={(event) => setSectionOrder(Number(event.target.value))} required /></label><button className="button primary" disabled={busy}><Save /> {t('common.save')}</button></form>}</section>

          <section className="panel admin-editor"><header><div><h2>{t('cards.title')}</h2><p>{t('admin.entriesText', { count: number(cards.data?.total ?? 0) })}</p></div><button className="button primary" onClick={() => editCard()}><Plus /> {t('admin.card')}</button></header><label className="search-field"><BookOpen /><input value={cardQuery} onChange={(event) => { setCardQuery(event.target.value); setCardPage(1); }} placeholder={t('admin.searchCards')} /></label>{cardFormOpen && <CardEditor form={cardForm} setForm={setCardForm} editing={Boolean(cardEdit)} deck={selectedDeck} sections={sections.data ?? []} busy={busy} onSubmit={saveCard} onCancel={() => { setCardFormOpen(false); setCardEdit(null); }} />}
            {cards.loading ? <PageLoading label={t('common.cardsLoading')} /> : <div className="admin-card-list">{cards.data?.items.map((card) => <article key={card.id} className={!card.active ? 'archived' : ''}><button onClick={() => editCard(card)}><span lang={selectedDeck.front_language}>{card.front_text}</span><small lang={selectedDeck.back_language}>{card.back_text}</small><em>{card.section_title ?? t('common.noSection')}{!card.active ? ` · ${t('common.archived')}` : ''}</em></button>{card.active && <button className="icon-button" aria-label={t('admin.archiveCard', { card: card.front_text })} onClick={() => void archiveCard(card)}><Archive /></button>}</article>)}</div>}
            {cards.data && cards.data.pages > 1 && <nav className="pagination"><button disabled={cardPage <= 1} onClick={() => setCardPage((value) => value - 1)}><ArrowLeft /> {t('common.back')}</button><span>{t('common.pageOf', { page: number(cards.data.page), pages: number(cards.data.pages) })}</span><button disabled={cardPage >= cards.data.pages} onClick={() => setCardPage((value) => value + 1)}>{t('common.next')} <ArrowRight /></button></nav>}
          </section>

        </>}

        <section className="panel admin-editor"><header><div><h2>{t('admin.importTitle')}</h2><p>{t('admin.importText')}</p></div><FileUp /></header><form className="import-form" onSubmit={importDeck}><label className="file-field"><span>{t('admin.jsonFile')}</span><input type="file" accept="application/json,.json" onChange={(event) => void loadImportFile(event.target.files?.[0])} /></label><label><span>{t('admin.manifestPreview')}</span><textarea rows={9} value={importText} onChange={(event) => setImportText(event.target.value)} placeholder='{"schemaVersion":1,"id":"..."}' /></label><button className="button primary" disabled={busy || !importText.trim()}><FileUp /> {t('admin.validateImport')}</button></form></section>
      </div>
    </section>
  </main>;
}

function DeckFields({ form, setForm, includeSlug = false }: { form: DeckForm; setForm(value: DeckForm): void; includeSlug?: boolean }) {
  const { t } = useI18n();
  const field = (name: keyof DeckForm) => ({ value: form[name], onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [name]: event.target.value }) });
  return <div className="admin-form-grid">{includeSlug && <label><span>{t('admin.deckId')}</span><input {...field('slug')} placeholder="english-german" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" /></label>}<label><span>{t('admin.titleField')}</span><input {...field('title')} required /></label><label className="wide"><span>{t('admin.description')}</span><textarea {...field('description')} rows={2} /></label><label><span>{t('admin.frontLabel')}</span><input {...field('front_label')} placeholder="English" required /></label><label><span>{t('admin.backLabel')}</span><input {...field('back_label')} placeholder="German" required /></label><label><span>{t('admin.frontLanguage')}</span><input {...field('front_language')} placeholder="en" required /></label><label><span>{t('admin.backLanguage')}</span><input {...field('back_language')} placeholder="de" required /></label><label><span>{t('admin.frontMatcher')}</span><div className="select-wrap"><select {...field('front_matcher')}><option value="generic-v1">{t('admin.matcherGeneric')}</option><option value="german-v1">{t('admin.matcherGerman')}</option><option value="latin-v1">{t('admin.matcherLatin')}</option></select><ChevronDown /></div></label><label><span>{t('admin.backMatcher')}</span><div className="select-wrap"><select {...field('back_matcher')}><option value="generic-v1">{t('admin.matcherGeneric')}</option><option value="german-v1">{t('admin.matcherGerman')}</option><option value="latin-v1">{t('admin.matcherLatin')}</option></select><ChevronDown /></div></label><label><span>{t('admin.contentLicense')}</span><input {...field('license')} placeholder="CC0-1.0" /></label><label><span>{t('admin.attribution')}</span><input {...field('attribution')} /></label></div>;
}

function CardEditor({ form, setForm, editing, deck, sections, busy, onSubmit, onCancel }: { form: CardForm; setForm(value: CardForm): void; editing: boolean; deck: Deck; sections: Section[]; busy: boolean; onSubmit(event: FormEvent<HTMLFormElement>): void; onCancel(): void }) {
  const { t } = useI18n();
  const field = (name: keyof CardForm) => ({ value: String(form[name]), onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setForm({ ...form, [name]: event.target.value }) });
  return <form className="card-editor" onSubmit={onSubmit}><div className="admin-form-grid"><label><span>{t('admin.stableCardId')}</span><input {...field('stable_key')} disabled={editing} required pattern="[A-Za-z0-9][A-Za-z0-9._:-]*" /></label><label><span>{t('admin.section')}</span><div className="select-wrap"><select {...field('section_id')}><option value="">{t('common.noSection')}</option>{sections.map((section) => <option value={section.id} key={section.id}>{section.title}</option>)}</select><ChevronDown /></div></label><label><span>{t('admin.order')}</span><input type="number" min={1} value={form.sort_order} onChange={(event) => setForm({ ...form, sort_order: Number(event.target.value) })} required /></label><label className="wide"><span>{deck.front_label}</span><textarea {...field('front_text')} rows={2} required /></label><label className="wide"><span>{deck.back_label}</span><textarea {...field('back_text')} rows={2} required /></label><label><span>{t('admin.additionalAnswers', { side: deck.front_label })}</span><textarea {...field('front_answers')} rows={4} placeholder={t('admin.oneAlternativeLine')} /></label><label><span>{t('admin.additionalAnswers', { side: deck.back_label })}</span><textarea {...field('back_answers')} rows={4} placeholder={t('admin.oneAlternativeLine')} /></label><label className="wide"><span>{t('admin.metadata')}</span><textarea {...field('metadata')} rows={5} spellCheck={false} /></label>{editing && <label className="checkbox-field"><input type="checkbox" checked={form.active} onChange={(event) => setForm({ ...form, active: event.target.checked })} /><span>{t('admin.cardActive')}</span></label>}</div><div className="admin-actions"><button type="button" className="button secondary" onClick={onCancel}>{t('common.cancel')}</button><button className="button primary" disabled={busy}><Save /> {t('admin.saveCard')}</button></div></form>;
}
