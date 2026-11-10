# Browser mode: analysis and the Dashboard

Read this together with `browser-mode.md` when the request asks about the results ("which groups differ?", "how is energy by work mode?"), segments, or the Dashboard. Everything here is read only, except saving a segment (an update) and refreshing the Dashboard.

## Crosstabs

Sync first if `overview().freshness.waitingToSync` is above 0 (`browser-data.md`).

- `listVariables()` lists the reportable variables: questions, grid rows and calculated variables, with their answers.
- `await crosstab({ variables: [...], by, filter?, compact: true })`: one table per variable, with the same columns (the total, then one per answer of `by`), in one call (at most 20 variables).
  - Compact output: `{ columns: [{ id, label }], tables: [{ variable, text, base: [per column], rows: [[id, label, percent per column]] }] }`.
  - Without `compact` you get counts too; `variable` instead of `variables` gives one table.
  - `filter` is `{ variable, answers: [...], not? }` (or an array of them, all must match). `by` and filters must be single or multiple choice.
  - A column with fewer than 5 responses has `null` for its base and percents: report it as "too few responses", never guess its numbers, and don't narrow filters to get around it.

## Finding segments

Work like an analyst, with few calls:

1. **Start from a question**, the user's or the survey's main outcome (satisfaction, energy, intention to stay). Plan the tables before you call anything.
2. **Cross outcomes by explanations only**: the outcome questions as `variables`, one background or explanatory variable as `by` (role, work mode, region, age group). Batch them: one call per `by`, not one per pair.
3. **Judge a difference against its margin of error**, not against a fixed n. For two percentages p1 and p2 with bases n1 and n2, the difference is clear when it exceeds about 2 × √(p1(1−p1)/n1 + p2(1−p2)/n2). The suppression rule (fewer than 5) is only the floor. The more tables you look at, the stricter you should be: with 20 comparisons, one will look clear by chance.
4. **Look for consistency**: a segment that differs on several related questions is more convincing than one big difference.
5. **A predefined segment is an idea until tested.** If a group the user asks about is too small, say "too small to tell", not "no difference".
6. **Save a segment worth following** as a calculated variable hidden from respondents: a report update (`{ scope: "report" }`, `excluded: true`, see "From the report" in `browser-survey.md` and `calculated-variables.md`). The user reviews and applies it; then `crosstab` and the Dashboard can use it.
7. **Report** each finding with its base (n), the size of the difference, and a caveat when the base is small or the comparison is one of many.

## The Dashboard

- `reportStatus()`: `{ running, report: { id, name, created }, newResponsesForReport }`.
- `dashboard()`: the open report's pages `[{ id, name, type, variables }]`.
- `await refreshReport()` (Dashboard tab): creates the dashboard, or syncs the responses and updates it. It asks like `syncResponses` and returns a handle; `result(handle, { timeoutMs: 60000 })` says `done` when the report is ready. At most once a minute.
- `await openDashboardEdit()` opens Edit on the Dashboard for the user.

## Suggestions

**On the Dashboard or Report tab, when the skill is only called:** finding interesting differences between groups; saving a segment as a report variable; updating the dashboard with the latest responses.

**Next steps:**

| What just happened | Offer |
|---|---|
| A crosstab or segment search found something | Save the segment as a report variable. The same groups on related questions. |
| A segment was saved as a report variable | Update the Dashboard so it shows it (`refreshReport`). |
| The Dashboard was refreshed | The main differences in a few lines. |
