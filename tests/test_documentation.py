"""Documentation contract tests for repository operators and contributors."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_required_document(name: str) -> str:
    path = ROOT / name
    assert path.is_file(), f"{name} must exist at the repository root"
    return path.read_text(encoding="utf-8")


def _fenced_curl_examples(document: str) -> tuple[str, ...]:
    bash_blocks = re.findall(r"```bash\n(.*?)\n```", document, flags=re.DOTALL)
    return tuple(block for block in bash_blocks if block.lstrip().startswith("curl "))


def _json_payload(curl_example: str) -> object:
    match = re.search(r"(?:^|\s)-d\s+'(?P<payload>\{.*\})'\s*$", curl_example, flags=re.DOTALL)
    assert match is not None, (
        "curl example must contain a single-quoted -d JSON payload: "
        f"{curl_example}"
    )
    return json.loads(match.group("payload"))


def test_readme_documents_setup_configuration_and_quality_commands() -> None:
    readme = _read_required_document("README.md")

    required_fragments = (
        "Python 3.11",
        "uv sync --extra dev",
        "python -m venv .venv",
        "pip install -e '.[dev]'",
        "APP_NAME",
        "APP_ENV",
        "LOG_LEVEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_CHAT_MODEL",
        "DEEPSEEK_ADVICE_MODEL",
        "DEEPSEEK_AGENT_MODEL",
        "DEEPSEEK_TIMEOUT_SECONDS",
        "DEEPSEEK_MAX_RETRIES",
        "uv run uvicorn app.main:app --reload",
        "uv run ruff check .",
        "uv run mypy app tests",
        "uv run pytest",
    )

    for fragment in required_fragments:
        assert fragment in readme

    assert "test -e .env || cp .env.example .env" in readme
    assert "cp .env.example .env" not in {line.strip() for line in readme.splitlines()}


def test_readme_documents_api_contract_and_deployment_boundary() -> None:
    readme = _read_required_document("README.md")

    required_fragments = (
        "curl http://localhost:8000/health",
        "http://localhost:8000/ai/chat",
        "http://localhost:8000/ai/wellness-advice",
        '"success": false',
        '"errorCode": "AI_PROVIDER_UNAVAILABLE"',
        '"requestId"',
        "Android",
        "Spring Boot",
        "private",
        "FastAPI",
        "AI_PROVIDER_NOT_CONFIGURED",
        "503",
        "pytest -m live tests/integration/test_live_deepseek.py",
    )

    for fragment in required_fragments:
        assert fragment in readme

    assert "Android must call Spring Boot" in readme
    assert "must never call FastAPI directly" in readme
    assert "private network reachable only by Spring Boot" in readme


def test_readme_documents_exact_curl_payloads() -> None:
    readme = _read_required_document("README.md")
    examples = _fenced_curl_examples(readme)

    assert any(example.strip() == "curl http://localhost:8000/health" for example in examples)

    chat = next(example for example in examples if "http://localhost:8000/ai/chat" in example)
    assert _json_payload(chat) == {
        "userId": 1,
        "message": "How can I improve my sleep schedule?",
        "history": [
            {"role": "user", "content": "I usually sleep six hours."},
            {"role": "assistant", "content": "A consistent bedtime may help."},
        ],
    }

    advice_examples = [
        example for example in examples if "http://localhost:8000/ai/wellness-advice" in example
    ]
    advice_payloads = [_json_payload(example) for example in advice_examples]
    assert {
        "userId": 1,
        "logs": [
            {
                "logDate": "2026-06-24",
                "sleepHours": 7.5,
                "moodScore": 4,
                "waterCups": 6,
                "steps": 8000,
                "exerciseMinutes": 30,
                "note": "Felt tired in the afternoon.",
            }
        ],
    } in advice_payloads
    assert {"userId": 1, "logs": []} in advice_payloads


def test_fenced_curl_examples_do_not_send_authentication_headers() -> None:
    readme = _read_required_document("README.md")
    examples = _fenced_curl_examples(readme)
    forbidden_auth = re.compile(
        r"authorization|authentication|bearer|x-jwt|x-api-key|api-key|x-service-token",
        flags=re.IGNORECASE,
    )

    assert examples
    for example in examples:
        assert forbidden_auth.search(example) is None


def test_readme_documents_all_missing_key_behaviors() -> None:
    readme = _read_required_document("README.md")

    assert "`GET /health` still returns `200 OK`" in readme
    assert "`POST /ai/chat` returns `503` with `AI_PROVIDER_NOT_CONFIGURED`" in readme
    assert (
        "`POST /ai/wellness-advice` with non-empty `logs` returns `503` with "
        "`AI_PROVIDER_NOT_CONFIGURED`"
    ) in readme
    assert (
        "`POST /ai/wellness-advice` with empty `logs` returns `200 OK` with the stable "
        "no-data advice"
    ) in readme


def test_agents_encodes_approved_repository_guardrails() -> None:
    agents = _read_required_document("AGENTS.md")

    required_fragments = (
        "Source of truth",
        "Android",
        "Spring Boot",
        "FastAPI",
        "thin",
        "provider-independent",
        "prompts",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "timeouts",
        "bounded retries",
        "usage",
        "privacy",
        "safety",
        "offline",
        "dependencies",
        "RAG",
        "Agent",
        "Author: 2692341798",
        "500 lines",
        "800 lines",
        ".env",
        "commit",
        "push",
        "pull request",
    )

    for fragment in required_fragments:
        assert fragment in agents

    source_order = (
        "`Mobile Application Development CA.pdf`",
        "`wellness-app/Android Wellness App — Product & API Document.md`",
        "The shared API contract agreed by the frontend, backend, and AI owners.",
        "Existing source code and examples.",
    )
    positions = [agents.index(item) for item in source_order]
    assert positions == sorted(positions)

    assert "retired `deepseek-chat` or `deepseek-reasoner` aliases" in agents
    assert (
        "Keep versioned prompts and JSON-output instructions outside route and "
        "provider modules"
        in agents
    )
    assert "stable error mapping, and token usage observability" in agents
    assert (
        "Do not diagnose illness, claim medical certainty, prescribe medication, "
        "or provide dosages"
        in agents
    )
    assert (
        "deterministic escalation for urgent symptoms, self-harm, crisis, and emergency language "
        "before any provider call"
    ) in agents
    assert (
        "Never send email, username, JWT, password, unrelated identity data, or internal `userId` "
        "to DeepSeek"
    ) in agents
    assert (
        "Never log raw messages, history, prompts, generated text, wellness notes, keys, tokens, "
        "credentials, or other private user content"
    ) in agents
    assert "Update tests whenever prompts, schemas" in agents
    assert "or error mappings change" in agents
    assert (
        "shared API contract whenever an API request, response, path, status, "
        "or error shape changes"
        in agents
    )
    assert "Update `README.md` and the shared API contract whenever an API" in agents
    assert "default tests deterministic and offline" in agents
    assert "no external network calls or paid token usage" in agents
    assert "Justify new dependencies before adding them" in agents
    assert "without an approved concrete use case" in agents
    assert (
        "Never commit `.env`, keys, tokens, virtual environments, caches, coverage artifacts"
        in agents
    )
    assert "build output, or IDE state" in agents
    assert "without explicit user instruction" in agents
