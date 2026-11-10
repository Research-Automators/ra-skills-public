# Browser mode: Survey Automator open in the tab

Read this only when `window.surveyAutomator` exists in the user's browser tab (SKILL.md, Step 0). The user is logged in, and **the result goes straight into their project, not into a file**. This holds for every kind of request: a new survey ("create a survey and add it here", "lägg in en enkät här"), a change, or a short request about "the survey", "the data", a question id or a variable ("create age groups from YOB", "skapa åldersgrupper från YOB"). Don't ask for files.

Do the task's authoring work as usual (task file, format files, example). Only where the result goes, and what you deliver, differ.

This file has the rules for every request. Then read **only the file for what the request needs**:

| The request | Read |
|---|---|
| Create a survey, change it (Tasks 1, 2, 6), report variables from the Dashboard, design (CSS), survey messages and redirects, publish and test | `browser-survey.md` |
| Example responses, participants, syncing responses (Tasks 3, 4) | `browser-data.md` |
| Invitation, reminder and thank-you e-mails and SMS (Task 5) | `browser-messages.md` |
| Results, crosstabs, segments, the Dashboard | `browser-analysis.md` |
| No project open, the user's projects, a new project | `browser-home.md` |

Read the file before your first call in its area: each has rules the call needs (e.g. `match` for participants, `{ scope: "report" }` on the Dashboard).

This describes API version 6 (`surveyAutomator.version`).

## Start of a session

1. Call `project()`. If it throws, no project is open: read `browser-home.md`.
2. Otherwise call `await surveyAutomator.overview()`. It gives the project at a glance; use it to talk naturally:
   - `name`, `status` (`setup`, `started`, `reporting`, `closed`), `published`;
   - `totals` (participants, started, finished, last response; approximate);
   - `freshness.waitingToSync` (responses not yet brought into the project);
   - `structure` (questions, calculated variables, conditions, quotas, reports), `languages`, `theme`;
   - `user.firstName`: address the user by it now and then, not in every message;
   - `role` (what the user may change), `tab`, `unsavedChanges`.
3. With `unsavedChanges`, ask the user to save: the other calls see the saved survey.

## Friendly, contextual suggestions

Suggest what is useful next, from where the user is and what just happened. Be a helpful colleague, not a menu: short, concrete, in the user's language, and easy to say no to. Each area file has a "Suggestions" section with what fits there.

- **When the user only calls the skill** ("help", "survey automator", "what can you do?"): greet them by first name and offer two to four things that fit the tab, from that area's file (`Home`: `browser-home.md`; `Survey`: `browser-survey.md`; `Messages`, `Participants`: `browser-messages.md` and `browser-data.md`; `Responses`: `browser-data.md`; `Dashboard`, `Report`: `browser-analysis.md`). Don't list every call.
- **After a task**: end with **one** short offer of a natural next step, as a question: "Would you like me to …?" ("Vill du att jag …?"). At most two options.
- Make it concrete with what `overview()` says: "15 responses so far; want me to look for differences between work modes?", "7 responses are waiting to be synced".
- Only offer what the user can do (`overview().role`) and what fits the tab and the project's state.
- Never offer test responses for a project in fieldwork (`status` started with real responses): offer a copy of the project instead.
- Don't offer the same thing again after the user said no, and don't offer anything after a short factual answer.
- The offer is a question. Do nothing until the user says yes.

## The API

`window.surveyAutomator` runs in the user's own session. `surveyAutomator.help` is a list of every call with its arguments.

| Call | Area (file) |
|---|---|
| `project()`, `await overview()`, `await openTab(name)`, `await showQuestion(id)` | Here |
| `await result(handle, { timeoutMs })`, `beginInput()`, `appendInput(inputId, text)` | Here |
| `await getSurveyJson()`, `await createSurvey(survey)`, `await previewUpdate(update, options?)`, `openUpdateReview(update, options?)`, `reportScope()` | `browser-survey.md` |
| `getScriptsCss()`, `await setScriptsCss(...)`, `getSurveyMessages()`, `await setSurveyMessages(...)` | `browser-survey.md` |
| `await publishStatus()`, `await publishAndTest({ open: true })` | `browser-survey.md` |
| `await importResponses(data)`, `await importParticipants(data, { mode, match })`, `await syncResponses()` | `browser-data.md` |
| `await getMessagesJson()`, `await previewMessages(json)`, `await openMessagesReview(json)` | `browser-messages.md` |
| `listVariables()`, `await crosstab(...)`, `reportStatus()`, `dashboard()`, `await refreshReport()`, `await openDashboardEdit()` | `browser-analysis.md` |
| `await listProjects(...)`, `await projectsSummary()`, `await recentProjects()`, `await listFolders()`, `await openProject(id)`, `await showHome()`, `await newProject(...)` | `browser-home.md` |

`openTab(name)` opens `Survey`, `Distribute`, `Responses`, `Report` or `Dashboard`; `showQuestion(id)` opens the Survey tab at a question. Both only move the view.

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
| `Messages`, `Participants` (the Distribute tab), `Responses` | Survey changes as above; also data and messages. |
| `Dashboard`, `Report` (`reportScope: true`) | Report changes only (`browser-survey.md`, "From the report"). |
| `Home` | The project list (`browser-home.md`). |

## Delivery

- The delivery is the change in the project (`createSurvey`, the review dialog, the confirmations). Don't write or offer a file, and don't add the import line, unless the user asks.
- A short request gets a short answer.
- Publish, sync or create projects only when the user asks, and never click Apply, Allow, Import, Add or Create for the user.
