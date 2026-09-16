import { AlertTriangle, Check, ChevronDown, LogOut, Mail, Save, Trash2, UserRound } from 'lucide-react';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useResource } from '../api/useResource';
import { useAuth } from '../auth/AuthContext';
import { useModalDialog } from '../hooks/useModalDialog';
import { useI18n } from '../i18n';
import { languageNames, supportedLanguages } from '../i18n/locale';
import type { Deck, Direction, InputMode, Section, UiLanguage, User } from '../types';

export function SettingsPage() {
  const { user, updateUser, clearUser, logout } = useAuth();
  const { date, language, setLanguage, t } = useI18n();
  const decks = useResource(() => api<Deck[]>('/decks'));
  const [dailyGoal, setDailyGoal] = useState(user?.daily_goal ?? 12);
  const [direction, setDirection] = useState<Direction>(user?.direction ?? 'forward');
  const [inputMode, setInputMode] = useState<InputMode>(user?.input_mode ?? 'typing');
  const [interfaceLanguage, setInterfaceLanguage] = useState<UiLanguage>(user?.language ?? language);
  const [deckId, setDeckId] = useState(user?.selected_deck_id ?? '');
  const [sectionId, setSectionId] = useState(user?.selected_section_ids && user.selected_section_ids.length > 1 ? 'multiple' : user?.selected_section_id ?? '');
  const sections = useResource(() => deckId ? api<Section[]>(`/sections?deck_id=${deckId}`) : Promise.resolve([]), deckId);
  const [saving, setSaving] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const saveQueue = useRef(Promise.resolve());
  const saveVersion = useRef(0);
  const [error, setError] = useState('');
  const [profileName, setProfileName] = useState(user?.display_name ?? '');
  const [profileEmail, setProfileEmail] = useState(user?.email ?? '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [password, setPassword] = useState('');
  const closeDelete = () => { setConfirmDelete(false); setPassword(''); setError(''); };
  const deleteDialogRef = useModalDialog<HTMLElement>(confirmDelete, closeDelete);

  useEffect(() => {
    if (!deckId && decks.data?.[0]) setDeckId(decks.data[0].id);
  }, [deckId, decks.data]);

  useEffect(() => {
    if (!user) return;
    setProfileName(user.display_name);
    setProfileEmail(user.email);
  }, [user?.display_name, user?.email]);

  if (!user) return null;
  const selectedDeck = decks.data?.find((deck) => deck.id === deckId) ?? decks.data?.[0] ?? null;
  const profileChanged = profileName.trim() !== user.display_name
    || profileEmail.trim().toLowerCase() !== user.email;

  function save(changes: Partial<Pick<User, 'daily_goal' | 'direction' | 'input_mode' | 'language' | 'selected_deck_id' | 'selected_section_id'>>) {
    const version = ++saveVersion.current;
    const body = JSON.stringify({
      daily_goal: dailyGoal,
      direction,
      input_mode: inputMode,
      language: interfaceLanguage,
      selected_deck_id: selectedDeck?.id ?? null,
      selected_section_id: sectionId === 'multiple' ? null : sectionId || null,
      selected_section_ids: 'selected_section_id' in changes
        ? (changes.selected_section_id ? [changes.selected_section_id] : [])
        : sectionId === 'multiple' ? user?.selected_section_ids : sectionId ? [sectionId] : [],
      ...changes,
    });
    setSettingsSaving(true); setSaved(false); setError('');
    // Serialize writes so rapid changes cannot overwrite newer preferences.
    saveQueue.current = saveQueue.current.then(async () => {
      try {
        const next = await api<User>('/account/settings', { method: 'PATCH', body });
        if (version === saveVersion.current) {
          updateUser(next);
          setSaved(true);
        }
      } catch (caught) {
        if (version === saveVersion.current) {
          setError(caught instanceof ApiError ? caught.message : t('settings.saveError'));
        }
      } finally {
        if (version === saveVersion.current) setSettingsSaving(false);
      }
    });
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault(); setProfileSaving(true); setProfileSaved(false); setProfileError('');
    try {
      const next = await api<User>('/account/profile', {
        method: 'PATCH',
        body: JSON.stringify({ display_name: profileName, email: profileEmail }),
      });
      updateUser(next); setProfileName(next.display_name); setProfileEmail(next.email); setProfileSaved(true);
      window.setTimeout(() => setProfileSaved(false), 2500);
    } catch (caught) { setProfileError(caught instanceof ApiError ? caught.message : t('settings.accountSaveError')); }
    finally { setProfileSaving(false); }
  }

  async function deleteAccount() {
    setSaving(true); setError('');
    try {
      await api('/account', { method: 'DELETE', body: JSON.stringify({ password }) });
      clearUser();
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : t('settings.deleteError')); setSaving(false); }
  }

  return <main className="page-wrap settings-page">
    <header className="page-header"><p className="section-kicker">{t('settings.kicker')}</p><h1>{t('settings.title')}</h1><p>{t('settings.intro')}</p></header>
    <section className="settings-grid">
      <section className="panel settings-form">
        <header><span className="panel-icon violet"><Save /></span><div><h2>{t('settings.learning')}</h2><p>{t('settings.learningIntro')}</p></div></header>
        <label><span>{t('common.language')}</span><div className="select-wrap"><select value={interfaceLanguage} onChange={(event) => { const next = event.target.value as UiLanguage; setInterfaceLanguage(next); setLanguage(next); save({ language: next }); }}>{supportedLanguages.map((value) => <option key={value} value={value}>{languageNames[value]}</option>)}</select><ChevronDown /></div></label>
        {selectedDeck && <><label><span>{t('settings.defaultDeck')}</span><div className="select-wrap"><select value={selectedDeck.id} onChange={(event) => { setDeckId(event.target.value); setSectionId(''); save({ selected_deck_id: event.target.value, selected_section_id: null }); }}>{decks.data?.map((deck) => <option key={deck.id} value={deck.id}>{deck.title}</option>)}</select><ChevronDown /></div></label><label><span>{t('settings.defaultSection')}</span><div className="select-wrap"><select value={sectionId} onChange={(event) => { setSectionId(event.target.value); save({ selected_section_id: event.target.value || null }); }}><option value="">{t('common.allSections')}</option>{sectionId === 'multiple' && <option value="multiple" disabled>{sections.data?.filter((section) => user.selected_section_ids?.includes(section.id)).map((section) => section.title).join(', ') || t('learn.chooseSection')}</option>}{sections.data?.map((section) => <option key={section.id} value={section.id}>{section.title}</option>)}</select><ChevronDown /></div></label></>}
        <label><span>{t('settings.dailyGoal')}</span><div className="select-wrap"><select value={dailyGoal} onChange={(event) => { setDailyGoal(Number(event.target.value)); save({ daily_goal: Number(event.target.value) }); }}>{[5, 10, 12, 20, 30, 50, 100, 150, 200, 250, 500].map((value) => <option key={value} value={value}>{t(value === 1 ? 'common.cardsOne' : 'common.cardsMany', { count: value })}</option>)}</select><ChevronDown /></div></label>
        <label><span>{t('settings.direction')}</span><div className="select-wrap"><select value={direction} onChange={(event) => { setDirection(event.target.value as Direction); save({ direction: event.target.value as Direction }); }}><option value="forward">{selectedDeck ? `${selectedDeck.front_label} → ${selectedDeck.back_label}` : t('settings.frontToBack')}</option><option value="reverse">{selectedDeck ? `${selectedDeck.back_label} → ${selectedDeck.front_label}` : t('settings.backToFront')}</option><option value="mixed">{t('settings.mixed')}</option></select><ChevronDown /></div></label>
        <fieldset><legend>{t('settings.defaultMode')}</legend><div className="settings-modes"><label className={inputMode === 'typing' ? 'selected' : ''}><input type="radio" name="mode" checked={inputMode === 'typing'} onChange={() => { setInputMode('typing'); save({ input_mode: 'typing' }); }} /><strong>{t('settings.typeAnswer')}</strong><small>{t('settings.typeAnswerHint')}</small></label><label className={inputMode === 'reveal' ? 'selected' : ''}><input type="radio" name="mode" checked={inputMode === 'reveal'} onChange={() => { setInputMode('reveal'); save({ input_mode: 'reveal' }); }} /><strong>{t('settings.revealCard')}</strong><small>{t('settings.revealCardHint')}</small></label></div></fieldset>
        {error && <p className="form-error" role="alert">{error}</p>}
        <p role="status">{settingsSaving ? t('common.saving') : saved ? t('common.saved') : ''}</p>
      </section>
      <aside><section className="panel account-card"><header><span className="panel-icon"><UserRound /></span><div><h2>{t('settings.account')}</h2><p>{t('settings.accountIntro')}</p></div></header><form className="account-profile-form" onSubmit={saveProfile}><label className="field"><span>{t('settings.name')}</span><div><UserRound /><input type="text" autoComplete="name" minLength={2} maxLength={80} required value={profileName} onChange={(event) => setProfileName(event.target.value)} /></div></label><label className="field account-email-field" htmlFor="account-email"><span>{t('settings.email')}</span><div><Mail /><input id="account-email" type="email" autoComplete="email" aria-describedby="account-email-hint" maxLength={320} required value={profileEmail} onChange={(event) => setProfileEmail(event.target.value)} /></div></label><small id="account-email-hint" className="field-hint">{t('settings.emailSignInHint')}</small>{profileError && <p className="form-error" role="alert">{profileError}</p>}<button className="button primary wide" disabled={profileSaving || !profileChanged}>{profileSaved ? <><Check /> {t('common.saved')}</> : profileSaving ? t('common.saving') : <><Save /> {t('settings.saveAccount')}</>}</button></form><dl className="account-meta"><div><dt>{t('settings.role')}</dt><dd>{user.role === 'admin' ? t('settings.roleAdmin') : t('settings.roleLearner')}</dd></div><div><dt>{t('settings.memberSince')}</dt><dd>{date(user.created_at)}</dd></div></dl>{user.role === 'admin' && <Link className="button secondary wide" to="/admin">{t('settings.manageDecks')}</Link>}<button className="button secondary wide" onClick={() => void logout()}><LogOut /> {t('nav.logout')}</button></section><section className="panel danger-zone"><header><span className="panel-icon red"><AlertTriangle /></span><div><h2>{t('settings.danger')}</h2><p>{t('settings.dangerIntro')}</p></div></header><button className="button danger subtle" onClick={() => setConfirmDelete(true)}><Trash2 /> {t('settings.deleteAccount')}</button></section></aside>
    </section>
    {confirmDelete && <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDelete(); }}><section ref={deleteDialogRef} tabIndex={-1} className="detail-dialog delete-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-description"><span className="panel-icon red"><Trash2 /></span><h2 id="delete-title">{t('settings.deleteTitle')}</h2><p id="delete-description">{t('settings.deleteDescription')}</p><label className="field"><span>{t('settings.confirmPassword')}</span><div><input data-autofocus type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></div></label>{error && <p className="form-error" role="alert">{error}</p>}<div className="dialog-actions"><button className="button secondary" onClick={closeDelete}>{t('common.cancel')}</button><button className="button danger" disabled={!password || saving} onClick={() => void deleteAccount()}>{saving ? t('settings.deleting') : t('settings.deleteForever')}</button></div></section></div>}
  </main>;
}
