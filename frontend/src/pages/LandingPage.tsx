import { ArrowRight, Check, RotateCcw, ShieldCheck, Sparkles } from 'lucide-react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Brand } from '../components/Brand';
import { useI18n } from '../i18n';

export function LandingPage() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  if (!loading && user) return <Navigate to="/" replace />;

  return (
    <main className="landing-shell">
      <header className="landing-header">
        <Brand />
        <nav className="landing-actions" aria-label={t('landing.accountAccess')}>
          <Link className="text-link" to="/anmelden">{t('landing.signIn')}</Link>
          <Link className="button dark small" to="/registrieren">{t('landing.createAccount')}</Link>
        </nav>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow"><Sparkles aria-hidden="true" /> {t('landing.eyebrow')}</p>
          <h1>{t('landing.headlineStart')} <span>{t('landing.headlineEnd')}</span></h1>
          <p className="hero-intro">
            {t('landing.intro')}
          </p>
          <div className="hero-actions">
            <Link className="button dark large" to="/registrieren">{t('landing.startFree')} <ArrowRight /></Link>
            <p><ShieldCheck /> {t('landing.dataPrivate')}</p>
          </div>
        </div>
        <div className="product-stage" aria-label={t('landing.previewLabel')}>
          <div className="preview-window">
            <div className="preview-top"><span className="mini-mark">VT</span><span>{t('landing.basics')}</span><small>{t('landing.previewProgress', { current: 4, total: 12 })}</small></div>
            <div className="progress-track"><span style={{ width: '34%' }} /></div>
            <div className="preview-card">
              <p>{t('landing.question')}</p>
              <strong lang="fr">bonjour</strong>
              <div className="preview-answer"><Check /><span><small>{t('landing.correct')}</small>{t('landing.previewAnswer')}</span></div>
            </div>
            <div className="preview-ratings"><button><RotateCcw /> {t('landing.again')}</button><button>{t('landing.hard')}</button><button className="selected">{t('landing.good')}</button><button>{t('landing.easy')}</button></div>
          </div>
          <div className="floating-stat top"><small>{t('landing.today')}</small><strong>{t('landing.due', { count: 12 })}</strong></div>
          <div className="floating-stat bottom"><small>{t('landing.yourStreak')}</small><strong>{t('landing.days', { count: 8 })}</strong></div>
        </div>
      </section>
      <section className="benefit-row">
        <article><span>01</span><div><h2>{t('landing.benefitSectionsTitle')}</h2><p>{t('landing.benefitSectionsText')}</p></div></article>
        <article><span>02</span><div><h2>{t('landing.benefitModesTitle')}</h2><p>{t('landing.benefitModesText')}</p></div></article>
        <article><span>03</span><div><h2>{t('landing.benefitManagedTitle')}</h2><p>{t('landing.benefitManagedText')}</p></div></article>
      </section>
    </main>
  );
}
