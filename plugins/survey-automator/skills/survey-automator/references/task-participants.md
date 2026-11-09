# Task 4 — Generate participants for a survey

The user provided (or already has) a Survey Automator JSON survey definition and is asking specifically for **participants** — pre-loaded invitees for the survey, not respondents who have answered it.

Triggers: the user uses the word "participants" — e.g. "create example participants", "generate test participants", "add 20 participants for this survey", "give me a participant invite list". If the user says "responses", "respondents", "mock data", or "test data" without saying "participants", use Task 3 (responses) instead.

## What participants are

Participants are people the survey will be sent to. They carry only background data — system metadata (name, email, phone, event date, external IDs) and category attributes (panel/CRM fields like gender, region, segment). They have **no survey answers** because the survey hasn't been answered yet.

## Output shape

Participants live in a top-level `participants` array, **separate from** `responses`. A participant file typically has `questions` + `participants` only.

```json
{
  "questions": [ ... ],
  "participants": [
    {
      "External ID": "1234",
      "First Name": "Kaiser",
      "Last Name": "Söze",
      "Email": "kaiser@usual.com",
      "Event Date": "20260127000000",
      "gender": "Man",
      "Test": "Test"
    }
  ]
}
```

See `references/participants-example.json` for a complete worked example.

## Task-specific rules

- **Do not generate `responses`.** This task produces participants only — no example responses, even if Task 1 (prompt to survey) ran first and would normally create them.
- **`responses` and `participants` are mutually exclusive.** If the input file contains a non-empty `responses` array, do **not** carry it into the output — drop it. A file represents either collected answers or an invite list, never both. Mention the drop in your chat summary so the user knows.
- **Key order in the output JSON: `participants` must be the last top-level key.** Preserve the other top-level keys from the input (e.g. `surveyMessages`, `messages`) in their original positions, and place `participants` last. The validator rejects files where `participants` is followed by any other top-level key.
- **The input `questions` array is immutable** in the same sense as Task 3. Copy it through unchanged. The only addition is the `participants` array.
  - **One exception:** if the survey doesn't already have a `Test` category question and you're generating test/example participants, you may add one (see "Flag generated participants" below). Mention it in your chat summary so the user knows.
- **Validate the input first.** Run the validator on the input file (see the steps in "Output, validation and delivery" in SKILL.md) before generating participants. If validation fails, surface the errors and stop.
- **Keys allowed in participant objects:** only ids of `system` and `category` questions. Survey-question keys (`single`, `multiple`, `open`, matrix rows, connected-Open) must not appear — the validator rejects them.
- **`system` fields:** fill these in. Unlike Task 3 (where the platform fabricates system values at response time), system fields here are *inputs* — names, emails, phone numbers, event dates, external identifiers. Generate plausible values per field name.
- **`category` fields with an `answers` array:** the value must be one of the answer ids.
- **`category` fields without `answers`:** free-text. Generate plausible values (region names, segment labels, IDs).
- **Omitting fields is fine.** Not every category needs to be present on every participant — purely administrative or rarely-populated fields can be left absent. A field is either present with a real value or absent; do not write empty strings.
- **Default count is 10** unless the user specifies otherwise.
- **Internal consistency per participant.** Treat each participant as a coherent person — name matches gender plausibly, email matches name, region matches country/business unit if both fields exist, phone country code matches region. Don't randomise fields independently.

## Flag generated participants with a Test category

So generated example/test participants are easy to identify and exclude later, tag them via a `Test` category question.

- **If the survey already has a category question whose `id` or `text` is `Test` (case-insensitive)**, use it. Pick an answer that means "test data" — typically an answer with id or text `"Test"`. If multiple plausible answers exist, ask the user which to use.
- **If no such question exists**, add one to `questions`:
  ```json
  {
    "id": "Test",
    "type": "category",
    "text": "Test",
    "answers": [
      { "id": "Test", "text": "Test" }
    ]
  }
  ```
  Then set `"Test": "Test"` on every generated participant. Mention in your chat summary that you added the `Test` category so the user knows.
- If the survey has a `Test`-like category but it lacks a sensible "test" answer value, ask the user before adding one.

## Format essentials

- **All values are strings** (same rule as responses). Numeric IDs, dates, phone numbers — all quoted.
- **Date format:** match what the survey/CRM uses. The common Survey Automator convention is `YYYYMMDDHHMMSS` (e.g. `"20260127000000"` for midnight on 27 Jan 2026). If the input file already contains participants or responses with dates, mimic their format.
- **Language:** match the survey's language for any free-text values (region names, custom segments, etc.).
- **Email/phone uniqueness:** participants in the same export typically represent distinct people. Don't reuse emails or phones across participants unless the user explicitly asks for duplicates.
- **Phone numbers must be international `+CC...` format** (e.g. `+46701234567` for Sweden, `+447700900000` for UK). The platform does not auto-prefix country codes — local-format numbers like `0701234567` will fail to send if the survey has SMS messages. Match the country code to the participant's region when both are present. See `references/invitations.md` for the country-prefix reference table.
