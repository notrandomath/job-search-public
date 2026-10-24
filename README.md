# Job Search Skill

A job-search counselor skill. It reads your resume, asks what you want, and produces a verified job list and, if you ask, a short advice report.

Needs an agent that supports skills and can run Python 3 with web access.
## Load it

**Google Antigravity CLI (Free):** copy `job-search/` to `<project>/.agent/skills/` (or `~/.gemini/antigravity/skills/`).

**Codex (Free):** copy `job-search/` to `~/.codex/skills/`.

**Claude Code:** copy `job-search/` to `~/.claude/skills/`.

**Claude, claude.ai web (Free):** Settings → Capabilities → turn on *Code execution and file creation*. Then Customize → Skills → upload `job-search.zip`. Its sandbox often has no network access, which limits the search.

**Cursor:** copy `job-search/` to `.cursor/skills/` (or `~/.cursor/skills/`).

**GitHub Copilot in VS Code:** copy `job-search/` to `.github/skills/` (or `~/.copilot/skills/`), use agent mode.

Then say: "find me jobs" and attach your resume.

## Low on tokens

Choose **lite** when the skill asks for search depth: it uses far fewer tool calls and sources. Terminal agents (Antigravity CLI, Codex, Claude Code) fetch job boards more reliably than the web chat apps because they have direct network access.

## Not supported

**ChatGPT web:** no skill support on personal plans (skills are limited to Business, Enterprise and Edu workspaces).

**Gemini web:** supports skills, but scripts that need internet access can't run, and this skill relies on them.
