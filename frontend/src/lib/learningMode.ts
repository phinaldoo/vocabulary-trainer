import type { Deck } from '../types';

export function isSpecialVerbDeck(deck: Deck): boolean {
  return deck.front_matcher === 'latin-principal-parts-v1';
}

export function learnPath(specialVerbs: boolean): string {
  return specialVerbs ? '/verben/lernen' : '/lernen';
}

export function decksPath(specialVerbs: boolean): string {
  return specialVerbs ? '/decks?kind=special_verbs' : '/decks';
}
