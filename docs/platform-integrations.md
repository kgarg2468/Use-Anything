# Platform Integrations

Use-Anything now integrates with Codex as a native skill (`$use-anything`), not a slash prompt command.

## Prerequisite: Global CLI Install

Install `use-anything` globally first so commands work from any directory.

```bash
# from this repository root
uv tool install --from . use-anything
```

Verify:

```bash
use-anything --help
```

## Codex Skill

Install option 1 (Codex-native via skill installer):

```text
$skill-installer install https://github.com/kgarg2468/Use-Anything/tree/main/skills/use-anything
```

Install option 2 (shell):

```bash
bash /path/to/Use-Anything/scripts/install_use_anything.sh
```

Both install to `$CODEX_HOME/skills/use-anything` (defaults to `~/.codex/skills/use-anything`).

Invoke in Codex with:

```text
$use-anything
```

Restart Codex after install so new skills are discovered.

## Claude Code Project Command

Install project-local command files in your current project:

```bash
bash /path/to/Use-Anything/scripts/install_claude_project_command.sh
```

Installed command files:
- `.claude/commands/use-anything.md`
- `.claude/commands/useantyhig.md` (alias)

Invoke in Claude Code with:
- `/use-anything <target>`
- `/useantyhig <target>`

Restart Claude Code in that project after install.

## Legacy Prompt Cleanup

`install_use_anything.sh` removes legacy prompt-command files for Use-Anything:

- `~/.codex/prompts/use-anything.md`
- `~/.claude/commands/use-anything.md`
- `~/.config/opencode/commands/use-anything.md`

## Update Flow

Repo-based install:

```bash
git pull
uv tool install --force --from . use-anything
bash ./scripts/install_use_anything.sh
```

Release-based install:

```bash
uv tool upgrade use-anything
bash ./scripts/install_use_anything.sh
```

## Integration Tests

```bash
uv run pytest -q tests/integrations/test_install_use_anything.py tests/integrations/test_skill_package.py
```
