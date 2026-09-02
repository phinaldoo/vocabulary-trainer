import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { UiLanguage } from '../types';
import { detectBrowserLanguage, getActiveLanguage, setActiveLanguage } from './locale';
import { messages } from './messages';
import type { MessageKey } from './messages';

type Variables = Record<string, string | number>;

export function translate(language: UiLanguage, key: MessageKey, variables: Variables = {}): string {
  let value = messages[key][language] ?? messages[key].en;
  for (const [name, replacement] of Object.entries(variables)) {
    value = value.replaceAll(`{{${name}}}`, String(replacement));
  }
  return value;
}

export function translateCurrent(key: MessageKey, variables?: Variables): string {
  return translate(getActiveLanguage(), key, variables);
}

type I18nValue = {
  language: UiLanguage;
  setLanguage(language: UiLanguage): void;
  t(key: MessageKey, variables?: Variables): string;
  number(value: number): string;
  date(value: Date | string, options?: Intl.DateTimeFormatOptions): string;
};

const I18nContext = createContext<I18nValue | null>(null);

function applyDocumentLanguage(language: UiLanguage): void {
  setActiveLanguage(language);
  if (typeof document === 'undefined') return;
  document.documentElement.lang = language;
  document.documentElement.dir = 'ltr';
  document.title = translate(language, 'meta.title');
  document.querySelector<HTMLMetaElement>('meta[name="description"]')?.setAttribute(
    'content',
    translate(language, 'meta.description'),
  );
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<UiLanguage>(() => {
    const detected = detectBrowserLanguage();
    applyDocumentLanguage(detected);
    return detected;
  });

  const setLanguage = useCallback((next: UiLanguage) => {
    applyDocumentLanguage(next);
    setLanguageState(next);
  }, []);

  const value = useMemo<I18nValue>(() => ({
    language,
    setLanguage,
    t: (key, variables) => translate(language, key, variables),
    number: (number) => new Intl.NumberFormat(language).format(number),
    date: (input, options = { dateStyle: 'medium' }) => new Intl.DateTimeFormat(language, options).format(
      typeof input === 'string' ? new Date(input) : input,
    ),
  }), [language, setLanguage]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error('useI18n must be used within I18nProvider');
  return context;
}
