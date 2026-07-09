<!--
Author: Huang Qijun
Email: 2692341798@qq.com
-->

# Knowledge base

This directory contains project-maintained English wellness knowledge files for the local RAG feature.

## Allowed content

- English prose in `.md` or `.txt` files.
- Concise, paraphrased summaries of authoritative public wellness guidance.
- Narrow wellness topics (e.g. sleep, hydration, exercise, stress, nutrition).

## Prohibited content

- Medical diagnoses, prescription guidance, or dosage instructions.
- Copied/verbatim copyrighted text from third-party sources.
- Personally identifiable information or user health records.
- Private API keys, credentials, or environment secrets.

## Authoring guidelines

1. Each file covers one narrow topic.
2. Record source URLs and the date last reviewed.
3. Paraphrase source material. Do not copy wholesale.
4. Medical claims must be verified against current authoritative sources.
5. Adding or changing a knowledge file is a reviewable code change.
6. The index rebuilds automatically when files change.

## Example

```markdown
# Sleep hygiene

Good sleep hygiene supports recovery, mood, and concentration. Experts recommend:

- A consistent bedtime and wake time, even on weekends.
- A cool, dark, and quiet sleep environment.
- Limiting screen exposure 30-60 minutes before bed.
- Avoiding caffeine and large meals late in the day.

## References
- https://www.cdc.gov/sleep/about_sleep/sleep_hygiene.html
- Last reviewed: 2026-06-28
```
