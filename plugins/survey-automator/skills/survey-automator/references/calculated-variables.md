# Calculated variables

Read this file only when the user asks for derived, grouped or recoded variables, coded open ends, or report breakdowns by period or category — or when a JSON adds questions to an existing project. Everything else about the format is in `format-core.md`, `format-questions.md` and `format-data.md`.

A calculated variable is a question whose values the platform produces from other data, for use in reports — for example an age group made from an age question. Respondents never see it, so it normally has `"excluded": true`. Add calculated variables only when the user asks for derived, grouped or recoded variables, coded open ends, or report breakdowns by period or category.

There are four kinds. Each is recognised from its keys:

| Kind | In the JSON |
|---|---|
| Calculated | At least one answer (or grid row) has `calculation`. The question keeps its normal type, `single` or `multiple`. |
| Coded | The question has `coded`. Type `single` or `multiple`. |
| Period | `"type": "period"` with `period`. |
| Category variable | `"type": "categoryVariable"` with `category`. |

## Calculated questions

Each answer gets a rule in `calculation`. The short form is a string — the main thing of the answer:

- on a normal answer, the **condition**: the answer is selected when it is true;
- on an `Open` answer, the **value**: an arithmetic expression.

```json
{ "id": "AgeGroup", "type": "single", "text": "Age group", "excluded": true,
  "answers": [
    { "id": "1", "text": "18-34", "calculation": "{Age} >= 18 AND {Age} <= 34" },
    { "id": "2", "text": "35+",   "calculation": "{Age} >= 35" },
    { "id": "3", "type": "Open", "text": "Yearly income", "calculation": "{Income}:V1VALUEN * 12" }
  ] }
```

