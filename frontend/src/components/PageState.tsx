import { AlertCircle, RotateCcw } from 'lucide-react';
import { useI18n } from '../i18n';

export function PageLoading({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="page-state" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <p>{label ?? t('common.loading')}</p>
    </div>
  );
}

export function PageError({ message, retry }: { message: string; retry(): void }) {
  const { t } = useI18n();
  return (
    <div className="page-state error" role="alert">
      <AlertCircle aria-hidden="true" />
      <h2>{t('common.loadErrorTitle')}</h2>
      <p>{message}</p>
      <button className="button secondary" type="button" onClick={retry}>
        <RotateCcw aria-hidden="true" /> {t('common.retry')}
      </button>
    </div>
  );
}
