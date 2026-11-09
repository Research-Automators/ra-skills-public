# Survey Automator skills

AI skills from [Research Automators](https://www.researchautomators.com) for working with [Survey Automator](https://app.researchautomators.com). They follow the open [Agent Skills](https://agentskills.io) format, so they work in Claude, ChatGPT and other assistants that support skills.

| Skill | What it does |
|---|---|
| [survey-automator](plugins/survey-automator/skills/survey-automator/SKILL.md) | Builds surveys in the Survey Automator JSON import format from a prompt or a survey brief (Word, PDF, text), updates existing surveys, generates realistic example responses and participants, adds calculated variables and writes invitation messages. |

## Install

Every [release](../../releases) has the same skill in two files: `survey-automator.skill` for Claude, and `survey-automator.zip` for ChatGPT and other platforms. The two files are identical except for their names.

**Claude (claude.ai, Claude Desktop)**: download `survey-automator.skill` and upload it under **Customize → Skills**.

**Claude Code**

```
/plugin marketplace add Research-Automators/ra-skills-public
/plugin install survey-automator@research-automators
```

**ChatGPT**: download `survey-automator.zip` and add it as a skill in ChatGPT.

**Other assistants with Agent Skills support**: unzip `survey-automator.zip` into the assistant's skills folder. The skill is the `survey-automator` folder with `SKILL.md` at its top.

Then ask something like *"Create a customer satisfaction survey with 10 questions"*, and import the JSON file into Survey Automator.

## For maintainers

- One folder per skill, with `SKILL.md`, `references/`, `scripts/` and, for ChatGPT's icon and name, `agents/openai.yaml`. The `plugins/…` path and `.claude-plugin/` exist so that Claude Code can install from this repository. Other platforms use only the skill folder.
- Shipped files must work on every platform. Platform paths and tool names go only in SKILL.md's "Output, validation and delivery" section, and scripts use only the Python standard library.
- `scripts/package.sh [--dev] [name]` checks each skill and builds `dist/<name>.skill` and `dist/<name>.zip`. It checks the frontmatter, the description length, the version, portability and `agents/openai.yaml`. `--dev` builds a separately installable `<name>-dev` test copy.
- Release: merge to `main`, run `scripts/package.sh <name>`, and create the GitHub release `<name>-<version>` with both files attached.

## Licence

Free to use **with Survey Automator only**. See [LICENSE](LICENSE).
