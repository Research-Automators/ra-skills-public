# Browser mode: responses, participants and sync

Read this together with `browser-mode.md` when the request imports responses or participants (Tasks 3 and 4), or needs the latest responses.

## Responses (Task 3)

1. Read the survey with `getSurveyJson()`; generate the responses as `task-responses.md` says, keyed by the survey's own ids.
2. `await importResponses({ responses })` (the survey's questions are used when you leave `questions` out). The user sees the first rows ("Showing 5 of N rows") and confirms; the Responses tab refreshes.
3. Imported responses count in reports like real ones, and the platform has no "test response" flag for them. Say so when the project is, or will be, in fieldwork, and suggest a copy of the project for testing.

Hundreds of rows: build them inside the page in a script, or send them in parts (`beginInput`, `browser-mode.md`).

## Participants (Task 4)

`await importParticipants({ questions, participants }, { mode, match })` with the fields as in `task-participants.md`:

| `mode` | What happens |
|---|---|
| `add` (default) | Every row is a new participant. Sending the same people twice duplicates them. |
| `update` | Rows update the participant with the same `match` field; other rows are skipped. |
| `addOrUpdate` | Update the matching participants, add the rest. |

- `match` is `"External ID"` (the default when the rows have it) or `"Email"`. Every row needs it.
- `update` and `addOrUpdate` take system fields only (name, e-mail, phone, External ID, ...), no category fields.
- When the user adds people who may already be there, use `addOrUpdate`, not `add`.
- The confirmation counts duplicate and invalid e-mail addresses; fix them before the user has to.
- Nobody is invited by the import. Invitations: `browser-messages.md`.

## Sync

`await syncResponses()` brings in responses waiting on the survey server (`overview().freshness.waitingToSync`), as the sync button does.
- The user allows it the first time (Cancel / Allow once / Allow this session). At most once a minute.
- Sync before analysing or reporting when responses are waiting.
- The result is `{ status: "synced", freshness }`.

## Suggestions

**On the Responses tab, when the skill is only called:** example responses for testing (only before fieldwork); syncing new responses; a quick look at how the responses are going. **On Participants:** importing or updating participants.

**Next steps:**

| What just happened | Offer |
|---|---|
| Participants were imported | The invitation (and an SMS) for them (`browser-messages.md`). |
| Example responses were imported | A quick crosstab of the main question, or the Dashboard (`browser-analysis.md`). |
| Responses were synced | A quick look at what changed since last time. |
