# Survey Automator skills for Claude

Claude skills from [Research Automators](https://www.researchautomators.com) for working with [Survey Automator](https://app.researchautomators.com).

| Skill | What it does |
|---|---|
| [survey-automator](plugins/survey-automator/skills/survey-automator/SKILL.md) | Builds surveys in the Survey Automator JSON import format from a prompt or a survey brief (Word, PDF, text), generates realistic example responses and participants, adds calculated variables and writes invitation messages. |

## Install

**Claude Code**

```
/plugin marketplace add Research-Automators/ra-skills-public
/plugin install survey-automator@research-automators
```

**Claude.ai / Claude Desktop**

Download `survey-automator.skill` from [Releases](../../releases) and upload it under **Customize → Skills**.

Then ask Claude something like *"Create a customer satisfaction survey with 10 questions"* and import the JSON file into Survey Automator.

## Licence

Free to use **with Survey Automator only**. See [LICENSE](LICENSE).
