import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, ensureCsrf } from '../api/client';
import { useI18n } from '../i18n';
import { detectBrowserLanguage } from '../i18n/locale';
import type { User } from '../types';

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string, displayName: string): Promise<void>;
  logout(): Promise<void>;
  refresh(): Promise<void>;
  updateUser(user: User): void;
  clearUser(): void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { setLanguage } = useI18n();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const applyUser = useCallback((next: User) => {
    setUser(next);
    if (next.language) setLanguage(next.language);
  }, [setLanguage]);

  const refresh = useCallback(async () => {
    try {
      await ensureCsrf();
      let next = await api<User>('/auth/me');
      if (!next.language) {
        next = await api<User>('/account/language/initialize', {
          method: 'POST',
          body: JSON.stringify({ language: detectBrowserLanguage() }),
        });
      }
      applyUser(next);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [applyUser]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const clear = () => {
      setUser(null);
      setLanguage(detectBrowserLanguage());
    };
    window.addEventListener('vocabulary-trainer:unauthorized', clear);
    return () => window.removeEventListener('vocabulary-trainer:unauthorized', clear);
  }, [setLanguage]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async login(email, password) {
        const next = await api<User>('/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email, password, language: detectBrowserLanguage() }),
        });
        applyUser(next);
      },
      async register(email, password, displayName) {
        const next = await api<User>('/auth/register', {
          method: 'POST',
          body: JSON.stringify({ email, password, display_name: displayName, language: detectBrowserLanguage() }),
        });
        applyUser(next);
      },
      async logout() {
        try {
          await api<void>('/auth/logout', { method: 'POST' });
        } finally {
          setUser(null);
          setLanguage(detectBrowserLanguage());
          try {
            await ensureCsrf(true);
          } catch {
            // Logging out locally remains useful while the server is unavailable.
          }
        }
      },
      refresh,
      updateUser: applyUser,
      clearUser: () => {
        setUser(null);
        setLanguage(detectBrowserLanguage());
      },
    }),
    [applyUser, loading, refresh, setLanguage, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
