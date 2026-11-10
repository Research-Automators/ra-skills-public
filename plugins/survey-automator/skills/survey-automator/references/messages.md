# Survey messages

> **Not the same as the top-level `messages` array.** This file documents `surveyMessages` — the *screens* shown to respondents inside the survey (thank-you, screened-out, etc.). For *outbound* email and SMS communications sent to participants (invitations, reminders, thank-yous, notifications), see `invitations.md`.

The optional top-level `surveyMessages` object holds the platform-level messages shown to respondents *outside* the question flow — the screens they see when they finish, get screened out, hit the wrong password, return after already completing, or arrive at a closed survey.

This is not a question type. It sits alongside `questions`, `responses`, and `participants` at the root of the export:

```json
{
  "questions": [ ... ],
  "surveyMessages": {
    "surveyComplete": { ... },
    "screenedOut": { ... }
  }
}
```

If `surveyMessages` is omitted entirely, the platform shows its own defaults. Including the object is only useful when you want to override one or more of those defaults with survey-specific copy.

## Message keys

| Key | Shown when |
|---|---|
| `surveyComplete` | The respondent successfully submits their final answer. The standard thank-you screen. Often the only message worth customizing. |
| `screenedOut` | The respondent hits a `screenout` item (see `flow-control.md`) and is exited before completing. |
| `invalidPassword` | The respondent enters the wrong access password on a password-protected survey. |
| `alreadyCompleted` | The respondent returns to the survey link after having already submitted a response. |
| `surveyClosed` | The respondent opens the link after fieldwork has been closed. |

All five keys are optional. Set only the ones you want to override.

## Message shape

Each message is an object with three optional text fields:

| Field | Type | Description |
|---|---|---|
| `header` | [text](format-questions.md#texts) | Large heading shown at the top of the message screen. |
| `body` | [text](format-questions.md#texts) | The main message text. |
| `footer` | [text](format-questions.md#texts) | Smaller text below the body — typically a closing line like "You may now close this window". |

`surveyComplete` additionally accepts one more field:

| Field | Type | Description |
|---|---|---|
| `redirectURL` | string | Full URL the respondent is redirected to a few seconds after the thank-you screen renders. Omit unless the user explicitly requests a redirect. |

With a Survey Automator project open in the browser, messages and redirects can also be changed in the project itself, including redirects for screen-outs and quota full (see "Survey messages and redirects" in `browser-mode.md`).

No other fields are allowed; the validator rejects typos and unknown keys.

## Writing the copy

Each message addresses the respondent directly at a specific moment, so the tone differs from question text:

- **`surveyComplete`** — warm thanks, brief acknowledgement that the response was saved, and a closing line. Match the survey's overall tone (formal vs. casual).
- **`screenedOut`** — thank them for their time and explain briefly that they don't match the audience. Do **not** reveal the screening criteria — same logic as the `surveyText` on `screenout` items in `flow-control.md`. Note that responses from screened-out respondents are typically not saved; the body may reflect that.
- **`invalidPassword`** — short, direct, actionable. Tell them to check the password and try again, and where to get help if it persists.
- **`alreadyCompleted`** — brief acknowledgement that their earlier response was received. No instructions needed.
- **`surveyClosed`** — short, neutral. Don't apologize at length; just state the survey isn't accepting responses anymore.

Headers are typically a short phrase (3–6 words). Bodies are one or two sentences. Footers are one short line.

## Inline example

A complete `surveyMessages` block with all five messages set:

```json
{
  "surveyMessages": {
    "surveyComplete": {
      "header": "Thank you for participating!",
      "body": "Your responses have been saved.",
      "footer": "You may now close this window",
      "redirectURL": "https://researchautomators.com/"
    },
    "screenedOut": {
      "header": "Thank you for your time",
      "body": "Unfortunately you did not match the target audience. Your responses will not be saved.",
      "footer": "You may now close this window"
    },
    "invalidPassword": {
      "header": "Incorrect password",
      "body": "Please check your password and try again.",
      "footer": "Contact the survey sender if the problem persists"
    },
    "alreadyCompleted": {
      "header": "Survey already completed",
      "body": "We have already received your response.",
      "footer": "Thank you for participating"
    },
    "surveyClosed": {
      "header": "Survey closed",
      "body": "This survey is no longer accepting responses.",
      "footer": "You may now close this window"
    }
  }
}
```

A more typical minimal block — just the completion screen:

```json
{
  "surveyMessages": {
    "surveyComplete": {
      "header": "Thank you!",
      "body": "Your responses have been saved.",
      "footer": "You may now close this window"
    }
  }
}
```

## Notes

- `surveyMessages` is platform output, not response data. It never appears in `responses` and is not collected from respondents.
- A survey with no `surveyMessages` block at all is perfectly valid — the platform falls back to its defaults.
- When a survey has `screenout` items, set `screenedOut` so screened-out respondents see survey-appropriate copy rather than the generic default.
