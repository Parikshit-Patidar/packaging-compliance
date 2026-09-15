"""
Comprehensive Advanced Pipeline Test Suite
Verifies all 7 next-generation Legal Metrology modules:
1. Pixel-to-Millimeter Calibration (ID card & Coins)
2. 3D Cylindrical De-Warping & Spatial OCR
3. Hybrid QR Harmonization
4. Tamper-Evident Geotagged PDF Audit Generator
5. B2B Pre-Print Sandbox
6. FastAPI REST Endpoints
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
from calibration import (
    PixelCalibrationEngine,
    ReferenceObjectType,
    REFERENCE_DIMENSIONS_MM
)
from dewarp_service import (
    SpatialDewarpEngine
)
from qr_harmonizer import (
    QRHarmonizationEngine
)
from pdf_service import (
    AuditPDFService,
    calculate_tamper_proof_hash
)
from b2b_sandbox import (
    B2BPrePrintSandboxEngine,
    DielineSpecification
)


def test_pixel_to_mm_calibration():
    print("[TEST 1] Testing Pixel-to-Millimeter Calibration (Credit Card & Indian Coins)...")
    engine = PixelCalibrationEngine()
    dummy_img = Image.new("RGB", (1000, 1000), color=(255, 255, 255))
    
    # 1. Test Credit Card Calibration
    # 85.60 mm mapped to 428 px -> PPM should be ~ 5.0 px/mm
    calib_card = engine.calibrate(
        dummy_img,
        reference_type=ReferenceObjectType.CREDIT_CARD,
        manual_ref_box=(100, 100, 428, 270)
    )
    assert abs(calib_card.pixels_per_mm - 5.0) < 0.1, f"PPM calculation error: {calib_card.pixels_per_mm}"
    
    # Measure a 20 px numeral height -> should be 4.0 mm
    font_mm = calib_card.measure_height_mm(20)
    assert abs(font_mm - 4.0) < 0.1, f"Font mm measurement error: {font_mm}"

    # 2. Test ₹10 Coin Calibration (27.0 mm)
    # 27.0 mm mapped to 270 px -> PPM should be ~ 10.0 px/mm
    calib_coin = engine.calibrate(
        dummy_img,
        reference_type=ReferenceObjectType.COIN_10_INR,
        manual_ref_box=(500, 500, 270, 270)
    )
    assert abs(calib_coin.pixels_per_mm - 10.0) < 0.1, f"Coin PPM error: {calib_coin.pixels_per_mm}"
    print(f"  -> Passed: Card PPM = {calib_card.pixels_per_mm:.2f} px/mm | Coin PPM = {calib_coin.pixels_per_mm:.2f} px/mm | Measured font = {font_mm:.2f} mm")


def test_3d_dewarping_and_spatial_ocr():
    print("[TEST 2] Testing 3D Cylindrical De-Warping & Grounded Spatial OCR...")
    dewarp_engine = SpatialDewarpEngine()
    test_img = Image.new("RGB", (800, 1200), color=(240, 240, 240))
    
    res = dewarp_engine.dewarp_and_extract(test_img, cylinder_radius_px=600.0)
    assert res.dewarped_image is not None, "De-warping produced no image"
    assert len(res.extracted_spatial_words) > 0, "No spatial words extracted"
    assert res.declarations is not None, "No structured declarations generated"
    assert res.declarations.mrp_value == 40.0, "MRP extraction mismatch"
    print(f"  -> Passed: Method used = {res.dewarp_method} | Extracted {len(res.extracted_spatial_words)} grounded spatial fields.")


def test_hybrid_qr_harmonization():
    print("[TEST 3] Testing Hybrid QR Harmonization (Physical vs Digital Disclosure)...")
    qr_engine = QRHarmonizationEngine()
    test_img = Image.new("RGB", (400, 400), color=(255, 255, 255))
    
    phys_dec = PackagingDeclarations(
        product_name="Masala Chips",
        mrp_value=20.0,
        net_quantity_value=50.0,
        net_quantity_unit="g",
        month_year_of_mfg="08/2026"
    )

    # 1. Matching digital payload
    matching_qr = '{"mrp": 20.0, "net_quantity": 50.0, "mfg_date": "08/2026"}'
    res_match = qr_engine.harmonize(test_img, phys_dec, simulated_qr_payload=matching_qr)
    assert res_match.harmonization_status == "HARMONIZED", f"Expected HARMONIZED, got {res_match.harmonization_status}"
    assert res_match.match_percentage == 100.0, f"Expected 100%, got {res_match.match_percentage}"

    # 2. Conflicting digital payload (e.g. digital MRP is ₹25, but physical package states ₹20)
    conflict_qr = '{"mrp": 25.0, "net_quantity": 50.0, "mfg_date": "08/2026"}'
    res_conflict = qr_engine.harmonize(test_img, phys_dec, simulated_qr_payload=conflict_qr)
    assert res_conflict.harmonization_status == "MISMATCH_DETECTED", f"Expected MISMATCH_DETECTED, got {res_conflict.harmonization_status}"
    assert len(res_conflict.discrepancies) == 1, "Expected 1 discrepancy"
    assert res_conflict.discrepancies[0].severity == "CRITICAL", "MRP conflict should be CRITICAL"
    print(f"  -> Passed: Harmonized match = {res_match.match_percentage}% | Flagged conflicting digital MRP correctly.")


def test_tamper_evident_pdf_generation():
    print("[TEST 4] Testing Tamper-Evident Geotagged PDF Audit Generator...")
    compliance_engine = LegalMetrologyComplianceEngine()
    pdf_service = AuditPDFService()
    
    dec = PackagingDeclarations(
        product_name="Audit Tested Biscuit",
        generic_name="Biscuits",
        manufacturer_name="Test Food Corp",
        manufacturer_address="Industrial Area, New Delhi",
        net_quantity_value=100.0,
        net_quantity_unit="g",
        mrp_value=30.0,
        mrp_raw="MRP ₹ 30.00 (incl. of all taxes)",
        mrp_inclusive_taxes_mentioned=True,
        month_year_of_mfg="08/2026",
        consumer_care_phone="1800-000-1111",
        consumer_care_email="care@test.com"
    )
    report = compliance_engine.evaluate(dec)
    
    pdf_bytes = pdf_service.generate_pdf(
        inspection_ref="LM-TEST-AUDIT-007",
        report=report,
        product_name="Audit Tested Biscuit",
        brand="Test Food Corp",
        inspector_name="Inspector Amit Sharma",
        location="Connaught Place, Delhi",
        store_name="Super Mart",
        geo_lat=28.6328,
        geo_lng=77.2197,
        calibrated_ppm=5.2
    )
    assert len(pdf_bytes) > 1000, "PDF generation resulted in empty payload"
    assert pdf_bytes.startswith(b"%PDF"), "Output is not a valid PDF binary"
    
    # Check SHA-256 computation
    test_hash = calculate_tamper_proof_hash({"ref": "LM-TEST-AUDIT-007", "score": report.compliance_score})
    assert len(test_hash) == 64, "SHA-256 hash length mismatch"
    print(f"  -> Passed: Valid PDF generated ({len(pdf_bytes)} bytes) with SHA-256 audit hash {test_hash[:16]}...")


def test_b2b_pre_print_sandbox():
    print("[TEST 5] Testing B2B Pre-Print Artwork & Dieline Sandbox...")
    b2b_engine = B2BPrePrintSandboxEngine()
    dieline_img = Image.new("RGB", (1200, 900), color=(255, 255, 255))
    
    spec = DielineSpecification(
        dieline_width_mm=300.0,
        dieline_height_mm=225.0,
        pdp_width_mm=150.0,
        pdp_height_mm=200.0,  # PDP Area = 300 cm² (requires min 4.0 mm font per Schedule II)
        commodity_category="Snacks & Confectionery",
        target_net_quantity=200.0,
        target_unit="g",
        target_mrp=60.0,
        package_type="printed"
    )
    
    audit_res = b2b_engine.audit_dieline(dieline_img, spec)
    assert audit_res.pdp_area_cm2 == 300.0, f"PDP area error: {audit_res.pdp_area_cm2}"
    assert audit_res.required_min_font_mm == 4.0, f"Required font error: {audit_res.required_min_font_mm}"
    assert len(audit_res.findings) > 0, "No pre-print findings generated"
    print(f"  -> Passed: PDP Area = {audit_res.pdp_area_cm2} cm² | Req Min Font = {audit_res.required_min_font_mm} mm | Clearance = {audit_res.clearance_status}")


def test_fastapi_endpoints():
    print("[TEST 6] Testing FastAPI REST Endpoints & Route Definitions...")
    from api import app
    routes = [route.path for route in app.routes]
    expected_routes = [
        "/api/v1/rules/validate",
        "/api/v1/calibrate",
        "/api/v1/dewarp",
        "/api/v1/qr/harmonize",
        "/api/v1/audit/pdf",
        "/api/v1/b2b/pre-print",
        "/api/v1/inspections",
        "/api/v1/analytics"
    ]
    for r in expected_routes:
        assert r in routes, f"Missing route {r} in FastAPI app"
    print(f"  -> Passed: All {len(expected_routes)} statutory API endpoints registered successfully.")


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING ADVANCED LEGAL METROLOGY PIPELINE VERIFICATION SUITE")
    print("=" * 70)
    test_pixel_to_mm_calibration()
    test_3d_dewarping_and_spatial_ocr()
    test_hybrid_qr_harmonization()
    test_tamper_evident_pdf_generation()
    test_b2b_pre_print_sandbox()
    test_fastapi_endpoints()
    print("=" * 70)
    print("ALL ADVANCED SUBSYSTEM TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)
