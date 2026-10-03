import { RotateCcw } from 'lucide-react';
import { useRef, useState, type FormEvent } from 'react';
import { api, ApiError } from '../api/client';
import { useModalDialog } from '../hooks/useModalDialog';
import { useI18n } from '../i18n';
import type { Deck } from '../types';

export function ProgressReset({ decks, defaultDeckId }: { decks: Deck[]; defaultDeckId: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [deckId, setDeckId] = useState('');
  const [password, setPassword] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const close = () => {
    if (inFlight.current) return;
    setOpen(false); setPassword(''); setConfirmed(false); setError('');
  };
  const dialogRef = useModalDialog<HTMLElement>(open, close);
  const scope = decks.find((deck) => deck.id === deckId)?.title ?? t('reset.allDecks');

  async function reset(event: FormEvent) {
    event.preventDefault();
    if (!confirmed || !password || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError('');
    try {
      await api('/account/progress/reset', {
        method: 'POST', body: JSON.stringify({ deck_id: deckId || null, password, confirm: true }),
      });
      setSuccess(t('reset.success', { scope }));
      setOpen(false); setPassword(''); setConfirmed(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t('common.genericError'));
    } finally {
      inFlight.current = false; setBusy(false);
    }
  }

  return <>
    <section className="panel reset-progress-card">
      <header><span className="panel-icon"><RotateCcw /></span><div><h2>{t('reset.title')}</h2><p>{t('reset.intro')}</p></div></header>
      <button type="button" className="button secondary wide" onClick={() => { setDeckId(defaultDeckId); setSuccess(''); setOpen(true); }}>{t('reset.open')}</button>
      {success && <p role="status">{success}</p>}
    </section>
    {open && <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
      <section ref={dialogRef} tabIndex={-1} className="detail-dialog reset-progress-dialog" role="dialog" aria-modal="true" aria-labelledby="reset-title" aria-describedby="reset-description">
        <h2 id="reset-title">{t('reset.title')}</h2>
        <p id="reset-description">{t('reset.description')}</p>
        <form onSubmit={reset}>
          <label className="reset-scope"><span>{t('reset.scope')}</span><select data-autofocus value={deckId} disabled={busy} onChange={(event) => { setDeckId(event.target.value); setConfirmed(false); }}><option value="">{t('reset.allDecks')}</option>{decks.map((deck) => <option key={deck.id} value={deck.id}>{deck.title}</option>)}</select></label>
          <label className="field"><span>{t('settings.confirmPassword')}</span><div><input type="password" autoComplete="current-password" required disabled={busy} value={password} onChange={(event) => setPassword(event.target.value)} /></div></label>
          <label className="reset-confirm"><input type="checkbox" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} /><span>{t('reset.confirm', { scope })}</span></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="dialog-actions"><button type="button" className="button secondary" disabled={busy} onClick={close}>{t('common.cancel')}</button><button className="button danger" disabled={!password || !confirmed || busy}>{busy ? t('reset.busy') : t('reset.submit')}</button></div>
        </form>
      </section>
    </div>}
  </>;
}
