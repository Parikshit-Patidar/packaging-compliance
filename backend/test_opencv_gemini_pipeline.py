"""
Verification Test for OpenCV Preprocessing, Grounding & Zero-Hallucination Pipeline
"""

import sys
import os
import io
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))

from ocr_service import (
    OpenCVPackagingPreprocessor,
    PackagingDeclarationsSchema,
    extract_packaging_declarations,
    verify_grounding,
    create_synthetic_package_image
)
from rules import PackagingDeclarations


def test_opencv_preprocessor():
    print("[TEST 1] Testing OpenCVPackagingPreprocessor...")
    img = create_synthetic_package_image("compliant_biscuit")
    enhanced, roi_crop, roi_bbox, diagnostics = OpenCVPackagingPreprocessor.preprocess(img)

    assert enhanced is not None, "Enhanced image is None"
    assert "shadow_attenuated" in diagnostics, "Missing shadow attenuation flag"
    assert "glare_percentage" in diagnostics, "Missing glare percentage"
    assert "roi_detected" in diagnostics, "Missing roi_detected flag"
    print(f"  -> Enhanced size: {enhanced.size}")
    print(f"  -> ROI detected: {diagnostics['roi_detected']}, bbox: {roi_bbox}")
    print(f"  -> Diagnostics: {diagnostics}")
    if roi_crop:
        print(f"  -> Cropped ROI size: {roi_crop.size}")
    print("  -> Passed OpenCV preprocessing.")


def test_grounding_verification():
    print("[TEST 2] Testing verify_grounding logic...")
    dec = PackagingDeclarations(
        product_name="Sunfeast Marie Light",
        mrp_value=25.0,
        mrp_raw="₹ 25.00",
        net_quantity_value=120.0,
        net_quantity_unit="g",
        month_year_of_mfg="08/2026"
    )
    ocr_text = "Sunfeast Marie Light Biscuits MRP Rs. 25.00 Net Wt: 120 g Mfg: 08/2026 B.No: A12"
    report = verify_grounding(dec, ocr_text)

    assert report["is_grounded"] is True, "Expected grounded"
    assert report["grounding_score"] == 100.0, f"Expected 100.0, got {report['grounding_score']}"
    assert "Maximum Retail Price (MRP)" in report["verified_fields"]
    assert "Net Quantity" in report["verified_fields"]
    assert "Date of Manufacture" in report["verified_fields"]
    print(f"  -> Grounding report: {report}")
    print("  -> Passed Grounding Verification.")


def test_end_to_end_extraction():
    print("[TEST 3] Testing master extract_packaging_declarations with synthetic sample...")
    img = create_synthetic_package_image("compliant_biscuit")
    dec, transcript, engine = extract_packaging_declarations(img, force_local=False)

    print(f"  -> Engine used: {engine}")
    print(f"  -> Product Name: {dec.product_name}")
    print(f"  -> MRP: {dec.mrp_value} (raw: {dec.mrp_raw})")
    print(f"  -> Net Qty: {dec.net_quantity_value} {dec.net_quantity_unit}")
    print(f"  -> Mfg Date: {dec.month_year_of_mfg}")
    print(f"  -> ROI Base64 attached: {bool(getattr(dec, '_roi_crop_base64', None))}")
    print(f"  -> Grounding attached: {getattr(dec, '_grounding', None)}")
    print("  -> Passed End-to-End Extraction.")


if __name__ == "__main__":
    test_opencv_preprocessor()
    test_grounding_verification()
    test_end_to_end_extraction()
    print("\nALL OPENCV & GROUNDING TESTS COMPLETED SUCCESSFULLY!")
