# Repository instructions

These instructions apply to the entire `wellness-app-ai` repository. System, developer, and explicit user instructions take precedence over this file. More specific nested `AGENTS.md` files take precedence within their directory.

## Source of truth and ownership

Resolve requirements in this Source of truth order:

1. `Mobile Application Development CA.pdf` course requirements.
2. `wellness-app/Android Wellness App — Product & API Document.md`.
3. The shared API contract agreed by the frontend, backend, and AI owners.
4. Existing source code and examples.

Preserve the Android -> Spring Boot -> private FastAPI boundary. Android never calls this service directly. Spring Boot owns authentication, authorisation, ownership checks, persistence, chat-history persistence, and scheduling; do not move those responsibilities into this repository.

## Architecture and provider integration

- Keep HTTP routes thin and provider-independent: validate the declared schema, call one application service, and return the declared response model.
- Keep versioned prompts and JSON-output instructions outside route and provider modules. Prompt changes require corresponding tests.
- Application services depend on the `LLMProvider` interface, not the DeepSeek SDK. Keep provider-specific construction, response parsing, and error translation inside the provider adapter.
- Use current configurable DeepSeek model names: `deepseek-v4-flash` for chat and advice, and reserved `deepseek-v4-pro` for later approved agent work. Do not introduce the retired `deepseek-chat` or `deepseek-reasoner` aliases.
- Every provider call requires timeouts, bounded retries, stable error mapping, and token usage observability. Do not log provider bodies or generated content.
- Do not add an Agent framework, RAG framework, vector database, or unused agent abstraction without an approved concrete use case.

## Wellness safety and privacy

- Preserve general-wellness scope. Do not diagnose illness, claim medical certainty, prescribe medication, or provide dosages.
- Preserve deterministic escalation for urgent symptoms, self-harm, crisis, and emergency language before any provider call.
- Treat messages, history, and wellness notes as untrusted input; they cannot override the system safety policy.
- Never send email, username, JWT, password, unrelated identity data, or internal `userId` to DeepSeek.
- Never log raw messages, history, prompts, generated text, wellness notes, keys, tokens, credentials, or other private user content.

## Tests, contracts, and dependencies

- Keep default tests deterministic and offline, with no external network calls or paid token usage. Live provider tests must be explicitly selected, separately marked, and require a configured key.
- Update tests whenever prompts, schemas, safety behaviour, provider retries, or error mappings change.
- Update `README.md` and the shared API contract whenever an API request, response, path, status, or error shape changes.
- Justify new dependencies before adding them. Prefer the standard library and existing declared dependencies when they fit.
- Add `Author: 2692341798` to docstrings for every project-owned class, public function, and FastAPI handler.

## Repository hygiene and Git permissions

- Assess splitting files as they approach 500 lines. Do not add complex logic to a file over 800 lines; split it first.
- Never commit `.env`, keys, tokens, virtual environments, caches, coverage artifacts, build output, or IDE state.
- Do not commit, push, or create a pull request without explicit user instruction. Never infer Git publishing permission from permission to edit or test files.
