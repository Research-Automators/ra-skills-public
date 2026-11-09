# Texts — tokens, media, the object form and HTML

Read this file only when a text needs more than plain wording, the formatting tags and a bookmark: the typed text of an open answer, category values, pictures/videos/sound/links, conditional text, sized media, or raw HTML. The basics (plain strings, allowed tags, `\n`, bookmarks and their page-break rule) are in [Texts](format-questions.md#texts) in `format-questions.md`.

## Tokens

| Token | Shows |
|---|---|
| `{Q2}` | The answer(s) the respondent gave to question `Q2` — a **bookmark**, see [Bookmarks](format-questions.md#bookmarks-in-text-piping) in `format-questions.md`. |
| `{Aspects.1}` | The same for a grid row (its row id). |
| `{Comments:3}` | The text typed into the `Open` answer with id `3` of `Comments` (a `multiple` question with several open inputs). |
| `{Comments:0}` | The text typed into the question's own open answer (the `Open` answer with id `0`) — also the "please specify" text of an `Other` option, e.g. `{Fruit:0}`. |
| `{First Name}`, `{Email}`, … | Participant data. Write the token as the `system` question's `id`: `First Name`, `Last Name`, `Email`, `Company`, `Title`, `Department`, `Phone number`, `Country`, `data1`… |
| `{City}` | The respondent's value of a `category` question of the file (its `id`). See [Background data](format-questions.md#background-data-in-conditions-and-texts). |
| `{SPACE}`, `{EMPTY}`, `{Company name}` | Built-in fields: a space, an empty value, the company name. Rarely needed when authoring. |
| `{https://…/logo.png}` | A picture, video, sound or document link — see [Pictures, videos and links](#pictures-videos-and-links). |

An unknown name stays as literal text, braces included. The answer reference `{Q}:{3}` (both parts in braces) is a *condition atom* used in `condition.definition`, not a text token. In text, the open answer form is `{Q:3}`.

## Pictures, videos and links

Write the URL in braces: `{url}`. Add a text after `|`: `{url|text}` — the alt text of a picture, video or sound, the link text of a document or web link.

```json
"surveyText": "Which fish is this?\n{~/fish.png|A red fish}",
"comment": "Please read {https://example.com/terms.pdf|our terms} before you answer."
```

- A token is a URL when it starts with `~/`, `http://`, `https://`, `//`, `/` or `mailto:`.
- The **type comes from the file extension**: `.png .jpg .jpeg .gif .svg .webp .bmp` picture, `.mp4 .webm .mov .m4v .ogv` video, `.mp3 .wav .ogg .m4a .aac` sound, anything else (`.pdf`, `.docx`, web pages) a link.
- **`~/file name`** is a file in the project's own media library. Exported surveys write their media this way. On import it points to the media library of the project it is imported into — the file is not copied, so it must be uploaded there (the import warns about missing files). Use `~/` only for files that are, or will be, in the media library; otherwise write a full `https://` URL.
- A picture, video or sound without `|text` gets its file name (without extension) as alt text. `{url|}` means no alt text. A link without `|text` has no link text.

## Fields with settings: the object form

When a field needs settings — a size, a condition, a conditional text, or a type the extension does not show — the text becomes an object. `text` holds the text with `{key}` tokens, and `fields` defines each key:

```json
"surveyText": {
  "text": "{logo}\nThank you {First Name}!{followUp}",
  "fields": {
    "logo":     { "type": "picture", "url": "https://example.com/logo.png", "width": 120, "height": 40, "altText": "Our logo" },
    "followUp": { "type": "conditionalText", "condition": "{Contact}:{1}", "text": " We will <b>contact you</b> soon." }
  }
}
```

| `type` | Properties |
|---|---|
| `answer` | `question` (question or row id), `answer`? (id of an open answer, `"0"` = the question's own) |
| `participant` | `field` (e.g. `"First name"`) |
| `category` | `category` (the category path, e.g. `"region"`) |
| `conditionalText` | `text` (a plain string — formatting tags allowed, **no `{tokens}` or `fields`**) |
| `link` | `url`, `text`? (plain string, no `{tokens}`) |
| `picture` / `video` / `sound` | `url`, `width`?, `height`? (pixels or e.g. `"50%"`), `controls`? (video), `altText`? |
| `space` / `empty` / `companyName` | — |
| *(any type)* | `condition`? — shown only when true (same syntax as `condition.definition`, e.g. `NOT({Region}:{1})`) |

- Keys are free names. Exported files use `picture1`, `text1`, `link1`, … Don't use a question id as a key.
- A conditional text is not trimmed — start it with a space when it follows a word.
- **Fields cannot be nested.** A field's own `text` / `altText` is shown as written: a `{token}` inside it (a bookmark, participant field, URL or another field key) is **not** replaced, and a text object (`text` + `fields`) is not allowed there. Bookmarks and fields only work in the top-level `text` of a text object.

### Conditional content that contains a bookmark

To show a bookmark, picture or link only under a condition, don't put it inside a `conditionalText`. Split the content into **sibling fields that share the same condition**: the static parts become `conditionalText` fields, and the bookmark becomes an `answer` / `participant` / `category` field (or a `picture` / `link` field) with the same `condition`. Nested conditions are combined with `AND`.

Not supported (nested):

```json
"apple": { "type": "conditionalText", "condition": "{Taste}.1:{5}", "text": "you love apples ({Taste.1}/5)." }
```

Supported (flat, same result):

```json
"surveyText": {
  "text": "Apples: {loveA}{loveRating}{loveB}",
  "fields": {
    "loveA":      { "type": "conditionalText", "condition": "{Taste}.1:{5}", "text": "you love apples (" },
    "loveRating": { "type": "answer", "question": "Taste.1", "condition": "{Taste}.1:{5}" },
    "loveB":      { "type": "conditionalText", "condition": "{Taste}.1:{5}", "text": "/5)." }
  }
}
```

A condition inside a condition (outer `[Toppings] >= 2`, inner `{Visits} >= 10`) becomes one field per piece with the combined condition, e.g. `"[Toppings] >= 2 AND {Visits} >= 10"` on the inner pieces.
- Use the object form only when needed. A plain string is always preferred.

## HTML code

A text can be raw HTML instead: `{ "html": "…" }`. Use it only when the user asks for HTML or a layout the formatting tags can't make. `fields` and `{tokens}` work here too; other braces (CSS) stay as they are.

```json
"comment": { "html": "<div style=\"color:#c00\">Deadline: <b>31 May</b></div>" }
```
