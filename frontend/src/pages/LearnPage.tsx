import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Keyboard,
  Layers3,
  RotateCcw,
  Search,
  Sparkles,
  X,
} from 'lucide-react';
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, ApiError, createIdempotencyKey } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { PageError, PageLoading } from '../components/PageState';
import type { Deck, Direction, InputMode, ReviewResult, Section, SelectionMode, StudySession } from '../types';
import { useI18n } from '../i18n';
import type { MessageKey } from '../i18n/messages';

type CheckedAnswer = { correct: boolean; solution: string; match_kind: string | null; missing_meanings?: string[] };

const ratingOptions = [
  { value: 0, label: 'learn.ratingAgain', key: '1', tone: 'again' },
  { value: 1, label: 'learn.ratingHard', key: '2', tone: 'hard' },
  { value: 2, label: 'learn.ratingGood', key: '3', tone: 'good' },
  { value: 3, label: 'learn.ratingEasy', key: '4', tone: 'easy' },
] as const;

function SectionPicker({
  sections,
  selected,
  onSelect,
}: {
  sections: Section[];
  selected: string | null;
  onSelect(value: string | null): void;
}) {
  const { language, number, t } = useI18n();
  const [query, setQuery] = useState('');
  const filtered = sections.filter((section) =>
    section.title.toLocaleLowerCase(language).includes(query.trim().toLocaleLowerCase(language)),
  );
  const total = sections.reduce((sum, section) => sum + section.total, 0);

  return (
    <div className="chapter-picker">
      <label className="search-field" htmlFor="section-search">
        <Search aria-hidden="true" />
        <input id="section-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('learn.searchSection')} />
      </label>
      <div className="chapter-grid" role="group" aria-label={t('learn.chooseSection')}>
        <button type="button" aria-pressed={selected === null} className={selected === null ? 'selected all-chapters' : 'all-chapters'} onClick={() => onSelect(null)}>
          <span><Layers3 /> {t('common.allSections')}</span><small>{t(total === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: number(total) })}</small>
        </button>
        {filtered.map((section) => (
          <button key={section.id} type="button" aria-pressed={selected === section.id} className={selected === section.id ? 'selected' : ''} onClick={() => onSelect(section.id)}>
            <span>{section.title}</span>
            <small>{t('learn.sectionSummary', { cards: t(section.total === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: number(section.total) }), percent: number(section.progress_percent) })}</small>
            {section.due > 0 && <em>{t('learn.due', { count: number(section.due) })}</em>}
          </button>
        ))}
      </div>
    </div>
  );
}

type StartConfig = {
  deck_id: string;
  section_id: string | null;
  direction: Direction;
  input_mode: InputMode;
  selection_mode: SelectionMode;
  limit: number;
};

