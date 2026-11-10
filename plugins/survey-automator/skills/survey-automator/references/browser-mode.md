# Browser mode: a Survey Automator project open in the tab

Read this only when `window.surveyAutomator` exists in the user's browser tab (SKILL.md, Step 0). The user is logged in with a project open, and **the result goes straight into that project, not into a file**. This holds for every kind of request: a new survey ("create a survey and add it here", "lägg in en enkät här"), a change, or a short request about "the survey", "the data", a question id or a variable ("create age groups from YOB", "skapa åldersgrupper från YOB"). Don't ask for files.

Do the task's authoring work as usual (task file, format files, example). Only where the result goes, and what you deliver, differ. Those rules are below.

## The API

`window.surveyAutomator` runs in the user's own session. `surveyAutomator.help` lists the calls.

| Call | What it does |
|---|---|
| `project()` | `{ id, name, unsavedChanges, questionCount, tab, reportScope }`. Call it first. With `unsavedChanges`, ask the user to save: the other calls see the saved survey. |
| `await getSurveyJson()` | The saved survey as its JSON export, with `surveyVersion`. |
| `await createSurvey(survey)` | Only when `questionCount` is 0. Creates the survey from a normal survey JSON (`{ questions, conditions? }`) at once, without a review. Returns `{ status: "created" \| "errors", errors, created, notImported }`. |
| `await previewUpdate(update, options?)` | The server's checks of an update file. Returns `{ status: "review" \| "errors", errors, review }` with every problem at once. Changes nothing. |
| `openUpdateReview(update, options?)` | Opens the review dialog. The user reviews and applies the changes there. |
| `reportScope()` | `true` on the Dashboard and Report tabs. |
| `getScriptsCss()` / `await setScriptsCss({ head?, header?, footer? })` | Survey settings → Scripts / CSS. See "Design: Scripts / CSS". |
| `getSurveyMessages()` / `await setSurveyMessages(messages)` | Thank-you and other screens, with redirect URLs. See "Survey messages and redirects". |
| `await publishStatus()` / `await publishAndTest()` | Whether the survey is published, and its test link. See "Publish and test". |
| `await importResponses(data)` | Example responses into the project (Task 3). See "Responses and participants". |
| `await importParticipants(data)` | Participants into Distribute → Participants (Task 4). |
| `listVariables()` / `await crosstab({ variable, by?, filter? })` | Read-only analysis of the responses. See "Analysis: crosstabs". |

**Every call that changes something waits for the user.** The app shows what will change (a confirmation, the review dialog, or a permission dialog for publishing), and only the user's own click answers it. Your call returns when they have answered: `status` is `applied`, `imported`, `published` or `cancelled`. On `cancelled`, ask what they want instead; don't call again unasked. Never click the buttons in these dialogs yourself, even if you could: the user decides.

**Values the browser tool hides.** Claude in Chrome may show a value as `[BLOCKED: ...]` (e.g. a key named like a password, or text with a URL query string). The page still has it; read only the part you need (e.g. one `<style id="...">` block of the HEAD), or ask the user.

**Outdated page.** If a call named here is missing, the page runs an older platform version. If `unsavedChanges` is false, reload the page and check again. Otherwise, ask the user to save and then reload. If the call is still missing, leave browser mode: write and deliver files as in SKILL.md.

## Which tab

`tab` decides what you may change:

| Tab | What to do |
|---|---|
| `Survey`, another non-report tab, or empty | Any change. With `questionCount` 0: create the survey. Otherwise: an update. |
| `Messages`, `Participants` (the Distribute tab), `Responses` | Survey changes as above. Participants and responses: see "Responses and participants". |
| `Dashboard`, `Report` (`reportScope: true`) | Report changes only (see "From the report"). If the user asks for another change, say it is made on the Survey tab, and offer to do it there. |

## Empty project: create the survey (Tasks 1 and 2)

1. Write the survey JSON as usual. Validate it if you can run the validator (SKILL.md, "Output, validation and delivery").
2. Call `await window.surveyAutomator.createSurvey(survey)`. Never use an update file (`updateMode`) for an empty project. If `status` is `errors`, fix them and call it again.
3. `questions`, `conditions` and `surveyMessages` are imported. Anything else, such as `responses`, is listed in `notImported`. So don't put example responses in the survey JSON (this overrides the default in `task-prompt.md`); if the user wants them, import them afterwards with `importResponses` (see "Responses and participants").
4. Tell the user in a few lines what you made, and what `notImported` lists, if anything.

## Project with questions: an update (Task 6)

Every change is an update in the format of `task-update.md`, sent through the API instead of a file.

1. Read the survey with `getSurveyJson()`, again before every new round of changes: the user may have unticked something in the last review or changed the survey in the editor. Use it as the base and copy `surveyVersion` into `baseVersion`.
2. Find what the user means from the survey's ids and texts. "YOB" is the year-of-birth question, whatever its id.
3. Call `previewUpdate(update)`. Fix everything in `errors` and repeat until `status` is `review`.
4. Call `openUpdateReview(update)` and tell the user in one or two lines what the update does (e.g. "AgeGroup: 18-34, 35-54, 55+, from the year of birth, age counted for 2026"). They review and apply it there. If the app asks about the project's edit lock, the user decides.

