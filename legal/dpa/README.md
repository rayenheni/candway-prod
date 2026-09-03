# Data Processing Agreements (DPAs)

This folder tracks the third-party DPAs that Candway relies on for
GDPR, Tunisian Law 2004-63, and equivalent data-protection
compliance.

The Candway backend forwards personally identifiable information
(PII) — at minimum, scrubbed CV text, job descriptions, and free-form
interview answers — to the following AI providers:

| Provider   | Vendor         | Sub-processors | Data residency | DPA on file |
| ---------- | -------------- | -------------- | -------------- | ----------- |
| Groq       | Groq Inc. (US) | AWS us-east-1  | United States  | NO — see P0-04 below |
| DeepSeek   | DeepSeek AI (CN) | Aliyun        | China          | NO — see P0-04 below |
| Gemini     | Google (US)    | Google Cloud   | United States  | NO — see P0-04 below |
| Ollama     | Local          | n/a            | Customer host  | n/a         |

## P0-04 — Required before the next 10 paying customers

For each provider, the platform must:

1. Have a signed DPA on file in this folder (PDF + signed XML/JSON
   if available).
2. Update `backend/llm_consent.py::PROVIDERS` to mark the provider
   as `dpa_signed=True` and record the DPA version.
3. Update the admin settings (`/admin/settings`) to expose a
   "block un-DPA'd providers" toggle. When on, any call to a
   provider with `dpa_signed=False` is refused.

## Files in this folder

- `GROQ_DPA_TEMPLATE.md` — template covering Groq's data-processing
  addendum. Final signed copy must replace this template.
- `DEEPSEEK_DPA_TEMPLATE.md` — placeholder. DeepSeek's terms of
  service are not GDPR-equivalent; this section is the highest-risk
  un-signed agreement.
- `GEMINI_DPA_TEMPLATE.md` — references Google's Cloud DPA which
  covers Gemini API calls.

## Change log

- 2026-06-02 — Folder created (P0-04). All templates are
  un-signed; treat every cross-border LLM call as **NOT** under a
  signed DPA.
