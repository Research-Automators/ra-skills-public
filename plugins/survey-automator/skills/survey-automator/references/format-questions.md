# Survey Export Format — questions

Authoring reference: question and answer objects, interfaces, groups, points, matrices and grids, conditions, texts and bookmarks. Top-level structure and key order are in `format-core.md`; response and participant values are in `format-data.md`.

## Question object

Each entry in `questions` describes one question or a section header.

```json
{
  "id": "Gender",
  "type": "single",
  "text": "Gender",
  "surveyText": "What is your gender?",
  "comment": "Choose one",
  "min": 1,
  "max": 1,
  "interface": "buttons",
  "answers": [ ...answer objects... ]
}
```

### Question fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier (the question's client reference). Used as the key in response objects for non-matrix questions, and as `{id}` in expressions. |
| `type` | string | Yes | Question type. See [Question types](#question-types). |
| `text` | [text](#texts) | Yes | Internal label used in reporting and data exports. Without `surveyText` it is also the text shown to respondents. |
| `surveyText` | [text](#texts) | No | Text shown to respondents. May differ from `text`. |
| `comment` | [text](#texts) | No | Additional instruction shown beneath the question text. |
| `group` | string | No | Report section this question belongs to, as a plain label (e.g. `"About you"`). Preferred form for authoring — no top-level array needed. Mutually exclusive with `groupId`. See [Groups](#groups-report-sections). |
| `groupId` | string | No | Reference to a top-level `groups` entry by its `id`. Use only when groups are declared in a top-level `groups` array. Mutually exclusive with `group`. |
| `excluded` | boolean | No | When `true`, the question is hidden from respondents — typically a calculated variable. Data is still present in responses. Default `false`, except on `period` and `categoryVariable` questions, which are hidden unless `"excluded": false`. |
| `min` | integer | No | Minimum number of answers the respondent must select or provide. |
| `max` | integer | No | Maximum number of answers the respondent may select or provide. Leave it out for no limit — a `max` equal to the number of answers is redundant. |
| `interface` | string | No | Renderer hint controlling how options are displayed. See [Interface types](#interface-types). |
| `placeholder` | string | No | Empty-state prompt shown before selection on an `interface: "dropdown"` question (e.g. `"Select a country…"`). Only valid with `dropdown`; for open-text prompts set `placeholder` on the Open answer instead. Always supply a relevant one on dropdowns. |
| `noInterfaceValidation` | boolean | No | When `true`, suppresses the opinionated checks on this question: the long-label check for `buttons`, the recommendation to use `buttons` for short/small answer sets, the anchored-scale rule (answer texts must be ≤2 chars when `scaleLeft`/`scaleRight` are set) — all **blocking validation errors** — and the missing-placeholder reminder for dropdowns (a non-blocking warning). Structural rules still apply. Set only when the chosen rendering is intentional. |
| `randomAnswers` | boolean | No | When `true`, answer options are shuffled for each respondent. |
| `pagebreak` | boolean | No | When `true`, a page break is inserted **before** this item in the rendered survey. Valid on any item but most commonly used on section headers so each section starts at the top of a new page. |
| `cssClass` | string | No | CSS class name(s) added to the item's container in the rendered survey. Space-separate multiple classes. Built-in value: `"connectToPreviousItem"` — attaches the item visually to the preceding item. Set only when the user or brief asks for it, or when importing JSON that already has it. See [CSS classes](#css-classes). |
| `scale` | string | No | Scale type. Set to `"Ordinal"` (capital O, the only defined value) on every question or grid whose answer options form an ordered sequence — rating points, agreement, satisfaction, frequency, likelihood etc. Omit only for unordered categorical options. Required whenever any answer is tagged `Positive` or `Negative` (validator-enforced). |
| `scaleLeft` | [text](#texts) | No | Label for the low/negative end of a scale. Use when the scale has two polarities (low-to-high spectrum); omit when each answer has its own descriptive label. Validator-enforced: when anchors are set, every answer text (including DontKnow) must be ≤2 characters (compact spectrum points like `"1"`–`"10"`, `"?"`). |
| `scaleRight` | [text](#texts) | No | Label for the high/positive end of a scale. Same usage rule as `scaleLeft`. |
| `scaleDK` | [text](#texts) | No | Label for the "don't know" anchor of a scale. Same usage rule as `scaleLeft`. |
| `rows` | array | No | Sub-items for matrix questions. See [Matrix questions](#matrix-questions). |
| `answers` | array | No | Available answer options or open-text input definition. See [Answer object](#answer-object). Absent for `header` type. |
| `condition` | object | No | Conditional display rule. The question is shown only when the rule evaluates to true based on prior answers. See [Conditions](#conditions). |
| `coded` | string, array or object | No | Coded open ends: the sources whose open answers are coded into this question's answers. See [Calculated variables](calculated-variables.md). |
| `period` | string or object | With `period` type | The period type of a `period` question, e.g. `"Month"`. See [Calculated variables](calculated-variables.md). |
| `category` | string or object | With `categoryVariable` type | The category path of a `categoryVariable` question, e.g. `"org"`. See [Calculated variables](calculated-variables.md). |
| `calculated` | boolean | No | Only for a calculated question that has no rules yet. A question whose answers have `calculation` needs no such key. |

---

## Question types

| Type | Description |
|---|---|
| `single` | Respondent selects exactly one answer from a closed list. |
| `multiple` | Respondent selects one or more answers from a closed list. `min`/`max` constrain how many. |
| `open` | A single free-text (or numeric) input. Either omit `answers` entirely, or supply exactly one answer of type `Open` with `id` `0`. For **multiple** open-ended inputs in one question (and for open-text inputs with non-zero ids), use `multiple` instead — it accepts any number of `Open` answers with any ids. With `rows`, it is an open grid with one input per row; its `Open` answer has id `1`, not `0` — see [Open grids](#open-grids). |
| `header` | A visual section divider or survey intro with no selectable answers. `id`, `type`, and `text` are required; `comment` (for an intro paragraph or section description) and `pagebreak` are also commonly used. `layout: "header"` is optional; the platform writes it on export, so don't add it when authoring. `answers` and `rows` must not be set. |
| `system` | Platform-generated metadata (e.g. `First Name`, `Email`, response timestamps, completion status). Not asked of the respondent. A few are recognised on the response side — see [Built-in response system fields](format-data.md#built-in-response-system-fields). |
| `category` | Pre-known background data on the respondent, used in conditions and bookmarks. See [Background data](#background-data-in-conditions-and-texts). |
| `screenout` | Flow-control item: ends the survey when its `condition` fires, showing a short message. Produces no response data. See `flow-control.md`. |
| `error` | Flow-control item: blocks the respondent with an inline error when its `condition` fires (typically used to enforce consistency between earlier answers). Produces no response data. See `flow-control.md`. |
| `period` | Calculated variable: the period of the response (e.g. its month), for reports over time. Its answers are generated. Requires `period`. See [Calculated variables](calculated-variables.md). |
| `categoryVariable` | Calculated variable: a project category made available as a question for reports. Its answers are generated from the category tree. Requires `category`. Not the same as `category`, which is the respondent's background data itself. |

---

## CSS classes

`cssClass` is an optional styling hook valid on any question item. The renderer adds the value as a class on the item's container, so it can be targeted by built-in styles or by custom CSS in **Survey settings → Scripts / CSS**.

Built-in classes:

| Class | Effect |
|---|---|
| `connectToPreviousItem` | Renders the item attached to the item directly before it, with no section gap. Typical use: a note, legal reference, or clarification that belongs to the previous question. |

```json
{
  "id": "Q754",
  "type": "header",
  "text": "Anslagsförordningen 14 §",
  "comment": "14 § anslagsförordningen (2011:223)\nRedovisning mot anslag och inkomsttitlar ska göras minst en gång i månaden.",
  "cssClass": "connectToPreviousItem"
}
```

Don't add `cssClass` by default. Use it only when the user asks for it, the brief calls for an item to be visually connected, or you're preserving it from imported JSON. Custom class names (other than the built-ins) are allowed but only have an effect if the survey's custom CSS defines them.

---

## Groups (report sections)

Groups organise questions into sections. Their main purpose is the **report**: each group normally becomes a section header with its related questions grouped beneath it. Grouping is entirely optional — ungrouped questions are fine, and a survey may mix grouped and ungrouped questions.

There are two supported forms. Pick one; do not set both `group` and `groupId` on the same question.

**Form A — per-question `group` string (preferred for authoring).** Add a `group` label directly to each question. The platform derives the set of groups from the distinct strings, in first-appearance order. No top-level array is needed.

```json
{ "id": "Gender", "type": "single", "text": "Gender", "group": "About you", "answers": [ ... ] }
```

**Form B — top-level `groups` array + `groupId` reference.** Declare groups once at the top level, then reference them by `id`. Useful when a group needs a stable id independent of its label.

```json
{
  "groups": [
    { "id": "G1", "label": "About you" }
  ],
  "questions": [
    { "id": "Gender", "type": "single", "text": "Gender", "groupId": "G1", "answers": [ ... ] }
  ]
}
```

Each `groups` entry requires `id` and `label`. A question's `groupId` must match a declared group id (validator-enforced).

For new surveys, Form A is simplest — just tag each question with its section label.

---

## Interface types

The `interface` field controls how answer options are rendered to the respondent.

| Value | Description |
|---|---|
| *(absent)* | Default rendering — radio buttons (single) or checkboxes (multiple). |
| `buttons` | Inline button strip for single- or multi-select; use whenever *all* answer labels are short. Also appropriate on grids with ≤5 options. The validator **rejects** (hard error) `buttons` when any answer `text` exceeds 25 characters (recommending `vertical` for grids and the default otherwise), and conversely **rejects** an absent interface when every label is under 15 characters and there are ≤6 answers. Set `"noInterfaceValidation": true` on the question to opt out of either rule. |
| `dropdown` | Dropdown selector; use for long ordered lists (~30+ items). Single-select only. Set a question-level `placeholder` for the empty-state prompt (e.g. `"Select a country…"`); always include a relevant one. |
| `vertical` | Stacked layout for matrices — each row renders as its own question. Requires `rows`. Use for multiple-select grids and when any answer label is long. |
| `slider`, `dragdrop`, `ranking` | Special grid interfaces (require `rows`). **Use `slider` and `dragdrop` only when the user or brief explicitly asks for them**; use `ranking` when respondents should rank items. Read `grid-interfaces.md` before writing any of them. |

The format also accepts two grid legends, `alpha` and `numeric` (an automatic `A, B, C…` or `1, 2, 3…` legend). They exist only so existing files validate — never choose them when authoring; use `vertical` or `buttons`.

---

## Answer object

Used inside `question.answers` to define either a selectable option or an open-text input field.

```json
{
  "id": "2",
  "text": "Women",
  "surveyText": "Female"
}
```

```json
{
  "id": "0",
  "type": "Open",
  "charWidth": "40",
  "charHeight": "4",
  "placeholder": "Share your best advise in life here"
}
```

### Answer fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Numeric string identifier. Stored as the answer value in response objects for closed questions. |
| `type` | string | No | Semantic classification. See [Answer types](#answer-types). |
| `text` | [text](#texts) | No | Display text shown on the button or label. |
| `surveyText` | [text](#texts) | No | Alternative display text in the survey when it differs from the internal label. |
| `symbolText` | [text](#texts) | No | Short symbol used in compact scale renderings (e.g. `"0"`–`"10"`, `"?"`). |
| `points` | number | No | Points scored when this answer is selected (for an `Open` answer: when it is answered). **Default `1`, and omitted from the JSON** — only write `points` when the value differs from 1. Summed by the `[QuestionId]` reference in conditions and calculations. See [Points](#points). |
| `exclusive` | boolean | No | When set to `true` on an answer in a `multiple`-choice question, selecting this option deselects all others (and vice versa). Standard usage: a "Don't know" or "None of the above" escape option that shouldn't be combined with substantive answers. Write a boolean, as the platform exports it; the legacy strings `"true"`/`"false"` are still accepted. |
| `calculation` | string or object | No | Calculated questions only: the rule that selects this answer (or, on an `Open` answer, gives its value). See [Calculated variables](calculated-variables.md). |
| `codes` | string | No | Coded questions only: the answer's match codes — comma-separated words or `/regex/i` patterns. |
| `color` | string | No | `period` and `categoryVariable` questions only: the report colour of a generated answer, e.g. `"#e15759"`. |

### Answer fields for open answers

These fields apply only to answers with `type: "Open"`.

| Field | Type | Required | Description |
|---|---|---|---|
| `dataType` | string | No | Expected data type for the input. `"integer"` enforces numeric-only input. Default is free text. |
| `charWidth` | string | No | Suggested visible width (characters) of the input. Maximum `"40"`. |
| `charHeight` | string | No | Suggested visible height (rows) of the input. |
| `placeholder` | string | No | Placeholder text shown in the empty input. |
| `minValue` | string | No | Lowest allowed value, for `dataType: "integer"` inputs. Required on a numeric slider grid (see `grid-interfaces.md`), where it is the slider's left end. |
| `maxValue` | string | No | Highest allowed value, for `dataType: "integer"` inputs. Required on a numeric slider grid (see `grid-interfaces.md`), where it is the slider's right end. |
| `connectedTo` | string | No | The `id` of another answer within the same question that triggers this input — typically used to attach a "please specify" text field to an `Other` option. The connected Open answer always has `id` `"0"` and is listed first in `answers`; the Other option keeps its own id. |

### Answer types

| Value | Meaning |
|---|---|
| `Open` | Marks this answer as a free-text input definition rather than a selectable option. When combined with `connectedTo`, the input is shown only when its linked option is selected. |
| `Negative` | Tags the answer as belonging to the negative/low end of a scale. Used for analysis and colouring. |
| `Positive` | Tags the answer as belonging to the positive/high end of a scale. |
| `DontKnow` | Tags the answer as a "don't know" or "not applicable" escape option. Valid on both scales and regular closed-list questions. |
| `Other` | Tags the answer as an "Other / something else" catch-all on a closed list. Usually paired with a follow-up `Open` answer that has `connectedTo` set to this answer's id. In a coded question it is the answer for texts that match no code. |
| *(absent)* | A neutral option with no special semantic classification. |

---

## Points

Every answer carries a points value used by calculations and conditions. A checked answer, or an answered open end, scores **1 by default**, and the default is **not written** to the JSON. Set `points` on an answer only when it should score something else:

```json
"answers": [
  { "id": "1", "text": "Very good", "points": 3.0 },
  { "id": "2", "text": "Fairly good", "points": 2.0 },
  { "id": "3", "text": "Fairly bad" },
  { "id": "4", "text": "Very bad", "points": 0 },
  { "id": "9", "text": "Don't know", "type": "DontKnow", "points": 0 }
]
```

Here "Fairly bad" scores the default 1. `[QuestionId]` then sums the points of what the respondent answered:

- **single** — the points of the chosen answer.
- **multiple** — the sum over all checked answers. With default points this is the number of checked options.
- **open** — 1 (or the Open answer's `points`) when answered.
- **grid** — `[Q]` sums every row. `[Q.N]` gives row N only. Points sit on the shared `answers` list, so they apply to every row.

Authoring rules:

- Add `points` only when the user or brief asks for scoring or weighting (e.g. "score 3/2/1/0", an index, a quiz, a threshold on a total). Don't invent scores.
- Never write `"points": 1`. It's the default, and exported JSON leaves it out.
- When a scored scale has a "Don't know" or other escape option, decide whether it should count. Usually it should score `0`, so set that explicitly or it will count as 1.

---

## Matrix questions

A question can act as a matrix by including a `rows` array alongside `answers`. The respondent then rates each row independently using the same set of answer options.

```json
{
  "id": "Aspects",
  "type": "single",
  "rows": [
    { "id": "Aspects.1", "text": "Health & physical well-being" },
    { "id": "Aspects.2", "text": "Friends & social connection" }
  ],
  "answers": [ ...shared scale options... ]
}
```

### Row fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique row identifier in the format `<QuestionId>.<RowNumber>` (e.g. `"Aspects.1"`), where the number is the row's position. Used as the key in response objects. A survey exported from the platform may have rows with their own id (a row reference, e.g. `"price"`) — keep those as they are. |
| `text` | [text](#texts) | No | Row label shown to the respondent. Omitted when the question is a single Likert row (i.e. one scale without sub-items). |
| `surveyText` | [text](#texts) | No | Row text shown to respondents when it differs from `text`. |
| `calculation` | object | No | A calculated grid row: a map from grid answer id to that answer's rule. See [Calculated variables](calculated-variables.md). |

### Open grids

An `open` question with `rows` is an open grid: one input per row, for example a numeric grid of hours per activity. It has **exactly one** answer, of type `Open`, with id `"1"` (as exported). Don't use id `0` here: in a grid the import drops an `Open` answer with id `0`, and the grid gets no inputs. For numeric input, set `dataType: "integer"` on the answer.

```json
{
  "id": "Hours",
  "type": "open",
  "text": "Hours per week",
  "surveyText": "In a typical week, roughly how many hours do you spend on each of the following?",
  "rows": [
    { "id": "Hours.1", "text": "Meetings" },
    { "id": "Hours.2", "text": "Email & messaging" }
  ],
  "answers": [
    { "id": "1", "type": "Open", "charWidth": "4", "dataType": "integer" }
  ]
}
```

In responses, each row's value is keyed by the row id: `"Hours.1": "12"`. See [Key formats](format-data.md#key-formats).

---

## Conditions

A question can be shown conditionally based on answers given to earlier questions. Add a `condition` object to the question:

```json
{
  "id": "Advise",
  "type": "open",
  "text": "Best life advise",
  "surveyText": "What is your best life advise?",
  "condition": {
    "label": "Asked if fulfilled in life",
    "definition": "{Fulfilled}:{9} OR {Fulfilled}:{10} OR {Fulfilled}:{11}"
  },
  "answers": [ ... ]
}
```

### Condition fields

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | No | Human-readable summary of what the condition means, used in reports and UI. Keep it short and concise (less than 25 chars if not very complex). Not evaluated. |
| `definition` | string | Yes | Expression that evaluates to true/false based on prior responses. When true, the question is shown. |

### Definition expression syntax

Atoms reference a prior answer using the form `{<QuestionId>}:{<AnswerId>}` — the question id and answer id are each wrapped in curly braces, and they are exactly the `id`s of the same JSON. An atom is true when the respondent selected that answer. Atoms combine with `OR`, `AND` and `NOT` (uppercase). `AND`/`OR` are space-separated; **`NOT` is always written directly before a parenthesis, with no space: `NOT({Gender}:{2})`** — `NOT {Gender}:{2}` and `NOT ({Gender}:{2})` do not work on the platform. Parentheses may be used for grouping.

| Example | Meaning |
|---|---|
| `{Fulfilled}:{9}` | True if the respondent picked answer id `9` on question `Fulfilled`. |
| `{Fulfilled}:{9} OR {Fulfilled}:{10} OR {Fulfilled}:{11}` | True if any of answers 9, 10, or 11 was selected on `Fulfilled`. |
| `{Gender}:{2} AND {Important}:{3}` | True if the respondent picked answer 2 on `Gender` and answer 3 on `Important`. |
| `NOT({Gender}:{2})` | True if the respondent did not pick answer 2 on `Gender`. |
| `NOT({Fruit}:{3} OR {Fruit}:{4})` | True if the respondent picked neither answer 3 nor 4 on `Fruit`. |

For matrix questions, reference a specific row as `{<QuestionId>}.<RowNumber>:{<AnswerId>}` — the row number goes **after** the closing brace (e.g. `{Aspects}.1:{5}`). `{Aspects.1}:{5}` does not work. A row with its own id (exported rows only) is referenced by that id: `{price}:{5}`.

Exported surveys also use two other answer forms. Both count the answer's **position** in `answers` (1 = the first answer; the question's own open answer with id `0` is not counted):

| Form | Meaning |
|---|---|
| `{Gender}:A2` | The answer at position 2 selected. The export writes it when an answer's id equals its position. |
| `{Income}:V1VALUEN` | The numeric value typed into the `Open` answer at position 1. `{Age}:VALUEN` (or just `{Age}`) is the value of the question's own open answer. |

### Arithmetic operators and comparisons

In addition to answer-selection atoms, definitions support arithmetic operators and comparisons against respondent-provided values (typically from `open` questions with numeric input).

| Example | Meaning |
|---|---|
| `{Age} >= 18` | True if the respondent's answer to question `Age` is 18 or higher. |

Arithmetic operators: `+`, `-`, `*`, `/`. Comparison operators: `>`, `>=`, `<`, `<=`, `=`, `<>`. These can be combined with `AND`/`OR` and parentheses just like answer-selection atoms.

### Points references

`[<QuestionId>]` (square brackets) is the **sum of points** of the respondent's answers on that question. It is a numeric value, used in arithmetic position like `{Age}`, and works on a single/multiple question, a whole grid (summed over all rows), or one grid row with `[<QuestionId>.<RowNumber>]`.

| Example | Meaning |
|---|---|
| `[Wellbeing] >= 10` | True if the answer points on grid `Wellbeing` sum to 10 or more. |
| `[Wellbeing.2] > 2` | True if row 2 of `Wellbeing` scored more than 2. |
| `[Topics] >= 3` | On a `multiple` question with default points, true if 3 or more options were checked. |
| `[Q1] + [Q2] > 5` | Combined score across two questions. |

See [Points](#points) for how answer points are set.

**Known platform bug — don't compare `[Q]` on a question with an open answer.** When `Q` has an open answer of its own (an `Open` answer with id `0`, e.g. the text field of an "Other" option, or an `open` question), the import turns `[Q] >= 2` into `[Q:VALUEN] >= 2` and fails. Until it is fixed, write such rules with answer atoms. "At least 2 of answers 1–3": `({Q}:{1} AND {Q}:{2}) OR ({Q}:{1} AND {Q}:{3}) OR ({Q}:{2} AND {Q}:{3})`. An exclusive answer such as "None of these" can't be picked together with others, so leave it out of the pairs. `[Q]` on its own as the value of a calculated `Open` answer works. If the atom form would get very long (many answers, or a higher threshold), tell the user and suggest writing the count rule in the platform's expression editor instead. The validator flags this case.

### Background data in conditions and texts

`category` and `system` questions hold what is known about the respondent before the survey starts (segment, city, name). They use the **same syntax** as survey questions and are available from the first page:

```json
{ "id": "First Name", "type": "system", "text": "First Name" },
{ "id": "Segment", "type": "category", "text": "Customer segment",
  "answers": [ { "id": "Customer", "text": "Customer" }, { "id": "Member", "text": "Member" }, { "id": "Prospect", "text": "Prospect" } ] },
{ "id": "City", "type": "category", "text": "City" },
{ "id": "CustomerSince", "type": "single", "text": "Customer how long",
  "surveyText": "How long have you been a customer of ours, {First Name}?",
  "condition": { "label": "Segment Customer", "definition": "{Segment}:{Customer}" }, "answers": [ … ] },
{ "id": "ProspectInterest", "type": "single", "text": "Interest in offers",
  "condition": { "label": "Not customer or member", "definition": "NOT({Segment}:{Customer}) AND NOT({Segment}:{Member})" }, "answers": [ … ] },
{ "id": "CityCheck", "type": "single", "text": "City check",
  "surveyText": "According to our records you live in {City}. Is that correct?", "answers": [ … ] }
```

- **Category conditions** use the category's answer ids, which are often words (`{Segment}:{Customer}`), exactly as the participants file stores them. A category without `answers` can be bookmarked but has no answer ids to condition on.
- `NOT(…)` is also true for a respondent with no value for the category, so use it when respondents without a value should be included.
- **Bookmarks** `{City}` and `{First Name}` need no page break. Write the token exactly as the `system` or `category` question's `id`.
- Put the `system`/`category` questions first in `questions`, and give participants or responses their values (see `format-data.md`).

### Not usable in conditions: coded questions

A **coded** question (one with `coded`, see `calculated-variables.md`) **cannot be used in a condition yet** — not in `condition.definition`, a `screenout`/`error`, or a text field's `condition`. The coding is not done while the respondent answers, so such a condition never works in the survey. This changes when online coded variables are added to the platform. If the user asks for one, tell them and branch on a closed question instead. The validator rejects it.

---

## Texts

Every text shown in the survey — `surveyText` (or `text` when there is no `surveyText`), `comment`, `scaleLeft`/`scaleRight`/`scaleDK`, answer and row `text`/`surveyText`, `symbolText`, and the `header`/`body`/`footer` of `surveyMessages` — follows the same rules. `placeholder`, `codes`, `redirectURL` and outbound `messages` stay plain strings.

**A text is a plain string.** Most texts are just that:

```json
"surveyText": "How satisfied are you with our service?"
```

**Formatting uses a few small HTML tags:** `<b>`, `<i>`, `<u>`, `<a href="…">`, `<ul><li>`. A line break is a real newline (`\n`). Everything else is literal text: `<`, `&`, `*` and `_` need no escaping, and there are no entities. Any other tag (`<div>`, `<p>`, `<span>`, …) would show as text — the validator rejects it.

```json
"surveyText": "How <b>satisfied</b> are you?\nPlease answer <u>honestly</u>.",
"comment": "Read more on <a href=\"https://example.com\">our site</a>."
```

A link opens in a new tab. Add `target` only for something else, e.g. `<a href="…" target="_self">`.

**`{tokens}` insert something into the text.** The common ones:

| Token | Shows |
|---|---|
| `{Q2}` | The answer(s) the respondent gave to question `Q2` — a **bookmark**, see below. |
| `{Aspects.1}` | The same for a grid row (its row id). |
| `{First Name}`, `{Email}`, … | Participant data from a `system` question — write its `id` (`First Name`, `Last Name`, `Email`, …). |
| `{City}` | The respondent's value of a `category` question. |

An unknown name stays as literal text, braces included. The answer reference `{Q}:{3}` (both parts in braces) is a *condition atom* used in `condition.definition`, not a text token.

**More is in `texts.md`** — the typed text of an open answer (`{Q:0}`), category values, pictures, videos and document links (`{url|text}`, `~/` media library files), conditional text and sized pictures (the object form with `fields`), and raw HTML code. Read it only when the user wants one of those.

### Bookmarks (in-text piping)

A **bookmark** is a `{<QuestionId>}` token that the platform replaces at runtime with what the respondent gave for that earlier question. Use it to echo a previous answer back into later text — e.g. "You said you bought *{PurchaseFrequency}* from us — how satisfied were you?".

The target item's `type` determines both what is piped and what rules apply:

| Target type | Rendered value |
|---|---|
| `single` / `multiple` (fixed answers) | The **text** of the answer(s) the respondent selected. |
| `open` (no fixed answers) | The respondent's typed text. |
| `single` / `multiple` with an open "other" | The selected **answer text**. For the typed "please specify" text use `{Q:0}`, e.g. `{Fruit:0}` (see `texts.md`). |
| `category` | The respondent's category value (e.g. `{City}` → `Malmö`). |
| `system` | The system column value (e.g. `{First Name}`). |

`header`, `screenout`, and `error` items carry nothing to pipe and are **not** valid bookmark targets.

A bookmark works only in a text itself (a plain string, or the top-level `text` of a text object) — never inside a field's `text`, such as a conditional text. To show a bookmark conditionally, give it its own field with a `condition`; see [Conditional content that contains a bookmark](texts.md#conditional-content-that-contains-a-bookmark).

If the target is unanswered, was never reached, or the id does not exist, the bookmark renders **blank** (no placeholder, no error).

A bookmark to a **data question** (`single`/`multiple`/`open`) must point to a question on an **earlier page** — there must be at least one page break (`pagebreak: true`) between them, since a page's answers are not submitted until the respondent advances. A same-page reference renders blank. **`category`, `system`** and participant fields (`{First Name}`) are background data, available from the start, so no page break is required for them.
