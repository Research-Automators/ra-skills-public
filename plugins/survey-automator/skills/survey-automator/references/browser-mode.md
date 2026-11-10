# Browser mode: Survey Automator open in the tab

Read this only when `window.surveyAutomator` exists in the user's browser tab (SKILL.md, Step 0). The user is logged in, and **the result goes straight into their project, not into a file**. This holds for every kind of request: a new survey ("create a survey and add it here", "lägg in en enkät här"), a change, or a short request about "the survey", "the data", a question id or a variable ("create age groups from YOB", "skapa åldersgrupper från YOB"). Don't ask for files.

Do the task's authoring work as usual (task file, format files, example). Only where the result goes, and what you deliver, differ. Those rules are below.

This file describes API version 6 (`surveyAutomator.version`).

## Start of a session

1. Call `await surveyAutomator.overview()` when a project is open (`project()` returns its id). It gives the project at a glance; use it to talk naturally:
   - `name`, `status` (`setup`, `started`, `reporting`, `closed`), `published`;
   - `totals` (participants, started, finished, last response; approximate);
   - `freshness.waitingToSync` (responses not yet brought into the project);
   - `structure` (questions, calculated variables, conditions, quotas, reports), `languages`, `theme`;
   - `user.firstName`: address the user by it;
   - `role` (what the user may change), `tab`, `unsavedChanges`.
2. With `unsavedChanges`, ask the user to save: the other calls see the saved survey.
3. No project open (`project()` throws, or `tab` is `Home`): see "Home: projects and folders".

## The API

`window.surveyAutomator` runs in the user's own session. `surveyAutomator.help` is a list of every call with its arguments.

| Call | What it does |
|---|---|
| `project()` | `{ id, name, unsavedChanges, questionCount, tab, reportScope }`. |
| `await overview()` | The project at a glance (above). Read only. |
| `await getSurveyJson()` | The saved survey as its JSON export, with `surveyVersion`. |
| `await createSurvey(survey)` | Only when `questionCount` is 0. Creates the survey at once, with Undo. |
| `await previewUpdate(update, options?)` | The server's checks of an update file. Changes nothing. |
| `openUpdateReview(update, options?)` | Opens the review dialog. Returns a handle. |
| `getScriptsCss()` / `await setScriptsCss(...)` | Survey settings → Scripts / CSS. |
| `getSurveyMessages()` / `await setSurveyMessages(...)` | Thank-you and other screens, with redirect URLs. |
| `await publishStatus()` / `await publishAndTest({ open: true })` | Publish, and open the test in a new tab. |
| `await importResponses(data)` / `await importParticipants(data, { mode })` | Data into the project. |
| `await getMessagesJson()` / `await previewMessages(json)` / `await openMessagesReview(json)` | E-mail and SMS invitations, reminders, thank-yous. |
| `await syncResponses()` | Brings in responses waiting on the survey server. |
| `listVariables()` / `await crosstab(...)` | Read-only analysis. |
| `reportStatus()` / `dashboard()` / `await refreshReport()` / `await openDashboardEdit()` | The Dashboard. |
| `await openTab(name)` / `await showQuestion(id)` | Show the user something (navigation only). |
| `await listProjects(...)` / `await projectsSummary()` / `await recentProjects()` / `await listFolders()` | The user's projects. |
| `await openProject(id)` / `await showHome()` / `await newProject({ name, folder })` | Move between projects; create one. |
| `await result(handle, { timeoutMs })` | The outcome of a call that waited for the user. |
| `beginInput()` / `appendInput(inputId, text)` | Large JSON in parts. |

## Calls that wait for the user

**Every call that changes something waits for the user's click.** The app shows what will change (a confirmation, the review dialog, or a permission dialog), and only the user's own click answers it. Never click Apply, Allow, Import, Add or Create for the user, even if you could: the user decides.

These calls return as soon as the app shows its dialog:

```js
const r = await surveyAutomator.importParticipants(data);
// r = { status: "waiting", handle: "importParticipants-3", message: "..." }
```

1. Tell the user what to check in the dialog, in one or two lines.
2. Don't keep a call open while you wait (the browser tool times out). Do other work, or end your turn.
3. Then read the outcome: `await surveyAutomator.result(r.handle, { timeoutMs: 30000 })`. It waits at most `timeoutMs` (max 60000) and returns `{ status: "waiting" }` if the user hasn't answered yet.
4. A call that needs no click (nothing to change, or the user allowed it for this session) returns its outcome directly, without a handle.

The outcomes are `applied`, `saved`, `imported`, `published`, `created`, `synced`, `done`, `cancelled`, `errors` or `failed`. On `cancelled`, ask what the user wants instead; don't call again unasked.

