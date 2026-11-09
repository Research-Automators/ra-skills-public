# Survey Automator skill for AI assistants

Let your AI assistant build surveys for [Survey Automator](https://app.researchautomators.com). Describe the survey you want, or give it a questionnaire (Word, PDF or text), and it creates a file you import into Survey Automator. It can also update an existing survey, create example responses for testing, and write invitation emails.

It works in **Claude**, **ChatGPT** and other AI assistants that support skills.

## Download

| You use | Download this file |
|---|---|
| **Claude** (claude.ai or the Claude app) | [⬇ survey-automator.skill](https://github.com/Research-Automators/ra-skills-public/releases/latest/download/survey-automator.skill) |
| **ChatGPT** or another AI assistant | [⬇ survey-automator.zip](https://github.com/Research-Automators/ra-skills-public/releases/latest/download/survey-automator.zip) |

Clicking a link downloads the latest version. You don't need a GitHub account.

## Add it to your assistant

**Claude**
1. Open [claude.ai](https://claude.ai) or the Claude app.
2. Go to **Customize → Skills**.
3. Upload `survey-automator.skill`.

**ChatGPT**: add `survey-automator.zip` as a skill in ChatGPT.

**Claude Code** (for developers): run
```
/plugin marketplace add Research-Automators/ra-skills-public
/plugin install survey-automator@research-automators
```

**Other AI assistants with skills support**: unpack `survey-automator.zip` into the assistant's skills folder.

## Try it

Start a new chat and ask, for example:

> *Create a customer satisfaction survey with 10 questions.*

The assistant gives you a JSON file. In [Survey Automator](https://app.researchautomators.com), create a **New (empty) project**, then choose **Import survey → From JSON** and pick the file.

When a new version comes out, download the file again and upload it the same way.

Older versions and what changed in each are on the [releases page](https://github.com/Research-Automators/ra-skills-public/releases).

## Licence

Free to use **with Survey Automator only**. See [LICENSE](LICENSE).

---

## For maintainers

- One folder per skill, with `SKILL.md`, `references/`, `scripts/` and, for ChatGPT's icon and name, `agents/openai.yaml`. The `plugins/…` path and `.claude-plugin/` exist so that Claude Code can install from this repository. Other platforms use only the skill folder ([survey-automator](plugins/survey-automator/skills/survey-automator/SKILL.md)).
- Shipped files must work on every platform. Platform paths and tool names go only in SKILL.md's "Output, validation and delivery" section, and scripts use only the Python standard library.
- `scripts/package.sh [--dev] [name]` checks each skill and builds `dist/<name>.skill` and `dist/<name>.zip`. It checks the frontmatter, the description length, the version, portability and `agents/openai.yaml`. `--dev` builds a separately installable `<name>-dev` test copy.
- Release: merge to `main`, run `scripts/package.sh <name>`, and create the GitHub release `<name>-<version>` with **both** files attached, keeping their names as they are. The download links above point to the latest release's files with those names.
