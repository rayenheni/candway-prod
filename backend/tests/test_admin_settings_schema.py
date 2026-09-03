from backend.routers.admin.common import SystemSettings


def test_system_settings_model_covers_admin_platform_fields():
    config = SystemSettings(
        bank_name="Banque Zitouna",
        bank_account_name="Candway SARL",
        bank_account_number="123456789",
        bank_iban="TN590000000000000000000000",
        payment_instructions="Pay within 48h",
        ab_test_enabled=True,
        ab_test_bucket_size=25,
        google_client_id="demo-google-client-id",
        google_enabled=True,
    )

    assert config.bank_name == "Banque Zitouna"
    assert config.bank_account_name == "Candway SARL"
    assert config.bank_account_number == "123456789"
    assert config.bank_iban == "TN590000000000000000000000"
    assert config.payment_instructions == "Pay within 48h"
    assert config.ab_test_enabled is True
    assert config.ab_test_bucket_size == 25
    assert config.google_client_id.get_secret_value() == "demo-google-client-id"
    assert config.google_enabled is True