**Permission dialogs** (publish, sync, new project) have Cancel / Allow once / Allow this session. "Allow this session" lasts until the page reloads or another project opens, and is never stored. Publish and sync each have their own permission.

## What the API refuses, and limits

- It returns the survey's definition, totals and aggregates only. Never responses or participants' personal data; don't try to get those through the page.
- Arguments are checked: an object with only the keys the call knows (an unknown top-level key is an error, not ignored), at most 2 MB (10 MB for responses and participants).
- At most 120 calls a minute; sync and report refresh at most once a minute.
- Changes made through the API are logged in the project's activity log as "via browser API".
- `window.surveyAutomator` is undefined when the feature is switched off for the user: deliver files as in SKILL.md.

**Outdated page.** If a call named here is missing, or `version` is below 6, the page runs an older platform version. If `unsavedChanges` is false, reload the page and check again. Otherwise ask the user to save and then reload. If the call is still missing, leave browser mode: write and deliver files as in SKILL.md.

## Practical notes for the browser tool

- **Hidden values.** Claude in Chrome shows a value as `[BLOCKED: ...]` when it looks like a password or a URL with a query string (`?`, `&`, `=`). The page still has it. Return only what you need, and replace those characters when you print text: `JSON.stringify(x).replace(/[=&?]/g, "·")`.
- **Never read or open `testUrl` yourself.** Use `publishAndTest({ open: true })`: the app opens the test tab from the user's click.
- **Large data** (hundreds of responses, a long survey): build it inside the page in a script, or send it in parts:
  ```js
  const { inputId } = surveyAutomator.beginInput();
  surveyAutomator.appendInput(inputId, part1);   // text parts of the JSON
  surveyAutomator.appendInput(inputId, part2);
  await surveyAutomator.createSurvey({ inputId }); // each input is used once
  ```
- **Changing tabs:** `await openTab("Distribute")`. Don't click the app's tabs through the page.
- **After a reload** the API object is new; earlier handles are gone.

## Which tab

`tab` decides what you may change:

| Tab | What to do |
|---|---|
| `Survey`, another non-report tab | Any change. With `questionCount` 0: create the survey. Otherwise: an update. |
| `Messages`, `Participants` (the Distribute tab), `Responses` | Survey changes as above; also data and messages (below). |
| `Dashboard`, `Report` (`reportScope: true`) | Report changes only (see "From the report"). For another change, say it is made on the Survey tab, and offer `openTab("Survey")`. |
| `Home` | The project list: see "Home: projects and folders". |

## Home: projects and folders

These work without an open project:

- `await listProjects({ search?, status?, limit? })`: the user's projects, most recent first: `[{ id, name, folder, status, participants, started, finished, lastResponse, modified, starred }]`. `search` is part of the name, or `#id`.
- `await projectsSummary()`: how many projects are in setup, started, reporting, closed.
- `await recentProjects()`: the projects the user opened last.
- `await listFolders()`: `[{ id, name, path, canCreateProjects }]`.
- `await openProject(id)` opens a project, as clicking its card. `await showHome()` shows the list.

Use them to answer questions like "which of my surveys are running?" or "find the customer survey from last spring", and to open the right project before you work in it.

**A new project:** `await newProject({ name, folder })`, with `folder` as an id or path from `listFolders()` where `canCreateProjects` is true. Ask the user which folder if it isn't clear: the folder decides who can see the project.
- The app opens its New project dialog, filled in. The user creates the project there, and it opens.
- If the user chose "Allow this session", your next `newProject` calls in that folder create projects directly (5 in all), each with Undo.
- Then fill the new, empty project with `createSurvey` (below).

## Empty project: create the survey (Tasks 1 and 2)

1. Write the survey JSON as usual. Validate it if you can run the validator (SKILL.md, "Output, validation and delivery").
2. Call `await surveyAutomator.createSurvey(survey)`. Never use an update file (`updateMode`) for an empty project. If `status` is `errors`, fix them and call it again. The server checks that the project is empty; if someone else is editing it, the call fails and you tell the user.
3. `questions`, `conditions` and `surveyMessages` are imported. Anything else, such as `responses`, is listed in `notImported`. So don't put example responses in the survey JSON (this overrides the default in `task-prompt.md`); if the user wants them, import them afterwards with `importResponses`.
4. Tell the user in a few lines what you made, and what `notImported` lists. The app shows **Undo** for 15 seconds.

## Project with questions: an update (Task 6)

Every change is an update in the format of `task-update.md`, sent through the API instead of a file.

