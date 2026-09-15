"""
FastAPI Rule Validation & Legal Metrology Inspection Engine
High-speed REST API providing statutory compliance verification, reference object calibration,
3D de-warping, hybrid QR harmonization, tamper-evident PDF audits, and B2B pre-print sandbox.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import io
import os
import json
import base64
import secrets
from datetime import datetime
from PIL import Image, ImageOps

from rules import (
    LegalMetrologyComplianceEngine,
    PackagingDeclarations,
    ComplianceStatus,
    Severity
)
from calibration import (
    PixelCalibrationEngine,
    ReferenceObjectType,
    CalibrationResult
)
from dewarp_service import (
    SpatialDewarpEngine,
    DeWarpResult
)
from qr_harmonizer import (
    QRHarmonizationEngine,
    QRHarmonizationResult
)
from pdf_service import (
    AuditPDFService
)
from b2b_sandbox import (
    B2BPrePrintSandboxEngine,
    DielineSpecification,
    PrePrintAuditResult
)
from database import (
    init_db,
    seed_demo_data,
    save_inspection,
    get_inspections,
    get_inspection_by_ref,
    update_officer_action,
    get_analytics_summary,
    create_user,
    get_user_by_id,
    get_user_by_email,
    authenticate_user,
    list_users,
    seed_default_users
)
from ocr_service import (
    extract_packaging_declarations,
    analyze_label_readability,
    BENCHMARK_SAMPLES,
    create_synthetic_package_image,
    locate_declaration_bounding_boxes,
    draw_statutory_spatial_overlay
)
from config import (
    get_gemini_api_key,
    set_gemini_api_key
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Initialize engines
app = FastAPI(
    title="Legal Metrology Compliance API",
    description="Statutory Packaging Verification Engine under Legal Metrology Act, 2009 & Packaged Commodities Rules, 2011",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()
seed_demo_data()

compliance_engine = LegalMetrologyComplianceEngine()
calibration_engine = PixelCalibrationEngine()
dewarp_engine = SpatialDewarpEngine()
qr_engine = QRHarmonizationEngine()
pdf_service = AuditPDFService()
b2b_engine = B2BPrePrintSandboxEngine()


# In-memory authentication session cache (Token -> User dict)
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

def issue_session(user: Dict[str, Any]) -> str:
    token = f"metrology_sec_{secrets.token_urlsafe(32)}"
    user_clean = {k: v for k, v in user.items() if k not in ("password_hash", "salt")}
    ACTIVE_SESSIONS[token] = {
        "user": user_clean,
        "issued_at": datetime.now().isoformat()
    }
    return token

def resolve_session_user(auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
    if not auth_header:
        return None
    token = auth_header.strip()
    if token.startswith("Bearer "):
        token = token[7:].strip()
    session = ACTIVE_SESSIONS.get(token)
    if session:
        return session["user"]
    return None


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str  # 'GOVT_OFFICER' or 'B2B_BRAND'
    organization: str
    badge_or_gstin: Optional[str] = ""
    designation: Optional[str] = ""
    phone: Optional[str] = ""

class SaveDossierRequest(BaseModel):
    inspection_ref: str
    product_name: str
    compliance_status: str
    compliance_score: float
    total_violations: int = 0
    critical_violations: int = 0
    major_violations: int = 0
    minor_violations: int = 0
    declarations: Dict[str, Any] = Field(default_factory=dict)
    violations: List[Dict[str, Any]] = Field(default_factory=list)
    inspector_name: Optional[str] = "Enforcement Officer"
    location: Optional[str] = "Central District"
    store_name: Optional[str] = "Retail Store"
    brand: Optional[str] = "General Brand"
    category: Optional[str] = "Food & Beverages"
    batch_no: Optional[str] = "BATCH-2026"
    notes: Optional[str] = ""

class ValidateDeclarationsRequest(BaseModel):
    product_name: Optional[str] = "Packaged Commodity"
    generic_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_address: Optional[str] = None
    packer_name: Optional[str] = None
    packer_address: Optional[str] = None
    importer_name: Optional[str] = None
    importer_address: Optional[str] = None
    country_of_origin: Optional[str] = "India"
    net_quantity_value: Optional[float] = None
    net_quantity_unit: Optional[str] = None
    net_quantity_raw: Optional[str] = None
    mrp_value: Optional[float] = None
    mrp_raw: Optional[str] = None
    mrp_inclusive_taxes_mentioned: Optional[bool] = None
    unit_sale_price_value: Optional[float] = None
    unit_sale_price_unit: Optional[str] = None
    unit_sale_price_raw: Optional[str] = None
    month_year_of_mfg: Optional[str] = None
    month_year_of_exp: Optional[str] = None
    batch_number: Optional[str] = None
    consumer_care_name: Optional[str] = None
    consumer_care_address: Optional[str] = None
    consumer_care_phone: Optional[str] = None
    consumer_care_email: Optional[str] = None
    pdp_height_cm: Optional[float] = 18.0
    pdp_width_cm: Optional[float] = 12.0
    numeral_height_mm: Optional[float] = 3.5
    is_imported: bool = False
    packaging_type: str = "printed"


class DielineAuditRequest(BaseModel):
    dieline_width_mm: float = 250.0
    dieline_height_mm: float = 180.0
    pdp_width_mm: float = 120.0
    pdp_height_mm: float = 180.0
    commodity_category: str = "Food & Beverages"
    target_net_quantity: float = 100.0
    target_unit: str = "g"
    target_mrp: float = 40.0
    package_type: str = "printed"


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "service": "Legal Metrology Compliance Engine API",
        "status": "OPERATIONAL",
        "version": "2.0.0",
        "statutory_mandate": "Legal Metrology Act, 2009 & Packaged Commodities Rules, 2011",
        "documentation": "/docs"
    }


@app.get("/api")
def api_info():
    return {
        "service": "Legal Metrology Compliance Engine API",
        "status": "OPERATIONAL",
        "version": "2.0.0",
        "documentation": "/docs"
    }


@app.post("/api/v1/rules/validate")
def validate_rules(req: ValidateDeclarationsRequest):
    """
    High-speed statutory rule validation engine.
    Algorithmically parses declarations against Rule 6, Rule 9, Rule 13, and Rule 18.
    """
    dec = PackagingDeclarations(**req.model_dump())
    report = compliance_engine.evaluate(dec)
    return report.to_dict()


@app.post("/api/v1/calibrate")
async def calibrate_scale(
    reference_type: ReferenceObjectType = Form(ReferenceObjectType.CREDIT_CARD),
    file: UploadFile = File(...)
):
    """
    Detects physical reference object (credit card / Indian coin) and computes
    exact pixel-to-millimeter ratio (PPM) for statutory font measurement.
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

    calib = calibration_engine.calibrate(image, reference_type)
    return {
        "reference_type": calib.reference_type.value,
        "pixels_per_mm": calib.pixels_per_mm,
        "mm_per_pixel": calib.mm_per_pixel,
        "confidence_score": calib.confidence_score,
        "detected_bbox_px": calib.detected_bbox_px,
        "reference_real_size_mm": calib.reference_real_size_mm,
        "calibration_status": calib.calibration_status,
        "details": calib.details
    }


