# Flow control: `screenout` and `error`

Two advanced item types interrupt the normal flow of a survey based on a condition. They are not data-collection items — they produce no response data, never appear in `responses`, and are excluded from reports and analysis. Most surveys do not need them.

| Type | Effect when condition fires |
|---|---|
| `screenout` | The respondent is exited from the survey. A short message is shown explaining why before the session ends. |
| `error` | A blocking dialog is shown, telling the respondent that one of their previous answers is logically inconsistent and must be changed before they can continue. |

## Condition semantics

Both items use the same `condition` object as regular questions, but the meaning is **inverted**:

- On a regular question, the condition controls **display** — the question is shown when the condition is true.
- On `screenout` and `error`, the condition controls **firing** — the action triggers when the condition is true.

Both items must appear **after** every question their condition references. They do not need to come immediately after; any later position is fine.

A `condition` is required on both types. An item without a condition would either screen out or error every respondent, which is never useful.

## Field rules

The following fields are **required**:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier. Used internally for traceability; never appears as a key in `responses`. |
| `type` | string | `"screenout"` or `"error"`. |
| `text` | string | Internal label used in the survey designer and logs. |
| `surveyText` | string | Message shown to the respondent — the screenout reason or the error explanation. |
| `condition` | object | The trigger condition. See [Conditions](format-questions.md#conditions). |

The following fields are **forbidden** and rejected by the validator: `min`, `max`, `answers`, `rows`, `interface`, `randomAnswers`, `scale`, `scaleLeft`, `scaleRight`, `scaleDK`, `excluded`, `pagebreak`.

`comment` is allowed but rarely useful; the message lives in `surveyText`.

## Writing the messages

`surveyText` on these items speaks **directly to the respondent** at the moment the action fires, so the tone differs from a question prompt:

- **Screenout** — explain briefly and politely why the survey is ending. Thank them. Do not reveal the screening criteria in detail (it can bias future fielding).
- **Error** — name the inconsistency and tell them what to do. Keep it short and actionable; the respondent has to read it and then go back to fix something.

## Examples

### Screenout

A B2B survey only wants respondents who have purchased the product. Anyone who selected "Never" on the purchase-frequency question is screened out.

```json
{
  "id": "ScreenoutNonBuyer",
  "type": "screenout",
  "text": "Screenout: never purchased",
  "surveyText": "Thanks for your interest! This survey is for current customers, so we won't take any more of your time. Have a great day.",
  "condition": {
    "label": "Never purchased",
    "definition": "{PurchaseFrequency}:{5}"
  }
}
```

### Error

A respondent claims to be employed full-time but also reports zero hours worked last week. The error blocks them until one answer is changed.

```json
{
  "id": "ErrorEmploymentHours",
  "type": "error",
  "text": "Error: full-time but zero hours",
  "surveyText": "You indicated you are employed full-time, but also that you worked 0 hours last week. Please go back and adjust one of these answers.",
  "condition": {
    "label": "FT but 0 hours",
    "definition": "{Employment}:{1} AND {HoursLastWeek} = 0"
  }
}
```

## Notes

- These items produce no key in any response object.
- They are stripped from standard exports and do not show up in dashboards or aggregate reports.
- A single survey may contain any number of `screenout` and `error` items, scattered through the question list as the logic requires.
- A reasonable convention is to prefix internal `text` and `id` with `Screenout` / `Error` so they are easy to spot in the designer.

## Bookmarks

`references/flow-control-example.json` also demonstrates a **bookmark** — the `{PurchaseFrequency}` token in its `Satisfaction` question's `surveyText` echoes the respondent's earlier purchase-frequency answer back into the text. See [Bookmarks (in-text piping)](format-questions.md#bookmarks-in-text-piping) in `format-questions.md` for the full rule: bare `{QuestionId}` in a text shown to respondents (see [Texts](format-questions.md#texts) for where texts allow tokens), resolves to the selected answer's text (or blank if unanswered). Note that in the example file the `pagebreak` sits on the section headers (`WorkSection`, `SatisfactionSection`) — a convention so each page opens with a header — and the bookmark target must be on an earlier page.
