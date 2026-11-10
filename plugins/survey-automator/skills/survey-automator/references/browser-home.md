# Browser mode: projects and folders (the Home tab)

Read this together with `browser-mode.md` when no project is open (`tab` is `Home`), or the request is about the user's projects ("which surveys are running?", "open the customer survey", "create a new project"). These calls work without an open project.

## Reading

- `await listProjects({ search?, status?, limit? })`: the user's projects, most recent first: `[{ id, name, folder, status, participants, started, finished, lastResponse, modified, starred }]`. `search` is part of the name, or `#id`. `status` is `setup`, `started`, `reporting` or `closed`.
- `await projectsSummary()`: how many projects are in setup, started, reporting, closed.
- `await recentProjects()`: the projects the user opened last.
- `await listFolders()`: `[{ id, name, path, canCreateProjects }]`.

**A quick update on active projects:** `listProjects({ status: "started" })`, then a few lines: name, finished responses, last response ("3 days ago"), and anything that stands out (no responses yet, no response for a week). Totals only; it's what the project cards show.

## Moving

- `await openProject(id)` opens a project, as clicking its card. Then call `overview()` (`browser-mode.md`).
- `await showHome()` shows the project list.

## A new project

`await newProject({ name, folder })`, with `folder` as an id or path from `listFolders()` where `canCreateProjects` is true.
- Ask which folder if it isn't clear: the folder decides who can see the project.
- The app opens its New project dialog, filled in. The user creates the project there, and it opens.
- If the user chose "Allow this session", your next `newProject` calls in that folder create projects directly (5 in all), each with Undo.
- Then fill the new, empty project with `createSurvey` (`browser-survey.md`).

## Suggestions

**On the Home tab, when the skill is only called:** setting up a new project; a quick update on your active projects; finding a project.

**Next steps:**

| What just happened | Offer |
|---|---|
| A new project was created | Create its survey from a description or a brief. |
| A quick update on the projects was given | Open the project that needs attention (no responses yet, a long pause). |
| A project was opened | What fits its tab (`browser-mode.md`, "Friendly, contextual suggestions"). |
