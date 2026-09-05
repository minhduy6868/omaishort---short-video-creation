# omaishort agent notes

Read [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md), [docs/RESEARCH.md](docs/RESEARCH.md), and [docs/ROADMAP.md](docs/ROADMAP.md) before changing the pipeline.

Rules live in `.cursor/rules/`. Skills live in `.cursor/skills/`.

When the user asks to learn from MoneyPrinter, OpenMontage, HyperFrames / AI-auto-generate-video, or other video repos, use skill `source-research`. Do not clone those trees into this project. `kind=news` / `kind=knowledge` map the editorial arc; they do not vendor HyperFrames. Legacy `kind=brief` aliases to news.

- Pipeline contract: `.cursor/rules/pipeline.mdc`
- Quality bar: `.cursor/rules/quality.mdc`
- How we work: `.cursor/rules/working.mdc`
- GitHub / PRs: `.cursor/rules/github.mdc`
- CI: `.cursor/rules/cicd.mdc`

Do not fork a random story-to-video repo into this tree. Extend the engine in `apps/api/omaishort`.
