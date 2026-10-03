import { useI18n } from '../i18n';
import { extraMetadata, metadataFields, metadataValue } from '../lib/vocabularyMetadata';

export function CardMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const { t } = useI18n();
  const entries = [
    ...metadataFields.map(({ key, label }) => ({ key, label: t(label), value: metadataValue(metadata, key) })),
    ...Object.entries(extraMetadata(metadata))
      .filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value))
      .map(([key, value]) => ({ key, label: key, value: String(value) })),
  ].filter(({ value }) => value.trim());
  if (!entries.length) return null;
  return <dl className="vocabulary-metadata">{entries.map(({ key, label, value }) =>
    <div key={key}><dt>{label}</dt><dd>{value}</dd></div>,
  )}</dl>;
}
