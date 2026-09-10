import { translateCurrent } from '../i18n';
import type { MessageKey } from '../i18n/messages';

type ErrorEnvelope = { error?: { code?: string; message?: string } };

const errorMessages: Record<string, MessageKey> = {
  admin_required: 'api.adminRequired',
  origin_not_allowed: 'api.requestRejected',
  cross_site_request: 'api.requestRejected',
  csrf_invalid: 'api.csrfInvalid',
  unauthorized: 'api.signInRequired',
  session_expired: 'api.sessionExpired',
  rate_limited: 'api.rateLimited',
  validation_error: 'api.validationError',
  registration_failed: 'api.registrationFailed',
  invalid_credentials: 'api.invalidCredentials',
  email_in_use: 'api.emailInUse',
  user_not_found: 'api.userNotFound',
  deck_not_found: 'api.deckNotFound',
  section_not_found: 'api.sectionNotFound',
  password_invalid: 'api.passwordInvalid',
  invalid_answer_spec: 'api.invalidAnswerSpec',
  deck_version_conflict: 'api.deckVersionConflict',
  deck_version_older: 'api.deckVersionOlder',
  no_cards: 'api.noCards',
  study_session_not_found: 'api.studySessionNotFound',
  study_item_not_found: 'api.studyItemNotFound',
  wrong_study_mode: 'api.wrongStudyMode',
  already_reviewed: 'api.alreadyReviewed',
  stale_review: 'api.staleReview',
  answer_not_revealed: 'api.answerNotRevealed',
  answer_not_checked: 'api.answerNotChecked',
  review_conflict: 'api.reviewConflict',
  deck_slug_exists: 'api.deckSlugExists',
  deck_conflict: 'api.deckConflict',
  matcher_incompatible: 'api.matcherIncompatible',
  deck_empty: 'api.deckEmpty',
  section_conflict: 'api.orderConflict',
  card_conflict: 'api.orderConflict',
  card_not_found: 'api.cardNotFound',
  payload_too_large: 'api.payloadTooLarge',
  idempotency_mismatch: 'api.idempotencyMismatch',
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = 'request_failed',
  ) {
    super(message);
  }
}

export function createIdempotencyKey(): string {
  const webCrypto = globalThis.crypto;
  if (typeof webCrypto?.randomUUID === 'function') return webCrypto.randomUUID();

  const bytes = new Uint8Array(16);
  if (typeof webCrypto?.getRandomValues === 'function') {
    webCrypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function cookie(name: string) {
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

let csrfPromise: Promise<string> | null = null;

export async function ensureCsrf(force = false): Promise<string> {
  const existing = cookie('vocabulary_trainer_csrf');
  if (existing && !force) return decodeURIComponent(existing);
  if (!csrfPromise || force) {
    csrfPromise = fetch('/api/v1/auth/csrf', { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) throw new ApiError(translateCurrent('common.securityError'), response.status);
        const payload = (await response.json()) as { csrf_token: string };
        return payload.csrf_token;
      })
      .finally(() => {
        csrfPromise = null;
      });
  }
  return csrfPromise;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers.set('X-CSRF-Token', await ensureCsrf());
  }
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    method,
    headers,
    credentials: 'include',
  });
  if (!response.ok) {
    let payload: ErrorEnvelope = {};
    try {
      payload = (await response.json()) as ErrorEnvelope;
    } catch {
      // Keep the user-safe fallback below.
    }
    const code = payload.error?.code ?? 'request_failed';
    const key = errorMessages[code];
    const error = new ApiError(
      key ? translateCurrent(key) : translateCurrent('common.genericError'),
      response.status,
      code,
    );
    if (response.status === 401) {
      window.dispatchEvent(new Event('vocabulary-trainer:unauthorized'));
    }
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