function Setup({ decks, start }: { decks: Deck[]; start(config: StartConfig): Promise<void> }) {
  const { user } = useAuth();
  const { number, t } = useI18n();
  const [params, setParams] = useSearchParams();
  const requestedDeck = params.get('deck');
  const initialDeckId = decks.some((deck) => deck.id === requestedDeck)
    ? requestedDeck!
    : decks.some((deck) => deck.id === user?.selected_deck_id)
      ? user!.selected_deck_id!
      : decks[0]?.id ?? '';
  const [deckId, setDeckId] = useState(initialDeckId);
  const requestedSection = params.get('section');
  const [sectionId, setSectionId] = useState<string | null>(requestedSection ?? user?.selected_section_id ?? null);
  const [direction, setDirection] = useState<Direction>(user?.direction ?? 'forward');
  const [mode, setMode] = useState<InputMode>(user?.input_mode ?? 'typing');
  const requestedSelection = params.get('selection');
  const [selectionMode, setSelectionMode] = useState<SelectionMode>(
    requestedSelection === 'random' || requestedSelection === 'adaptive' ? requestedSelection : 'scheduled',
  );
  const [limit, setLimit] = useState(user?.daily_goal ?? 12);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const sections = useResource(() => api<Section[]>(`/sections?deck_id=${deckId}`), deckId);
  const deck = decks.find((entry) => entry.id === deckId) ?? decks[0];

  useEffect(() => {
    if (!sections.data || !sectionId) return;
    if (!sections.data.some((section) => section.id === sectionId)) setSectionId(null);
  }, [sectionId, sections.data]);

  async function begin() {
    if (!deck) return;
    setStarting(true);
    setError('');
    try {
      await start({ deck_id: deck.id, section_id: sectionId, direction, input_mode: mode, selection_mode: selectionMode, limit });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t('learn.startError'));
    } finally {
      setStarting(false);
    }
  }

  function selectDeck(value: string) {
    setDeckId(value);
    setSectionId(null);
    const next = new URLSearchParams(params);
    next.set('deck', value);
    next.delete('section');
    setParams(next, { replace: true });
  }

  function selectSection(value: string | null) {
    setSectionId(value);
    const next = new URLSearchParams(params);
    if (value) next.set('section', value);
    else next.delete('section');
    setParams(next, { replace: true });
  }

  if (!deck) return null;
  const sectionTitle = sections.data?.find((section) => section.id === sectionId)?.title;

  return (
    <main className="page-wrap learn-setup">
      <header className="page-header"><p className="section-kicker">{t('learn.newSession')}</p><h1>{t('learn.whatToday')}</h1><p>{t('learn.setupIntro')}</p></header>

      <section className="setup-section panel">
        <div className="setup-heading"><span>1</span><div><h2>{t('learn.chooseDeckSection')}</h2><p>{t('learn.managedContent')}</p></div></div>
        <label className="deck-select"><span>{t('common.deck')}</span><div className="select-wrap"><select value={deck.id} onChange={(event) => selectDeck(event.target.value)}>{decks.map((entry) => <option value={entry.id} key={entry.id}>{entry.title} · {entry.front_label} → {entry.back_label}</option>)}</select><ChevronDown /></div></label>
        {sections.loading ? <PageLoading label={t('common.sectionsLoading')} /> : sections.data ? <SectionPicker sections={sections.data} selected={sectionId} onSelect={selectSection} /> : <PageError message={sections.error} retry={() => void sections.reload()} />}
      </section>

      <section className="setup-two-column">
        <article className="setup-section panel">
          <div className="setup-heading"><span>2</span><div><h2>{t('learn.studyMode')}</h2><p>{t('learn.chooseEachTime')}</p></div></div>
          <div className="choice-cards">
            <button type="button" aria-pressed={mode === 'typing'} className={mode === 'typing' ? 'selected' : ''} onClick={() => setMode('typing')}>
              <span className="choice-icon"><Keyboard /></span><strong>{t('settings.typeAnswer')}</strong><small>{t('learn.typeAnswerText')}</small>{mode === 'typing' && <CheckCircle2 className="choice-check" />}
            </button>
            <button type="button" aria-pressed={mode === 'reveal'} className={mode === 'reveal' ? 'selected' : ''} onClick={() => setMode('reveal')}>
              <span className="choice-icon"><Layers3 /></span><strong>{t('settings.revealCard')}</strong><small>{t('learn.revealText')}</small>{mode === 'reveal' && <CheckCircle2 className="choice-check" />}
            </button>
          </div>
        </article>
        <article className="setup-section panel compact-settings">
          <div className="setup-heading"><span>3</span><div><h2>{t('learn.directionSize')}</h2><p>{t('learn.matchGoal')}</p></div></div>
          <label><span>{t('settings.direction')}</span><div className="select-wrap"><select value={direction} onChange={(event) => setDirection(event.target.value as Direction)}><option value="forward">{deck.front_label} → {deck.back_label}</option><option value="reverse">{deck.back_label} → {deck.front_label}</option><option value="mixed">{t('settings.mixed')}</option></select><ChevronDown /></div></label>
          <label><span>{t('learn.selectionMode')}</span><div className="select-wrap"><select aria-describedby="selection-help" value={selectionMode} onChange={(event) => setSelectionMode(event.target.value as SelectionMode)}>{(['scheduled', 'random', 'adaptive'] as const).map((value) => <option key={value} value={value}>{t(`learn.selection.${value}`)}</option>)}</select><ChevronDown /></div></label>
          <p id="selection-help">{t(`learn.selectionHelp.${selectionMode}`)} {t('learn.randomSections')}</p>
          <label><span>{t('learn.cardCount')}</span><div className="select-wrap"><select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>{[5, 10, 12, 20, 30, 50].map((value) => <option key={value} value={value}>{t(value === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: number(value) })}</option>)}</select><ChevronDown /></div></label>
        </article>
      </section>
      {error && <p className="form-error centered" role="alert">{error}</p>}
      <div className="setup-footer"><div><strong>{deck.title}</strong><span> · {sectionTitle ?? t('common.allSections')} · {t(`learn.selection.${selectionMode}`)} · {mode === 'typing' ? t('learn.modeTyping') : t('settings.revealCard')} · {t(limit === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: number(limit) })}</span></div><button className="button primary large" type="button" disabled={starting || sections.loading} onClick={() => void begin()}>{starting ? t('learn.preparing') : t('dashboard.start')} {!starting && <ArrowRight />}</button></div>
    </main>
  );
}

