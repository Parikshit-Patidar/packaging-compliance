"""
Test Suite for Forensic Accuracy, Evidentiary Justification & Zero-Error Assurance Engine
"""

import sys
import os
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))

from rules import (
    LegalMetrologyComplianceEngine,
    PackagingDeclarations,
    ComplianceStatus
)
from ocr_service import (
    create_synthetic_package_image,
    extract_packaging_declarations,
    locate_declaration_bounding_boxes,
    generate_accuracy_and_justification_dossier
)
from benchmark_service import (
    BenchmarkService,
    BENCHMARK_TEST_BATTERY
)
from pdf_service import (
    AuditPDFService
)
from report_generator import (
    generate_html_report
)


def test_decision_trace_generation():
    print("[TEST 1] Testing XAI Decision Trace Generation on Compliant & Defective SKUs...")
    engine = LegalMetrologyComplianceEngine()
    
    # 1. Compliant SKU
    dec_comp = PackagingDeclarations(
        product_name="Masala Chips",
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
    rep_comp = engine.evaluate(dec_comp)
    assert rep_comp.overall_status == ComplianceStatus.COMPLIANT
    for c in rep_comp.check_results:
        assert c.decision_trace is not None, f"Decision trace missing for {c.rule_id}"
        assert "observed_fact" in c.decision_trace
        assert "deterministic_proof" in c.decision_trace
        assert c.decision_trace["legal_verdict"] == "STATUTORY_COMPLIANT_PASS"

    # 2. Defective SKU ('gms')
    dec_def = PackagingDeclarations(
        product_name="Defective Biscuits",
        generic_name="Biscuits",
        manufacturer_name="Baker Entity",
        manufacturer_address="Small town",
        country_of_origin="India",
        net_quantity_value=100.0,
        net_quantity_unit="gms",  # Prohibited!
        mrp_value=30.0,
        month_year_of_mfg="08/2026"
    )
    rep_def = engine.evaluate(dec_def)
    unit_check = next((c for c in rep_def.check_results if c.rule_id == "RULE_6_1_C_STD_UNIT"), None)
    assert unit_check is not None
    assert not unit_check.passed
    assert "STATUTORY_VIOLATION" in unit_check.decision_trace["legal_verdict"]
    print("  -> Passed: Rich deterministic decision traces generated for all statutory rules.")


def test_accuracy_and_justification_dossier():
    print("[TEST 2] Testing Evidentiary Accuracy Dossier & Bounding Box Crops...")
    img = create_synthetic_package_image("SAMPLE_COMPLIANT_SNACK")
    dec, trans, eng = extract_packaging_declarations(img, force_local=True)
    boxes = locate_declaration_bounding_boxes(dec, getattr(dec, "_lines_info", []), img.size)
    dossier = generate_accuracy_and_justification_dossier(
        img,
        dec,
        boxes,
        getattr(dec, "_lines_info", []),
        trans,
        eng
    )

    assert "overall_confidence" in dossier
    assert dossier["overall_confidence"] >= 85.0
    assert "dual_engine_concordance" in dossier
    assert "grounding_verification" in dossier
    assert "assurance_tier" in dossier
    assert dossier["assurance_tier"]["tier_id"] == "TIER_1_CERTIFIED_HIGH_CONFIDENCE"
    assert dossier["assurance_tier"]["risk_of_error_pct"] == 0.00
    assert len(dossier["field_evidence_matrix"]) > 0

    # Verify at least one photographic evidence crop exists
    has_crops = any(b.get("evidence_crop_base64") is not None for b in dossier["field_evidence_matrix"])
    assert has_crops, "No photographic evidence crops generated"
    print(f"  -> Passed: Dossier generated with {dossier['overall_confidence']}% confidence, Tier 1 Assurance, and {len(dossier['field_evidence_matrix'])} visual evidence crops.")


def test_benchmark_service_zero_error_rate():
    print("[TEST 3] Testing Benchmark Battery (10 FMCG Cases) for 0.00% False Positive Rate...")
    bench = BenchmarkService()
    res = bench.run_benchmark()
    summ = res["summary"]

    assert summ["total_cases"] == 10
    assert summ["overall_accuracy_pct"] == 100.0, f"Expected 100% accuracy, got {summ['overall_accuracy_pct']}"
    assert summ["precision_pct"] == 100.0, f"Expected 100% precision, got {summ['precision_pct']}"
    assert summ["false_positive_rate_pct"] == 0.0, f"Expected 0.00% FPR, got {summ['false_positive_rate_pct']}"
    assert summ["confusion_matrix"]["false_positives"] == 0, "False positives detected!"
    print(f"  -> Passed: 10/10 Benchmark cases matched ground truth (Accuracy: 100%, False-Positive Rate: 0.00%, Latency: {summ['average_latency_per_sku_ms']} ms/sku).")


def test_reports_with_evidentiary_certificate():
    print("[TEST 4] Testing PDF & HTML Generation with Section 63 BSA Certificate...")
    engine = LegalMetrologyComplianceEngine()
    dec = PackagingDeclarations(
        product_name="Masala Chips 50g",
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

    dossier = {
        "overall_confidence": 98.6,
        "assurance_tier": {
            "badge": "🟢 TIER 1: CERTIFIED HIGH CONFIDENCE (0.00% False-Positive Risk)",
            "risk_of_error_pct": 0.00
        },
        "dual_engine_concordance": {"concordance_score": 99.2},
        "grounding_verification": {"grounding_score": 100.0}
    }

    # Test PDF
    pdf_service = AuditPDFService()
    pdf_bytes = pdf_service.generate_pdf(
        inspection_ref="LM-TEST-AUDIT",
        report=report,
        product_name="Masala Chips",
        brand="Top Foods",
        inspector_name="Inspector Rajesh Kumar",
        location="New Delhi",
        store_name="Mega Mart",
        accuracy_dossier=dossier
    )
    assert len(pdf_bytes) > 2000

    # Test HTML
    html_text = generate_html_report(
        inspection_ref="LM-TEST-AUDIT",
        report=report,
        product_name="Masala Chips",
        brand="Top Foods",
        category="Snacks",
        batch_no="B-001",
        inspector_name="Inspector Rajesh Kumar",
        location="New Delhi",
        store_name="Mega Mart",
        accuracy_dossier=dossier
    )
    assert "Section 63 of Bharatiya Sakshya Adhiniyam, 2023" in html_text
    assert "TIER 1: CERTIFIED HIGH CONFIDENCE" in html_text
    print("  -> Passed: Section 63 BSA Evidentiary Certificate successfully compiled into PDF & HTML deliverables.")


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING FORENSIC ACCURACY, JUSTIFICATION & ZERO-ERROR TEST SUITE")
    print("=" * 70)
    test_decision_trace_generation()
    test_accuracy_and_justification_dossier()
    test_benchmark_service_zero_error_rate()
    test_reports_with_evidentiary_certificate()
    print("=" * 70)
    print("ALL ACCURACY & EVIDENTIARY JUSTIFICATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)
