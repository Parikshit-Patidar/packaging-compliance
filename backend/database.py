"""
Legal Metrology Compliance Database & Repository
SQLite-based persistent vault for packaging inspection records, audit trails, and enforcement analytics.
Stores data reliably in AppData/PackagingCompliance/compliance_vault.db (bypassing Windows Controlled Folder Access).
"""

import sqlite3
import json
import os
import hashlib
import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import is_dataclass, asdict


def _safe_json_dumps(obj: Any) -> str:
    """Safely serializes dataclasses, dicts, enums and custom objects to JSON string."""
    def _default(o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        if hasattr(o, "__dict__"):
            return o.__dict__
        if hasattr(o, "value"):
            return o.value
        return str(o)
    return json.dumps(obj, default=_default)


def get_db_path() -> str:
    base_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    vault_dir = os.path.join(base_dir, "PackagingCompliance")
    os.makedirs(vault_dir, exist_ok=True)
    return os.path.join(vault_dir, "compliance_vault.db")

DB_PATH = get_db_path()


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Generates salted SHA-256 PBKDF2 password hash."""
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return pw_hash, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verifies a plain password against stored hash and salt."""
    check_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(check_hash, hashed)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Statutory Inspections Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_ref TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            inspector_name TEXT NOT NULL,
            location TEXT,
            store_name TEXT,
            product_name TEXT NOT NULL,
            brand TEXT,
            category TEXT,
            batch_no TEXT,
            compliance_status TEXT NOT NULL,
            compliance_score REAL NOT NULL,
            total_violations INTEGER NOT NULL,
            critical_violations INTEGER NOT NULL,
            major_violations INTEGER NOT NULL,
            minor_violations INTEGER NOT NULL,
            declarations_json TEXT,
            violations_json TEXT,
            check_results_json TEXT,
            image_path TEXT,
            officer_action TEXT DEFAULT 'Pending Review',
            notes TEXT,
            user_id INTEGER,
            user_role TEXT DEFAULT 'GOVT_OFFICER'
        )
    """)

    # Check and add columns if upgrading existing table
    cursor.execute("PRAGMA table_info(inspections)")
    existing_cols = [row["name"] for row in cursor.fetchall()]
    if "user_id" not in existing_cols:
        try:
            cursor.execute("ALTER TABLE inspections ADD COLUMN user_id INTEGER DEFAULT NULL")
        except Exception:
            pass
    if "user_role" not in existing_cols:
        try:
            cursor.execute("ALTER TABLE inspections ADD COLUMN user_role TEXT DEFAULT 'GOVT_OFFICER'")
        except Exception:
            pass

    # 2. Users and Authentication Credentials Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,           -- 'GOVT_OFFICER' or 'B2B_BRAND'
            organization TEXT NOT NULL,   -- e.g., 'Dept of Consumer Affairs' or 'Apex FMCG Ltd'
            badge_or_gstin TEXT,          -- Official Badge ID (LMO-DEL-048) or GSTIN
            designation TEXT,             -- e.g., 'Legal Metrology Officer' or 'Packaging Technologist'
            phone TEXT,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()

    # Seed demo users if empty
    seed_default_users()


def save_inspection(
    inspection_ref: str,
    product_name: str,
    compliance_status: str,
    compliance_score: float,
    total_violations: int,
    critical_violations: int,
    major_violations: int,
    minor_violations: int,
    declarations: Dict[str, Any],
    violations: List[Dict[str, Any]],
    check_results: List[Dict[str, Any]],
    inspector_name: str = "Enforcement Officer (Div-01)",
    location: str = "New Delhi Central Market",
    store_name: str = "Super Retail Mart",
    brand: str = "General FMCG",
    category: str = "Food & Beverages",
    batch_no: str = "BATCH-2026",
    image_path: Optional[str] = None,
    officer_action: str = "Pending Review",
    notes: str = "",
    user_id: Optional[int] = None,
    user_role: Optional[str] = "GOVT_OFFICER"
) -> str:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT OR REPLACE INTO inspections (
            inspection_ref, timestamp, inspector_name, location, store_name,
            product_name, brand, category, batch_no, compliance_status,
            compliance_score, total_violations, critical_violations,
            major_violations, minor_violations, declarations_json,
            violations_json, check_results_json, image_path,
            officer_action, notes, user_id, user_role
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inspection_ref, timestamp, inspector_name, location, store_name,
        product_name, brand, category, batch_no, compliance_status,
        compliance_score, total_violations, critical_violations,
        major_violations, minor_violations,
        _safe_json_dumps(declarations),
        _safe_json_dumps(violations),
        _safe_json_dumps(check_results),
        image_path, officer_action, notes, user_id, user_role
    ))
    conn.commit()
    conn.close()
    return inspection_ref


def get_inspections(
    search_query: Optional[str] = None,
    status_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    user_id: Optional[int] = None,
    user_role: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM inspections WHERE 1=1"
    params: List[Any] = []
    
    # B2B Brand users see their own enterprise dossiers or public self-audits
    if user_role == "B2B_BRAND" and user_id is not None:
        query += " AND (user_id = ? OR user_role = 'B2B_BRAND')"
        params.append(user_id)
        
    if search_query:
        query += " AND (product_name LIKE ? OR brand LIKE ? OR inspection_ref LIKE ? OR store_name LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term, term, term])
        
    if status_filter and status_filter != "ALL":
        query += " AND compliance_status = ?"
        params.append(status_filter)
        
    if category_filter and category_filter != "ALL":
        query += " AND category = ?"
        params.append(category_filter)
        
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    result = []
    for r in rows:
        d = dict(r)
        d["declarations"] = json.loads(d["declarations_json"]) if d["declarations_json"] else {}
        d["violations"] = json.loads(d["violations_json"]) if d["violations_json"] else []
        d["check_results"] = json.loads(d["check_results_json"]) if d["check_results_json"] else []
        result.append(d)
        
    conn.close()
    return result


def get_inspection_by_ref(ref: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inspections WHERE inspection_ref = ?", (ref,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["declarations"] = json.loads(d["declarations_json"]) if d["declarations_json"] else {}
    d["violations"] = json.loads(d["violations_json"]) if d["violations_json"] else []
    d["check_results"] = json.loads(d["check_results_json"]) if d["check_results_json"] else []
    return d


def update_officer_action(ref: str, action: str, notes: str = ""):
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE inspections SET officer_action = ?, notes = ? WHERE inspection_ref = ?", (action, notes, ref))
    conn.commit()
    conn.close()


def get_analytics_summary() -> Dict[str, Any]:
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM inspections")
    total_inspections = cursor.fetchone()[0]
    
    if total_inspections == 0:
        conn.close()
        return {
            "total_inspections": 0,
            "compliant_count": 0,
            "non_compliant_count": 0,
            "conditional_count": 0,
            "compliance_rate": 0.0,
            "critical_violations_total": 0,
            "major_violations_total": 0,
            "minor_violations_total": 0,
            "status_distribution": {},
            "top_violated_rules": [],
            "brand_compliance": []
        }
        
    cursor.execute("SELECT compliance_status, COUNT(*) FROM inspections GROUP BY compliance_status")
    status_dist = {row[0]: row[1] for row in cursor.fetchall()}
    
    compliant_count = status_dist.get("COMPLIANT", 0)
    non_compliant_count = status_dist.get("NON_COMPLIANT", 0)
    conditional_count = status_dist.get("CONDITIONAL", 0)
    compliance_rate = round((compliant_count / total_inspections) * 100, 1)
    
    cursor.execute("SELECT SUM(critical_violations), SUM(major_violations), SUM(minor_violations) FROM inspections")
    crit_sum, maj_sum, min_sum = cursor.fetchone()
    
    cursor.execute("""
        SELECT brand, COUNT(*) as total, 
               SUM(CASE WHEN compliance_status = 'COMPLIANT' THEN 1 ELSE 0 END) as compliant,
               SUM(CASE WHEN compliance_status = 'NON_COMPLIANT' THEN 1 ELSE 0 END) as non_compliant
        FROM inspections 
        GROUP BY brand 
        ORDER BY total DESC 
        LIMIT 10
    """)
    brand_stats = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT violations_json FROM inspections WHERE violations_json IS NOT NULL")
    all_v_rows = cursor.fetchall()
    rule_counts: Dict[str, int] = {}
    for r in all_v_rows:
        try:
            v_list = json.loads(r[0])
            for v in v_list:
                rule_name = v.get("title", v.get("rule_clause", "Unknown Violation"))
                rule_counts[rule_name] = rule_counts.get(rule_name, 0) + 1
        except Exception:
            pass
            
    top_rules = sorted([{"rule": k, "count": v} for k, v in rule_counts.items()], key=lambda x: x["count"], reverse=True)[:8]
    
    conn.close()
    return {
        "total_inspections": total_inspections,
        "compliant_count": compliant_count,
        "non_compliant_count": non_compliant_count,
        "conditional_count": conditional_count,
        "compliance_rate": compliance_rate,
        "critical_violations_total": crit_sum or 0,
        "major_violations_total": maj_sum or 0,
        "minor_violations_total": min_sum or 0,
        "status_distribution": status_dist,
        "top_violated_rules": top_rules,
        "brand_compliance": brand_stats
    }


def seed_demo_data():
    """Seed repository with realistic packaging inspection history if empty."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM inspections")
    count = cursor.fetchone()[0]
    conn.close()
    
    if count > 0:
        return
        
    sample_records = [
        {
            "ref": "LM-INSP-2026-001",
            "product": "Crispy Masala Potato Chips",
            "brand": "Golden Crunchy Foods Ltd",
            "category": "Snacks & Packaged Food",
            "batch": "GCF-AUG26-01",
            "status": "COMPLIANT",
            "score": 100.0,
            "crit": 0, "maj": 0, "min": 0,
            "action": "Verified & Cleared",
            "notes": "All statutory declarations complete under Legal Metrology Rules 2011.",
            "declarations": {
                "Product / Brand": "Crispy Masala Potato Chips",
                "Generic Commodity Name": "Potato Chips",
                "Manufacturer": "Golden Crunchy Foods Pvt Ltd",
                "Manufacturer Address": "Plot 42, Okhla Industrial Area Phase-III, New Delhi 110020",
                "Net Quantity": "50 g",
                "Standard Metric Unit": "g",
                "MRP": "MRP ₹ 20.00 (incl. of all taxes)",
                "Unit Sale Price (USP)": "₹ 0.40 per g",
                "Date of Mfg / Packing": "08/2026",
                "Consumer Care Helpline": "1800-112-4455",
                "Consumer Care Email": "customercare@goldencrunchy.in",
                "Country of Origin": "India",
                "PDP Area (cm²)": "180.0",
                "Numeral Height (mm)": "4.2"
            },
            "violations": []
        },
        {
            "ref": "LM-INSP-2026-002",
            "product": "Royal Butter Delights Biscuits",
            "brand": "Royal Treats Bakery",
            "category": "Bakery & Confectionery",
            "batch": "RTB-9981-JUL",
            "status": "NON_COMPLIANT",
            "score": 45.0,
            "crit": 1, "maj": 2, "min": 0,
            "action": "Notice Issued (Sec 36)",
            "notes": "Non-standard unit 'gms', missing tax notice, and missing Unit Sale Price.",
            "declarations": {
                "Product / Brand": "Royal Butter Delights Biscuits",
                "Generic Commodity Name": "Butter Biscuits",
                "Manufacturer": "Royal Treats Bakery Ltd",
                "Manufacturer Address": "GIDC Estate, Naroda, Ahmedabad 382330",
                "Net Quantity": "150 gms",
                "Standard Metric Unit": "gms",
                "MRP": "MRP Rs. 45.00",
                "Unit Sale Price (USP)": "Not Declared",
                "Date of Mfg / Packing": "07/2026",
                "Consumer Care Helpline": "Not Declared",
                "Consumer Care Email": "support@royaltreats.com",
                "Country of Origin": "India",
                "PDP Area (cm²)": "160.0",
                "Numeral Height (mm)": "2.2"
            },
            "violations": [
                {
                    "rule_id": "RULE_6_1_C_STD_UNIT",
                    "title": "Non-Standard Unit Symbol Used (e.g. 'gms')",
                    "rule_clause": "Rule 13 & Schedule I, LM(PC) Rules, 2011",
                    "severity": "MAJOR",
                    "description": "Symbol 'gms' is prohibited under Rule 13. Statutory symbol is 'g'.",
                    "extracted_value": "gms",
                    "expected_standard": "Use standard symbol 'g'. No trailing period or pluralization."
                },
                {
                    "rule_id": "RULE_6_1_DA_USP",
                    "title": "Missing Unit Sale Price (USP)",
                    "rule_clause": "Rule 6(1)(da) [Amendment 2022], LM(PC) Rules, 2011",
                    "severity": "MAJOR",
                    "description": "Every packaged commodity must declare Unit Sale Price.",
                    "extracted_value": "NOT FOUND",
                    "expected_standard": "Declaration in format '₹ 0.30 per g'."
                },
                {
                    "rule_id": "RULE_6_1_E_TAX",
                    "title": "Missing 'Inclusive of All Taxes' Declaration on MRP",
                    "rule_clause": "Rule 6(1)(e), LM(PC) Rules, 2011",
                    "severity": "MAJOR",
                    "description": "Omission of 'inclusive of all taxes' alongside MRP.",
                    "extracted_value": "MRP Rs. 45.00",
                    "expected_standard": "MRP Rs. 45.00 (incl. of all taxes)."
                },
                {
                    "rule_id": "RULE_6_1_N_CONSUMER_CARE",
                    "title": "Missing Consumer Helpline Telephone",
                    "rule_clause": "Rule 6(1)(n), LM(PC) Rules, 2011",
                    "severity": "CRITICAL",
                    "description": "Telephone helpline missing for consumer complaint redressal.",
                    "extracted_value": "MISSING",
                    "expected_standard": "Valid consumer telephone helpline number."
                }
            ]
        },
        {
            "ref": "LM-INSP-2026-003",
            "product": "Hydro-Glow Imported Facial Serum",
            "brand": "Luxe Paris Skincare",
            "category": "Personal Care & Cosmetics",
            "batch": "LP-IMP-2026-78",
            "status": "NON_COMPLIANT",
            "score": 30.0,
            "crit": 2, "maj": 1, "min": 0,
            "action": "Seizure / Summons Recommended",
            "notes": "Imported product lacking Importer name/address and Country of Origin declaration.",
            "declarations": {
                "Product / Brand": "Hydro-Glow Imported Facial Serum",
                "Generic Commodity Name": "Facial Serum",
                "Manufacturer": "Luxe Paris Laboratories, France",
                "Manufacturer Address": "Not Declared",
                "Net Quantity": "30 ml",
                "Standard Metric Unit": "ml",
                "MRP": "₹ 1499.00",
                "Unit Sale Price (USP)": "₹ 49.97 per ml",
                "Date of Mfg / Packing": "05/2026",
                "Consumer Care Helpline": "Not Declared",
                "Consumer Care Email": "Not Declared",
                "Country of Origin": "Not Declared",
                "PDP Area (cm²)": "75.0",
                "Numeral Height (mm)": "1.2"
            },
            "violations": [
                {
                    "rule_id": "RULE_6_1_A_MFG",
                    "title": "Missing Indian Importer Name & Postal Address",
                    "rule_clause": "Rule 6(1)(a), LM(PC) Rules, 2011",
                    "severity": "CRITICAL",
                    "description": "Imported packages must state the complete name and address of the Indian importer.",
                    "extracted_value": "MISSING",
                    "expected_standard": "Full postal address of the authorized importer in India."
                },
                {
                    "rule_id": "RULE_6_10_ORIGIN",
                    "title": "Missing Country of Origin on Imported Commodity",
                    "rule_clause": "Rule 6(10) / Rule 10, LM(PC) Rules, 2011",
                    "severity": "CRITICAL",
                    "description": "Country of origin is absent on imported cosmetic pack.",
                    "extracted_value": "MISSING",
                    "expected_standard": "Clear statement: 'Country of Origin: France'."
                }
            ]
        },
        {
            "ref": "LM-INSP-2026-004",
            "product": "Pure Mountain Spring Mineral Water 1L",
            "brand": "Aqua Pure Beverages",
            "category": "Food & Beverages",
            "batch": "AQ-2608-W1",
            "status": "COMPLIANT",
            "score": 95.0,
            "crit": 0, "maj": 0, "min": 1,
            "action": "Verified & Cleared",
            "notes": "Full compliance observed across all statutory provisions.",
            "declarations": {
                "Product / Brand": "Pure Mountain Spring Mineral Water",
                "Generic Commodity Name": "Packaged Drinking Water",
                "Manufacturer": "Aqua Pure Beverages Ltd",
                "Manufacturer Address": "Survey 88, Kalka Highway, Pinjore 134102",
                "Net Quantity": "1 l",
                "Standard Metric Unit": "l",
                "MRP": "MRP ₹ 20.00 (incl. of all taxes)",
                "Unit Sale Price (USP)": "₹ 20.00 per l",
                "Date of Mfg / Packing": "08/2026",
                "Consumer Care Helpline": "0172-2589000",
                "Consumer Care Email": "info@aquapure.co.in",
                "Country of Origin": "India",
                "PDP Area (cm²)": "320.0",
                "Numeral Height (mm)": "5.0"
            },
            "violations": []
        }
    ]
    
    for s in sample_records:
        save_inspection(
            inspection_ref=s["ref"],
            product_name=s["product"],
            compliance_status=s["status"],
            compliance_score=s["score"],
            total_violations=len(s["violations"]),
            critical_violations=s["crit"],
            major_violations=s["maj"],
            minor_violations=s["min"],
            declarations=s["declarations"],
            violations=s["violations"],
            check_results=[],
            brand=s["brand"],
            category=s["category"],
            batch_no=s["batch"],
            officer_action=s["action"],
            notes=s["notes"]
        )


