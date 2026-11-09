# Task 1 — Prompt to survey

The user described a survey in natural language and wants you to draft it. This is the most common task and the default when no other signals apply.

## Task-specific rules

- **Always open with an intro header.** Create a `header` item whose `text` is the survey name and whose `comment` is a one-to-three-sentence introduction. This intro header does NOT get `pagebreak: true` — it's already at the top. **Do not place another `header` directly after the intro header** — put at least one real question between them.
- **Always organize the survey into sections** using additional `header` items with `pagebreak: true`. Even short surveys benefit from at least one section header beyond the intro.
- **Always populate both `text` and `surveyText`** on every non-header question. `text` is the short reporting label (e.g. "Tenure"); `surveyText` is the full sentence shown to respondents (e.g. "How long have you worked here?"). Do not omit either.
- **Always generate 20 example responses** unless the user says otherwise and do not generate responses if user asks for participants.
- **Key order in the output JSON: `responses` must be the last top-level key.** Put `questions` first, then `surveyMessages`, then `responses` last. The validator rejects files where `responses` is followed by any other top-level key.
- **Always include a `surveyComplete` message.** Every prompt-driven survey gets a top-level `surveyMessages.surveyComplete` block with `header` (a short phrase of 3–6 words), `body` (one or two sentences: warm thanks and that the response was saved) and `footer` (one short closing line, e.g. "You may now close this window"). Match the survey's tone (formal vs. casual). Omit `redirectURL` unless the user asked for a redirect. Do not set the other four message keys (`screenedOut`, `invalidPassword`, `alreadyCompleted`, `surveyClosed`) for prompt-driven surveys — they default to platform copy. Read `references/messages.md` only if the user asks for other end-of-flow screens or a redirect.
  ```json
  "surveyMessages": {
    "surveyComplete": {
      "header": "Thank you for your answers!",
      "body": "Your response has been saved. We appreciate you taking the time to share your views.",
      "footer": "You may now close this window."
    }
  }
  ```
- **Flow control.** If the user's prompt mentions screening respondents out, exit criteria, blocking inconsistent answers, or validation errors between questions, read `references/flow-control.md` before drafting — these are implemented as `screenout` and `error` items, and respondents that would be screened out should not appear in the generated example responses.

## Authoring questions

Read `references/format-core.md` and `references/format-questions.md` for the full spec. The high-leverage points:

