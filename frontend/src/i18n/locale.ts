import type { UiLanguage } from '../types';

export const supportedLanguages: readonly UiLanguage[] = ['en', 'zh-Hans', 'hi', 'es', 'de'];
export const defaultLanguage: UiLanguage = 'en';

const supported = new Set<string>(supportedLanguages);
let activeLanguage: UiLanguage = defaultLanguage;

export function normalizeLanguage(value: string | null | undefined): UiLanguage | null {
  if (!value) return null;
  const normalized = value.trim().replaceAll('_', '-');
  if (supported.has(normalized)) return normalized as UiLanguage;
  const primary = normalized.split('-')[0]?.toLocaleLowerCase('en-US');
  if (primary === 'zh') return 'zh-Hans';
  if (primary && supported.has(primary)) return primary as UiLanguage;
  return null;
}

export function detectBrowserLanguage(
  languages: readonly string[] = typeof navigator === 'undefined'
    ? []
    : (navigator.languages.length ? navigator.languages : [navigator.language]),
): UiLanguage {
  for (const candidate of languages) {
    const normalized = normalizeLanguage(candidate);
    if (normalized) return normalized;
  }
  return defaultLanguage;
}

export function getActiveLanguage(): UiLanguage {
  return activeLanguage;
}

export function setActiveLanguage(language: UiLanguage): void {
  activeLanguage = language;
}

export const languageNames: Record<UiLanguage, string> = {
  en: 'English',
  'zh-Hans': '中文（简体）',
  hi: 'हिन्दी',
  es: 'Español',
  de: 'Deutsch',
};