function Study({ session, setSession, leave }: { session: StudySession; setSession(value: StudySession): void; leave(): void }) {
  const { number, t } = useI18n();
  const card = session.cards[0] ?? null;
  const [answer, setAnswer] = useState('');
  const [checked, setChecked] = useState<CheckedAnswer | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [solution, setSolution] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const startedAt = useRef(Date.now());
  const inputRef = useRef<HTMLInputElement>(null);
  const actionRef = useRef<HTMLButtonElement>(null);
  const inFlightRef = useRef(false);
  const mountedRef = useRef(true);
  const reviewAttemptRef = useRef<{ cardId: string; body: Record<string, unknown> } | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const resetCard = useCallback(() => {
    setAnswer(''); setChecked(null); setRevealed(false); setSolution(''); setError('');
    reviewAttemptRef.current = null;
    inFlightRef.current = false;
    startedAt.current = Date.now();
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  useEffect(() => { resetCard(); }, [card?.item_id, resetCard]);

  async function check(event: FormEvent) {
    event.preventDefault();
    if (!card || !answer.trim() || inFlightRef.current) return;
    inFlightRef.current = true;
    setSubmitting(true); setError('');
    try {
      const result = await api<CheckedAnswer>(`/study-sessions/${session.id}/check`, { method: 'POST', body: JSON.stringify({ item_id: card.item_id, answer }) });
      if (mountedRef.current) { setChecked(result); setSolution(result.solution); }
    } catch (caught) {
      if (mountedRef.current) setError(caught instanceof ApiError ? caught.message : t('learn.checkError'));
    } finally { inFlightRef.current = false; if (mountedRef.current) setSubmitting(false); }
  }

  async function reveal() {
    if (!card || inFlightRef.current || revealed) return;
    inFlightRef.current = true;
    setSubmitting(true); setError('');
    try {
      const result = await api<{ solution: string }>(`/study-sessions/${session.id}/items/${card.item_id}/reveal`, { method: 'POST' });
      if (mountedRef.current) { setSolution(result.solution); setRevealed(true); }
    } catch (caught) {
      if (mountedRef.current) setError(caught instanceof ApiError ? caught.message : t('learn.revealError'));
    } finally { inFlightRef.current = false; if (mountedRef.current) setSubmitting(false); }
  }

  async function rate(value: number | boolean) {
    if (!card || inFlightRef.current) return;
    inFlightRef.current = true;
    setSubmitting(true); setError('');
    const response = session.input_mode === 'typing'
      ? { type: 'typing', answer, rating: Number(value) }
      : { type: 'self_assessment', known: Boolean(value) };
    const attempt = reviewAttemptRef.current?.cardId === card.item_id
      ? reviewAttemptRef.current
      : {
          cardId: card.item_id,
          body: {
            idempotency_key: createIdempotencyKey(),
            item_id: card.item_id,
            base_version: card.state_version,
            response_ms: Math.min(600000, Date.now() - startedAt.current),
            response,
          },
        };
    reviewAttemptRef.current = attempt;
    try {
      const result = await api<ReviewResult>(`/study-sessions/${session.id}/reviews`, { method: 'POST', body: JSON.stringify(attempt.body) });
      if (!mountedRef.current) return;
      reviewAttemptRef.current = null;
      setSession({ ...session, reviewed: result.reviewed, correct_reviewed: result.correct_reviewed, complete: result.complete, cards: session.cards.slice(1) });
    } catch (caught) {
      if (caught instanceof ApiError && caught.status < 500) reviewAttemptRef.current = null;
      if (mountedRef.current) setError(caught instanceof ApiError ? caught.message : t('learn.saveProgressError'));
    } finally { inFlightRef.current = false; if (mountedRef.current) setSubmitting(false); }
  }

  useEffect(() => {
    if (!checked && !revealed) return;
    const frame = requestAnimationFrame(() => actionRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [checked, revealed]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if (!card || submitting) return;
      const target = event.target instanceof Element ? event.target : null;
      const interactive = Boolean(target?.closest('input, textarea, select, button, a, [contenteditable="true"]'));
      if (session.input_mode === 'reveal' && !revealed && !interactive && (event.key === ' ' || event.key === 'Enter')) {
        event.preventDefault(); void reveal();
      } else if (session.input_mode === 'reveal' && revealed && !interactive && ['1', '2'].includes(event.key)) {
        event.preventDefault(); void rate(event.key === '2');
      } else if (session.input_mode === 'typing' && checked && !interactive && ['1', '2', '3', '4'].includes(event.key)) {
        event.preventDefault(); void rate(Number(event.key) - 1);
      }
    }
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  });

  if (session.complete || !card) {
    const accuracy = session.reviewed ? Math.round((session.correct_reviewed / session.reviewed) * 100) : 0;
    return <main className="study-shell"><section className="completion-card panel"><span className="completion-icon"><Sparkles /></span><p className="section-kicker">{t('learn.completed')}</p><h1>{t('learn.wellDone')}</h1><p>{t('learn.completedText', { count: number(session.reviewed), source: session.section_title ?? session.deck_title })}</p><div className="completion-stats"><div><strong>{number(session.reviewed)}</strong><span>{t('learn.reviewed')}</span></div><div><strong>{number(accuracy)}%</strong><span>{t('learn.known')}</span></div></div><div className="completion-actions"><button className="button primary" onClick={leave}>{t('learn.newSessionButton')}</button><Link className="button secondary" to="/">{t('learn.overview')}</Link></div></section></main>;
  }

  const progress = session.total ? (session.reviewed / session.total) * 100 : 0;
  const resultVisible = session.input_mode === 'typing' ? checked !== null : revealed;
  const promptLabel = card.direction === 'forward' ? session.front_label : session.back_label;
  const answerLabel = card.direction === 'forward' ? session.back_label : session.front_label;
  const metadataText = Object.values(card.metadata).filter((value): value is string => typeof value === 'string').slice(0, 3).join(' · ');

  return (
    <main className="study-shell">
      <header className="study-header"><button className="icon-button" type="button" disabled={submitting} onClick={leave} aria-label={t('learn.leave')}><ArrowLeft /></button><div><span>{card.section_title ?? session.deck_title}</span><small>{promptLabel} → {answerLabel}</small></div><strong>{number(session.reviewed + 1)} <span>{t('common.of')} {number(session.total)}</span></strong></header>
      <div className="study-progress"><span style={{ width: `${progress}%` }} /></div>
      <section className="study-stage">
        <div className={`flashcard ${resultVisible ? 'revealed' : ''} ${session.input_mode === 'reveal' ? 'flip-mode' : ''}`}>
          <div className="card-face card-front">
            <div className="card-meta"><span>{promptLabel}</span>{card.is_new && <em>{t('learn.newCard')}</em>}</div>
            <p>{t('learn.question', { language: answerLabel })}</p>
            <h1 lang={card.prompt_language}>{card.prompt}</h1>
            {metadataText && <small>{metadataText}</small>}
          </div>
          {session.input_mode === 'reveal' && revealed && <div className="card-face card-back"><div className="card-meta"><span>{t('learn.solution', { language: answerLabel })}</span><CheckCircle2 /></div><p>{t('learn.solutionIs')}</p><h2 lang={card.answer_language}>{solution}</h2><small>{metadataText || t('learn.honestRating')}</small></div>}
        </div>

        {session.input_mode === 'typing' && !checked && <form className="answer-form" onSubmit={check}><label htmlFor="answer">{t('learn.yourAnswer')}</label><div><input ref={inputRef} id="answer" autoComplete="off" value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder={t('learn.answerPlaceholder', { language: answerLabel })} /><button className="button primary" disabled={!answer.trim() || submitting}>{t('learn.check')} <ArrowRight /></button></div></form>}
        {session.input_mode === 'typing' && checked && <section className={`answer-result ${checked.correct ? 'correct' : 'incorrect'}`}><header className="answer-result-header">{checked.correct ? <Check /> : <X />}<div className="answer-result-copy"><strong>{checked.correct ? t('landing.correct') : checked.missing_meanings?.length ? t('learn.incomplete') : t('learn.notQuite')}</strong>{!checked.correct && !!checked.missing_meanings?.length && <span>{t('learn.missingMeanings')} <b lang={card.answer_language}>{checked.missing_meanings.join(' · ')}</b></span>}<span>{t('learn.solutionInline')} <b lang={card.answer_language}>{solution}</b></span></div></header><div className="rating-grid">{ratingOptions.map((option) => <button ref={option.value === 2 ? actionRef : undefined} type="button" key={option.value} className={option.tone} disabled={submitting} onClick={() => void rate(option.value)}>{option.value === 0 && <RotateCcw />}<span>{t(option.label as MessageKey)}<small>{t('learn.key', { key: option.key })}</small></span></button>)}</div></section>}
        {session.input_mode === 'reveal' && !revealed && <button className="button primary large continue-button" disabled={submitting} onClick={() => void reveal()}>{t('learn.flip')} <Layers3 /></button>}
        {session.input_mode === 'reveal' && revealed && <div className="binary-rating"><button ref={actionRef} className="button secondary no" disabled={submitting} onClick={() => void rate(false)}><X /> {t('learn.didNotKnow')} <small>1</small></button><button className="button secondary yes" disabled={submitting} onClick={() => void rate(true)}><Check /> {t('learn.didKnow')} <small>2</small></button></div>}
        {error && <p className="form-error centered" role="alert">{error}</p>}
      </section>
    </main>
  );
}

export function LearnPage() {
  const { t } = useI18n();
  const { user, updateUser } = useAuth();
  const [params, setParams] = useSearchParams();
  const [session, setSession] = useState<StudySession | null>(null);
  const [resumeError, setResumeError] = useState('');
  const decks = useResource(() => api<Deck[]>('/decks'));
  const sessionId = params.get('session');

  useEffect(() => {
    if (!sessionId) {
      setSession(null);
      setResumeError('');
      return;
    }
    let active = true;
    setSession((current) => current?.id === sessionId ? current : null);
    setResumeError('');
    void api<StudySession>(`/study-sessions/${sessionId}`)
      .then((value) => { if (active) setSession(value); })
      .catch((caught: unknown) => { if (active) setResumeError(caught instanceof ApiError ? caught.message : t('learn.resumeError')); });
    return () => { active = false; };
  }, [sessionId]);

  async function start(config: StartConfig) {
    const next = await api<StudySession>('/study-sessions', { method: 'POST', body: JSON.stringify(config) });
    if (user) {
      updateUser({
        ...user,
        selected_deck_id: config.deck_id,
        selected_section_id: config.section_id,
        direction: config.direction,
        input_mode: config.input_mode,
      });
    }
    setSession(next);
    const search = new URLSearchParams();
    search.set('session', next.id);
    setParams(search, { replace: true });
  }

  function leave() {
    setSession(null);
    const search = new URLSearchParams();
    if (session?.deck_id) search.set('deck', session.deck_id);
    if (session?.section_id) search.set('section', session.section_id);
    if (session?.selection_mode) search.set('selection', session.selection_mode);
    setParams(search, { replace: true });
  }

  if (resumeError) return <PageError message={resumeError} retry={() => setParams({}, { replace: true })} />;
  if (sessionId && !session) return <PageLoading label={t('learn.sessionLoading')} />;
  if (session) return <Study session={session} setSession={setSession} leave={leave} />;
  if (decks.loading) return <PageLoading label={t('common.decksLoading')} />;
  if (!decks.data) return <PageError message={decks.error} retry={() => void decks.reload()} />;
  if (decks.data.length === 0) return <main className="page-wrap"><section className="empty-state panel"><Layers3 /><h2>{t('cards.noDeck')}</h2><p>{t('learn.emptyDecksText')}</p></section></main>;
  return <Setup decks={decks.data} start={start} />;
}
