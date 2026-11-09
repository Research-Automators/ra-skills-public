# Task 5 — Generate invitation messages

The user wants outbound email and/or SMS messages for a survey — invitations, reminders, thank-yous, or notifications. This is a separate task from authoring the survey itself; it produces the top-level `messages` array.

Trigger words: "invitation email", "send-out email", "SMS reminder", "thank-you email", "notification", "draft an invite", "invitation copy", or any combination of these. If the user just says "messages" without context, ask whether they mean outbound invitations (this task) or end-of-flow screens (`messages.md` / `surveyMessages`).

**Read `references/invitations.md` before drafting.** It is the full reference for the `messages` array shape, merge fields, and conditions.

## Task-specific rules

- **Read `references/invitations.md` first.** It covers fields, send types, merge fields, conditions, and copy guidance.
- **The output JSON is `messages`-focused.** At minimum it contains:
  - a `questions` array with the `system` questions referenced by merge fields (commonly `First Name`, `Email`, `Phone`) and any `category` questions referenced by conditions
  - the `messages` array
- **Do not generate `responses`.** Invitation work is pre-fieldwork. Omit `responses` entirely.
- **Do not generate `surveyMessages`** unless the user explicitly asked for end-of-flow copy as well. They are unrelated.
- **Standalone vs combined import.** Both are valid:
  - *Standalone*: just `questions` (system/category only) + `messages`. Use this when the user already has the survey in the platform and only wants to add send-out copy.
  - *Combined*: full survey (`questions` with real survey items) + `messages`. Use this when the user asked for both in one go — typically after Task 1 or Task 2.
- **Default message set.** If the user says "create invitation messages" without specifying which, default to **one email invitation + one email reminder**. Add an SMS reminder gated on `acceptsSMS` only if the user mentions SMS, or if a phone-equipped audience is implied (e.g. field staff, customers). Add a `thanks` message only if explicitly requested.
- **Always include `#FirstName#` in the greeting** when the audience has first-name data (almost always). Email greetings go in `title`; SMS greetings open `body`.
- **Always include `#DsLink#`.** In emails it's implicit in the `linkLabel` button — you do not type it, but a `linkLabel` is mandatory. In SMS the token must appear literally in `body`.
- **Email footers carry opt-out language.** Provide `footer` + `optOutLabel` on every email invitation and reminder. Thank-yous and notifications may omit them if not promotional.
- **Match the survey's tone.** If you have access to the survey itself, mirror its formality. Otherwise default to warm-professional.

## When merge fields require new system questions

If your message uses `#FirstName#` and the user's survey doesn't already include a `type: "system"` question for first name, add it:

```json
{ "id": "First Name", "type": "system", "text": "First Name" }
```

Same for `Email`, `Phone`, `Last Name`. These are standard system fields the platform recognises.

## Recipient routing (read this — it's not configurable)

The platform picks the recipient address from a hard-coded system field per channel:

- **Email messages** → sent to the participant's `Email` system field
- **SMS messages** → sent to the participant's `Phone` system field

There is no per-message "to" field. Consequences for the output JSON:

- **Any email message means an `Email` system question is required** in the `questions` array. Add it if it doesn't exist.
- **Any SMS message means a `Phone` system question is required** in the `questions` array. Add it if it doesn't exist.
- The validator enforces both.

### Phone numbers

`Phone` values must be in international `+CC...` format, or SMS won't be delivered. See "Phone number format" in `references/invitations.md` for the rule and country prefixes, and mention it to the user when they're preparing real participant data for a file with SMS messages.

## SMS reminder pattern

A common request is "send an SMS reminder to those who opted in to SMS". The shape:

1. Add a `category` question for the opt-in flag if it doesn't exist:
   ```json
   {
     "id": "acceptsSMS",
     "type": "category",
     "text": "Accepts SMS",
     "answers": [ { "id": "1", "text": "Yes" } ]
   }
   ```
2. Add an SMS message with `sendType: "reminder"` and a `condition` referencing it:
   ```json
   "condition": { "label": "Accepts SMS", "definition": "{acceptsSMS}:{1}" }
   ```

The `sendType: "reminder"` already filters to participants who have not completed — the condition just adds the SMS-opt-in filter on top.

## Send-type quick reference

| `sendType` | Auto-filtered to | Typical use |
|---|---|---|
| `invitation` | All eligible participants | First send |
| `reminder` | Participants sent an invitation AND not yet completed | Nudge non-responders |
| `thanks` | Participants who completed | Post-completion thank-you |
| `notification` | No automatic filter | Ad-hoc broadcasts ("survey closes tomorrow") |

Do not encode "not completed" or "completed" in a `condition` — let the `sendType` do that.

## Output

Write, validate and deliver the file following the steps in "Output, validation and delivery" in SKILL.md. Suggested names: `<survey-name>-messages.json`, or `invitation-messages.json` for standalone work. The validator checks message field requirements, merge field references and condition syntax. Summarise briefly: number of messages by `sendType` + `messageType`, any conditions applied, and one line on how to import.

## Import instructions

For standalone messages imports, the user uploads the JSON via Survey Automator's import flow on the **existing** project (Distribute tab → import messages). For combined survey+messages imports, the standard new-project import works — both the survey and the messages come in together.

## Key order in the output JSON

Recommended order: `questions` first, then `messages`. If by some combination `responses` is included, it must still be the last top-level key — the validator enforces this.
