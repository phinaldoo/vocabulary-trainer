import {
  BarChart3,
  BookOpen,
  ChevronRight,
  Database,
  House,
  LogOut,
  Settings,
  Sparkles,
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from '../auth/AuthContext';
import { Brand } from './Brand';
import { useI18n } from '../i18n';

const navigation = [
  { label: 'nav.home', href: '/', icon: House },
  { label: 'nav.learn', href: '/lernen', icon: Sparkles },
  { label: 'nav.cards', href: '/vokabeln', icon: BookOpen },
  { label: 'nav.progress', href: '/fortschritt', icon: BarChart3 },
] as const;

function initials(name: string, locale: string) {
  return name
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toLocaleUpperCase(locale))
    .join('');
}

export function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { language, t } = useI18n();
  const location = useLocation();
  if (!user) return null;

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Brand />
        <nav className="side-nav" aria-label={t('nav.main')}>
          {navigation.map(({ label, href, icon: Icon }) => (
            <NavLink key={href} to={href} end={href === '/'}>
              <Icon aria-hidden="true" />
              {t(label)}
            </NavLink>
          ))}
          {user.role === 'admin' && <NavLink to="/admin"><Database aria-hidden="true" />{t('nav.admin')}</NavLink>}
        </nav>
        <div className="account-nav">
          <NavLink className="account-link" to="/einstellungen">
            <span className="avatar">{initials(user.display_name, language)}</span>
            <span className="account-copy">
              <strong>{user.display_name}</strong>
              <small>{t('nav.settings')}</small>
            </span>
            <ChevronRight aria-hidden="true" />
          </NavLink>
          <button className="logout-button" type="button" onClick={() => void logout()}>
            <LogOut aria-hidden="true" /> {t('nav.logout')}
          </button>
        </div>
      </aside>

      <header className="mobile-header">
        <Brand compact />
        <NavLink className="avatar" to="/einstellungen" aria-label={t('nav.openSettings')}>
          {initials(user.display_name, language)}
        </NavLink>
      </header>

      <div className="app-content">{children}</div>

      <nav className="bottom-nav" aria-label={t('nav.mobile')}>
        {navigation.map(({ label, href, icon: Icon }) => {
          const active = href === '/' ? location.pathname === '/' : location.pathname.startsWith(href);
          return (
            <NavLink key={href} to={href} className={active ? 'active' : ''}>
              <Icon aria-hidden="true" />
              <span>{t(label)}</span>
            </NavLink>
          );
        })}
        <NavLink to="/einstellungen" className={location.pathname === '/einstellungen' ? 'active' : ''}>
          <Settings aria-hidden="true" />
          <span>{t('nav.account')}</span>
        </NavLink>
      </nav>
    </div>
  );
}
