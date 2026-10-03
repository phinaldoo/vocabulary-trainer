import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { I18nProvider } from '../i18n';
import { CardMetadata } from './CardMetadata';

describe('vocabulary details', () => {
  it('labels all four legacy fields in order and keeps unrelated metadata', () => {
    const { container } = render(<I18nProvider><CardMetadata metadata={{
      genus: 'f.', partOfSpeech: 'noun', info: 'First declension', note: 'Fourth field',
      grammar: 'Preserved grammar', empty: '',
    }} /></I18nProvider>);
    expect(Array.from(container.querySelectorAll('dt'), (node) => node.textContent)).toEqual([
      'Gender', 'Part of speech', 'Additional information', 'Additional information 2', 'grammar',
    ]);
    expect(screen.getByText('Fourth field')).toBeInTheDocument();
    expect(screen.getByText('Preserved grammar')).toBeInTheDocument();
  });

  it('prefers canonical values and omits empty fields', () => {
    const { container } = render(<I18nProvider><CardMetadata metadata={{
      gender: 'm.', genus: 'f.', additional_info_2: 'Last detail', part_of_speech: ' ',
    }} /></I18nProvider>);
    expect(screen.getByText('m.')).toBeInTheDocument();
    expect(screen.queryByText('f.')).not.toBeInTheDocument();
    expect(container.querySelectorAll('dt')).toHaveLength(2);
  });
});
