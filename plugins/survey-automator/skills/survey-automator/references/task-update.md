# Task 6 — Update an existing survey (Survey Update Mode)

The user has a survey that already exists in Survey Automator, often with responses, and wants to change it while keeping its data: reword, add or remove questions or answers, move, rename, change a type. Produce an **update file**. The platform checks every claim in it, shows a review dialog, and applies only the changes the user approves.

Use Task 1 or 2 instead when the user wants a new survey, or a new copy of a survey ("make a v2 as a new project").

## In the browser: window.surveyAutomator

If you can run JavaScript in the user's browser tab (e.g. Claude in Chrome) and the tab shows a Survey Automator project, check `typeof window.surveyAutomator`. If it is there, use it instead of asking for files. It runs in the user's own session:
- `surveyAutomator.project()`: `{ id, name, unsavedChanges, questionCount }`. With `unsavedChanges`, ask the user to save first: the other calls see the saved survey. With `questionCount` 0 the project is empty: create the survey with `createSurvey` (see SKILL.md, "In the browser"), not with an update.
- `await surveyAutomator.getSurveyJson()`: the current export, with `surveyVersion`. Use it as the base and copy `surveyVersion` into `baseVersion`. Read it again before every new round of changes: the user may have unticked something in the last review, or changed the survey in the editor.
- `await surveyAutomator.previewUpdate(update)`: the server's checks. It returns `{ status: "review" | "errors", errors, review }` with every problem at once. Fix and repeat until the status is `review`. It does not change the survey.
- `surveyAutomator.openUpdateReview(update)`: opens the review dialog. Tell the user in one line what the update does, and that they review and apply it there. You can't apply it yourself, and you shouldn't click Apply for the user. If the app asks about the project's edit lock, the user decides.

`surveyAutomator.help` lists the calls. If it isn't there (another page, or an older version of the platform), use the files as below.

## Changing a survey you made earlier

Without the browser API, write an update file against your latest version of the survey and leave out `baseVersion`, unless you have an export. End with one line: "If the import is refused because the survey has responses, or you've changed it in the editor or unticked changes in the review, export the survey and give me the export." If the user hasn't imported the survey yet, they import the full revised survey instead (Task 1 or 2): give it if they ask.

## Input: the current survey (export)

The survey's JSON export starts with `"surveyVersion"` (8 hex characters), lists conditions in a top-level `conditions` array that questions point to with `conditionId`, and may have `responses`. Use it whenever you have it, and always when the survey has responses: ask the user to export the survey again if they have only a description or an old file. Without an export, your latest version is the base: use its ids exactly.

Read `format-core.md` and `format-questions.md` (and `example.json`) as well: added and replaced questions follow the normal authoring rules. `update-example.json` is a worked update of `example.json`.

## File structure

```json
{
  "updateMode": true,
  "baseVersion": "081bf687",
  "questions": [
    { "id": "Advise", "text": "Best life advice",
      "update": { "action": "edit", "change": "text", "note": "Fixed spelling" } }
  ]
}
```

- `updateMode: true`, then `baseVersion` = the export's `surveyVersion`, copied exactly. Never invent it. Leave it out only when you have no export and the survey has no responses: the importer then accepts the file and the review notes that changes made in the editor since may be overwritten. With responses a file without `baseVersion` is refused. A `baseVersion` that doesn't match the survey makes the review warn that the survey has changed, and the user has to confirm.
- Only `questions`. Any other top-level key (`conditions`, `responses`, `surveyMessages`, `groups`, `messages`) is refused.
- Every changed question has an `update` object. Update markup is never allowed in a normal (create) import.

## The `update` object

| Property | Used with | Meaning |
|---|---|---|
| `action` | all | `add`, `edit`, `replace`, `move` or `remove` (below) |
| `change` | `edit`, `replace` | Riskiest kind of change: `text` < `order` < `additions` < `structure`. Optional, but if you give it, it must not be lower than what the diff shows, or the file is refused. |
| `placeAfter` | `add`, `edit`, `replace`, `move` | Id of the question to place it after; `null` = first. Leave it out to keep the position (an `add` without it goes last). |
| `oldId` | `edit`, `replace` | The previous id when renaming. The entry uses the **new** id. |
| `note` | all | Short reason in the user's language. It is the only text you write that the review dialog shows. Always write one. |

| Action | Send | Effect |
|---|---|---|
| `add` | The full new question, new id | New question |
| `edit` | `id` + only what changes | Sent properties replace current values, and `null` clears one (`"condition": null`). Everything not sent stays. |
| `replace` | The full question | Swaps the whole question; anything not sent is gone. Needed to remove answers or rows, or to change the type. |
| `move` | `id` only + `placeAfter` | Position only |
| `remove` | `id` only | Soft delete: sets `excluded: true`, so the data is kept and the id stays reserved |

`change` kinds: `text` = only wording (question texts, `scaleLeft`/`scaleRight`/`scaleDK`, answer and row `text`). `order` = answers or rows reordered. `additions` = new answers or rows with new ids. `structure` = anything else: type, condition, `pagebreak`, interface, min/max, scale, removed items, renames, and any reorder of an `Ordinal` scale's answers.

