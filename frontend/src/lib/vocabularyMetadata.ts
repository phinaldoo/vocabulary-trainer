export const metadataFields = [
  { key: 'gender', label: 'metadata.gender', aliases: ['gender', 'genus'] },
  { key: 'part_of_speech', label: 'metadata.partOfSpeech', aliases: ['part_of_speech', 'partOfSpeech', 'wortart'] },
  { key: 'additional_info', label: 'metadata.additionalInfo', aliases: ['additional_info', 'info', 'zusatzinformation'] },
  { key: 'additional_info_2', label: 'metadata.additionalInfo2', aliases: ['additional_info_2', 'note', 'zusatzinformation2'] },
] as const;

export type MetadataField = typeof metadataFields[number]['key'];
export type MetadataValues = Record<MetadataField, string>;

export function metadataValue(metadata: Record<string, unknown>, key: MetadataField): string {
  const field = metadataFields.find((entry) => entry.key === key)!;
  for (const alias of field.aliases) {
    const value = metadata[alias];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return '';
}

export function metadataValues(metadata: Record<string, unknown>): MetadataValues {
  return Object.fromEntries(metadataFields.map(({ key }) => [key, metadataValue(metadata, key)])) as MetadataValues;
}

export function extraMetadata(metadata: Record<string, unknown>): Record<string, unknown> {
  const known = new Set<string>(metadataFields.flatMap(({ aliases }) => [...aliases]));
  return Object.fromEntries(Object.entries(metadata).filter(([key]) => !known.has(key)));
}