1. Read the survey with `getSurveyJson()`, again before every new round of changes: the user may have unticked something in the last review or changed the survey in the editor. Use it as the base and copy `surveyVersion` into `baseVersion`.
2. Find what the user means from the survey's ids and texts. "YOB" is the year-of-birth question, whatever its id.
3. Call `previewUpdate(update)`. Fix everything in `errors` and repeat until `status` is `review`.
4. Call `openUpdateReview(update)` and tell the user in one or two lines what the update does (e.g. "AgeGroup: 18-34, 35-54, 55+, from the year of birth, age counted for 2026"). New calculated variables are listed under "New calculated variables".
5. `await result(handle)` gives `{ status: "applied", applied, warnings }`, `cancelled` or `errors`. After `applied` the project reloads in place and the first changed question is selected; `await showQuestion(id)` shows another one.

If the user asked for a **new** survey and the project already has questions, don't replace them. Offer `newProject`, or to replace the survey with an update.

## From the report

On the Dashboard and Report tabs (`reportScope()` is `true`), what happens in the report stays in the report. Pass `{ scope: "report" }` as the second argument to `previewUpdate` and `openUpdateReview`. The platform accepts only two kinds of change:
- calculated variables hidden from respondents (`excluded: true`): add, edit, replace, move or remove them;
- the report text of a question: send only `text`. The text respondents see is kept as its `surveyText`.

Anything else is refused (`reportScopeSurveyChange`, `reportScopeVisible`). The review dialog says "Report changes only".

**The Dashboard:**
- `reportStatus()`: `{ running, report: { id, name, created }, newResponsesForReport }`.
- `dashboard()`: the open report's pages `[{ id, name, type, variables }]`.
- `await refreshReport()` (Dashboard tab): creates the dashboard, or syncs the responses and updates it. It asks like `syncResponses` and returns a handle; `result(handle, { timeoutMs: 60000 })` says `done` when the report is ready.
- `await openDashboardEdit()` opens Edit on the Dashboard for the user.

## Design: Scripts / CSS

Custom design is CSS (and scripts) in **Survey settings → Scripts / CSS**, the HEAD-tag HTML of the survey. The **survey-automator-css-helper** skill knows how to write it (selectors, theme colours, preview); use it for design requests if it is available. `overview().theme` has the project's colours.

- `getScriptsCss()` returns `{ head, header, footer }`.
- `await setScriptsCss({ head })` asks the user to apply and save. Only the fields you give change; `""` clears one. Send the whole new HEAD: keep what was there and replace only your own block, e.g. `<style id="ra-overrides">…</style>`.
- The confirmation shows the lines that change. After `applied`, ask the user to check the preview.

## Survey messages and redirects

The screens respondents see outside the questions (`messages.md`):

- `getSurveyMessages()`: `{ surveyComplete?, screenedOut?, quotaFull?, surveyClosed?, alreadyCompleted?, invalidPassword? }`, each `{ header, body, footer, redirectURL }`.
- `await setSurveyMessages({ surveyComplete: { header: "Thank you!" } })`: only what you give changes; `""` clears a field. The user confirms in the app.
- **Redirects.** `redirectURL` sends the respondent on to another page after the screen, e.g. back to a panel provider. It is allowed on every message, also `screenedOut` and `quotaFull` (panels usually want one URL each for complete, screen-out and quota full). It must start with `https://` or `http://`. Ask the user for the exact URLs; never invent them.
- `quotaFull` exists only in the browser API, not in the survey JSON file format.

## Publish and test

- `await publishStatus()`: `{ published }`. Read only.
- `await publishAndTest({ open: true })` publishes the saved survey after the user allows it, and the app opens the test in a new tab. The result is `{ status: "published", opened }`; if `opened` is false the browser blocked the tab: ask the user to press TEST.
- Publish only when the user asks you to publish or test. A published survey is live: new respondents get the new version at once. Publishing doesn't send invitations.
- Report what you found in the test; don't test by changing the survey.

## Responses and participants

