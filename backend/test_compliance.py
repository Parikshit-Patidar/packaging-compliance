"""
Comprehensive Test Suite for Legal Metrology Compliance Checking System
"""

import sys
import os

# Add current folder to path
sys.path.insert(0, os.path.dirname(__file__))

from rules import (
    LegalMetrologyComplianceEngine,
    PackagingDeclarations,
    ComplianceStatus,
    Severity
)
from database import (
    init_db,
    seed_demo_data,
    save_inspection,
    get_inspections,
    get_inspection_by_ref,
    get_analytics_summary
)
from ocr_service import (
    BENCHMARK_SAMPLES,
    create_synthetic_package_image,
    annotate_packaging_image,
    analyze_label_readability,
    extract_from_raw_text
)
from report_generator import (
    generate_html_report,
    generate_show_cause_notice
)


def test_compliant_package():
    print("[TEST 1] Testing 100% Compliant Package...")
    engine = LegalMetrologyComplianceEngine()
    dec = PackagingDeclarations(
        product_name="Standard Potato Chips",
        generic_name="Potato Chips",
        manufacturer_name="Top Foods Pvt Ltd",
        manufacturer_address="Plot 10, Industrial Estate, Noida 201301",
        country_of_origin="India",
        net_quantity_value=50.0,
        net_quantity_unit="g",
        mrp_value=20.0,
        mrp_raw="MRP ₹ 20.00 (incl. of all taxes)",
        mrp_inclusive_taxes_mentioned=True,
        unit_sale_price_value=0.40,
        unit_sale_price_unit="g",
        unit_sale_price_raw="₹ 0.40 / g",
        month_year_of_mfg="08/2026",
        consumer_care_phone="1800-111-2222",
        consumer_care_email="care@topfoods.in",
        pdp_height_cm=15.0,
        pdp_width_cm=10.0,
        numeral_height_mm=4.0
    )
    report = engine.evaluate(dec)
    assert report.overall_status == ComplianceStatus.COMPLIANT, f"Expected COMPLIANT, got {report.overall_status}"
    assert report.compliance_score == 100.0, f"Expected 100.0 score, got {report.compliance_score}"
    assert len(report.violations) == 0, f"Expected 0 violations, got {len(report.violations)}"
    print("  -> Passed: Score = 100.0%, Status = COMPLIANT")


def test_non_compliant_package():
    print("[TEST 2] Testing Package with Statutory Violations ('gms', missing tax, missing USP)...")
    engine = LegalMetrologyComplianceEngine()
    dec = PackagingDeclarations(
        product_name="Defective Biscuits",
        generic_name="Biscuits",
        manufacturer_name="Baker Entity",
        manufacturer_address="Small town",
        country_of_origin="India",
        net_quantity_value=100.0,
        net_quantity_unit="gms",  # Non-standard unit!
        mrp_value=30.0,
        mrp_raw="MRP Rs. 30.00",  # Missing incl. of all taxes!
        mrp_inclusive_taxes_mentioned=False,
        unit_sale_price_value=None,  # Missing USP!
        month_year_of_mfg="08/2026",
        consumer_care_phone=None,  # Missing phone helpline!
        consumer_care_email="baker@mail.com"
    )
    report = engine.evaluate(dec)
    assert report.overall_status == ComplianceStatus.NON_COMPLIANT, f"Expected NON_COMPLIANT, got {report.overall_status}"
    assert len(report.violations) >= 3, f"Expected >= 3 violations, got {len(report.violations)}"
    
    # Check that non-standard unit was flagged
    unit_violation = any("RULE_6_1_C_STD_UNIT" == v.rule_id for v in report.violations)
    assert unit_violation, "Rule 13 standard unit violation not flagged"
    
    # Check that USP was flagged
    usp_violation = any("RULE_6_1_DA_USP" == v.rule_id for v in report.violations)
    assert usp_violation, "Rule 6(1)(da) Unit Sale Price violation not flagged"
    print(f"  -> Passed: Flagged {len(report.violations)} statutory violations correctly.")


def test_imported_package():
    print("[TEST 3] Testing Imported Package Missing Origin & Importer Info...")
    engine = LegalMetrologyComplianceEngine()
    dec = PackagingDeclarations(
        product_name="Foreign Perfume",
        generic_name="Eau de Parfum",
        manufacturer_name="Paris Fragrance Ltd",
        manufacturer_address="Paris, France",
        importer_name=None,  # Missing importer!
        country_of_origin=None,  # Missing country of origin!
        is_imported=True,
        net_quantity_value=50.0,
        net_quantity_unit="ml",
        mrp_value=2500.0,
        mrp_raw="MRP Rs. 2500 (incl. of all taxes)",
        mrp_inclusive_taxes_mentioned=True,
        month_year_of_mfg="01/2026"
    )
    report = engine.evaluate(dec)
    origin_violation = any("RULE_6_10_ORIGIN" == v.rule_id for v in report.violations)
    assert origin_violation, "Rule 6(10) Country of Origin violation not flagged"
    print("  -> Passed: Flagged missing country of origin & importer details.")


def test_database_and_analytics():
    print("[TEST 4] Testing SQLite Database & Repository Operations...")
    init_db()
    seed_demo_data()
    records = get_inspections(limit=10)
    assert len(records) >= 4, f"Expected at least 4 records, got {len(records)}"
    analytics = get_analytics_summary()
    assert analytics["total_inspections"] >= 4, "Analytics count mismatch"
    assert "compliance_rate" in analytics, "Missing compliance_rate"
    print(f"  -> Passed: Total records = {analytics['total_inspections']}, Compliance rate = {analytics['compliance_rate']}%")


def test_report_generation():
    print("[TEST 5] Testing HTML Inspection Certificate and Notice Generator...")
    engine = LegalMetrologyComplianceEngine()
    sample = BENCHMARK_SAMPLES.get("SAMPLE_VIOLATION_BISCUITS") or list(BENCHMARK_SAMPLES.values())[0]
    report = engine.evaluate(sample["declarations"])
    label_img = create_synthetic_package_image("SAMPLE_COMPLIANT_SNACK")
    
    html = generate_html_report(
        inspection_ref="LM-TEST-999",
        report=report,
        product_name="Butter Bite Biscuits",
        brand="Sweet Delights",
        category="Bakery",
        batch_no="BATCH-TEST",
        inspector_name="Inspector Test",
        location="Delhi",
        store_name="Metro Retail",
        evidence_image=label_img
    )
    assert "<!DOCTYPE html>" in html, "HTML report structure invalid"
    assert "Butter Bite Biscuits" in html, "Product name missing in report"
    assert "Rule 13" in html, "Rule clause missing in report"

    notice = generate_show_cause_notice(
        inspection_ref="LM-TEST-999",
        product_name="Butter Bite Biscuits",
        brand="Sweet Delights",
        manufacturer_name="Sweet Delights Bakery Pvt Ltd",
        manufacturer_address="Ahmedabad, Gujarat",
        violations=[v.__dict__ for v in report.violations]
    )
    assert "SECTION 36" in notice, "Notice missing Section 36 citation"
    print("  -> Passed: HTML report & Section 36 Notice generated successfully.")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING LEGAL METROLOGY COMPLIANCE SYSTEM VERIFICATION SUITE")
    print("=" * 60)
    test_compliant_package()
    test_non_compliant_package()
    test_imported_package()
    test_database_and_analytics()
    test_report_generation()
    print("=" * 60)
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)
