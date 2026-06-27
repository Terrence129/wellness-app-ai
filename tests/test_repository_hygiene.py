from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_has_names_but_no_secret() -> None:
    content = (ROOT / ".env.example").read_text()
    assert "DEEPSEEK_API_KEY=" in content
    assert "sk-" not in content


def test_gitignore_excludes_local_and_generated_files() -> None:
    content = (ROOT / ".gitignore").read_text().splitlines()
    required_entries = (
        ".env",
        ".DS_Store",
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".coverage",
        "htmlcov/",
    )
    for required in required_entries:
        assert required in content
