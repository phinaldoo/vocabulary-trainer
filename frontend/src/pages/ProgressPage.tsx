import { ArrowRight, BarChart3, BookCheck, CheckCircle2, ChevronDown, Flame, Target } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { PageError, PageLoading } from '../components/PageState';
import type { Deck, Progress } from '../types';
import { useI18n } from '../i18n';

type MasteryStat = { icon: LucideIcon; label: string; value: number; detail: string };

function ProgressForDeck({ deck, decks }: { deck: Deck; decks: Deck[] }) {
  const { number, t } = useI18n();
  const [params, setParams] = useSearchParams();
  const resource = useResource(() => api<Progress>(`/progress?deck_id=${deck.id}`), deck.id);
  if (resource.loading) return <PageLoading label={t('progress.loading')} />;
  if (!resource.data) return <PageError message={resource.error} retry={() => void resource.reload()} />;
  const data = resource.data;
  const startedPercent = data.total ? Math.round((data.learned / data.total) * 100) : 0;
  const mastery: MasteryStat[] = [
    { icon: BookCheck, label: t('progress.secure'), value: data.secure, detail: t('progress.secureDetail') },
    { icon: CheckCircle2, label: t('progress.familiar'), value: data.familiar, detail: t('progress.familiarDetail') },
    { icon: BarChart3, label: t('progress.learning'), value: data.learning, detail: t('progress.learningDetail') },
  ];

  function chooseDeck(value: string) {
    const next = new URLSearchParams(params); next.set('deck', value); setParams(next);
  }

  return <main className="page-wrap progress-page">
    <header className="page-header horizontal"><div><p className="section-kicker">{t('progress.kicker')}</p><h1>{t('progress.title')}</h1><p>{t('progress.intro', { deck: deck.title })}</p></div><label className="header-select"><span>{t('common.deck')}</span><div className="select-wrap"><select value={deck.id} onChange={(event) => chooseDeck(event.target.value)}>{decks.map((entry) => <option key={entry.id} value={entry.id}>{entry.title}</option>)}</select><ChevronDown /></div></label></header>
    {data.learned === 0 ? <section className="empty-state panel"><BarChart3 /><h2>{t('progress.firstCard')}</h2><p>{t('progress.firstCardText')}</p><Link className="button primary" to={`/lernen?deck=${deck.id}`}>{t('dashboard.start')} <ArrowRight /></Link></section> : <>
      <section className="progress-hero-grid"><article className="progress-overview"><p className="section-kicker light">{t('progress.deckStarted')}</p><strong>{number(startedPercent)}%</strong><p>{t('progress.cardsProgress', { learned: number(data.learned), total: number(data.total) })}</p><div className="progress-track"><span style={{ width: `${startedPercent}%` }} /></div></article><article className="panel progress-summary"><div><span className="panel-icon violet"><Target /></span><small>{t('progress.accuracy')}</small><strong>{number(data.accuracy)}%</strong><p>{t('progress.fromAnswers', { count: number(data.reviews) })}</p></div><div><span className="panel-icon amber"><Flame /></span><small>{t('dashboard.streak')}</small><strong>{number(data.streak)}</strong><p>{t(data.streak === 1 ? 'common.dayOne' : 'common.dayMany', { count: number(data.streak) })}</p></div></article></section>
      <section className="stat-grid mastery-grid">{mastery.map(({ icon: Icon, label, value, detail }) => <article className="panel stat-card" key={label}><div><small>{label}</small><Icon className="stat-icon" /></div><strong>{number(value)}</strong><p>{detail}</p></article>)}</section>
      <section className="panel lesson-progress"><header><div><h2>{t('progress.bySection')}</h2><p>{t('progress.bySectionText')}</p></div></header><div className="lesson-progress-grid">{data.sections.map((section) => <Link key={section.id} to={`/lernen?deck=${deck.id}&section=${section.id}`}><div><strong>{section.title}</strong><span>{number(section.learned)}/{number(section.total)}</span></div><div className="progress-track"><span style={{ width: `${section.progress_percent}%` }} /></div><small>{section.due ? t('progress.due', { count: number(section.due) }) : section.progress_percent ? t('progress.startedPercent', { percent: number(section.progress_percent) }) : t('progress.notStarted')}</small></Link>)}</div></section>
    </>}
  </main>;
}

export function ProgressPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [params] = useSearchParams();
  const decks = useResource(() => api<Deck[]>('/decks'));
  if (decks.loading) return <PageLoading label={t('common.decksLoading')} />;
  if (!decks.data) return <PageError message={decks.error} retry={() => void decks.reload()} />;
  const requested = params.get('deck');
  const deck = decks.data.find((entry) => entry.id === requested)
    ?? decks.data.find((entry) => entry.id === user?.selected_deck_id)
    ?? decks.data[0];
  if (!deck) return <main className="page-wrap"><section className="empty-state panel"><BarChart3 /><h2>{t('progress.noDeck')}</h2><p>{t('progress.noDeckText')}</p></section></main>;
  return <ProgressForDeck deck={deck} decks={decks.data} />;
}