**Responses (Task 3).**
1. Read the survey with `getSurveyJson()`; generate the responses as `task-responses.md` says, keyed by the survey's own ids.
2. `await importResponses({ responses })` (the survey's questions are used when you leave `questions` out). The user sees the first rows ("Showing 5 of N rows") and confirms; the Responses tab refreshes.
3. Imported responses count in reports like real ones, and the platform has no "test response" flag for them. Say so when the project is, or will be, in fieldwork, and suggest a copy of the project for testing.

**Participants (Task 4).** `await importParticipants({ questions, participants }, { mode, match })` with the fields as in `task-participants.md`:

| `mode` | What happens |
|---|---|
| `add` (default) | Every row is a new participant. Sending the same people twice duplicates them. |
| `update` | Rows update the participant with the same `match` field; other rows are skipped. |
| `addOrUpdate` | Update the matching participants, add the rest. |

- `match` is `"External ID"` (the default when the rows have it) or `"Email"`. Every row needs it.
- `update` and `addOrUpdate` take system fields only (name, e-mail, phone, External ID, ...), no category fields.
- The confirmation counts duplicate and invalid e-mail addresses; fix them before the user has to.
- Nobody is invited by the import.

**Sync.** `await syncResponses()` brings in responses waiting on the survey server (`overview().freshness.waitingToSync`), as the sync button does. The user allows it the first time. Sync before analysing when responses are waiting.

## Invitations and reminders (Task 5)

The messages of Task 5 go into the project's **Distribute → Messages**. Write them in the `messages` format of `invitations.md`.

1. `await getMessagesJson()` returns `{ messages: [...] }`: every message of the project, each with its `id`. A message with `customHtml: true` has its own HTML and can only be changed in the app.
2. **To change a message**, send its `id` and only the fields that change, e.g. `{ id: 9, linkLabel: "Answer here" }`. A field you leave out keeps its value; `""` clears one. **Without `id`**, a message is new. Nothing is deleted.
3. `await previewMessages({ messages })` checks them and returns `{ status: 'review' | 'errors' | 'unchanged', messages: [{ action, changes, warnings, errors }] }`. Fix `errors` and repeat.
4. `await openMessagesReview({ messages })`:
   - **only new messages**: a short confirmation, from any tab; the toast has Undo;
   - **changes to existing messages**: the full review in Distribute → Messages. Open it first: `await openTab("Distribute")`, and if the call still says so, ask the user to show the messages.
   - The result (`result(handle)`) is `saved`, `cancelled` or `errors`. Nothing is sent by saving.
5. **SMS sender name**: at most 11 letters and digits (no spaces, hyphens or other characters), or a phone number; carriers may reject anything else. Fix the warning `previewMessages` gives.

## Analysis: crosstabs

On any tab, read only. Sync first if `overview().freshness.waitingToSync` is above 0.

- `listVariables()` lists the reportable variables: questions, grid rows and calculated variables, with their answers.
- `await crosstab({ variables: [...], by, filter?, compact: true })`: one table per variable, with the same columns (the total, then one per answer of `by`), in one call (at most 20 variables).
  - Compact output: `{ columns: [{ id, label }], tables: [{ variable, text, base: [per column], rows: [[id, label, percent per column]] }] }`.
  - Without `compact` you get counts too; `variable` instead of `variables` gives one table.
  - `filter` is `{ variable, answers: [...], not? }` (or an array of them, all must match). `by` and filters must be single or multiple choice.
  - A column with fewer than 5 responses has `null` for its base and percents: report it as "too few responses", never guess its numbers, and don't narrow filters to get around it.

**Finding segments.** Work like an analyst, with few calls:

1. **Start from a question**, the user's or the survey's main outcome (satisfaction, energy, intention to stay). Plan the tables before you call anything.
2. **Cross outcomes by explanations only**: the outcome questions as `variables`, one background or explanatory variable as `by` (role, work mode, region, age group). Batch them: one call per `by`, not one per pair.
3. **Judge a difference against its margin of error**, not against a fixed n. For two percentages p1 and p2 with bases n1 and n2, the difference is clear when it exceeds about 2 × √(p1(1−p1)/n1 + p2(1−p2)/n2). The suppression rule (fewer than 5) is only the floor. The more tables you look at, the stricter you should be: with 20 comparisons, one will look clear by chance.
4. **Look for consistency**: a segment that differs on several related questions is more convincing than one big difference.
5. **A predefined segment is an idea until tested.** If a group the user asks about is too small, say "too small to tell", not "no difference".
6. **Save a segment worth following** as a calculated variable hidden from respondents: a report update (`{ scope: "report" }`, `excluded: true`, see "From the report" and `calculated-variables.md`). The user reviews and applies it; then `crosstab` and the Dashboard can use it.
7. **Report** each finding with its base (n), the size of the difference, and a caveat when the base is small or the comparison is one of many.

## Delivery

- The delivery is the change in the project (`createSurvey`, the review dialog, the confirmations). Don't write or offer a file, and don't add the import line, unless the user asks.
- A short request gets a short answer. Use the user's first name now and then, not in every message.
- Publish, sync or create projects only when the user asks, and never click Apply, Allow, Import, Add or Create for the user.