**Age groups from a year of birth.** Compare the year with the current year minus the age, and say which year you counted from (e.g. in the update's `note`). `> 0` keeps respondents without an answer out of the last group.

```json
{ "id": "AgeGroup", "type": "single", "text": "Age group", "excluded": true,
  "answers": [
    { "id": "1", "text": "Under 35", "calculation": "{YOB}:VALUEN > 2026 - 35" },
    { "id": "2", "text": "35-54",    "calculation": "{YOB}:VALUEN <= 2026 - 35 AND {YOB}:VALUEN > 2026 - 55" },
    { "id": "3", "text": "55+",      "calculation": "{YOB}:VALUEN > 0 AND {YOB}:VALUEN <= 2026 - 55" }
  ] }
```

The long form is an object, used only when the short form can't express the rule:

| Key | Meaning |
|---|---|
| `condition` | The answer is selected when this is true. Optional on an `Open` answer. |
| `value` | The value of an `Open` answer. |
| `disabled` | `true` switches the whole rule off. |

```json
{ "id": "4", "text": "Old rule", "calculation": { "condition": "{Age} > 99", "disabled": true } },
{ "id": "5", "type": "Open", "text": "Income if known",
  "calculation": { "condition": "{Income}:V1VALUEN > 0", "value": "{Income}:V1VALUEN * 12" } }
```

- An answer without `calculation` is never selected.
- A calculated question with no rules at all (not set up yet) has `"calculated": true`. Don't write it when any answer has a rule.
- The question's own open answer (an `Open` answer with id `0`) can't be calculated. Use an `Open` answer with another id on a `multiple` question.

**Calculated grid rows.** All rows share the grid's answers, so each row's `calculation` is a map from grid answer id to rule. Each rule follows the rules above. The map adds rules to the grid's answers; it never defines new answers.

```json
{ "id": "Grouped", "type": "single", "text": "Satisfaction (grouped)", "excluded": true,
  "rows": [
    { "id": "Grouped.1", "text": "Price",   "calculation": { "1": "{Sat}.1:{1} OR {Sat}.1:{2}", "2": "{Sat}.1:{3} OR {Sat}.1:{4}" } },
    { "id": "Grouped.2", "text": "Quality", "calculation": { "1": "{Sat}.2:{1} OR {Sat}.2:{2}", "2": "{Sat}.2:{3} OR {Sat}.2:{4}" } }
  ],
  "answers": [ { "id": "1", "text": "Low" }, { "id": "2", "text": "High" } ] }
```

**Expressions** use the [condition syntax](format-questions.md#definition-expression-syntax): answer atoms, `AND`/`OR`/`NOT`, comparisons and arithmetic, with the ids of the same JSON. A rule may use only questions placed **before** its question. The validator checks the syntax described in `format-questions.md`; the platform also knows functions such as `IF(…)`, which the validator does not accept.

A points count compared with a number (`[Q] >= 2`) fails on import when `Q` has an open answer of its own — a known platform bug. Write it with answer atoms; see [Points references](format-questions.md#points-references).

## Coded open ends

A coded question sorts the texts of open answers into its answers. `coded` names the sources; each answer's `codes` holds its match codes (comma-separated words or `/regex/i`). The answer's `text` counts as a code too. A text that matches no code gets the `Other` answer.

```json
{ "id": "Reasons", "type": "multiple", "text": "Reasons (coded)", "excluded": true, "coded": "Why",
  "answers": [
    { "id": "1", "text": "Price", "codes": "price, expensive, /cost(s)?/i" },
    { "id": "2", "type": "Other", "text": "Other" }
  ] }
```

A source is not an expression: write it like its response key, **without braces**. The importer leaves out a source in braces.

| Source | Meaning |
|---|---|
| `Why` | All open answers of the question |
| `Sat.1` | All open answers of a grid row (its id) |
| `Comments:0` | The question's own open answer |
| `Comments:3` | Open answer `3` (by id) |

One source is a string; several sources are a list: `"coded": ["Why", "Comments:3"]`. Sources must be placed before the coded question. The long form is used only when a setting differs from its default:

| Key | Default | Meaning |
|---|---|---|
| `sources` | — (required) | A string or a list, as above |
| `matchMode` | `search` | `search`: a code found anywhere in the text (`/regex/i` codes work only here); `exact`: the whole text equals a code — `expensive` matches, `Too expensive` does not. Use it only for short answers such as one-word or brand answers; for sentences use `search` |
| `multipleCodes` | `true` on `multiple`, `false` on `single` | One text can get several codes |

```json
"coded": { "sources": ["Why", "Comments:3"], "matchMode": "exact" }
```

**A coded question can't be used in a condition yet** (question `condition`, `screenout`/`error`, or a text field's `condition`): the coding is not done while the respondent answers. This changes when online coded variables are added. Coded questions are for reports; branch on a closed question instead. See [Not usable in conditions](format-questions.md#not-usable-in-conditions-coded-questions).

## Period

A `period` question gives each response its period — for example its month — for reports over time. Its answers are generated. `period` is the period type: `Year`, `HalfYear`, `Quarter`, `Month`, `Week` or `Day`.

```json
{ "id": "Month", "type": "period", "text": "Response month", "period": "Month" }
```

The long form is used only when a setting differs from its default:

| Key | Default | Meaning |
|---|---|---|
| `periodType` | — (required) | As above |
| `periodBase` | `EventDate` | The date the period is taken from: `EventDate`, `Response` (response end time) or `ResponseStart` |
| `periodLength` | `1` | Periods per answer, e.g. `2` with `Week` for fortnights |
| `calendarWeekRule` | `FirstDay` | `FirstDay`, `FirstFullWeek` or `FirstFourDayWeek` |
| `firstDayOfWeek` | `Monday` | `Monday` … `Sunday` |

```json
"period": { "periodType": "Week", "periodLength": 2, "firstDayOfWeek": "Sunday" }
```

## Category variable

A `categoryVariable` question makes a project category available as a question for reports. Its answers are generated from the category tree. `category` is the category path — relative ids separated by `:`, e.g. `"org"` or `"org:dept"`. A missing category is created on import.

```json
{ "id": "Department", "type": "categoryVariable", "text": "Department", "category": "org" }
```

| Key | Default | Meaning |
|---|---|---|
| `path` | — (required) | The category path |
| `startLevel` | `1` | The first tree level used as answers |
| `endLevel` | none | The last tree level used |
| `sortPropertyName` | `"Order"` | Category property the answers are sorted by; `null` for no sorting |
| `sortPropertyIsNumeric` | `false` | Sort the property as numbers |
| `directConnections` | `false` | Count only a respondent's own category, not its parents |

This is not the `category` type: a `category` question is the respondent's background data itself, set for participants or responses.

## Answers of period and category variable questions

Their answers are generated, so `answers` lists only answers that have a report colour, as `{ "id", "color" }`. Leave `answers` out when there are no colours. A period answer id is `PA<n>` (the n-th period shown in the report); a category answer id is its category path.

```json
{ "id": "Department", "type": "categoryVariable", "text": "Department", "category": "org",
  "answers": [ { "id": "org:sales", "color": "#e15759" }, { "id": "org:support", "color": "#4e79a7" } ] }
```

Both types are hidden by default — write `"excluded": false` only for a visible one.

## Adding calculated variables to an existing survey

A JSON may hold only the new questions and refer to questions that already exist in the project, by their ids (as `get_survey` shows them). On import, ids in the same JSON are found first, then the project's questions. Validate such a file together with the project's survey:

```
python <skill-root>/scripts/validate.py new-questions.json --existing project-survey.json
```

## Not in the JSON

Report formulas (`aggregated`), values read from a database, and other calculation methods are not exported: such questions appear as normal questions without calculation keys.
