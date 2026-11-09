# Task 3 — Populate responses for existing JSON

The user provided a Survey Automator JSON file (the `questions` array is already complete) and wants synthetic responses generated for it. The JSON is generally valid since it comes from Survey Automator.

## Task-specific rules

- **The input `questions` array is immutable.** Copy it into the output unchanged. Do not edit, reorder, rename, "fix", or "improve" any question or answer — even if you spot something you'd do differently. The output's `questions` array must be byte-for-byte equivalent to the input's. The only thing that changes between input and output is `responses`.
- **Key order in the output JSON: `responses` must be the last top-level key.** Preserve the other top-level keys from the input (e.g. `surveyMessages`, `messages`) in their original positions, and place `responses` last. The validator rejects files where `responses` is followed by any other top-level key.
- **`responses` and `participants` are mutually exclusive.** If the input file contains a non-empty `participants` array, do **not** carry it into the output — drop it. A file represents either collected answers or an invite list, never both. If the user wanted both, they should keep the participants in a separate file. Mention the drop in your chat summary so the user knows.
- **Validate the input first.** Run the validator on the input file (see the steps in "Output, validation and delivery" in SKILL.md) before generating responses. If validation fails, surface the errors to the user and stop — don't build responses on a broken foundation.
- **Default to 20 responses** unless the user specifies a count.
- **If the input already contains responses**, append the new ones rather than overwriting. The new respondents should plausibly come from the same population as the existing ones (similar demographic spread, similar value ranges) but should not duplicate existing responses verbatim.
- **`system` questions: time-distributed data.** By default `system` questions get no values (see `response-generation.md`). **Exception — time-distributed data:** when the user asks for responses spread over time (e.g. "a year of responses", "monthly data for 2024", "quarterly"), set each respondent's completion time via the `EndTime` system field, formatted as 14 digits `YYYYMMDDHHMMSS` (e.g. `"20240814160018"`). Distribute the timestamps across the requested period. If an `EndTime` system question is not already in the `questions` array, add one (`{ "id": "EndTime", "type": "system", "text": "End timestamp" }`) — this is the one permitted addition to the otherwise-immutable `questions` array, and only for this purpose. A matching `StartTime` field exists but is rarely needed; only populate it if the user explicitly asks for start times.
- **`StatusText` system field**, when present, records completion status and must be one of `Completed`, `Started`, or `Screenout`. Use `Completed` for finished respondents; use `Started` for partials/dropouts and `Screenout` for screened-out respondents only if the user asks for a realistic status mix.

## Generating the responses

Read `references/response-generation.md` and follow it: personas, realism, and the key and value format of every question type. The full key and value specification is in `references/format-data.md`; `references/format-core.md` covers key order and calculated variables. You don't need `format-questions.md` unless the input's question shapes are unclear.
