import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';

export function Brand({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  return (
    <Link className="brand" to="/" aria-label={t('brand.home')}>
      <span className={compact ? 'brand-mark compact' : 'brand-mark'} aria-hidden="true">V</span>
      <span>verba</span>
    </Link>
  );
}
