import { describe, expect, it } from 'vitest';
import { translate } from '.';
import { detectBrowserLanguage, normalizeLanguage, supportedLanguages } from './locale';
import { messageRows } from './messages';

describe('internationalization', () => {
  it('normalizes browser language variants and falls back to English', () => {
    expect(normalizeLanguage('de-AT')).toBe('de');
    expect(normalizeLanguage('en_US')).toBe('en');
    expect(normalizeLanguage('es-MX')).toBe('es');
    expect(normalizeLanguage('hi-IN')).toBe('hi');
    expect(normalizeLanguage('zh-TW')).toBe('zh-Hans');
    expect(normalizeLanguage('fr-FR')).toBeNull();
    expect(detectBrowserLanguage(['fr-FR', 'es-ES'])).toBe('es');
    expect(detectBrowserLanguage(['fr-FR'])).toBe('en');
  });

  it('has unique, non-empty translations for every supported language', () => {
    const keys = messageRows.map(([key]) => key);
    expect(new Set(keys).size).toBe(keys.length);
    for (const [key] of messageRows) {
      for (const language of supportedLanguages) {
        expect(translate(language, key).trim(), `${language}:${key}`).not.toBe('');
      }
    }
  });

  it('keeps the same interpolation variables in every translation', () => {
    const variables = (value: string) => [...value.matchAll(/{{(\w+)}}/g)]
      .map((match) => match[1])
      .sort();
    for (const [key, english, ...translations] of messageRows) {
      for (const translation of translations) {
        expect(variables(translation), key).toEqual(variables(english));
      }
    }
  });

  it('interpolates localized variables', () => {
    expect(translate('es', 'common.pageOf', { page: 2, pages: 5 })).toBe('Página 2 de 5');
    expect(translate('zh-Hans', 'dashboard.cardsWaitingMany', { count: 3 })).toContain('3');
  });
});
