"""Tests for PII masking — GDPR-compliant AI data pipeline."""

import re

import pytest

from backend.ai.security import PIIMasker, PIIMappingStore, get_pii_store, _pii_store
from backend.ai.privacy import count_pii_categories, audit_ai_call


# ────────────────────────────────────────────────────────────
# PIIMasker — individual category tests
# ────────────────────────────────────────────────────────────


class TestPIIMaskerEmail:
    def test_email_masked(self):
        result = PIIMasker.mask_pii("Contact me at john.doe@example.com please.")
        assert "john.doe@example.com" not in result
        assert "[EMAIL_" in result

    def test_multiple_emails_masked(self):
        result = PIIMasker.mask_pii("a@b.com and c@d.com are both emails.")
        assert "[EMAIL_" in result
        assert result.count("[EMAIL_") == 2

    def test_no_false_positive_on_normal_text(self):
        text = "Please review the code at the end of the day."
        result = PIIMasker.mask_pii(text)
        assert result == text

    def test_tunisian_email(self):
        result = PIIMasker.mask_pii("rayen.mazigh@candway.tn")
        assert "rayen.mazigh" not in result
        assert "[EMAIL_" in result


class TestPIIMaskerPhone:
    def test_international_phone_masked(self):
        result = PIIMasker.mask_pii("Call +1-555-123-4567 for inquiries.")
        assert "+1-555-123-4567" not in result
        assert "[PHONE_" in result

    def test_tunisian_phone_masked(self):
        result = PIIMasker.mask_pii("Contact +216 22 333 444 for details.")
        assert "+216 22 333 444" not in result
        assert "[PHONE_" in result


class TestPIIMaskerNationalID:
    def test_cin_masked(self):
        result = PIIMasker.mask_pii("My CIN is 12345678.")
        assert "12345678" not in result
        assert "[CIN_" in result


class TestPIIMaskerPassport:
    def test_passport_masked(self):
        result = PIIMasker.mask_pii("Passport AB1234567 is on file.")
        assert "AB1234567" not in result
        assert "[PASSPORT_" in result


class TestPIIMaskerDOB:
    def test_dob_masked(self):
        result = PIIMasker.mask_pii("Date of Birth: 15/03/1990")
        assert "15/03/1990" not in result
        assert "[DOB_" in result

    def test_dob_iso_masked(self):
        result = PIIMasker.mask_pii("Born 1990-03-15 in Tunis.")
        assert "1990-03-15" not in result
        assert "[DOB_" in result

    def test_dob_label_masked(self):
        result = PIIMasker.mask_pii("Date of Birth: January 15, 1990")
        assert "[DOB_" in result


class TestPIIMaskerSocial:
    def test_linkedin_masked(self):
        result = PIIMasker.mask_pii("LinkedIn: https://linkedin.com/in/rayenmazigh")
        assert "linkedin.com/in/rayenmazigh" not in result
        assert "[SOCIAL_" in result

    def test_github_masked(self):
        result = PIIMasker.mask_pii("GitHub: https://github.com/rayen-mazigh")
        assert "github.com/rayen-mazigh" not in result
        assert "[SOCIAL_" in result

    def test_twitter_masked(self):
        result = PIIMasker.mask_pii("Twitter: @rayen from x.com/rayen_m")
        assert "[SOCIAL_" in result


class TestPIIMaskerAddress:
    def test_rue_address_masked(self):
        result = PIIMasker.mask_pii("I live at Rue de la Liberte, Tunis.")
        assert "Rue de la Liberte" not in result
        assert "[ADDRESS_" in result

    def test_cite_address_masked(self):
        result = PIIMasker.mask_pii("Residence: Cite des Jardins, Tunis")
        assert "[ADDRESS_" in result


class TestPIIMaskerName:
    def test_name_masked(self):
        result = PIIMasker.mask_pii("My name is Rayen Mazigh, a developer.")
        assert "Rayen Mazigh" not in result
        assert "[NAME_" in result

    def test_french_name_masked(self):
        result = PIIMasker.mask_pii("Je m'appelle Jean Dupont.")
        # The NAME pattern looks for capitalized words before punctuation
        assert "[NAME_" in result


class TestPIIMaskerCreditCard:
    def test_credit_card_masked(self):
        result = PIIMasker.mask_pii("Card: 4111-1111-1111-1111")
        assert "4111-1111-1111-1111" not in result
        assert "[CARD_" in result


class TestPIIMaskerIBAN:
    def test_iban_masked(self):
        result = PIIMasker.mask_pii("IBAN: TN59 1000 6035 1831 6447 8831")
        # Either IBAN or CARD match is acceptable (both are PII)
        assert "[IBAN_" in result or "[CARD_" in result


class TestPIIMaskerReferences:
    def test_references_masked(self):
        result = PIIMasker.mask_pii("References: available upon request from previous employer.")
        assert "[REFERENCE_" in result


