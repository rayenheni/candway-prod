import os
import secrets

import httpx

from backend.config import get_settings
from backend.logger import logger


def _make_offer_document(offer_data: dict, candidate_name: str) -> str:
    html = f"""
    <html><head><meta charset="utf-8"><style>
      body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 20px; color: #1e293b; }}
      h1 {{ color: #4f46e5; font-size: 24px; }}
      .offer {{ border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; margin: 20px 0; }}
      .signature {{ margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
    </style></head><body>
    <h1>Job Offer — {offer_data.get("position", "Position")}</h1>
    <div class="offer">
      <p><strong>Candidate:</strong> {candidate_name}</p>
      <p><strong>Position:</strong> {offer_data.get("position", "")}</p>
      <p><strong>Salary:</strong> {offer_data.get("salary", "")}</p>
      <p><strong>Start Date:</strong> {offer_data.get("start_date", "TBD")}</p>
      <hr>
      <div>{offer_data.get("body", "")}</div>
    </div>
    <div class="signature">
      <p>By signing below, you accept the terms of this offer.</p>
    </div>
    </body></html>
    """
    return html


async def create_esign_envelope(
    offer_data: dict,
    candidate_email: str,
    candidate_name: str,
    recruiter_email: str,
) -> dict:
    """
    Generate an e-signature envelope using DocuSign REST API v2.1.
    Falls back to a hosted Candway signing page if DocuSign is not configured.
    """
    settings = get_settings()
    docusign_account_id = os.getenv("DOCUSIGN_ACCOUNT_ID")
    docusign_integration_key = os.getenv("DOCUSIGN_INTEGRATION_KEY")
    docusign_user_id = os.getenv("DOCUSIGN_USER_ID")
    docusign_private_key = os.getenv("DOCUSIGN_PRIVATE_KEY")
    docusign_base_url = os.getenv(
        "DOCUSIGN_BASE_URL", "https://demo.docusign.net/restapi"
    )

    if docusign_account_id and docusign_integration_key and docusign_private_key:
        try:
            document_html = _make_offer_document(offer_data, candidate_name)
            base64_html = (
                __import__("base64").b64encode(document_html.encode()).decode()
            )

            envelope_data = {
                "emailSubject": f"Please sign your offer — {offer_data.get('position', '')}",
                "documents": [
                    {
                        "documentBase64": base64_html,
                        "name": "Offer Letter.html",
                        "fileExtension": "html",
                        "documentId": "1",
                    }
                ],
                "recipients": {
                    "signers": [
                        {
                            "email": candidate_email,
                            "name": candidate_name,
                            "recipientId": "1",
                            "routingOrder": "1",
                            "clientUserId": "1",
                        }
                    ]
                },
                "status": "sent",
                "eventNotification": {
                    "url": f"{settings.base_url}/api/v1/recruiter/offers/docusign-webhook",
                    "loggingEnabled": "true",
                    "requireAcknowledgment": "true",
                    "useSoapInterface": "false",
                    "includeCertificateWithSoap": "false",
                    "signMessageWithX509Cert": "false",
                    "includeDocuments": "false",
                    "includeEnvelopeVoidReason": "true",
                    "includeTimeZone": "true",
                    "envelopeEvents": [{"envelopeEventStatusCode": "completed"}],
                    "recipientEvents": [{"recipientEventStatusCode": "completed"}],
                },
            }

            async with httpx.AsyncClient(timeout=30) as client:
                auth_resp = await client.post(
                    "https://account-d.docusign.com/oauth/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": _generate_jwt_assertion(
                            docusign_integration_key,
                            docusign_user_id,
                            docusign_private_key,
                        ),
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if auth_resp.status_code != 200:
                    logger.error(f"DocuSign auth failed: {auth_resp.text}")
                    raise Exception("DocuSign authentication failed")

                token_data = auth_resp.json()
                access_token = token_data["access_token"]

                envelope_resp = await client.post(
                    f"{docusign_base_url}/v2.1/accounts/{docusign_account_id}/envelopes",
                    json=envelope_data,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )
                if envelope_resp.status_code not in (200, 201):
                    logger.error(
                        f"DocuSign envelope creation failed: {envelope_resp.text}"
                    )
                    raise Exception("Failed to create DocuSign envelope")

                envelope = envelope_resp.json()
                envelope_id = envelope["envelopeId"]

                signing_resp = await client.post(
                    f"{docusign_base_url}/v2.1/accounts/{docusign_account_id}/envelopes/{envelope_id}/views/recipient",
                    json={
                        "returnUrl": f"{settings.frontend_url}/candidate/esign-view?envelope_id={envelope_id}",
                        "authenticationMethod": "email",
                        "email": candidate_email,
                        "userName": candidate_name,
                        "clientUserId": "1",
                    },
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )
                if signing_resp.status_code not in (200, 201):
                    logger.error(
                        f"DocuSign signing URL creation failed: {signing_resp.text}"
                    )
                    raise Exception("Failed to create signing URL")

                signing_data = signing_resp.json()
                signing_url = signing_data.get("url", "")

            return {
                "envelope_id": envelope_id,
                "signing_url": signing_url,
                "status": "sent",
            }

        except Exception as e:
            logger.error(f"DocuSign integration error: {e}", exc_info=True)
            return await _fallback_esign(
                offer_data, candidate_email, candidate_name, recruiter_email
            )
    else:
        return await _fallback_esign(
            offer_data, candidate_email, candidate_name, recruiter_email
        )


def _generate_jwt_assertion(
    integration_key: str, user_id: str, private_key: str
) -> str:
    import time as _time

    from jose import jwt as _jwt

    now = int(_time.time())
    claims = {
        "iss": integration_key,
        "sub": user_id,
        "aud": "account-d.docusign.com",
        "iat": now,
        "exp": now + 3600,
        "scp": ["signature", "impersonation"],
    }
    return _jwt.encode(claims, private_key, algorithm="RS256")


async def _fallback_esign(
    offer_data: dict,
    candidate_email: str,
    candidate_name: str,
    recruiter_email: str,
) -> dict:
    settings = get_settings()
    envelope_id = f"candway_{secrets.token_hex(12)}"

    signing_url = (
        f"{settings.frontend_url}/candidate/esign-view"
        f"?envelope_id={envelope_id}"
        f"&email={candidate_email}"
        f"&name={candidate_name}"
    )

    return {
        "envelope_id": envelope_id,
        "signing_url": signing_url,
        "status": "sent",
        "fallback": True,
    }


async def get_esign_status(envelope_id: str) -> dict:
    docusign_account_id = os.getenv("DOCUSIGN_ACCOUNT_ID")
    docusign_integration_key = os.getenv("DOCUSIGN_INTEGRATION_KEY")
    docusign_user_id = os.getenv("DOCUSIGN_USER_ID")
    docusign_private_key = os.getenv("DOCUSIGN_PRIVATE_KEY")
    docusign_base_url = os.getenv(
        "DOCUSIGN_BASE_URL", "https://demo.docusign.net/restapi"
    )

    if not (docusign_account_id and docusign_integration_key and docusign_private_key):
        return {"status": "sent", "envelope_id": envelope_id, "signed": False}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            auth_resp = await client.post(
                "https://account-d.docusign.com/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": _generate_jwt_assertion(
                        docusign_integration_key, docusign_user_id, docusign_private_key
                    ),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if auth_resp.status_code != 200:
                return {"status": "error", "detail": "Auth failed"}

            tokens = auth_resp.json()
            resp = await client.get(
                f"{docusign_base_url}/v2.1/accounts/{docusign_account_id}/envelopes/{envelope_id}",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            if resp.status_code != 200:
                return {"status": "error", "detail": "Envelope not found"}

            env_data = resp.json()
            signed = env_data.get("status") == "completed"
            return {
                "status": env_data.get("status", "unknown"),
                "envelope_id": envelope_id,
                "signed": signed,
            }
    except Exception as e:
        logger.error(f"Error checking DocuSign status: {e}")
        return {"status": "error", "detail": str(e)}
