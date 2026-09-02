import { ArrowLeft, ArrowRight, LockKeyhole, Mail, UserRound } from 'lucide-react';
import { FormEvent, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Brand } from '../components/Brand';
import { useI18n } from '../i18n';

export function AuthPage({ register = false }: { register?: boolean }) {
  const { user, loading, login, register: createAccount } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const destination = (location.state as { from?: string } | null)?.from ?? '/';

  if (!loading && user) return <Navigate to={destination} replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      if (register) await createAccount(email, password, displayName);
      else await login(email, password);
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t('auth.tryAgain'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-aside">
        <Brand />
        <div>
          <p className="eyebrow light">{t('auth.tagline')}</p>
          <h1>{register ? t('auth.registerHero') : t('auth.loginHero')}</h1>
          <p>{t('auth.heroText')}</p>
        </div>
        <small>{t('auth.footer')}</small>
      </section>
      <section className="auth-form-side">
        <Link className="back-link" to="/willkommen"><ArrowLeft /> {t('common.back')}</Link>
        <form className="auth-card" onSubmit={submit}>
          <p className="section-kicker">{register ? t('landing.createAccount') : t('landing.signIn')}</p>
          <h2>{register ? t('auth.registerTitle') : t('auth.loginTitle')}</h2>
          <p className="muted">{register ? t('auth.registerDescription') : t('auth.loginDescription')}</p>

          {register && (
            <label className="field"><span>{t('auth.name')}</span><div><UserRound /><input autoComplete="name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={2} maxLength={80} required placeholder={t('auth.namePlaceholder')} /></div></label>
          )}
          <label className="field"><span>{t('auth.email')}</span><div><Mail /><input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required placeholder={t('auth.emailPlaceholder')} /></div></label>
          <label className="field"><span>{t('auth.password')}</span><div><LockKeyhole /><input type="password" autoComplete={register ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} minLength={register ? 10 : 1} maxLength={128} required placeholder={register ? t('auth.newPasswordPlaceholder') : t('auth.passwordPlaceholder')} /></div></label>

          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button primary wide" disabled={submitting}>
            {submitting ? t('auth.working') : register ? t('landing.createAccount') : t('landing.signIn')}
            {!submitting && <ArrowRight />}
          </button>
          <p className="auth-switch">
            {register ? t('auth.haveAccount') : t('auth.noAccount')}{' '}
            <Link to={register ? '/anmelden' : '/registrieren'}>{register ? t('landing.signIn') : t('auth.registerNow')}</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
