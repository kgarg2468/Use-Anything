.PHONY: clean-workspace check-hygiene

clean-workspace:
	bash scripts/clean_workspace.sh

check-hygiene:
	uv run python scripts/check_repo_hygiene.py
