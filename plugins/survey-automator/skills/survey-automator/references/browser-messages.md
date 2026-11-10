# Browser mode: invitations and reminders (Task 5)

Read this together with `browser-mode.md` when the request writes or changes the e-mails and SMS sent to participants. The messages go into the project's **Distribute → Messages**. Write them as Task 5 says (`task-invitations.md`), in the `messages` format of `invitations.md`. These are not the screens inside the survey (thank-you, screen-out): those are survey messages (`browser-survey.md`, `messages.md`).

1. `await getMessagesJson()` returns `{ messages: [...] }`: every message of the project, each with its `id`. A message with `customHtml: true` has its own HTML and can only be changed in the app.
2. **To change a message**, send its `id` and only the fields that change, e.g. `{ id: 9, linkLabel: "Answer here" }`. A field you leave out keeps its value; `""` clears one. **Without `id`**, a message is new. Nothing is deleted.
3. `await previewMessages({ messages })` checks them and returns `{ status: 'review' | 'errors' | 'unchanged', messages: [{ action, changes, warnings, errors }] }`. Fix `errors` and repeat.
4. `await openMessagesReview({ messages })`:
   - **only new messages**: a short confirmation, from any tab; the toast has Undo;
   - **changes to existing messages**: the full review in Distribute → Messages. Open it first: `await openTab("Distribute")`, and if the call still says so, ask the user to show the messages.
   - The result (`result(handle)`) is `saved`, `cancelled` or `errors`. Nothing is sent by saving.
5. **SMS sender name**: at most 11 letters and digits (no spaces, hyphens or other characters), or a phone number; carriers may reject anything else. Fix the warning `previewMessages` gives.

Sending is always the user's step in the Distribute tab.

## Suggestions

**On Messages, when the skill is only called:** writing or changing invitations and reminders; an SMS reminder; checking the SMS sender name.

**Next steps:**

| What just happened | Offer |
|---|---|
| Invitations or reminders were saved | Check who will get them (the participants). Remind the user that sending is their step in Distribute. |
| A message was changed that was already sent | Nothing to resend: only later sendouts use it. Say so. |
