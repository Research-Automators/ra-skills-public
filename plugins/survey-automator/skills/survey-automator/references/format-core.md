# Survey Export Format — core

Documentation for the JSON format used to export survey definitions and collected responses. The spec is split into three files:

- `format-core.md` (this file) — principles, top-level structure, key order, category questions and how to treat calculated variables. Read for every task.
- `format-questions.md` — questions, answers, interfaces, groups, points, matrices and grids, conditions, texts and bookmarks. Read when authoring or changing questions (Tasks 1 and 2).
- `format-data.md` — responses, built-in system fields and participants. Read when generating responses or participants (Tasks 1, 3 and 4).

All values in `responses` and `participants` are strings, whatever the underlying data type.

## Format principles

People and AI both read and write this JSON, so it stays clean and flat. Every key follows these rules:

- **Plain values first.** A key holds a string, number or boolean whenever one value is enough. An object is used only for real structure.
- **Leave out what can be inferred or is the default.** For example, a question whose answers have `calculation` is a calculated question — it needs no extra key.
- **Short form and long form.** When a plain value sometimes needs extra settings, the key takes either the plain value (short form) or an object (long form). Write the short form whenever nothing else is set — that is what the export writes.
- **Ids are the same everywhere.** Question, row and answer `id`s are the client references used in responses and expressions (`{Gender}:{2}`).
- **Texts are strings.** A text shown in the survey is a plain string with a few formatting tags and `{tokens}`. It becomes an object only when a field needs settings or the text is raw HTML. See [Texts](format-questions.md#texts).

---

## Top-level structure

```json
{
  "questions": [ ...question objects... ],
  "groups": [ ...group objects... ],
  "messages": [ ...outbound message objects... ],
  "responses": [ ...response objects... ],
  "surveyMessages": { ...platform-message overrides... }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `questions` | array | Yes | Ordered list of question/header objects defining the survey. |
| `groups` | array | No | Optional report sections. Only needed for the `groupId` form of grouping — see [Groups (report sections)](format-questions.md#groups-report-sections). The simpler per-question `group` string form needs no top-level array. |
| `responses` | array | No | One object per respondent, containing their answers. Omit (or use `[]`) for survey definitions without collected/example data. |
| `participants` | array | No | One object per pre-loaded invitee, containing only `system` and `category` field values (no survey answers). **Mutually exclusive with `responses`** — a file represents either collected answers or an invite list, never both. See [Participants](format-data.md#participants). |
| `messages` | array | No | Outbound email/SMS messages — invitations, reminders, thank-yous, notifications — sent to participants. See `invitations.md` for full detail. **Not the same as `surveyMessages`.** |
| `surveyMessages` | object | No | Optional overrides for the platform-level **screens shown to respondents inside the survey** (thank-you screen, screened-out screen, etc.). When omitted, the platform shows its own defaults. See `messages.md`. **Not the same as `messages`.** |

### Top-level key order

Whichever of `responses` or `participants` is present (non-empty) **must be the last top-level key**. The other keys (`questions`, `surveyMessages`, `messages`) may appear in any order before it. Recommended order: `questions` → `messages` → `surveyMessages` → (`participants` *or* `responses`). The validator enforces only the last-key constraint and the mutual exclusion of `responses` and `participants`.

Empty arrays (`"responses": []`, `"participants": []`) don't count as "present" for either rule — they're harmless and may appear anywhere.

This rule exists because response data is bulky and lives more naturally at the bottom of the file, after the survey definition and metadata that describe it. The validator rejects files where `responses` is followed by another top-level key.

---

## Category questions

`type: "category"` represents background data known about the respondent before the survey is sent. Only `id`, `type`, and `text` are required.

A category may have `answers` when the attribute has a fixed value set, or no `answers` when it is a free-text identifier. Category answers can be referenced in `condition` definitions just like any other question's answers (`{KnownGender}:{2}`), and a category can be bookmarked in texts (`{CustomerID}`). See [Background data in conditions and texts](format-questions.md#background-data-in-conditions-and-texts).

```json
{
  "id": "KnownGender",
  "type": "category",
  "text": "Gender",
  "answers": [
    { "id": "1", "text": "Men" },
    { "id": "2", "text": "Women" }
  ]
}
```

```json
{
  "id": "CustomerID",
  "type": "category",
  "text": "Customer ID"
}
```

---

## Calculated variables

Calculated variables — calculated, coded, `period` and `categoryVariable` questions — are documented in `calculated-variables.md`. **Read it only when the user asks for derived, grouped or recoded variables, coded open ends, or period/category breakdowns, or when the file adds questions to an existing project.** Otherwise, when you meet them in an existing survey: they are hidden from respondents, keep their keys (`calculation`, `calculated`, `coded`, `codes`, `period`, `category`, `color`) unchanged, and give them no values when generating responses (see `format-data.md`).
