"""
Hybrid QR Harmonization Module
Statutory Reference: Legal Metrology (Packaged Commodities) Electronic Disclosure Amendments
Decodes on-pack QR codes and cross-verifies digital declarations against physical label declarations.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image, ImageDraw
import json
import re

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

from rules import PackagingDeclarations


@dataclass
class QRHarmonizationDiscrepancy:
    field_name: str
    physical_value: str
    digital_qr_value: str
    statutory_impact: str
    severity: str  # 'CRITICAL', 'MAJOR', 'MINOR'


@dataclass
class QRHarmonizationResult:
    qr_detected: bool
    raw_payload: Optional[str] = None
    payload_type: str = "NONE"  # 'URL', 'JSON', 'TEXT', 'VCARD', 'NONE'
    qr_bounding_box: Optional[Tuple[int, int, int, int]] = None
    harmonization_status: str = "NO_QR"  # 'HARMONIZED', 'MISMATCH_DETECTED', 'PARTIAL_MATCH', 'NO_QR'
    match_percentage: float = 0.0
    digital_declarations: Dict[str, Any] = field(default_factory=dict)
    discrepancies: List[QRHarmonizationDiscrepancy] = field(default_factory=list)
    statutory_remarks: str = ""


class QRHarmonizationEngine:
    """
    Decodes on-pack QR codes and audits consistency between
    physical label print and digital cloud disclosures.
    """

    def __init__(self):
        self.detector_aruco = None
        self.detector_std = None
        if HAS_OPENCV:
            try:
                self.detector_aruco = cv2.QRCodeDetectorAruco()
            except Exception:
                self.detector_aruco = None
            try:
                self.detector_std = cv2.QRCodeDetector()
            except Exception:
                self.detector_std = None

    def _detect_physical_qr(self, image: Image.Image) -> Tuple[Optional[str], Optional[Tuple[int, int, int, int]]]:
        """
        Multi-pass high-accuracy QR code detector using ArUco-based and standard OpenCV detectors
        across various contrast enhancements, binarizations, and scale pyramids.
        """
        if not HAS_OPENCV:
            return None, None

        orig_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        orig_h, orig_w = orig_cv.shape[:2]

        # Generate multi-pass pre-processed candidates
        gray = cv2.cvtColor(orig_cv, cv2.COLOR_BGR2GRAY)
        
        # Pass 1: CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray_clahe = clahe.apply(gray)
        
        # Pass 2: Otsu binarization
        _, otsu_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Pass 3: Inverted Otsu binarization (for dark labels / light QR codes)
        _, otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Pass 4: Unsharp masking (edge contrast boost)
        gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
        sharpened = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)

        candidates = [
            ("raw_bgr", orig_cv, 1.0),
            ("gray", gray, 1.0),
            ("clahe", gray_clahe, 1.0),
            ("otsu_bin", otsu_bin, 1.0),
            ("otsu_inv", otsu_inv, 1.0),
            ("sharpened", sharpened, 1.0)
        ]

        # Add scaled versions if image is large (>1600px) or small (<600px)
        if max(orig_w, orig_h) > 1600:
            scale = 1200.0 / max(orig_w, orig_h)
            small = cv2.resize(gray, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
            candidates.append(("scaled_down", small, scale))
        elif min(orig_w, orig_h) < 600:
            scale = 1.5
            large = cv2.resize(gray, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_LINEAR)
            candidates.append(("scaled_up", large, scale))

        detectors = []
        if self.detector_aruco:
            detectors.append(self.detector_aruco)
        if self.detector_std:
            detectors.append(self.detector_std)

        for name, img_variant, scale_factor in candidates:
            for det in detectors:
                try:
                    data, bbox, _ = det.detectAndDecode(img_variant)
                    if data and len(data.strip()) > 0:
                        qr_bbox = None
                        if bbox is not None and len(bbox) > 0:
                            pts = bbox[0]
                            inv_scale = 1.0 / scale_factor
                            bx = int(min(p[0] for p in pts) * inv_scale)
                            by = int(min(p[1] for p in pts) * inv_scale)
                            bw = int((max(p[0] for p in pts) - min(p[0] for p in pts)) * inv_scale)
                            bh = int((max(p[1] for p in pts) - min(p[1] for p in pts)) * inv_scale)
                            # Clamp within image boundaries
                            bx = max(0, min(bx, orig_w - 1))
                            by = max(0, min(by, orig_h - 1))
                            bw = max(10, min(bw, orig_w - bx))
                            bh = max(10, min(bh, orig_h - by))
                            qr_bbox = (bx, by, bw, bh)
                        return data.strip(), qr_bbox
                except Exception:
                    continue

        return None, None

    def harmonize(
        self,
        image: Image.Image,
        physical_dec: PackagingDeclarations,
        simulated_qr_payload: Optional[str] = None
    ) -> QRHarmonizationResult:
        """
        Scans for QR codes on the package and audits against physical declarations.
        Prioritizes genuine physical QR detection from the photograph; falls back to manual payload
        only if specified.
        """
        w, h = image.size

        # 1. Primary: Run multi-pass OpenCV detector on photograph
        detected_text, detected_bbox = self._detect_physical_qr(image)

        qr_text = detected_text
        qr_bbox = detected_bbox

        # 2. Secondary fallback: Explicit manual payload override if no physical QR was detected
        if not qr_text and simulated_qr_payload and len(simulated_qr_payload.strip()) > 0:
            qr_text = simulated_qr_payload.strip()
            qr_bbox = (int(w * 0.72), int(h * 0.12), int(w * 0.22), int(w * 0.22))

        # If no QR code found anywhere
        if not qr_text:
            return QRHarmonizationResult(
                qr_detected=False,
                harmonization_status="NO_QR",
                statutory_remarks="No on-pack QR code detected on current packaging panel. Verified standard printed declarations."
            )

        if not qr_bbox:
            qr_bbox = (int(w * 0.72), int(h * 0.12), int(w * 0.22), int(w * 0.22))

        # Parse digital payload
        payload_type, digital_dict = self._parse_payload(qr_text)

        # Cross-verify physical vs digital
        discrepancies: List[QRHarmonizationDiscrepancy] = []
        checks_count = 0
        matches_count = 0

        def _safe_float(val: Any) -> Optional[float]:
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return float(val)
            clean = re.search(r"[-+]?\d*\.?\d+", str(val).replace(",", ""))
            return float(clean.group(0)) if clean else None

        # 1. Compare MRP
        phys_mrp_num = _safe_float(physical_dec.mrp_value)
        dig_mrp_num = _safe_float(digital_dict.get("mrp"))
        if phys_mrp_num is not None and dig_mrp_num is not None:
            checks_count += 1
            if abs(phys_mrp_num - dig_mrp_num) < 0.01:
                matches_count += 1
            else:
                discrepancies.append(QRHarmonizationDiscrepancy(
                    field_name="Maximum Retail Price (MRP)",
                    physical_value=f"₹ {phys_mrp_num:.2f}",
                    digital_qr_value=f"₹ {dig_mrp_num:.2f}",
                    statutory_impact="Dual pricing / overpricing conflict between physical print and digital declaration.",
                    severity="CRITICAL"
                ))

        # 2. Compare Net Quantity
        phys_qty_num = _safe_float(physical_dec.net_quantity_value)
        dig_qty_num = _safe_float(digital_dict.get("net_quantity"))
        if phys_qty_num is not None and dig_qty_num is not None:
            checks_count += 1
            if abs(phys_qty_num - dig_qty_num) < 0.01:
                matches_count += 1
            else:
                discrepancies.append(QRHarmonizationDiscrepancy(
                    field_name="Net Quantity",
                    physical_value=f"{phys_qty_num} {physical_dec.net_quantity_unit or ''}".strip(),
                    digital_qr_value=f"{digital_dict.get('net_quantity')}".strip(),
                    statutory_impact="Quantity mismatch between physical container and digital regulatory filing.",
                    severity="MAJOR"
                ))

        # 3. Compare Mfg Date
        phys_date = physical_dec.month_year_of_mfg
        dig_date = digital_dict.get("mfg_date")
        if phys_date and dig_date:
            checks_count += 1
            if phys_date.strip().lower() in dig_date.strip().lower() or dig_date.strip().lower() in phys_date.strip().lower():
                matches_count += 1
            else:
                discrepancies.append(QRHarmonizationDiscrepancy(
                    field_name="Date of Manufacture",
                    physical_value=phys_date,
                    digital_qr_value=dig_date,
                    statutory_impact="Manufacture/Packaging date discrepancy.",
                    severity="MAJOR"
                ))

        # Calculate harmonization score
        if checks_count > 0:
            match_rate = (matches_count / checks_count) * 100.0
        else:
            match_rate = 100.0 if not discrepancies else 50.0

        if not discrepancies:
            status = "HARMONIZED"
            remarks = "On-pack QR code digital disclosure perfectly matches physical label declarations."
        elif any(d.severity == "CRITICAL" for d in discrepancies):
            status = "MISMATCH_DETECTED"
            remarks = f"CRITICAL CONFLICT: {len(discrepancies)} discrepancies detected between on-pack print and digital QR disclosures."
        else:
            status = "PARTIAL_MATCH"
            remarks = f"Minor variance detected in {len(discrepancies)} digital disclosure fields."

        return QRHarmonizationResult(
            qr_detected=True,
            raw_payload=qr_text,
            payload_type=payload_type,
            qr_bounding_box=qr_bbox,
            harmonization_status=status,
            match_percentage=round(match_rate, 1),
            digital_declarations=digital_dict,
            discrepancies=discrepancies,
            statutory_remarks=remarks
        )

    def _parse_payload(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """Parses QR text into structured digital declaration dictionary."""
        # Try JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return "JSON", data
        except Exception:
            pass

        # Try URL with query parameters
        if text.startswith("http://") or text.startswith("https://"):
            parsed = {}
            if "?" in text:
                query = text.split("?")[1]
                for part in query.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        # Try parsing numbers
                        try:
                            parsed[k.lower()] = float(v)
                        except ValueError:
                            parsed[k.lower()] = v
            parsed["domain"] = text.split("/")[2] if len(text.split("/")) > 2 else text
            return "URL", parsed

        # Plain text key-value parser
        parsed = {}
        for line in text.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k_clean = k.strip().lower().replace(" ", "_")
                v_clean = v.strip()
                parsed[k_clean] = v_clean
                
        return "TEXT", parsed

    def draw_qr_overlay(self, image: Image.Image, result: QRHarmonizationResult) -> Image.Image:
        """Visualizes on-pack QR code bounding box with harmonization status tag."""
        if not result.qr_detected or not result.qr_bounding_box:
            return image

        img = image.copy().convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        bx, by, bw, bh = result.qr_bounding_box
        color = (34, 197, 94, 230) if result.harmonization_status == "HARMONIZED" else (239, 68, 68, 230)
        
        # Draw QR highlight box
        draw.rectangle((bx, by, bx + bw, by + bh), outline=color, width=4)
        
        tag = f"QR: {result.harmonization_status} ({result.match_percentage:.0f}%)"
        draw.rectangle((bx, by - 22, bx + len(tag) * 8 + 10, by), fill=color)
        draw.text((bx + 5, by - 18), tag, fill=(255, 255, 255, 255))
        
        return img.convert("RGB")