If the user asked for a **new** survey and the project already has questions, don't replace them. Ask whether to use a new, empty project, or to replace the survey with an update.

## From the report

On the Dashboard and Report tabs (`reportScope()` is `true`), what happens in the report stays in the report. Pass `{ scope: "report" }` as the second argument to `previewUpdate` and `openUpdateReview`. The platform accepts only two kinds of change:
- calculated variables hidden from respondents (`excluded: true`): add, edit, replace, move or remove them;
- the report text of a question: send only `text`. The text respondents see is kept as its `surveyText`.

Anything else is refused (`reportScopeSurveyChange`, `reportScopeVisible`). The review dialog says "Report changes only".

## Design: Scripts / CSS

Custom design is CSS (and scripts) in **Survey settings → Scripts / CSS**, the HEAD-tag HTML of the survey. The **survey-automator-css-helper** skill knows how to write it (selectors, theme colours, preview); use it for design requests if it is available.

- `getScriptsCss()` returns `{ head, header, footer }`, the HEAD-tag HTML and the survey's header and footer HTML.
- `await setScriptsCss({ head })` asks the user to apply and save. Only the fields you give change; `""` clears one. Send the whole new HEAD: keep what was there (other scripts, earlier blocks) and replace only your own block, e.g. `<style id="ra-overrides">…</style>`.
- The confirmation shows the lines that change. After `applied`, the preview shows the result; ask the user to check it.

## Survey messages and redirects

The screens respondents see outside the questions (`messages.md`) can be changed in a project with questions:

- `getSurveyMessages()`: `{ surveyComplete?, screenedOut?, quotaFull?, surveyClosed?, alreadyCompleted?, invalidPassword? }`, each `{ header, body, footer, redirectURL }`.
- `await setSurveyMessages({ surveyComplete: { header: "Thank you!" } })`: only what you give changes; `""` clears a field. The user confirms in the app.
- **Redirects.** `redirectURL` sends the respondent on to another page after the screen, e.g. back to a panel provider ("redirect completes to https://panel.example.com/complete?status=1"). Here it is allowed on every message, also `screenedOut` and `quotaFull` (panels usually want one URL each for complete, screen-out and quota full). It must start with `https://` or `http://`. Ask the user for the exact URLs; never invent them.
- `quotaFull` exists only in the browser API, not in the survey JSON file format.

## Publish and test

- `await publishStatus()`: `{ published, testUrl }`. Read only.
- `await publishAndTest()` publishes the saved survey only after the user allows it: the app asks "The AI assistant wants to publish and test the survey" with Cancel / Allow once / Allow this session. It returns `{ status, testUrl }`. With "Allow this session" later calls in the same tab don't ask again.
- Publish only when the user asks you to publish or test. A published survey is live: new respondents get the new version at once. Publishing doesn't send invitations.
- After `published`, open `testUrl` in a new tab to test the survey. It answers as a test respondent. Report what you found; don't test by changing the survey.

## Responses and participants

In browser mode, Tasks 3 and 4 put the data straight into the project instead of a file:

1. Read the survey with `getSurveyJson()`. Its `questions` are the input of Task 3; generate the responses as `task-responses.md` says, keyed by the survey's own ids.
2. Call `await importResponses({ responses })` (the survey's questions are used when you leave `questions` out), or `await importParticipants({ questions, participants })` with the participant fields as in `task-participants.md`.
3. The user sees the first rows and confirms. The result has the import's report in `message` (e.g. "Added count: 20").

Imported responses are counted in reports like real ones, and the platform has no "test response" flag for them. Say so when you import them into a project that is, or will be, in fieldwork, and suggest a copy of the project for testing. Participants are not invited by the import.

## Analysis: crosstabs

On any tab, you can analyse the responses read-only:

- `listVariables()` lists the reportable variables: questions, grid rows and calculated variables, with their answers.
- `await crosstab({ variable, by, filter? })` returns counts and percents of `variable` in total and per answer of `by`. `filter` is `{ variable, answers: [...] }` (or an array of them). It counts the saved responses.

To find interesting segments, cross the key questions by the background variables (age, region, role, ...), and look for large differences between columns with enough base. Then suggest a calculated variable for a segment worth following (e.g. "Hybrid workers with low energy") and create it as a report update: `{ scope: "report" }`, `excluded: true` (see "From the report" and `calculated-variables.md`). The user reviews and applies it. Report numbers with their base (n), and don't call a difference real when the base is small.

## Delivery

- The delivery is `createSurvey` or the review dialog. Don't write or offer a file, and don't add the import line, unless the user asks.
- A short request gets a short answer.
- Publish only when the user asks (see "Publish and test"), and never click Apply, Allow or Import for the user.