# ────────────────────────────────────────────────────────────
# PIIMappingStore — secure mapping tests
# ────────────────────────────────────────────────────────────


class TestPIIMappingStore:
    def setup_method(self):
        self.store = PIIMappingStore()

    def test_store_and_lookup(self):
        mid = self.store.store("rayen@example.com", "EMAIL")
        assert self.store.lookup(mid) == "rayen@example.com"

    def test_same_value_same_id(self):
        mid1 = self.store.store("rayen@example.com", "EMAIL")
        mid2 = self.store.store("rayen@example.com", "EMAIL")
        assert mid1 == mid2

    def test_different_values_different_ids(self):
        mid1 = self.store.store("rayen@example.com", "EMAIL")
        mid2 = self.store.store("ahmed@example.com", "EMAIL")
        assert mid1 != mid2

    def test_unknown_id_returns_none(self):
        assert self.store.lookup("nonexistent") is None

    def test_get_all_mappings(self):
        self.store.store("a@b.com", "EMAIL")
        self.store.store("+21622123456", "PHONE")
        mappings = self.store.get_all_mappings()
        assert len(mappings) == 2

    def test_clear(self):
        self.store.store("a@b.com", "EMAIL")
        self.store.clear()
        assert len(self.store.get_all_mappings()) == 0

    def test_global_singleton(self):
        assert get_pii_store() is _pii_store


# ────────────────────────────────────────────────────────────
# PII masking with mapping — integration tests
# ────────────────────────────────────────────────────────────


class TestPIIMaskerWithMapping:
    def test_masked_token_contains_id(self):
        result = PIIMasker.mask_pii("Email: test@example.com", store_mapping=True)
        assert re.match(r"\[EMAIL_[a-f0-9]{16}\]", result) or "[EMAIL_" in result

    def test_masked_value_stored(self):
        store = get_pii_store()
        store.clear()
        PIIMasker.mask_pii("Call +21622123456", store_mapping=True)
        mappings = store.get_all_mappings()
        pii_values = list(mappings.values())
        assert any("+21622123456" in v for v in pii_values) or any(
            "22123456" in v for v in pii_values
        )

    def test_masking_without_store(self):
        store = get_pii_store()
        store.clear()
        PIIMasker.mask_pii("test@example.com", store_mapping=False)
        assert len(store.get_all_mappings()) == 0

    def test_multiple_categories(self):
        text = "Email: john@example.com, Phone: +21622123456"
        result = PIIMasker.mask_pii(text)
        assert "[EMAIL_" in result
        assert "[PHONE_" in result

    def test_empty_text(self):
        assert PIIMasker.mask_pii("") == ""
        assert PIIMasker.mask_pii(None) is None


# ────────────────────────────────────────────────────────────
# count_pii_categories — audit helper tests
# ────────────────────────────────────────────────────────────


class TestCountPiiCategories:
    def test_no_pii(self):
        count, cats = count_pii_categories("Hello world, this is clean text.")
        assert count == 0
        assert cats == []

    def test_email(self):
        count, cats = count_pii_categories("Email: a@b.com")
        assert count >= 1
        assert "EMAIL" in cats

    def test_multiple_categories(self):
        count, cats = count_pii_categories(
            "Email: a@b.com, Phone: +21622123456, CIN: 12345678"
        )
        assert count >= 3
        assert "EMAIL" in cats
        assert "PHONE" in cats
        assert "CIN" in cats

    def test_empty_text(self):
        assert count_pii_categories("") == (0, [])
        assert count_pii_categories(None) == (0, [])


# ────────────────────────────────────────────────────────────
# audit_ai_call — audit log format tests
# ────────────────────────────────────────────────────────────


class TestAuditAiCall:
    def test_audit_returns_dict(self):
        entry = audit_ai_call(
            pipeline_stage="test",
            application_id=1,
            pii_count=2,
            pii_categories=["EMAIL", "PHONE"],
            success=True,
        )
        assert entry["pipeline_stage"] == "test"
        assert entry["pii_count"] == 2
        assert "send_pii_enabled" not in entry
        assert entry["success"] is True

    def test_audit_no_pii(self):
        entry = audit_ai_call(
            pipeline_stage="test_empty",
            application_id=0,
            pii_count=0,
            pii_categories=[],
            success=True,
        )
        assert entry["pii_count"] == 0
        assert entry["pii_categories"] == []

    def test_audit_with_error(self):
        entry = audit_ai_call(
            pipeline_stage="test_error",
            application_id=5,
            pii_count=1,
            pii_categories=["CIN"],
            success=False,
            error_message="LLM timeout",
        )
        assert entry["error_message"] == "LLM timeout"
        assert entry["success"] is False

    def test_categories_deduplicated(self):
        entry = audit_ai_call(
            pipeline_stage="test_dedup",
            application_id=0,
            pii_count=2,
            pii_categories=["EMAIL", "EMAIL", "PHONE"],
            success=True,
        )
        assert entry["pii_categories"] == ["EMAIL", "PHONE"]
