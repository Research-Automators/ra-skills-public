# Slider, drag-and-drop and ranking grids

Read this file only when the user or brief explicitly asks for a slider or drag-and-drop, when respondents should rank items, or when an existing survey uses one of these interfaces. Everything else about grids is in [Matrix questions](format-questions.md#matrix-questions) in `format-questions.md`.

| `interface` | Description |
|---|---|
| `slider` | **Grid-only, use only when explicitly asked for.** A slider per row. Two forms: a **choice slider** on a `single` grid, which slides between the answer alternatives (e.g. `1`–`10`), and a **numeric slider** on an `open` grid, which slides from `minValue` to `maxValue` of its single integer `Open` answer. See the examples below. |
| `dragdrop` | **Grid-only, `single` only, use only when explicitly asked for.** The respondent drags each row into one box per answer alternative. |
| `ranking` | **Grid-only, `single` only.** The respondent drags the rows into rank order. The answers are the rank positions, and their number decides how many rows get ranked (it can't exceed the number of rows). Use when respondents should rank items. |

**Avoid `slider` and `dragdrop` unless the user or brief explicitly asks for them** — `buttons`, `vertical` or the default rendering are better choices for normal grids.

The format also accepts two grid legends, `alpha` and `numeric`. They give an automatic `A, B, C…` or `1, 2, 3…` legend on the answer alternatives — the same result as setting `symbolText` to `"A"`, `"B"`, `"C"` or `"1"`, `"2"`, `"3"`. They are listed here only so existing files can be read and validated; don't choose them when authoring — use `vertical` or `buttons`.

## Examples

All of them are valid only on questions with `rows`.

**Choice slider** — a `single` grid with `interface: "slider"`. Each row gets a slider over the answer alternatives. Anchored-scale rules apply as usual (`scaleLeft`/`scaleRight`, answer texts ≤2 characters, `scale: "Ordinal"`).

```json
{
  "id": "ChoiceSlider",
  "type": "single",
  "text": "Rate each area",
  "rows": [
    { "id": "ChoiceSlider.1", "text": "Service" },
    { "id": "ChoiceSlider.2", "text": "Price" }
  ],
  "scale": "Ordinal",
  "interface": "slider",
  "scaleLeft": "Very poor",
  "scaleRight": "Excellent",
  "answers": [
    { "id": "1", "text": "1" },
    { "id": "2", "text": "2" },
    { "id": "3", "text": "3" },
    { "id": "4", "text": "4" },
    { "id": "5", "text": "5" }
  ]
}
```

**Numeric slider** — an `open` grid with `interface: "slider"` and exactly one `Open` answer with `dataType: "integer"`, `minValue` and `maxValue` (the slider's ends). Each row stores the chosen number. As in every [open grid](format-questions.md#open-grids), the Open answer has id `"1"`.

```json
{
  "id": "NumericSlider",
  "type": "open",
  "text": "Grid with sliders",
  "rows": [
    { "id": "NumericSlider.1", "text": "Statement A" },
    { "id": "NumericSlider.2", "text": "Statement B" }
  ],
  "max": 1,
  "scale": "Ordinal",
  "interface": "slider",
  "scaleLeft": "Don't agree",
  "scaleRight": "Agree",
  "answers": [
    { "id": "1", "type": "Open", "dataType": "integer", "minValue": "0", "maxValue": "100" }
  ]
}
```

**Drag and drop** — a `single` grid with `interface: "dragdrop"`. Each answer alternative is a box; the respondent drags each row into one box.

```json
{
  "id": "Sort",
  "type": "single",
  "text": "Sort the features",
  "rows": [
    { "id": "Sort.1", "text": "Dark mode" },
    { "id": "Sort.2", "text": "Offline sync" }
  ],
  "interface": "dragdrop",
  "answers": [
    { "id": "1", "text": "Must have" },
    { "id": "2", "text": "Nice to have" },
    { "id": "3", "text": "Not needed" }
  ]
}
```

**Ranking** — a `single` grid with `interface: "ranking"`. The respondent drags the rows into order. The answers are the rank positions: three answers means the top three rows get ranked. There may not be more answers than rows, and each rank goes to one row only.

```json
{
  "id": "Q108",
  "type": "single",
  "text": "Using a grid as a drag and drop ranking list",
  "rows": [
    { "id": "Q108.1", "text": "Price" },
    { "id": "Q108.2", "text": "Quality" },
    { "id": "Q108.3", "text": "Delivery time" },
    { "id": "Q108.4", "text": "Support" }
  ],
  "interface": "ranking",
  "answers": [
    { "id": "1", "text": "Ranked 1" },
    { "id": "2", "text": "Ranked 2" },
    { "id": "3", "text": "Ranked 3" }
  ]
}
```

## Responses

| Grid | Value per row | Example |
|---|---|---|
| Numeric slider | The chosen number as a string, within `minValue`–`maxValue` | `"NumericSlider.1": "64"` |
| Ranking | The rank position's answer `id`; each rank used once, unranked rows absent | `"Q108.2": "1"` |
| Choice slider, drag and drop | The selected answer `id`, as in any single-select grid | `"Sort.1": "2"` |