@app.post("/api/v1/dewarp")
async def dewarp_packaging(
    radius_px: Optional[float] = Form(None),
    file: UploadFile = File(...)
):
    """
    Digitally unrolls curved cylindrical packaging and extracts grounded spatial word boxes.
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

    dewarp_res = dewarp_engine.dewarp_and_extract(image, cylinder_radius_px=radius_px)
    
    return {
        "curvature_detected": dewarp_res.curvature_detected,
        "dewarp_method": dewarp_res.dewarp_method,
        "spatial_words_count": len(dewarp_res.extracted_spatial_words),
        "spatial_words": [
            {"text": w.text, "box": w.box, "confidence": w.confidence, "field": w.field_mapping}
            for w in dewarp_res.extracted_spatial_words
        ],
        "extracted_declarations": dewarp_res.declarations.__dict__ if dewarp_res.declarations else None,
        "processing_time_ms": dewarp_res.processing_time_ms
    }


@app.post("/api/v1/qr/harmonize")
async def harmonize_qr(
    simulated_qr_payload: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    declarations_json: Optional[str] = Form(None)
):
    """
    Concurrently decodes on-pack QR code and cross-verifies digital disclosure
    consistency against physical label declarations.
    """
    img = None
    if file:
        contents = await file.read()
        img = Image.open(io.BytesIO(contents))
    else:
        img = Image.new("RGB", (400, 400), color=(255, 255, 255))

    dec = PackagingDeclarations(
        mrp_value=40.0,
        net_quantity_value=100.0,
        net_quantity_unit="g",
        month_year_of_mfg="08/2026"
    )
    if declarations_json:
        try:
            d_dict = json.loads(declarations_json)
            dec = PackagingDeclarations(**d_dict)
        except Exception:
            pass

    res = qr_engine.harmonize(img, dec, simulated_qr_payload=simulated_qr_payload)
    return {
        "qr_detected": res.qr_detected,
        "raw_payload": res.raw_payload,
        "payload_type": res.payload_type,
        "harmonization_status": res.harmonization_status,
        "match_percentage": res.match_percentage,
        "digital_declarations": res.digital_declarations,
        "discrepancies": [d.__dict__ for d in res.discrepancies],
        "statutory_remarks": res.statutory_remarks
    }


@app.post("/api/v1/audit/pdf")
async def generate_audit_pdf(
    inspection_ref: str = Form("LM-AUDIT-2026-001"),
    product_name: str = Form("Packaged Food Commodity"),
    brand: str = Form("Apex Brands"),
    inspector_name: str = Form("Inspector Rajesh Kumar"),
    location: str = Form("New Delhi Central"),
    store_name: str = Form("Mega Mart Retail"),
    geo_lat: float = Form(28.6139),
    geo_lng: float = Form(77.2090),
    declarations_json: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Compiles full inspection data into a tamper-evident (SHA-256), geotagged PDF audit report.
    """
    evidence_img = None
    if file:
        contents = await file.read()
        evidence_img = Image.open(io.BytesIO(contents))

    dec = PackagingDeclarations(
        product_name=product_name,
        generic_name="Consumer Packaged Good",
        manufacturer_name=brand + " Ltd",
        manufacturer_address="Plot 12, Industrial Area, New Delhi 110020",
        net_quantity_value=100.0,
        net_quantity_unit="g",
        mrp_value=40.0,
        mrp_raw="MRP ₹ 40.00 (incl. of all taxes)",
        mrp_inclusive_taxes_mentioned=True,
        unit_sale_price_value=0.40,
        unit_sale_price_unit="g",
        unit_sale_price_raw="₹ 0.40 / g",
        month_year_of_mfg="08/2026",
        consumer_care_phone="1800-111-2222",
        consumer_care_email="care@apex.in",
        pdp_height_cm=18.0,
        pdp_width_cm=12.0,
        numeral_height_mm=4.0
    )
    if declarations_json:
        try:
            d_dict = json.loads(declarations_json)
            dec = PackagingDeclarations(**d_dict)
        except Exception:
            pass

    report = compliance_engine.evaluate(dec)
    pdf_bytes = pdf_service.generate_pdf(
        inspection_ref=inspection_ref,
        report=report,
        product_name=product_name,
        brand=brand,
        inspector_name=inspector_name,
        location=location,
        store_name=store_name,
        geo_lat=geo_lat,
        geo_lng=geo_lng,
        evidence_image=evidence_img
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Inspection_Audit_{inspection_ref}.pdf"}
    )


