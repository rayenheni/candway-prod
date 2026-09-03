# Gemini Data Processing Addendum — Template

Google's standard Cloud DPA covers the Gemini API. The signed
agreement is part of the Google Cloud / Workspace contract. Confirm
the relevant section of your Google Cloud agreement covers the
Gemini API endpoint before relying on this template.

## 1. Parties

- **Controller**: Candway
- **Processor**: Google LLC (Cloud division)

## 2. Scope of processing

Same as Groq: scrubbed CV text, job descriptions, interview Q&A,
structured AI outputs.

## 3. Sub-processors

- Google Cloud (regions selected by the customer; default us-central1).

## 4. International transfers

- Covered by Google's Cloud DPA + EU-U.S. Data Privacy Framework.
- Tunisia: SCCs required for any non-adequacy-decision region.

## 5. Required controls

- Per-call consent check via `backend/llm_consent.py::is_provider_allowed()`.
- Per-call audit log via the same helper.
- Set `google_cloud.project_id` and `google_cloud.region` in admin
  settings before the first call.

## 6. Signatures

- Google's Cloud DPA is accepted at order time on the Google Cloud
  Console. No separate signature is required.
- Confirm and link the agreement URL in the admin settings.

---

> Until the order is signed, the application refuses Gemini calls
> in production when `CANDWAY_BLOCK_UNDPA_PROVIDERS=1` is set.
