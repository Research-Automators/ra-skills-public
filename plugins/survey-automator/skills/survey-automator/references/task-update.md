# Task 6 — Update an existing survey (Survey Update Mode)

The user has a survey that already exists in Survey Automator, often with responses, and wants to change it while keeping its data: reword, add or remove questions or answers, move, rename, change a type. Produce an **update file**. The platform checks every claim in it, shows a review dialog, and applies only the changes the user approves.

Use Task 1 or 2 instead when the user wants a new survey, or a new copy of a survey ("make a v2 as a new project").

## Which file to give

When the user asks for changes to a survey made earlier (in this conversation or another one), decide by two facts: is the survey in Survey Automator yet, and does it have responses? If you can't tell, ask in one line: "Is the survey already in Survey Automator, and does it have responses or changes made in the editor since?"

1. **Not imported yet**: change the draft and give a new full survey JSON (Task 1 or 2). No update file.
2. **Imported, no responses yet**: give an update file built on your latest version of the survey. No export and no `baseVersion` are needed. This is better than clearing the project and importing again, because it keeps what was set up in the editor (layout, translations, settings). Two cautions:
   - If the user has changed questions in the editor since the import, ask for a fresh export first. Otherwise the update can undo those edits.
   - Your latest version assumes every change of the last update was applied. If the user unticked something in the review, your copy no longer matches the project: ask for an export.
3. **Has responses**: always work from a fresh export, with `baseVersion`, and follow "Data safety" below.

## Input: the current survey (export)

The survey's JSON export starts with `"surveyVersion"` (8 hex characters), lists conditions in a top-level `conditions` array that questions point to with `conditionId`, and may have `responses`. Use it whenever you have it, and always when the survey has responses: ask the user to export the survey again if they have only a description or an old file. Without an export (case 2 above) your latest version is the base: use its ids exactly.

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

- `updateMode: true`, then `baseVersion` = the export's `surveyVersion`, copied exactly. Never invent it. Leave it out only when you have no export and the survey has no responses (case 2): the importer then accepts the file and the review notes that changes made in the editor since may be overwritten. With responses a file without `baseVersion` is refused. A `baseVersion` that doesn't match the survey makes the review warn that the survey has changed, and the user has to confirm.
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