# ==============================================================================
# USER CREDENTIALS & ROLE-BASED ACCESS CONTROL (RBAC) REPOSITORY
# ==============================================================================

def create_user(
    email: str,
    password: str,
    full_name: str,
    role: str,
    organization: str,
    badge_or_gstin: str = "",
    designation: str = "",
    phone: str = ""
) -> Dict[str, Any]:
    """Creates a new user record with salted SHA-256 PBKDF2 password hash."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    email_clean = email.strip().lower()
    pw_hash, salt = hash_password(password)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        cursor.execute("""
            INSERT INTO users (
                email, password_hash, salt, full_name, role, organization,
                badge_or_gstin, designation, phone, created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            email_clean, pw_hash, salt, full_name.strip(), role.strip().upper(),
            organization.strip(), badge_or_gstin.strip(), designation.strip(),
            phone.strip(), created_at
        ))
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"User with email '{email_clean}' already exists.")
    finally:
        conn.close()
        
    return get_user_by_id(user_id)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves user profile by ID without leaking password hashes or salts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d.pop("password_hash", None)
    d.pop("salt", None)
    return d


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Internal user retrieval by email including password hash for verification."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates credentials against stored password hash. Returns public user dict on success."""
    user = get_user_by_email(email)
    if not user:
        return None
    if not user.get("is_active", 1):
        return None
    
    if verify_password(password, user["password_hash"], user["salt"]):
        user.pop("password_hash", None)
        user.pop("salt", None)
        return user
    return None


