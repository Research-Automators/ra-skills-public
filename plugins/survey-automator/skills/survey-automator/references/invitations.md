# Invitation messages

The optional top-level `messages` array holds **outbound** communications — the email and SMS invitations, reminders, thank-yous, and notifications that the platform sends to participants. This is the send-out side of fieldwork: who gets contacted, in what channel, with what copy.

> **Not the same as `surveyMessages`.** `surveyMessages` is end-of-flow *screens* shown to respondents inside the survey (thank-you screen, screened-out screen, …) — see `messages.md`. `messages` is *outbound emails/SMS* sent to participants. The names collide; the concepts don't.

The `messages` array sits at the root of the export alongside `questions`, `responses`, `participants`, and `surveyMessages`:

```json
{
  "questions": [ ... ],
  "messages": [
    { "name": "Email invitation", "sendType": "invitation", "messageType": "email", ... },
    { "name": "SMS reminder",     "sendType": "reminder",   "messageType": "sms",   ... }
  ]
}
```

## Standalone vs combined import

A `messages`-only file is a valid import. The minimum content is:

1. The `questions` array containing **at least the `system` and `category` questions** referenced by merge fields and conditions in the messages. No survey questions needed.
2. The `messages` array.

This is how a user adds invitation/reminder copy to an already-built survey without re-importing the full survey definition.

A combined file (survey + messages) is also valid and is what you get when the user asks for "a survey with invitation messages" in one go.

