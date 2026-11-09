# Survey Automator skill

Your AI assistant builds and updates [Survey Automator](https://app.researchautomators.com) surveys.

Works in Claude, ChatGPT and other assistants with skills.

## Download

- **Claude:** [⬇ survey-automator.skill](https://github.com/Research-Automators/ra-skills-public/releases/latest/download/survey-automator.skill)
- **ChatGPT and others:** [⬇ survey-automator.zip](https://github.com/Research-Automators/ra-skills-public/releases/latest/download/survey-automator.zip)

## Install

**Easiest:** drag the file into a chat and write:

> Add this skill please.

Or per assistant:

- **Claude:** Customize → Skills → upload the .skill file.
- **ChatGPT:** add the .zip file as a skill.
- **Claude Code:**

```
/plugin marketplace add Research-Automators/ra-skills-public
/plugin install survey-automator@research-automators
```

## What you can ask

> Create a customer satisfaction survey with 10 questions.

> Turn this Word questionnaire into a survey. *(attach the file)*

> Add 50 example responses to this survey. *(attach the survey JSON)*

> Group age into 18–34, 35–54 and 55+.

> Write an invitation email and a reminder SMS.

> Fix the typo in question 3 and add a "Don't know" option. *(attach the survey export)*

## Import into Survey Automator

1. Open or create a project.
2. Choose **Import survey → From JSON**.
3. Pick the file the assistant made.

## Update the skill

1. Download the file again.
2. Drag it into a chat and write: *Update this skill please.*
3. Start a new chat and ask: *Which survey-automator version do you have?*

## Licence

For use with Survey Automator only. See [LICENSE](LICENSE).

---

**Maintainers:** `scripts/package.sh [--dev] [name]` checks each skill and builds `dist/<name>.skill` and an identical `.zip`. Release as `<name>-<version>` with both files attached, names unchanged.