def list_users(role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists users without exposing hashes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if role:
        cursor.execute("SELECT id, email, full_name, role, organization, badge_or_gstin, designation, created_at, is_active FROM users WHERE role = ? ORDER BY id ASC", (role.upper(),))
    else:
        cursor.execute("SELECT id, email, full_name, role, organization, badge_or_gstin, designation, created_at, is_active FROM users ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seed_default_users():
    """Seeds default Government Official and B2B Brand demo credentials if missing."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users")
    row = cursor.fetchone()
    count = row["count"] if row else 0
    conn.close()
    
    if count == 0:
        # 1. Government Official (Jan Parichay / NIC)
        try:
            create_user(
                email="officer.delhi@nic.in",
                password="GovtOfficer@2026",
                full_name="Shri Rajesh Kumar",
                role="GOVT_OFFICER",
                organization="Dept. of Consumer Affairs, Delhi Circle",
                badge_or_gstin="LMO-DEL-048",
                designation="Legal Metrology Officer (Class-I)",
                phone="+91 11 2338 4567"
            )
        except Exception:
            pass
        
        # 2. B2B Packaging Brand Owner
        try:
            create_user(
                email="compliance@fmcgbrand.com",
                password="BrandUser@2026",
                full_name="Priya Sharma",
                role="B2B_BRAND",
                organization="Apex Consumer Goods Ltd",
                badge_or_gstin="07AABCA1234F1Z6",
                designation="Lead Packaging Technologist",
                phone="+91 98110 54321"
            )
        except Exception:
            pass
