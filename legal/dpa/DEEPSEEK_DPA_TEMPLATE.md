# DeepSeek Data Processing Addendum — Template

> **HIGHEST RISK**: DeepSeek's standard terms of service are not
> GDPR-equivalent and the data may transit through jurisdictions
> without an adequacy decision. Until a signed DPA is in place,
> prefer Groq / Gemini or local Ollama for any EU or Tunisian
> candidate data.

## 1. Parties

- **Controller**: Candway
- **Processor**: DeepSeek AI Co., Ltd. (Hangzhou, China)

## 2. Scope of processing

Same as Groq: scrubbed CV text, job descriptions, interview Q&A,
structured AI outputs.

## 3. Sub-processors

- Aliyun (Alibaba Cloud) for compute.
- Unverified sub-processor list — confirm before signing.

## 4. International transfers

- **China → Tunisia/EU/US** without a signed SCC. This is a
  notifiable transfer under GDPR Chapter V.
- Requires explicit, granular user consent captured at signup
  (`ConsentLog.agreement_type = "ai_processing_deepseek"`).

## 5. Required controls

- Per-call consent check via `backend/llm_consent.py::is_provider_allowed()`.
- Per-call audit log (provider, content hash, application id, user
  id, timestamp) via the same helper.
- The application code must NOT use DeepSeek for any candidate who
  has not granted explicit "ai_processing_deepseek" consent.

## 6. Signatures

- Candway authorised signatory: ____________________
- DeepSeek authorised signatory: ____________________
- Date: ____________________

---

> Until the signed PDF replaces this template, the application
> refuses DeepSeek calls in production when
> `CANDWAY_BLOCK_UNDPA_PROVIDERS=1` is set.