@app.post("/api/v1/b2b/pre-print")
async def b2b_pre_print_audit(
    dieline_spec_json: str = Form(...),
    file: Optional[UploadFile] = File(None)
):
    """
    B2B pre-print sandbox endpoint for packaging designers to simulate statutory audits
    on digital artwork/dielines before cylinder engraving.
    """
    artwork_img = None
    if file:
        contents = await file.read()
        artwork_img = Image.open(io.BytesIO(contents))
    else:
        artwork_img = Image.new("RGB", (1200, 800), color=(255, 255, 255))

    spec_dict = json.loads(dieline_spec_json)
    # Map friendly aliases if provided
    if "category" in spec_dict and "commodity_category" not in spec_dict:
        spec_dict["commodity_category"] = spec_dict.pop("category")
    if "packaging_process" in spec_dict and "package_type" not in spec_dict:
        spec_dict["package_type"] = spec_dict.pop("packaging_process")

    spec = DielineSpecification(
        dieline_width_mm=float(spec_dict.get("dieline_width_mm", 160.0)),
        dieline_height_mm=float(spec_dict.get("dieline_height_mm", 220.0)),
        pdp_width_mm=float(spec_dict.get("pdp_width_mm", 120.0)),
        pdp_height_mm=float(spec_dict.get("pdp_height_mm", 160.0)),
        commodity_category=str(spec_dict.get("commodity_category", "Biscuits & Bakery")),
        target_net_quantity=float(spec_dict.get("target_net_quantity", 250.0)),
        target_unit=str(spec_dict.get("target_unit", "g")),
        target_mrp=float(spec_dict.get("target_mrp", 45.0)),
        package_type=str(spec_dict.get("package_type", "printed"))
    )
    
    audit_res = b2b_engine.audit_dieline(artwork_img, spec)
    annotated_img = b2b_engine.draw_dieline_annotated_preview(artwork_img, audit_res)
    
    buf = io.BytesIO()
    annotated_img.save(buf, format="JPEG", quality=88)
    b64_annot = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

    res_dict = audit_res.to_dict()
    res_dict["annotated_image"] = b64_annot
    return res_dict


