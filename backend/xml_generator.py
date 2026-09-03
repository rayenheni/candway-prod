import xml.etree.ElementTree as ET
from datetime import UTC, datetime


def generate_teif_xml(invoice_data: dict) -> bytes:
    """
    Generates a TEIF-compliant XML for the Tunisian 'El Fatoora' system.
    Follows the standard UBL-based structure required by TTN.
    """

    # Root Element
    root = ET.Element(
        "Invoice", xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    )

    # 1. Invoice Metadata
    ET.SubElement(root, "ID").text = invoice_data.get("invoice_number", "UNKNOWN")
    ET.SubElement(root, "IssueDate").text = invoice_data.get(
        "date", datetime.now(UTC).strftime("%Y-%m-%d")
    )
    ET.SubElement(root, "InvoiceTypeCode").text = "380"  # Commercial Invoice
    ET.SubElement(root, "DocumentCurrencyCode").text = "TND"

    # 2. Supplier Party (Candway)
    supplier = ET.SubElement(root, "AccountingSupplierParty")
    sup_party = ET.SubElement(supplier, "Party")
    sup_name = ET.SubElement(sup_party, "PartyName")
    ET.SubElement(sup_name, "Name").text = "Candway Intelligence"

    sup_tax = ET.SubElement(sup_party, "PartyTaxScheme")
    ET.SubElement(sup_tax, "CompanyID").text = invoice_data.get(
        "supplier_mf", "1234567/A/M/000"
    )

    # 3. Customer Party
    customer = ET.SubElement(root, "AccountingCustomerParty")
    cust_party = ET.SubElement(customer, "Party")
    cust_name = ET.SubElement(cust_party, "PartyName")
    ET.SubElement(cust_name, "Name").text = invoice_data.get(
        "client_name", "Unknown Client"
    )

    cust_tax = ET.SubElement(cust_party, "PartyTaxScheme")
    # If MF is present, use it, otherwise use a placeholder or skip
    client_mf = invoice_data.get("client_mf") or "PASSAGER"
    ET.SubElement(cust_tax, "CompanyID").text = client_mf

    # 4. Payment Means
    payment = ET.SubElement(root, "PaymentMeans")
    ET.SubElement(payment, "PaymentMeansCode").text = "30"  # Credit Transfer
    ET.SubElement(payment, "PaymentID").text = invoice_data.get("transaction_id", "N/A")

    # 5. Tax Total
    tax_total = ET.SubElement(root, "TaxTotal")
    ET.SubElement(
        tax_total, "TaxAmount", currencyID="TND"
    ).text = f"{invoice_data.get('tva_amount', 0.0):.3f}"

    # 6. Legal Monetary Total
    monetary = ET.SubElement(root, "LegalMonetaryTotal")
    ET.SubElement(
        monetary, "LineExtensionAmount", currencyID="TND"
    ).text = f"{invoice_data.get('amount_ht', 0.0):.3f}"
    ET.SubElement(
        monetary, "TaxExclusiveAmount", currencyID="TND"
    ).text = f"{invoice_data.get('amount_ht', 0.0):.3f}"
    ET.SubElement(
        monetary, "TaxInclusiveAmount", currencyID="TND"
    ).text = f"{invoice_data.get('total_ttc', 0.0):.3f}"
    ET.SubElement(
        monetary, "PayableAmount", currencyID="TND"
    ).text = f"{invoice_data.get('total_ttc', 0.0):.3f}"

    # 7. Invoice Lines (Simplified as single service line for subscription)
    lines = ET.SubElement(root, "InvoiceLine")
    ET.SubElement(lines, "ID").text = "1"
    ET.SubElement(lines, "InvoicedQuantity", unitCode="EA").text = "1.0"
    ET.SubElement(
        lines, "LineExtensionAmount", currencyID="TND"
    ).text = f"{invoice_data.get('amount_ht', 0.0):.3f}"

    item = ET.SubElement(lines, "Item")
    ET.SubElement(item, "Description").text = "Platform Subscription Service (SaaS)"

    price = ET.SubElement(lines, "Price")
    ET.SubElement(
        price, "PriceAmount", currencyID="TND"
    ).text = f"{invoice_data.get('amount_ht', 0.0):.3f}"

    # Generate XML String
    return ET.tostring(root, encoding="utf-8", method="xml")