- **Question types** are `single`, `multiple`, `open`, `header`. **There is no `type: "matrix"`.** Matrices are `type: "single"` with a `rows` array — see the `Aspects` question in `references/example.json`.
- **Stable, meaningful `id`s** in PascalCase or short descriptive strings (`Gender`, `Aspects`, `NPS`), not numeric indices. The id is the response key.
- **Answer `id`s** are numeric strings starting from `"1"` for closed questions; `"0"` is used for open input definitions — except in open grids (with `rows`), where the single Open answer is `"1"`.
- **Single vs multiple:** `single` for exactly-one, `multiple` for one-or-more. Unless the user says otherwise, set `min: 1` on every question except open comment fields. On `multiple`, set `max` only for a real limit ("select up to 3" → `max: 3`); for no limit leave `max` out — never set it to the number of answers.
- **Open questions** have one `answers` entry with `type: "Open"`. Use `dataType: "integer"` for numeric-only input. Give every open-ended question a relevant `placeholder`, and always choose an appropriate `charWidth` and `charHeight` for the question.
- **Matrices** share one `answers` scale across multiple `rows`. Row ids MUST be `<QuestionId>.<N>` (e.g. `Aspects.1`). For a single standalone scale (one Likert with no sub-items), still model it as a matrix with one anonymous row whose `id` is `<QuestionId>.1` and no `text` field — see the `Fulfilled` question in the example.
- **`scale: "Ordinal"` whenever the answers have an order.** Any scaled question or grid whose answer options form an ordered sequence — numeric rating points (0–10, 1–5), agreement (Strongly disagree → Strongly agree), satisfaction, frequency (Never → Always), likelihood, and similar — MUST set `scale: "Ordinal"` (capital O). This applies regardless of whether polarity anchors (`scaleLeft`/`scaleRight`) are used. Omit `scale` only when the options are genuinely unordered categories (e.g. a list of brands, regions, transport modes). The validator enforces this whenever answers carry `Positive`/`Negative` tags.
- **Scale anchors:** tag low-end answers with `type: "Negative"`, high-end with `type: "Positive"`, "don't know"/"N/A" with `type: "DontKnow"`. Middle answers stay untyped. On every Likert-style question — anchored or descriptively labelled — give each answer a numeric `symbolText` (`"1"`, `"2"`, …; `"?"` for DontKnow) so compact renderings work. **Use `scaleLeft`/`scaleRight` (and `scaleDK`) whenever the scale has two polarities** — i.e. answer options are points on a spectrum between a low and a high anchor (the standard, preferred Likert pattern). **Omit them when each option already carries its own descriptive label** (e.g. "Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree") — the labels do the anchoring themselves.
- **"Other / please specify"**: add an answer with `type: "Other"`, then an answer with `type: "Open"`, `id: "0"` and `connectedTo: "<id-of-the-Other-answer>"`, listed first in `answers`. The free-text response is keyed `<QuestionId>.<TriggerAnswerId>`. See the `Important` question in the example.
- **`DontKnow` on closed lists**: not just for scales — add a `type: "DontKnow"` option to any single/multiple question where opting out is meaningful. On scale questions that use `symbolText` on other answers, the `DontKnow` answer takes `symbolText: "?"`; on polarity scales (those using `scaleLeft`/`scaleRight`) the `text` is also `"?"`. On non-scale closed lists, use a readable `text` like `"Don't know"` or `"Not sure"` with no `symbolText`.
- **`randomAnswers: true`** on opinion/preference lists where order bias matters. Not on scales or ordered sequences.
- **`excluded: true`** marks a question as hidden from respondents or calculated — data still appears in responses but the question is omitted from standard exports.
- **Calculated variables** (derived, grouped or recoded variables, coded open ends, period or category breakdowns) are added only when the user asks for them. Then read `calculated-variables.md` and write the short forms shown there.
- **Rich texts**: plain strings with `<b>`/`<i>`/`<u>`/`<a href>`/`<ul><li>` and bookmarks are covered in `format-questions.md`. Read `texts.md` only when a text needs a picture, video, document link, conditional text, the typed text of an open answer, or HTML code.
- **`interface`** controls how options are rendered. Absent interface means default radios or checkboxes — the right choice when no other rule applies. Use `"buttons"` whenever *all* answer labels are short, including on single-select grids with ≤5 options — and in particular always use `"buttons"` when every label is under 15 characters and there are 6 or fewer answers. Use `"dropdown"` for long ordered single-select lists (~30+). Use `"vertical"` on grids when any answer label is long. For polarity Likert grids, use `scaleLeft`/`scaleRight`/`scaleDK` and absent interface. When you use `"dropdown"`, always add a relevant question-level `placeholder` for the empty state (e.g. `"Select a country…"`, `"Choose your region…"`) — phrase it to match what the list contains. **Use `slider` or `dragdrop` only when the user or brief explicitly asks for a slider or drag-and-drop**; use `ranking` (a `single` grid whose answers are the rank positions) when respondents should rank items. Never choose `alpha` or `numeric` — use `vertical` or `buttons`. Before writing any of these, read `grid-interfaces.md`.
- **Headers**: `id`, `type`, `text`, optionally `comment` and `pagebreak`. No `answers`, no `rows`. Standard idiom is `pagebreak: true` on every section header *except the first*.

When in doubt about idiom, **mimic `references/example.json`** rather than reasoning from these prose rules. The example demonstrates most patterns concretely.

## Generating responses

Read `references/response-generation.md` and `references/format-data.md`, and follow them for the example responses. Prompt-task specifics: generate 20 responses unless the user says otherwise, none when the user asks for participants, and don't add `system` questions such as `EndTime` unless the user asks for responses spread over time (then follow the `EndTime` rule in `task-responses.md`).
