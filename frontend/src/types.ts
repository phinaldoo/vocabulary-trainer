export type Direction = 'forward' | 'reverse' | 'mixed';
export type CardDirection = Exclude<Direction, 'mixed'>;
export type InputMode = 'typing' | 'reveal';
export type UiLanguage = 'en' | 'zh-Hans' | 'hi' | 'es' | 'de';
export type DeckStatus = 'draft' | 'published' | 'archived';
export type MatcherProfile = 'generic-v1' | 'german-v1' | 'latin-v1';

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: 'user' | 'admin';
  language: UiLanguage | null;
  daily_goal: number;
  direction: Direction;
  input_mode: InputMode;
  selected_deck_id: string | null;
  selected_section_id: string | null;
  created_at: string;
};

export type AdminUser = Pick<User, 'id' | 'email' | 'display_name' | 'role' | 'created_at'>;

export type AdminUserPage = {
  items: AdminUser[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type Deck = {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  front_label: string;
  back_label: string;
  front_language: string;
  back_language: string;
  front_matcher: MatcherProfile;
  back_matcher: MatcherProfile;
  status: DeckStatus;
  version: number;
  license: string | null;
  attribution: string | null;
  sort_order: number;
  section_count: number;
  card_count: number;
};

export type Section = {
  id: string;
  deck_id: string;
  stable_key: string;
  title: string;
  sort_order: number;
  active: boolean;
  total: number;
  learned: number;
  mastered: number;
  due: number;
  progress_percent: number;
};

export type CardStatus = 'new' | 'learning' | 'familiar' | 'mastered' | 'difficult';

export type Card = {
  id: string;
  deck_id: string;
  section_id: string | null;
  section_title: string | null;
  stable_key: string;
  sort_order: number;
  front_text: string;
  back_text: string;
  front_answers: string[];
  back_answers: string[];
  metadata: Record<string, unknown>;
  active: boolean;
  favorite: boolean;
  status: CardStatus;
};

export type CardPage = {
  items: Card[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type StudyCard = {
  item_id: string;
  card_id: string;
  section_id: string | null;
  section_title: string | null;
  ordinal: number;
  direction: CardDirection;
  prompt: string;
  prompt_language: string;
  answer_language: string;
  metadata: Record<string, unknown>;
  state_version: number;
  is_new: boolean;
};

export type StudySession = {
  id: string;
  deck_id: string;
  deck_title: string;
  section_id: string | null;
  section_title: string | null;
  front_label: string;
  back_label: string;
  front_language: string;
  back_language: string;
  direction: Direction;
  input_mode: InputMode;
  total: number;
  reviewed: number;
  correct_reviewed: number;
  complete: boolean;
  cards: StudyCard[];
};

export type ReviewResult = {
  ok: boolean;
  correct: boolean;
  effective_rating: number;
  match_kind: string | null;
  solution: string;
  due_at: string;
  interval_days: number;
  version: number;
  reviewed: number;
  correct_reviewed: number;
  total: number;
  complete: boolean;
};

export type Dashboard = {
  deck: Deck | null;
  due_count: number;
  reviewed_today: number;
  learned_count: number;
  mastered_count: number;
  streak: number;
  total_count: number;
  progress_percent: number;
  weekly_activity: Array<{ date: string; count: number; today: boolean }>;
  difficult: Array<{
    id: string;
    deck_id: string;
    section_id: string | null;
    section_title: string | null;
    front_text: string;
    back_text: string;
    front_language: string;
    lapses: number;
  }>;
};

export type Progress = {
  deck: Deck | null;
  total: number;
  learned: number;
  secure: number;
  familiar: number;
  learning: number;
  accuracy: number;
  reviews: number;
  streak: number;
  sections: Section[];
};

export type ImportResult = {
  deck: Deck;
  created_sections: number;
  updated_sections: number;
  created_cards: number;
  updated_cards: number;
  archived_cards: number;
  unchanged: boolean;
};
