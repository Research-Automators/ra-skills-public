# Generating responses

Shared rules for synthetic respondent data, used both for the example responses of Task 1 (prompt to survey) and for Task 3 (populate responses). Task-specific rules, such as how many responses to make and what may change in the input, are in the task file. Key and value formats are specified in `format-data.md`.

## Realism

- **One persona per respondent.** Before filling in a respondent's answers, decide on a short persona: age, life situation and attitudes. Let it shape every answer, so each respondent reads as one coherent person across the whole survey. A respondent in their 70s shouldn't pick "less than 1 year" tenure on an employee survey.
- **Vary the respondents.** Give them different demographics, opinions and free-text styles. Avoid every respondent picking the middle of every scale.
- **Correlate where it makes sense.** Someone who picks "Health" as most important might rate their health satisfaction higher. Real data is noisy, but pure randomness feels fake.
- **Free text sounds like real people.** Keep it short, specific and sometimes messy, not marketing copy. Write it in the survey's language: English surveys get English free text, Swedish surveys get Swedish.
- **Respect the flow.** Leave out questions a respondent wouldn't see because of a `condition`. Respondents who would hit a `screenout` item don't appear in the data unless the user asked for a realistic status mix.

## Keys and values

- **All values are strings.** Integer open questions still get quoted: `"67"`, not `67`.
- **`single`** = the selected answer's `id`, e.g. `"2"`.
- **`multiple`** = semicolon-joined answer ids, e.g. `"1;3"`. Respect the question's `min`/`max` exactly.
- **Matrix rows** = one key per row, each with a single answer id: `"Aspects.1": "5"`, `"Aspects.2": "6"`.
- **Open grids** = one key per row with the typed value: `"Hours.1": "12"`.
- **Numeric slider grids** (`interface: "slider"` on an `open` grid) = one key per row with an integer string within `minValue`–`maxValue`: `"NumericSlider.1": "64"`.
- **Ranking grids** (`interface: "ranking"`) = each rank position (answer id) goes to exactly one row. With fewer ranks than rows, the unranked rows are absent. Drag-and-drop and choice-slider grids are keyed like ordinary matrices.
- **Connected-Open answers**: if the respondent picked an `Other` option, add a key `<QuestionId>.<TriggerAnswerId>` with the free text (e.g. `"Important.9": "..."`). Include it only when the Other option was actually picked.
- **Unanswered questions are absent.** You can model occasional dropouts or skipped optional questions by leaving keys out. Never write empty strings.
- **Excluded questions** (`excluded: true`) still get values, unless they are calculated variables. They capture data even when hidden.
- **Calculated variables get no values.** Leave out questions with answer or row `calculation`, `coded`, `period` or `categoryVariable`. The platform calculates them from the other answers after import.
- **`category` questions** hold known background data (e.g. `KnownGender`, `CustomerSegment`). Give each respondent a value: an answer id when the category has `answers`, otherwise a plausible free-text value.
- **`system` questions** are filled in by the platform, so by default don't write values for them. The task file says when timestamps or status values are wanted.
