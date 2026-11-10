# Browser mode: the survey

Read this together with `browser-mode.md` when the request creates or changes a survey, its design or its messages, or publishes it (Tasks 1, 2 and 6).

## Empty project: create the survey (Tasks 1 and 2)

1. Write the survey JSON as usual. Validate it if you can run the validator (SKILL.md, "Output, validation and delivery").
2. Call `await surveyAutomator.createSurvey(survey)`. Never use an update file (`updateMode`) for an empty project. If `status` is `errors`, fix them and call it again. The server checks that the project is empty; if someone else is editing it, the call fails and you tell the user.
3. `questions`, `conditions` and `surveyMessages` are imported. Anything else, such as `responses`, is listed in `notImported`. So don't put example responses in the survey JSON (this overrides the default in `task-prompt.md`); if the user wants them, import them afterwards with `importResponses` (`browser-data.md`).
4. Tell the user in a few lines what you made, and what `notImported` lists. The app shows **Undo** for 15 seconds.

## Project with questions: an update (Task 6)

Every change is an update in the format of `task-update.md`, sent through the API instead of a file.

1. Read the survey with `getSurveyJson()`, again before every new round of changes: the user may have unticked something in the last review or changed the survey in the editor. Use it as the base and copy `surveyVersion` into `baseVersion`.
2. Find what the user means from the survey's ids and texts. "YOB" is the year-of-birth question, whatever its id.
3. Call `previewUpdate(update)`. Fix everything in `errors` and repeat until `status` is `review`.
4. Call `openUpdateReview(update)` and tell the user in one or two lines what the update does (e.g. "AgeGroup: 18-34, 35-54, 55+, from the year of birth, age counted for 2026"). New calculated variables are listed under "New calculated variables".
5. `await result(handle)` gives `{ status: "applied", applied, warnings }`, `cancelled` or `errors`. After `applied` the project reloads in place and the first changed question is selected; `await showQuestion(id)` shows another one.

If the user asked for a **new** survey and the project already has questions, don't replace them. Offer `newProject` (`browser-home.md`), or to replace the survey with an update.

## From the report

On the Dashboard and Report tabs (`reportScope()` is `true`), what happens in the report stays in the report. Pass `{ scope: "report" }` as the second argument to `previewUpdate` and `openUpdateReview`. The platform accepts only two kinds of change:
- calculated variables hidden from respondents (`excluded: true`): add, edit, replace, move or remove them;
- the report text of a question: send only `text`. The text respondents see is kept as its `surveyText`.

Anything else is refused (`reportScopeSurveyChange`, `reportScopeVisible`). The review dialog says "Report changes only". For another change, say it is made on the Survey tab, and offer `openTab("Survey")`.

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
- Never read or open `testUrl` yourself.
- Report what you found in the test; don't test by changing the survey.
