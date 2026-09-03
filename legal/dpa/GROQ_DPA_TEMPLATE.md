# Groq Data Processing Addendum — Template

This is a **template** for the DPA between Candway and Groq Inc.
The signed PDF must replace this file before Groq is used to
process production candidate PII.

## 1. Parties

- **Controller**: Candway (the legal entity operating the platform)
- **Processor**: Groq Inc., 1600 Plymouth Street, Mountain View, CA
  94043, United States

## 2. Scope of processing

- **Data categories**: Scrubbed CV text, job descriptions,
  interview Q&A, structured AI outputs.
- **Data subjects**: Job candidates, recruiters, mentors who
  interact with AI features.
- **Purpose**: AI inference (LLM completion) for CV analysis,
  interview generation, evaluation, and roadmap generation.
- **Duration**: Until the request is completed; no retention by
  Groq beyond transient inference.

## 3. Sub-processors

- AWS (us-east-1) for compute. See
  https://console.groq.com/legal/data-processing-addendum

## 4. Technical and organisational measures

- TLS 1.2+ for in-transit data.
- Bearer-token authentication with per-customer API keys.
- Groq does not retain prompt/response content beyond the
  request/response cycle ("Zero Retention" mode).
- Groq staff cannot read prompt/response content.

## 5. Data subject rights

- Candway remains the single point of contact for data subject
  access requests (DSARs) and erasure requests.
- Groq cooperates with Candway to honour DSARs within 30 days.

## 6. International transfers

- Cross-border transfer from Tunisia / EU to the United States.
- Mechanism: Groq's Standard Contractual Clauses (SCCs) plus the
  EU-U.S. Data Privacy Framework.
- Tunisia: covered by Tunisian Law 2004-63 Article 14 only if an
  adequacy decision is in place; otherwise, SCCs are required.

## 7. Signatures

- Candway authorised signatory: ____________________
- Groq authorised signatory: ____________________
- Date: ____________________

---

> Until the signed PDF replaces this template, treat every call to
> Groq as **NOT** under a signed DPA. The application code blocks
> such calls in production when
> `CANDWAY_BLOCK_UNDPA_PROVIDERS=1` is set.
