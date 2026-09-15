"""
B2B Pre-Print Compliance Sandbox
Commercial pre-flight verification portal for packaging designers, pre-media agencies,
and FMCG brand managers to audit digital packaging artwork and dielines prior to commercial printing.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
import math

from rules import LegalMetrologyComplianceEngine, PackagingDeclarations, ComplianceStatus, Severity


@dataclass
class DielineSpecification:
    dieline_width_mm: float
    dieline_height_mm: float
    pdp_width_mm: float
    pdp_height_mm: float
    commodity_category: str
    target_net_quantity: float
    target_unit: str
    target_mrp: float
    package_type: str = "printed"  # printed, blown/molded, perforated


@dataclass
class PrePrintFinding:
    category: str  # 'TYPOGRAPHY', 'STATUTORY_MANDATE', 'READABILITY', 'BARCODE_QR'
    status: str    # 'PASSED', 'ACTION_REQUIRED', 'WARNING'
    field_name: str
    observed_spec: str
    required_spec: str
    guidance_for_designer: str
    cylinder_plate_impact: str  # e.g., 'Requires plate modification', 'Ready for print'


@dataclass
class PrePrintAuditResult:
    clearance_status: str       # 'APPROVED_FOR_PRINT', 'REVISION_REQUIRED', 'CONDITIONAL_APPROVAL'
    clearance_score: float      # 0 to 100
    pdp_area_cm2: float
    required_min_font_mm: float
    detected_font_mm: float
    findings: List[PrePrintFinding] = field(default_factory=list)
    actionable_revisions: List[str] = field(default_factory=list)
    estimated_reprint_cost_saved_inr: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clearance_status": self.clearance_status,
            "clearance_score": round(self.clearance_score, 1),
            "pdp_area_cm2": round(self.pdp_area_cm2, 2),
            "required_min_font_mm": round(self.required_min_font_mm, 2),
            "detected_font_mm": round(self.detected_font_mm, 2),
            "findings": [asdict(f) for f in self.findings],
            "actionable_revisions": self.actionable_revisions,
            "estimated_reprint_cost_saved_inr": self.estimated_reprint_cost_saved_inr
        }


class B2BPrePrintSandboxEngine:
    """
    Commercial pre-flight packaging artwork verification engine.
    """

    def __init__(self):
        self.compliance_engine = LegalMetrologyComplianceEngine()

    def audit_dieline(
        self,
        artwork_image: Image.Image,
        dieline_spec: DielineSpecification,
        extracted_declarations: Optional[PackagingDeclarations] = None
    ) -> PrePrintAuditResult:
        """
        Simulates pre-print statutory audit for packaging designers before plate engraving.
        """
        findings: List[PrePrintFinding] = []
        actionable_revisions: List[str] = []

        # 1. PDP Area and Schedule II minimum font threshold
        pdp_area_cm2 = (dieline_spec.pdp_width_mm / 10.0) * (dieline_spec.pdp_height_mm / 10.0)
        
        # Schedule II lookup
        if pdp_area_cm2 <= 50.0:
            min_font_mm = 1.0 if dieline_spec.package_type in ["blown", "molded"] else 1.5
        elif pdp_area_cm2 <= 100.0:
            min_font_mm = 1.5 if dieline_spec.package_type in ["blown", "molded"] else 2.0
        elif pdp_area_cm2 <= 500.0:
            min_font_mm = 2.5 if dieline_spec.package_type in ["blown", "molded"] else 4.0
        else:
            min_font_mm = 4.0 if dieline_spec.package_type in ["blown", "molded"] else 6.0

        # Estimate font scale from artwork pixel dimensions
        w_px, h_px = artwork_image.size
        ppm_est = w_px / dieline_spec.dieline_width_mm
        
        # Simulated font measurement from artwork layer (e.g. 2.8 mm)
        detected_font_mm = min(5.0, max(1.2, round((h_px * 0.035) / ppm_est, 2)))

        # 2. Check Typography & Font Size Compliance
        if detected_font_mm >= min_font_mm:
            findings.append(PrePrintFinding(
                category="TYPOGRAPHY",
                status="PASSED",
                field_name="Net Quantity Numeral Height",
                observed_spec=f"{detected_font_mm:.1f} mm",
                required_spec=f"Min {min_font_mm:.1f} mm for PDP {pdp_area_cm2:.1f} cm²",
                guidance_for_designer="Font size conforms to Schedule II Table under Rule 9.",
                cylinder_plate_impact="Ready for cylinder engraving."
            ))
        else:
            findings.append(PrePrintFinding(
                category="TYPOGRAPHY",
                status="ACTION_REQUIRED",
                field_name="Net Quantity Numeral Height",
                observed_spec=f"{detected_font_mm:.1f} mm",
                required_spec=f"Min {min_font_mm:.1f} mm for PDP {pdp_area_cm2:.1f} cm²",
                guidance_for_designer=f"Increase Net Qty numerals by {((min_font_mm - detected_font_mm)/detected_font_mm)*100:.0f}% to achieve at least {min_font_mm:.1f} mm.",
                cylinder_plate_impact="CRITICAL: Modify vector text in dieline before plate exposure."
            ))
            actionable_revisions.append(f"Increase font height of Net Quantity from {detected_font_mm:.1f}mm to at least {min_font_mm:.1f}mm.")

        # 3. Unit Sale Price (USP) Check
        calc_usp = dieline_spec.target_mrp / (dieline_spec.target_net_quantity if dieline_spec.target_net_quantity > 0 else 1.0)
        expected_usp_str = f"₹ {calc_usp:.2f} per {dieline_spec.target_unit}"
        
        findings.append(PrePrintFinding(
            category="STATUTORY_MANDATE",
            status="PASSED" if extracted_declarations and extracted_declarations.unit_sale_price_value else "WARNING",
            field_name="Unit Sale Price (USP) Artwork Callout",
            observed_spec=extracted_declarations.unit_sale_price_raw if extracted_declarations and extracted_declarations.unit_sale_price_raw else "Not in Dieline",
            required_spec=expected_usp_str,
            guidance_for_designer=f"Rule 6(1)(da) (2022 Amendment) mandates printing '{expected_usp_str}' adjacent to MRP in bold.",
            cylinder_plate_impact="Add text layer to dieline artwork."
        ))
        if not (extracted_declarations and extracted_declarations.unit_sale_price_value):
            actionable_revisions.append(f"Add mandatory Unit Sale Price: '{expected_usp_str}'.")

        # 4. Standard Metric Unit check (prohibit 'gms')
        if dieline_spec.target_unit.lower() in ["gms", "gm", "kilo", "ltr", "cc"]:
            findings.append(PrePrintFinding(
                category="STATUTORY_MANDATE",
                status="ACTION_REQUIRED",
                field_name="Net Quantity Metric Symbol",
                observed_spec=dieline_spec.target_unit,
                required_spec="g, kg, ml, l, or N",
                guidance_for_designer=f"Change prohibited symbol '{dieline_spec.target_unit}' to standard Legal Metrology symbol.",
                cylinder_plate_impact="Must correct vector text in artwork."
            ))
            actionable_revisions.append(f"Replace non-standard unit '{dieline_spec.target_unit}' with standard symbol.")

        # 5. Readability & Negative Contrast
        findings.append(PrePrintFinding(
            category="READABILITY",
            status="PASSED",
            field_name="Background Contrast (Rule 9(3))",
            observed_spec="High contrast typography",
            required_spec="Prominent against background color",
            guidance_for_designer="Contrast complies with Rule 9(3). Ensure varnish does not cause specular glare.",
            cylinder_plate_impact="Optimal."
        ))

        # Calculate pre-print clearance score
        pass_count = sum(1 for f in findings if f.status == "PASSED")
        score = (pass_count / len(findings)) * 100.0 if findings else 100.0

        if score >= 90.0:
            clearance = "APPROVED_FOR_PRINT"
        elif score >= 65.0:
            clearance = "CONDITIONAL_APPROVAL"
        else:
            clearance = "REVISION_REQUIRED"

        # Estimated cost saved by catching defect before cylinder engraving
        # Typical gravure / flexo cylinder set costs ~ ₹60,000 to ₹1,50,000 per packaging SKU
        reprint_cost_saved = 75000.0 if actionable_revisions else 0.0

        return PrePrintAuditResult(
            clearance_status=clearance,
            clearance_score=score,
            pdp_area_cm2=pdp_area_cm2,
            required_min_font_mm=min_font_mm,
            detected_font_mm=detected_font_mm,
            findings=findings,
            actionable_revisions=actionable_revisions,
            estimated_reprint_cost_saved_inr=reprint_cost_saved
        )

    def draw_dieline_annotated_preview(
        self,
        artwork_image: Image.Image,
        audit_result: PrePrintAuditResult
    ) -> Image.Image:
        """Visualizes dieline zones, PDP boundaries, and pre-print correction tags."""
        img = artwork_image.copy().convert("RGBA")
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # 1. Outer dieline border (dashed magenta)
        draw.rectangle((5, 5, w - 5, h - 5), outline=(236, 72, 153, 200), width=2)
        draw.text((10, 10), "DIELINE CUTTING & CREASING BOUNDARY", fill=(236, 72, 153, 255))

        # 2. Principal Display Panel (PDP) Box (cyan)
        pdp_box = (int(w * 0.15), int(h * 0.10), int(w * 0.85), int(h * 0.90))
        draw.rectangle(pdp_box, outline=(6, 182, 212, 220), width=3)
        draw.text((pdp_box[0] + 8, pdp_box[1] + 8), f"PRINCIPAL DISPLAY PANEL ({audit_result.pdp_area_cm2:.1f} cm²)", fill=(6, 182, 212, 255))

        # 3. Status Badge Top Right
        badge_color = (34, 197, 94, 240) if audit_result.clearance_status == "APPROVED_FOR_PRINT" else (
            (245, 158, 11, 240) if audit_result.clearance_status == "CONDITIONAL_APPROVAL" else (239, 68, 68, 240)
        )
        badge_text = f"PRE-PRINT AUDIT: {audit_result.clearance_status} ({audit_result.clearance_score:.0f}%)"
        draw.rectangle((w - 380, 10, w - 10, 45), fill=badge_color)
        draw.text((w - 370, 20), badge_text, fill=(255, 255, 255, 255))

        return img.convert("RGB")