## Answers and rows in an `edit`

Matched by `id`. An existing id updates only the properties you send, so `{ "id": "2" }` alone changes nothing. A new id adds the item.
- If the array lists **every** existing id, its order is the new order and new items sit where they appear. If it lists **only some**, new items go **last**, and the listed ones must stay in their current order: a partial list in a new order is refused (to reorder, list every id).
- Removing an answer or row needs `replace`.
- A grid's rows keep the `<QuestionId>.<N>` pattern. Number new rows after the highest existing one, even when you list a new row earlier (e.g. as the second row): existing rows keep their ids, so ids need not match positions in an update. With responses, new rows must go last (see "Data safety").

## Renames

```json
{ "id": "CountryOfResidence", "update": { "action": "edit", "oldId": "Country", "placeAfter": "Gender" } }
{ "id": "Aspects", "rows": [ { "id": "Aspects.Health", "update": { "oldId": "Aspects.1" } } ],
  "update": { "action": "edit", "change": "structure" } }
```
Renames are applied all at once, so swaps work. The importer rewrites references in conditions and texts, and a renamed question's rows follow its new prefix. The old id is reserved for good. Anywhere else in the file, including `placeAfter`, use the new id. With responses, a question or row rename gets a warning (reports, dashboards and integrations are not updated). An **answer** id rename is refused, because answer ids are the stored values.

## Data safety: when the survey has responses

Responses are stored by answer and row **position**. On a question with responses the importer refuses anything that moves an existing answer or row: reordering, inserting in the middle, or removing one that is not last. So with data:
- add new answers and rows **last**, and send only the new items in an `edit`;
- never repurpose an answer id with a new meaning (e.g. "Weekly" → "Monthly"). Add a new answer instead. Moving labels between existing answers (a swap, or shifting bands one step) is refused;
- never change a question between `open` and answer options (`single`/`multiple`): the stored values can't be read as answer codes, so it is refused. Add a new question with a new id and `remove` the old one;
- prefer `remove` (soft delete) over reusing a question;
- a reworded closed question or answer label is allowed, but tell the user it may break comparability with earlier answers.

## Calculated variables

An update file can add calculated variables (calculated, coded, period, category variable) with `add`, and change them with `edit` or `replace`. Write them as `calculated-variables.md` describes. In an `edit`, send the changed rule (`calculation`, `codes`, `period`, `category`) on the answer or question it belongs to.
- The platform computes their values for all existing responses after the update, so the data-safety rules above don't apply to them: their answers may be reordered, relabelled or removed even with responses. A question that stops being calculated keeps its values as data, and then the rules apply.
- An `edit` that changes their answers or rows rebuilds the question, so its translations are reset.
- A coded source has no braces: `"coded": "Comments"`, or `"Comments:3"` for one open answer. The importer refuses `{Comments}` in an update.
- A `multiple` question whose only answer is a calculated `Open` value stays `multiple` in the export. Keep it `multiple`.

## Rules

- One entry per question id. Combine changes into one `edit`, e.g. a change plus `placeAfter`.
- Conditions and text bookmarks may refer only to earlier questions (bookmarks: on an earlier page), and not to removed or excluded ones. Removing a question that is still referenced is refused. Update or clear the referring condition in the same file.
- Write a changed or new condition inline. The short form `"condition": "{Q}:{1}"` and the object form both work. Do not add top-level `conditions`.
- A flagged entry that changes nothing is refused.
- An `edit` that changes anything other than texts, condition, `pagebreak`, `excluded`, answers and rows rebuilds the question, which resets its translations. Tell the user when this happens.
- A question whose answer list is shared with other questions can only be changed in the editor. The importer reports this.

## Two forms: changes-only (default) and full

- **Changes-only** (default): only the entries with `update`, in the order they should apply. Positions come from `placeAfter`, and an entry may be placed after a question added earlier in the file. Keep `edit`s minimal.
- **Full**: give it when the user wants to review the whole new version. Every question appears in its final order, and the changed ones carry `update`. Array order is the new order, so `placeAfter` is optional. Questions without `update` must match the export exactly. A moved question still needs an `update`: `move` with `placeAfter`, or an `edit` of its full content.

## Validate and deliver

Run `python <skill-root>/scripts/validate.py <update.json> --base <export.json>`. With `--base` it runs the importer's checks: ids, merge, declared `change`, positions, references and data safety (using the export's `responses`, if any). It also prints the review dialog the user will see. It reports every problem in one run, as the importer does. Fix them all and re-run until clean. Without the export, run it without `--base` and say that only the file's own rules were checked.

Name the file `<survey>-update.json` (full form: `<survey>-update-full.json`). In the summary, list what each group of the review dialog will show, and point out anything under **Needs attention** and any removed question with data. Then: "To import: open the existing project in [Survey Automator](https://app.researchautomators.com/) → **Import survey** → **From JSON**, then review and apply the changes."
