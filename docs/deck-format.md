# Deck manifest format

Administrators can import a complete shared deck from **Admin → Deck import**.
The JSON document is validated before any catalogue data changes, and the
import runs in one database transaction.

```json
{
  "schemaVersion": 1,
  "id": "synthetic-demo",
  "version": 1,
  "title": "Synthetic import demo",
  "description": "Optional description",
  "front": {
    "label": "Prompt",
    "language": "zxx",
    "matcher": "generic-v1"
  },
  "back": {
    "label": "Answer",
    "language": "zxx",
    "matcher": "generic-v1"
  },
  "sections": [
    { "id": "generated-samples", "title": "Generated samples", "order": 1 }
  ],
  "cards": [
    {
      "id": "nuvexa-47",
      "section": "generated-samples",
      "order": 1,
      "front": { "text": "nuvexa-47", "answers": [] },
      "back": { "text": "qarilo-82", "answers": [] },
      "metadata": { "kind": "synthetic" }
    }
  ]
}
```

## Import rules

- `id` is the permanent deck slug. Section and card `id` values are permanent
  keys inside that deck. Keep all three stable across versions.
- `version` must increase when content changes. Importing the exact same file is
  idempotent; different content with the same version is rejected.
- `order` values must be unique within their deck or section collection.
- The optional `license` and `attribution` fields describe deck content rights.
- A card may omit `section` or set it to `null`.
- Cards missing from a newer manifest are archived, not deleted. Existing study
  history and frozen sessions therefore remain valid.
- A newly imported deck is a draft. Review it in the admin UI, then publish it
  to make it visible to every user.
- The maximum import size is 10 MiB and one manifest can contain up to 100,000
  cards.

## Answer matching

Each side declares one matcher:

- `generic-v1`: Unicode-aware, case-insensitive exact matching after punctuation
  and whitespace normalization. Put accepted alternatives in `answers`.
- `german-v1`: German dictionary-form matching with article, parenthesis, and
  common keyboard-spelling handling. All comma-/semicolon-separated meanings and
  separate utterances are required, in any order. Slash variants remain alternatives;
  parenthetical content, articles, punctuation, and extra whitespace are optional.
  Word boundaries are still required. Incomplete answers report missing meanings.
  Explicit `answers` entries remain alternative complete answer specifications;
  do not use them to list individual meanings of a multi-meaning answer.
- `latin-v1`: Latin principal-part and construction matching used by migrated
  legacy decks.

Language values are BCP 47-style tags such as `en`, `de`, `la`, or `pt-BR`.
Metadata is an arbitrary JSON object shown as supplemental card information.

The complete working example is in `examples/synthetic-demo.json`.