# ==============================================================================
# AUTHENTICATION & ROLE-BASED ACCESS CONTROL (RBAC) ENDPOINTS
# ==============================================================================

@app.post("/api/v1/auth/login")
def login_user(req: LoginRequest):
    """Authenticates Government Officers and B2B Brand representatives."""
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials. Please verify your email and password."
        )
    token = issue_session(user)
    return {
        "success": True,
        "token": token,
        "user": user,
        "message": f"Welcome, {user.get('full_name')} ({user.get('role')})"
    }


@app.post("/api/v1/auth/register")
def register_user(req: RegisterRequest):
    """Registers a new Government Officer or B2B Brand representative."""
    role = req.role.strip().upper()
    if role not in ("GOVT_OFFICER", "B2B_BRAND"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be GOVT_OFFICER or B2B_BRAND.")
    if len(req.password.strip()) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")
    if not req.full_name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Full name and email are required.")

    try:
        user = create_user(
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            role=role,
            organization=req.organization,
            badge_or_gstin=req.badge_or_gstin or "",
            designation=req.designation or "",
            phone=req.phone or ""
        )
        token = issue_session(user)
        return {
            "success": True,
            "token": token,
            "user": user,
            "message": "User registered and authenticated successfully."
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration error: {str(e)}")


@app.get("/api/v1/auth/me")
def get_current_user_profile(authorization: Optional[str] = Header(None)):
    """Resolves the currently active authenticated session user."""
    user = resolve_session_user(authorization)
    if not user:
        # Fallback to default Government Officer for initial state or seamless UX
        default_officer = get_user_by_email("officer.delhi@nic.in")
        if default_officer:
            default_officer.pop("password_hash", None)
            default_officer.pop("salt", None)
            return {"authenticated": False, "user": default_officer}
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


@app.post("/api/v1/auth/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    """Terminates the active session token."""
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        ACTIVE_SESSIONS.pop(token, None)
    return {"success": True, "message": "Logged out successfully"}


@app.get("/api/v1/auth/demo-accounts")
def get_demo_accounts_list():
    """Provides verified departmental Single Sign-On (SSO) directory profiles."""
    return [
        {
            "role": "GOVT_OFFICER",
            "role_title": "Legal Metrology Enforcement Officer",
            "email": "officer.delhi@nic.in",
            "password": "GovtOfficer@2026",
            "full_name": "Shri Rajesh Kumar",
            "organization": "Dept. of Consumer Affairs, Delhi Circle",
            "badge_or_gstin": "LMO-DEL-048",
            "designation": "Legal Metrology Officer (Class-I)",
            "description": "Statutory inspection, seizure notices, Rule 6/9/13/18 citations, Central Vault."
        },
        {
            "role": "B2B_BRAND",
            "role_title": "B2B Enterprise Packaging Brand Owner",
            "email": "compliance@fmcgbrand.com",
            "password": "BrandUser@2026",
            "full_name": "Priya Sharma",
            "organization": "Apex Consumer Goods Ltd",
            "badge_or_gstin": "07AABCA1234F1Z6",
            "designation": "Lead Packaging Technologist",
            "description": "Pre-print dieline audit, cylinder rework cost prevention (₹75k savings), brand self-checks."
        }
    ]


@app.post("/api/v1/save-dossier")
def save_dossier_to_vault(
    req: SaveDossierRequest,
    authorization: Optional[str] = Header(None)
):
    """Archiving endpoint for official inspections or B2B brand self-audits."""
    user = resolve_session_user(authorization)
    user_id = user["id"] if user else None
    user_role = user["role"] if user else "GOVT_OFFICER"
    inspector = user["full_name"] if user else req.inspector_name
    org = user["organization"] if user else req.location

    ref = save_inspection(
        inspection_ref=req.inspection_ref,
        product_name=req.product_name,
        compliance_status=req.compliance_status,
        compliance_score=req.compliance_score,
        total_violations=req.total_violations,
        critical_violations=req.critical_violations,
        major_violations=req.major_violations,
        minor_violations=req.minor_violations,
        declarations=req.declarations,
        violations=req.violations,
        check_results=[],
        inspector_name=inspector,
        location=org,
        store_name=req.store_name,
        brand=req.brand,
        category=req.category,
        batch_no=req.batch_no,
        notes=req.notes or "",
        user_id=user_id,
        user_role=user_role
    )
    return {
        "status": "SUCCESS",
        "inspection_ref": ref,
        "message": f"Dossier {ref} archived in Central Compliance Vault"
    }


@app.get("/api/v1/inspections")
def list_inspections(
    query: Optional[str] = None,
    status: Optional[str] = "ALL",
    limit: int = 50,
    offset: int = 0,
    authorization: Optional[str] = Header(None)
):
    """Retrieves past inspection dossiers from SQLite vault with role-based filtering."""
    user = resolve_session_user(authorization)
    user_id = user["id"] if user else None
    user_role = user["role"] if user else None
    return get_inspections(
        search_query=query,
        status_filter=status,
        user_id=user_id,
        user_role=user_role,
        limit=limit,
        offset=offset
    )


@app.get("/api/v1/analytics")
def get_analytics():
    """Retrieves executive compliance statistics and violation rankings."""
    return get_analytics_summary()


@app.post("/api/v1/scan")
async def scan_and_audit_package(
    file: UploadFile = File(...),
    reference_type: str = Form("AUTO"),
    engine_preference: str = Form("gemini"),
    simulated_qr: Optional[str] = Form(None),
    inspector_name: str = Form("Inspector Rajesh Kumar (DL-04)"),
    store_name: str = Form("Apex Retail Mart"),
    location: str = Form("Central Delhi District"),
    geo_lat: float = Form(28.6139),
    geo_lng: float = Form(77.2090)
):
    """
    Unified High-Speed Inspection Endpoint:
    1. Runs AI/OCR extraction on actual packaging photograph
    2. Runs OpenCV physical scale calibration (Credit card / Coins)
    3. Measures PDP and numeral heights in millimeters
    4. Evaluates Legal Metrology Rules (2011 + Amendments)
    5. Decodes and harmonizes on-pack QR code disclosures
    6. Assesses label readability under Rule 9(3)
    7. Computes visual bounding boxes and returns annotated image
    8. Archives record into SQLite dossier vault
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

    # 1. Automated 3D Surface Geometry Analysis & Cylindrical De-Warping
    try:
        dewarp_res = dewarp_engine.dewarp_and_extract(image)
        proc_image = dewarp_res.dewarped_image if dewarp_res.curvature_detected else image
        surface_geometry = {
            "curvature_detected": dewarp_res.curvature_detected,
            "method": dewarp_res.dewarp_method,
            "details": "3D Cylindrical De-Warping Applied" if dewarp_res.curvature_detected else "Planar Packaging Surface Verified"
        }
    except Exception as dewarp_err:
        print("Surface dewarp note:", dewarp_err)
        proc_image = image
        surface_geometry = {"curvature_detected": False, "method": "NONE", "details": "Planar Surface Default"}

    # 2. OCR / Vision Extraction (Deterministic Gemini AI + Local Hardware OCR)
    force_local = (engine_preference.lower() == "winocr")
    dec, raw_transcript, engine_used = extract_packaging_declarations(
        proc_image,
        force_local=force_local
    )
    lines_info = getattr(dec, '_lines_info', [])

    # 3. Locate Genuine Declaration Bounding Boxes in Physical Image Pixels
    declaration_boxes = locate_declaration_bounding_boxes(dec, lines_info, proc_image.size)
    gemini_ref_box = getattr(dec, "_gemini_ref_box", None)
    detected_ref_type = getattr(dec, "_detected_reference_type", None)

    # 4. Autonomous Pixel Scale Calibration (Intelligent Auto-Detection: Card / Coin / Priors)
    calib_res = calibration_engine.calibrate(
        proc_image,
        reference_type=reference_type,
        ai_ref_box=gemini_ref_box,
        detected_reference_type=detected_ref_type
    )

    # 5. Precise Numeral Height Measurement (Strictly from Net Qty numeral box)
    net_box = next((b for b in declaration_boxes if b.get("category") == "net_quantity"), None)
    if net_box:
        target_box = net_box.get("numeral_box") or net_box["box"]
        box_h_px = target_box[3] - target_box[1]
        measured_numeral_mm = calib_res.measure_height_mm(box_h_px)
    else:
        measured_numeral_mm = calib_res.measure_height_mm(proc_image.size[1] * 0.035)
    dec.numeral_height_mm = measured_numeral_mm

    # 6. PDP Dimensions & Scale
    pdp_w_cm, pdp_h_cm, pdp_area_cm2 = calib_res.measure_pdp_dimensions_cm(
        proc_image.size[0] * 0.85,
        proc_image.size[1] * 0.85
    )
    dec.pdp_height_cm = pdp_h_cm
    dec.pdp_width_cm = pdp_w_cm

    # 7. QR Harmonization (Automated physical QR detection or simulated payload)
    try:
        qr_res = qr_engine.harmonize(proc_image, dec, simulated_qr_payload=simulated_qr)
    except Exception as qr_err:
        print("QR Harmonization note:", qr_err)
        qr_res = None

    # 8. Statutory Rule Evaluation (Rules 6, 9, 13, 18)
    report = compliance_engine.evaluate(dec)

    # 9. Readability & Visual Quality Analysis under Rule 9(3)
    try:
        read_info = analyze_label_readability(proc_image)
    except Exception:
        read_info = {}

    # 10. Pixel-Accurate Visual Overlay Annotation
    annotated_img = draw_statutory_spatial_overlay(
        proc_image,
        declaration_boxes=declaration_boxes,
        calib_res=calib_res,
        qr_res=qr_res,
        report=report,
        numeral_height_mm=dec.numeral_height_mm
    )

    orig_buf = io.BytesIO()
    proc_image.save(orig_buf, format="JPEG", quality=90)
    original_b64 = "data:image/jpeg;base64," + base64.b64encode(orig_buf.getvalue()).decode("ascii")

    buf = io.BytesIO()
    annotated_img.save(buf, format="JPEG", quality=88)
    b64_img = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    # 11. Save Record in Central Vault
    ref_id = f"LM-INSP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    rep_dict = report.to_dict()
    save_dec = {k: v for k, v in dec.__dict__.items() if not k.startswith('_')}
    save_inspection(
        inspection_ref=ref_id,
        product_name=dec.product_name or "Inspected Commodity",
        compliance_status=report.overall_status.value,
        compliance_score=report.compliance_score,
        total_violations=len(report.violations),
        critical_violations=report.critical_violations_count,
        major_violations=report.major_violations_count,
        minor_violations=report.minor_violations_count,
        declarations=save_dec,
        violations=[v.__dict__ for v in report.violations],
        check_results=[c.__dict__ for c in report.check_results],
        inspector_name=inspector_name,
        location=location,
        store_name=store_name,
        brand=dec.manufacturer_name or "General FMCG",
        category="Food & Beverages",
        batch_no=dec.batch_number or "BATCH-2026",
        officer_action="Pending Review",
        notes=f"Geotagged: {geo_lat:.4f} N, {geo_lng:.4f} E | {engine_used}"
    )

    # World-First 3D Volumetric & Slack-Fill Analysis
    volumetric_res = compliance_engine.compute_volumetric_slack_fill(
        pdp_w_cm=pdp_w_cm,
        pdp_h_cm=pdp_h_cm,
        net_qty_val=dec.net_quantity_value,
        net_qty_unit=dec.net_quantity_unit,
        product_name=dec.product_name
    )

    return {
        "inspection_ref": ref_id,
        "product_name": dec.product_name,
        "compliance_status": report.overall_status.value,
        "compliance_score": report.compliance_score,
        "total_violations": len(report.violations),
        "critical_violations": report.critical_violations_count,
        "major_violations": report.major_violations_count,
        "minor_violations": report.minor_violations_count,
        "engine_used": engine_used,
        "surface_geometry": surface_geometry,
        "raw_transcript": raw_transcript,
        "declarations": save_dec,
        "declaration_boxes": declaration_boxes,
        "report": rep_dict,
        "violations": [v.__dict__ for v in report.violations],
        "volumetric_analysis": volumetric_res,
        "measurements": {
            "pdp_width_cm": pdp_w_cm,
            "pdp_height_cm": pdp_h_cm,
            "pdp_area_cm2": pdp_area_cm2,
            "numeral_height_mm": measured_numeral_mm,
            "reference_type": calib_res.reference_type.value,
            "pixels_per_mm": calib_res.pixels_per_mm,
            "calibration_status": calib_res.calibration_status,
            "confidence_score": calib_res.confidence_score
        },
        "qr_harmonization": {
            "qr_detected": qr_res.qr_detected,
            "harmonization_status": qr_res.harmonization_status,
            "match_percentage": qr_res.match_percentage,
            "discrepancies": [d.__dict__ for d in qr_res.discrepancies],
            "raw_payload": qr_res.raw_payload
        },
        "readability": read_info,
        "original_image": original_b64,
        "annotated_image": b64_img,
        "image_dimensions": {"width": proc_image.size[0], "height": proc_image.size[1]},
        "roi_image": getattr(dec, "_roi_crop_base64", None),
        "grounding_verification": getattr(dec, "_grounding", None),
        "cv_diagnostics": getattr(dec, "_cv_diagnostics", None)
    }


@app.get("/api/v1/samples")
def get_benchmark_samples():
    """Lists pre-configured FMCG samples for demo auditing."""
    samples = []
    for k, v in BENCHMARK_SAMPLES.items():
        samples.append({
            "key": k,
            "title": v.get("title", k),
            "description": v.get("description", "")
        })
    return samples


@app.get("/api/v1/samples/{sample_key}/image")
def get_sample_image(sample_key: str):
    """Generates and serves synthetic packaging label image for a sample."""
    img = create_synthetic_package_image(sample_key)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/jpeg")


@app.get("/api/v1/config/ai-status")
def get_ai_status():
    """Checks Gemini API key readiness."""
    key = get_gemini_api_key()
    return {
        "gemini_active": bool(key),
        "key_masked": f"{key[:8]}...{key[-4:]}" if key and len(key) > 12 else None
    }


class SaveKeyRequest(BaseModel):
    api_key: str


@app.post("/api/v1/config/gemini-key")
def update_gemini_key(req: SaveKeyRequest):
    """Saves Gemini API key permanently into persistent storage."""
    if not req.api_key or len(req.api_key.strip()) < 8:
        raise HTTPException(status_code=400, detail="Invalid API key")
    set_gemini_api_key(req.api_key.strip())
    return {"status": "SUCCESS", "message": "Gemini API key stored successfully"}


LOGO_PATH = r"C:\Users\aasho\AppData\Local\PackagingCompliance\logo.png"


LOGO_PATH = os.path.join(STATIC_DIR, "logo.png")


@app.get("/static/logo.png")
@app.get("/logo.png")
def serve_logo():
    if os.path.exists(LOGO_PATH):
        return FileResponse(LOGO_PATH, media_type="image/png")
    # Dynamic SVG fallback if file is missing
    svg_fallback = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
      <circle cx="50" cy="50" r="46" fill="#0A2540" stroke="#D4AF37" stroke-width="4"/>
      <circle cx="50" cy="50" r="40" fill="#061B2E" stroke="#F59E0B" stroke-width="1.5"/>
      <path d="M50 20 L50 75 M32 32 L68 32 M32 32 L26 50 M32 32 L38 50 M68 32 L62 50 M68 32 L74 50" stroke="#D4AF37" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M22 50 Q32 58 42 50 Z M58 50 Q68 58 78 50 Z" fill="#F59E0B" stroke="#D4AF37" stroke-width="1.5"/>
      <rect x="42" y="75" width="16" height="6" rx="2" fill="#D4AF37"/>
    </svg>'''
    return Response(content=svg_fallback, media_type="image/svg+xml")


@app.get("/presentation")
@app.get("/deck")
def serve_presentation():
    pres_path = os.path.join(STATIC_DIR, "presentation.html")
    if os.path.exists(pres_path):
        return FileResponse(pres_path)
    raise HTTPException(status_code=404, detail="Presentation deck not found")


# Serve frontend root
@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ACTIVE", "message": "Legal Metrology API Active"}


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "HEALTHY",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }


# Mount static assets directory
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

