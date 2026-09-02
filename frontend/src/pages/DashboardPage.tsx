import {
  ArrowRight,
  BookCheck,
  BookOpen,
  Clock3,
  Flame,
  MoveUpRight,
  Sparkles,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { PageError, PageLoading } from '../components/PageState';
import type { Dashboard } from '../types';
import { useI18n } from '../i18n';

type DashboardStat = { label: string; value: number; suffix: string; icon: LucideIcon };

function greetingKey() {
  const hour = new Date().getHours();
  if (hour < 11) return 'dashboard.greetingMorning' as const;
  if (hour < 18) return 'dashboard.greetingDay' as const;
  return 'dashboard.greetingEvening' as const;
}

export function DashboardPage() {
  const { user } = useAuth();
  const { date, number, t } = useI18n();
  const resource = useResource(() => api<Dashboard>('/dashboard'));
  if (resource.loading) return <PageLoading label={t('dashboard.loading')} />;
  if (!resource.data) return <PageError message={resource.error} retry={() => void resource.reload()} />;
  const data = resource.data;
  if (!data.deck) return <main className="page-wrap dashboard-page"><header className="page-header"><p className="section-kicker">{t('dashboard.welcome')}</p><h1>{t('dashboard.noDeck')}</h1><p>{t('dashboard.noDeckText')}</p></header>{user?.role === 'admin' && <Link className="button primary" to="/admin">{t('dashboard.openAdmin')} <ArrowRight /></Link>}</main>;
  const deck = data.deck;
  const maximum = Math.max(...data.weekly_activity.map((day) => day.count), 1);
  const stats: DashboardStat[] = [
    { label: t('dashboard.learnedToday'), value: data.reviewed_today, suffix: t(data.reviewed_today === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: number(data.reviewed_today) }), icon: Clock3 },
    { label: t('dashboard.startedTotal'), value: data.learned_count, suffix: t('dashboard.ofTotal', { count: number(data.total_count) }), icon: BookOpen },
    { label: t('dashboard.mastered'), value: data.mastered_count, suffix: t(data.mastered_count === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: number(data.mastered_count) }), icon: BookCheck },
  ];

  return (
    <main className="page-wrap dashboard-page">
      <header className="page-header horizontal">
        <div><p className="section-kicker">{t('dashboard.overview')}</p><h1>{t(greetingKey())}, {user?.display_name.split(' ')[0]}.</h1></div>
      </header>

      <section className="dashboard-hero-grid">
        <article className="learn-today-card">
          <div className="orb" aria-hidden="true" />
          <div className="learn-card-top"><span><Sparkles /> {t('dashboard.learnToday')}</span><small>{t(Math.max(2, Math.ceil(data.due_count / 3)) === 1 ? 'common.minutesOne' : 'common.minutesMany', { count: number(Math.max(2, Math.ceil(data.due_count / 3))) })}</small></div>
          <h2>{data.due_count > 0 ? t(data.due_count === 1 ? 'dashboard.cardsWaitingOne' : 'dashboard.cardsWaitingMany', { count: number(data.due_count) }) : t('dashboard.doneToday')}</h2>
          <div className="learn-card-bottom">
            <Link className="button light" to="/lernen">{data.reviewed_today ? t('dashboard.continue') : t('dashboard.start')} <ArrowRight /></Link>
            {data.reviewed_today > 0 && <span>{t('dashboard.reviewedToday', { count: number(data.reviewed_today) })}</span>}
          </div>
        </article>
        <article className="streak-card panel">
          <div className="panel-icon amber"><Flame /></div><small>{t('dashboard.streak')}</small>
          <div><strong>{number(data.streak)}</strong><h2>{t(data.streak === 1 ? 'common.dayOne' : 'common.dayMany', { count: number(data.streak) })}</h2><p>{t('dashboard.streakHint')}</p></div>
        </article>
      </section>

      <section className="stat-grid" aria-label={t('dashboard.statsLabel')}>
        {stats.map(({ label, value, suffix, icon: Icon }) => (
          <article className="stat-card panel" key={label}><div><small>{label}</small><Icon className="stat-icon" /></div><strong>{number(value)}</strong><p>{suffix}</p></article>
        ))}
      </section>

      <section className="dashboard-lower-grid">
        <article className="panel activity-card">
          <header><div><h2>{t('dashboard.yourWeek')}</h2><p>{t('dashboard.reviewedCards')}</p></div><Link to="/fortschritt">{t('dashboard.details')} <MoveUpRight /></Link></header>
          <div className="activity-chart" role="img" aria-label={t('dashboard.activityLabel', { days: data.weekly_activity.map((day) => `${date(`${day.date}T12:00:00`, { weekday: 'short' })} ${number(day.count)}`).join(', ') })}>
            {data.weekly_activity.map((day) => (
              <div key={day.date} className={day.today ? 'today' : ''}><span className="bar-shell"><span style={{ height: `${Math.max(8, (day.count / maximum) * 100)}%` }} /></span><small>{date(`${day.date}T12:00:00`, { weekday: 'short' })}</small></div>
            ))}
          </div>
        </article>
        <article className="panel progress-card">
          <header><div className="panel-icon violet"><BookOpen /></div><span>{data.progress_percent}%</span></header>
          <h2>{deck.title}</h2><p>{t('dashboard.deckProgress', { learned: number(data.learned_count), total: number(data.total_count) })}</p>
          <div className="progress-track"><span style={{ width: `${data.progress_percent}%` }} /></div>
          <Link to="/vokabeln">{t('dashboard.viewCards')} <ArrowRight /></Link>
        </article>
      </section>

      {data.difficult.length > 0 && (
        <section className="panel difficult-card"><header><div><h2>{t('dashboard.reviewAgain')}</h2><p>{t('dashboard.reviewAgainText')}</p></div></header><div className="difficult-list">{data.difficult.map((card) => <Link key={card.id} to={`/lernen?deck=${card.deck_id}${card.section_id ? `&section=${card.section_id}` : ''}`}><span lang={card.front_language}>{card.front_text}</span><small>{card.back_text}{card.section_title ? ` · ${card.section_title}` : ''}</small><ArrowRight /></Link>)}</div></section>
      )}
    </main>
  );
}