## Message object

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Internal label for the message (e.g. "Email invitation", "First reminder"). Not shown to the participant. |
| `sendType` | string | Yes | One of `invitation`, `reminder`, `thanks`, `notification`. See [Send types](#send-types). |
| `messageType` | string | Yes | One of `email`, `sms`. Determines which body fields apply. |
| `senderName` | string | Yes | Display name shown as the sender (e.g. "Acme HR", "Johnny"). **For SMS**, this is an alphanumeric sender ID: max 11 characters, letters and digits only — no spaces or punctuation (e.g. `"RASurvey"`, not `"RA Survey"`). |
| `condition` | object | No | Conditional send rule — only participants matching the condition receive this message. See [Conditions](#conditions). |

The remaining fields depend on `messageType`.

### Email-specific fields

| Field | Type | Required | Description |
|---|---|---|---|
| `subject` | string | Yes | Email subject line. |
| `title` | string | No | Large heading at the top of the email body. Typically a greeting like `"Hi #FirstName#,"`. |
| `bodyBeforeLink` | string | Yes | Main message text shown above the survey link button. Plain text with `\n` line breaks. |
| `linkLabel` | string | Yes | The button text for the survey link (e.g. "Take the survey"). The link itself is the built-in `#DsLink#`. |
| `bodyAfterLink` | string | No | Additional text shown below the link button. Often used for confidentiality reassurance or thanks. |
| `footer` | string | No | Smaller footer text. Typically opt-out language. |
| `optOutLabel` | string | No | Label for the unsubscribe link in the footer (e.g. "Unsubscribe"). |

### SMS-specific fields

| Field | Type | Required | Description |
|---|---|---|---|
| `body` | string | Yes | The full SMS body. Must contain `#DsLink#` somewhere (otherwise the recipient has no way to open the survey). Keep it short — SMS has practical length limits. |

SMS messages do **not** use `subject`, `title`, `bodyBeforeLink`, `bodyAfterLink`, `linkLabel`, `footer`, or `optOutLabel`. The validator rejects them.

## Send types

| `sendType` | Semantics |
|---|---|
| `invitation` | The initial send. Goes to all eligible participants. |
| `reminder` | Goes only to participants who were sent an `invitation` and have not yet completed. The "not completed" filter is automatic — do not try to encode it in a `condition`. |
| `thanks` | Goes only to participants who have completed the survey. The "completed" filter is automatic. |
| `notification` | Unconditional send. No automatic filtering. Useful for ad-hoc broadcasts (e.g. "the survey closes tomorrow"). |

A `condition` can be combined with any `sendType` — it narrows the audience further. The most common pattern is gating an SMS reminder on a `category` question like `acceptsSMS`.

## Merge fields

Tokens of the form `#FieldName#` are substituted with participant-specific values at send time. There are two kinds:

### Reserved tokens (built in — always available)

| Token | Substituted with |
|---|---|
| `#DsLink#` | The participant's unique survey link. **Required** in every email (`linkLabel` button needs it) and every SMS body. |
| `#OptOutUrl#` | The participant's unique opt-out link. Built into every message automatically — usually you do not need to insert this manually. |
| `#DSPwd#` | The participant's access password (alphanumeric). Built in; rarely used. |
| `#DSPwdNum#` | The participant's access password (numeric). Built in; rarely used. |

Reserved tokens never need a corresponding question in the `questions` array.

### Participant-data tokens

Any other `#FieldName#` token is a reference to a `system` question. Matching is **case-insensitive, whitespace-stripped**, against the question's `id` or `text`. So `#FirstName#` matches a question with `id: "First Name"` or `text: "First Name"`.

| Common token | Matches `system` question with id/text |
|---|---|
| `#FirstName#` | `First Name` |
| `#LastName#` | `Last Name` |
| `#Email#` | `Email` |
| `#Phone#` | `Phone` |

If a message uses `#FirstName#`, the `questions` array must include a `type: "system"` question whose `id` or `text` (whitespace-stripped, case-insensitive) is `firstname`. The validator enforces this.

## Recipients

The platform chooses the recipient by `messageType` — there is no per-message "to" field.

| `messageType` | Recipient address pulled from |
|---|---|
| `email` | The participant's `Email` system field |
| `sms` | The participant's `Phone` system field |

This routing is automatic and not configurable per message. Consequences:

- **Email messages require an `Email` system question.** If any message in the file has `messageType: "email"`, the `questions` array must include a `type: "system"` question whose `id` or `text` normalizes to `email`. The validator enforces this.
- **SMS messages require a `Phone` system question.** Same rule for `messageType: "sms"` and a `Phone` system field.
- **Participants without the relevant field are skipped** by the platform at send time. A participant with no `Email` value cannot receive an email invitation; one with no `Phone` cannot receive an SMS.

### Phone number format

`Phone` values must be in **international `+CC...` format** (e.g. `+46701234567` for a Swedish mobile). The platform does not auto-prefix country codes — a local-format number like `0701234567` will fail to send.

Recommended canonical form: `+CCNNNNNNNNN` with no spaces, dashes, or parentheses. The validator emits a warning (not a hard error) if participant `Phone` values don't start with `+`, since the format requirement only matters for messages the platform actually sends.

Common country prefixes for typical Survey Automator audiences:

| Country | Prefix | Example |
|---|---|---|
| Sweden | `+46` | `+46701234567` |
| Norway | `+47` | `+4791234567` |
| Denmark | `+45` | `+4512345678` |
| Finland | `+358` | `+358401234567` |
| United Kingdom | `+44` | `+447700900000` |
| Germany | `+49` | `+491701234567` |
| USA / Canada | `+1` | `+15551234567` |

When generating example participants for testing SMS flows, always use the `+46...` (or relevant country) form.

## Conditions

A message `condition` narrows the audience to participants whose `category` (or `system`) attributes match a rule. Same atom syntax as question conditions, but **only `AND`, `OR`, and parentheses are supported** — no arithmetic, no comparisons.

```json
{
  "condition": {
    "label": "Accepts SMS",
    "definition": "{acceptsSMS}:{1}"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | No | Human-readable summary of the rule. Not evaluated. Keep it short. |
| `definition` | string | Yes | Expression of atoms `{QuestionId}:{AnswerId}` combined with `AND` / `OR` and optional parentheses. |

Typical condition patterns:

| Pattern | Meaning |
|---|---|
| `{acceptsSMS}:{1}` | Participant has opted in to SMS. |
| `{Region}:{2} OR {Region}:{3}` | Participant is in region 2 or 3. |
| `{Manager}:{1} AND {Tenure}:{3}` | Manager with tenure level 3. |

Conditions on messages reference participant attributes (`category` and `system` questions), not survey responses — invitations are sent before the survey is answered.

## Worked example

A typical setup: one email invitation + one SMS reminder gated on `acceptsSMS`.

```json
{
  "questions": [
    { "id": "First Name", "type": "system", "text": "First Name" },
    { "id": "Phone",      "type": "system", "text": "Phone" },
    { "id": "Email",      "type": "system", "text": "Email" },
    {
      "id": "acceptsSMS",
      "type": "category",
      "text": "Accepts SMS",
      "answers": [
        { "id": "1", "text": "Yes" }
      ]
    }
  ],
  "messages": [
    {
      "name": "Email invitation",
      "sendType": "invitation",
      "messageType": "email",
      "senderName": "Johnny",
      "subject": "Got two minutes? We'd love your input",
      "title": "Hi #FirstName#,",
      "bodyBeforeLink": "We're working on improving how we operate, and your perspective would genuinely help shape what we do next.\n\nThe survey takes just a few minutes and works on any device.",
      "linkLabel": "Take me to the survey",
      "bodyAfterLink": "Your answers are confidential and will never be reported in a way that identifies you.\n\nThanks so much for helping out!",
      "footer": "You're receiving this because you're part of our community. You can opt out of future emails at any time:",
      "optOutLabel": "Unsubscribe"
    },
    {
      "name": "SMS reminder",
      "sendType": "reminder",
      "messageType": "sms",
      "condition": {
        "label": "Accepts SMS",
        "definition": "{acceptsSMS}:{1}"
      },
      "senderName": "Acme",
      "body": "Hi #FirstName#, just a quick nudge about our short survey — your input would mean a lot. Two minutes, any device: #DsLink#"
    }
  ]
}
```

## Writing the copy

Outbound messages address a person directly at a specific moment — the tone differs from question text and end-of-flow screens.

- **Invitations** — warm, brief, specific about *why* the recipient is being asked. Avoid corporate boilerplate openings ("We are pleased to announce…"). Lead with the ask, explain the relevance in a sentence, mention time-to-complete, end with a clear call to action.
- **Reminders** — short. The recipient already saw the invitation; do not repeat the full pitch. A single-paragraph nudge with the link.
- **Thanks** — short and genuine. Acknowledge their time, mention what happens next if relevant, no upsells.
- **Notifications** — match the purpose. A "survey closes tomorrow" notice is short and direct; a "results are now available" notice may include a brief next-step.
- **SMS** — drastically shorter than the email equivalent. One sentence, the link, a sign-off. No subject, no formal greeting beyond "Hi #FirstName#".

Always include `#FirstName#` in the greeting if the audience has first-name data. Always include opt-out language in email footers. Match the survey's overall formality.

## Common mistakes

- **Confusing `messages` with `surveyMessages`.** `messages` is outbound; `surveyMessages` is end-of-flow screens. They sit at the same level in the JSON but solve different problems.
- **Missing `#DsLink#`.** Every email's `linkLabel` button needs `#DsLink#` as the destination, and every SMS body needs `#DsLink#` literally in the text. Without it, the recipient cannot open the survey.
- **Missing recipient field.** Including an email message without an `Email` system question, or an SMS message without a `Phone` system question — the platform has no address to send to. Validator catches this.
- **Phone numbers in local format.** `0701234567` will not send — the platform requires international `+CC...` format (e.g. `+46701234567`). Always use the `+`-prefixed form in participant data.
- **Merge field without a `system` question.** Using `#FirstName#` requires a `type: "system"` question whose id or text matches. The validator catches this.
- **Using a reserved token unnecessarily.** `#OptOutUrl#`, `#DSPwd#`, `#DSPwdNum#` are built into every message automatically. You almost never need to type them.
- **Encoding "not yet completed" in a `condition`.** Don't. `sendType: "reminder"` does that automatically.
- **Encoding "has completed" in a `condition`.** Don't. `sendType: "thanks"` does that automatically.
- **Using arithmetic or comparisons in a message condition.** Not supported. Only `{Q}:{A}` atoms with `AND`/`OR`/parentheses.
- **SMS-specific fields on an email message, or vice versa.** Each `messageType` has its own field set. The validator rejects mixing.
