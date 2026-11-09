# Survey Export Format — responses and participants

Data reference: response objects, built-in system fields and participants. Top-level structure, key order and category questions are in `format-core.md`; question shapes are in `format-questions.md`.

## Response object

Each entry in `responses` is a flat key-value object representing one respondent's answers.

```json
{
  "Gender": "2",
  "Important": "1;3",
  "Advise": "Be positive and content with what you have.",
  "Age": "67",
  "Fulfilled.1": "9",
  "Aspects.1": "5",
  "Aspects.2": "6"
}
```

### Key formats

| Key format | Applies to | Description |
|---|---|---|
| `<QuestionId>` | `single`, `multiple`, `open` (non-matrix) | The question's `id` value. |
| `<QuestionId>.<RowNumber>` | Matrix rows | The row's `id` value (e.g. `"Aspects.1"`). In an [open grid](format-questions.md#open-grids) it is the key of the row's input (e.g. `"Hours.1"`). |
| `<RowId>:<AnswerId>` | Open grid rows | The same value with the `Open` answer's id added (e.g. `"Hours.1:1"`). The import accepts both forms; exports use the plain row id. Give each row only one of the two keys. |
| `<QuestionId>.<TriggerAnswerId>` | Connected-Open answers | When an `Open` answer has `connectedTo: "<id>"` and the respondent selected that option, the free-text value is keyed `<QuestionId>.<TriggerAnswerId>` (e.g. `"Important.9"` for the text attached to the answer with `id: "9"`). |

### Value formats

| Question type | Value format | Example |
|---|---|---|
| `single` | The selected answer's `id` | `"2"` |
| `multiple` | Semicolon-separated answer `id` values | `"1;3"` |
| `open` (text) | The literal text entered | `"Be positive..."` |
| `open` (`dataType: integer`) | Numeric value as a string | `"67"` |
| Matrix row | The selected answer's `id` for that row | `"5"` |
| Open grid row | The typed value, as for `open` (a numeric string with `dataType: "integer"`) | `"12"` |
| Numeric slider or ranking row | See `grid-interfaces.md` | `"64"` |
| `system` `EndTime` / `StartTime` | Timestamp as 14 digits `YYYYMMDDHHMMSS` | `"20240814160018"` |
| `system` `StatusText` | One of `Completed`, `Started`, `Screenout` | `"Completed"` |
| `system` (other) | Free-form string, whatever the platform recorded | `"…"` |

### Notes

- Response objects only contain keys for questions that the respondent answered. Unanswered questions are simply absent.
- Questions with `excluded: true` **are** present in responses. The flag reflects that the question was hidden from respondents during fieldwork or is a derived/calculated variable — it does not mean the data is absent.
- [Calculated variables](calculated-variables.md) can have values in files exported from the platform (a `period` value is a period text, e.g. `"2025-03"`; a `categoryVariable` question has none), but the platform calculates them again from the other answers after import. So keep such values when they're already in an input file, and never write them when generating responses.
- All values are strings, regardless of the underlying data type.

### Built-in response system fields

The platform records certain `system` fields on each response automatically. They are ordinary `type: "system"` questions in the `questions` array, keyed in responses by their `id`. Most system fields are free-form, but these carry a fixed shape:

| Field | Meaning | Format |
|---|---|---|
| `EndTime` | When the response was completed/last saved | 14 digits `YYYYMMDDHHMMSS`, e.g. `"20240814160018"` |
| `StartTime` | When the respondent began (rarely present) | 14 digits `YYYYMMDDHHMMSS` |
| `StatusText` | Completion status | `Completed`, `Started`, or `Screenout` |

```json
{
  "questions": [
    { "id": "EndTime", "type": "system", "text": "End timestamp" },
    { "id": "StatusText", "type": "system", "text": "StatusText" }
  ],
  "responses": [
    { "EndTime": "20240814160018", "StatusText": "Completed" },
    { "EndTime": "20230814160018", "StatusText": "Started" }
  ]
}
```

These are **not** authored into a survey from a prompt — a *prompt-to-survey* task should not add them. They are relevant when generating synthetic responses that need timestamps or status, especially time-distributed data (see `task-responses.md`).

---

## Participants

The optional top-level `participants` array holds pre-loaded invitees — people the survey will be sent to but who haven't answered yet. Each participant is a flat key-value object with the same shape as a response, but with a key restriction.

```json
{
  "questions": [ ... ],
  "participants": [
    {
      "External ID": "1234",
      "First Name": "Kaiser",
      "Last Name": "Söze",
      "Email": "kaiser@usual.com",
      "Event Date": "20260127000000",
      "gender": "Man"
    }
  ]
}
```

### Allowed keys

Participant objects may **only** contain keys that reference questions of type `system` or `category`. Survey-question keys (`single`, `multiple`, `open`, matrix rows, connected-Open) must not appear in participants — they belong in `responses`.

### Value formats

Same string-only rules as responses:

| Question type | Value format | Example |
|---|---|---|
| `system` | Free-form string. The platform-recognised system fields (e.g. `First Name`, `Email`, `Event Date`) accept whatever value you provide. | `"kaiser@usual.com"` |
| `category` with `answers` | The selected answer's `id` | `"Man"` |
| `category` without `answers` | Free-text identifier or label | `"Stockholm"` |

### Notes

- `responses` and `participants` serve different purposes. A file typically contains one or the other, not both.
- Unanswered/unset keys are simply absent from the object — never use empty strings as placeholders.
