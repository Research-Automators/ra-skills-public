# Survey Automator skill

Your AI assistant builds and updates [Survey Automator](https://app.researchautomators.com) surveys. Works in Claude, ChatGPT and other assistants with skills.

## Download

| Claude | [⬇ survey-automator.skill](https://github.com/Research-Automators/ra-skills-public/releases/latest/download/survey-automator.skill) |
|---|---|
| **ChatGPT and others** | [⬇ survey-automator.zip](https://github.com/Research-Automators/ra-skills-public/releases/latest/download/survey-automator.zip) |

## Install

Drag the file into a chat and write *"Add this skill please."*

Or: **Claude** → Customize → Skills → upload. **ChatGPT** → add the .zip as a skill. **Claude Code** → `/plugin marketplace add Research-Automators/ra-skills-public`, then `/plugin install survey-automator@research-automators`.

## Use

Ask *"Create a customer satisfaction survey with 10 questions."* Import the JSON in Survey Automator: **New (empty) project → Import survey → From JSON**.

## Update

Download again, drag into a chat: *"Update this skill please."* Replace the old one, start a new chat, ask *"Which survey-automator version do you have?"*

## Licence

Survey Automator use only. See [LICENSE](LICENSE).

---

**Maintainers:** `scripts/package.sh [--dev] [name]` checks each skill and builds `dist/<name>.skill` + identical `.zip`. Shipped files must work on every platform. Release `<name>-<version>` on GitHub with both files, names unchanged.
