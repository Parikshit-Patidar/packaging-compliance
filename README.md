# Legal Metrology (Packaged Commodities) Compliance System ⚖️📦
**Next-Generation AI Inspection, Reference Object Calibration & Statutory Enforcement Engine**

Built for Enforcement Officers, Brand Compliance Managers, and Packaging Designers under the **Legal Metrology Act, 2009** and **Legal Metrology (Packaged Commodities) Rules, 2011** (with 2021/2022 amendments).

---

## 🏛️ Core Subsystems & Technical Architecture

### 1. ⚡ FastAPI Rule Validation Engine (`backend/api.py` & `backend/rules.py`)
* High-speed REST API backend algorithmically validating mandatory label declarations:
  * **Rule 6(1)(a)**: Complete manufacturer/packer/importer name and physical address.
  * **Rule 6(1)(c) & Rule 13**: Standard SI units (`g`, `kg`, `ml`, `l`, `m`, `N`). Detects & penalizes non-standard symbols like `gms`, `gm`, `kilo`, `ltr`, `cc`.
  * **Rule 6(1)(d)**: Month & Year of manufacture / packing (`MM/YYYY` or `Month YYYY`).
  * **Rule 6(1)(da) (2022 Amendment)**: Mandatory Unit Sale Price (**USP**) (e.g. `₹ 0.40 per g`).
  * **Rule 6(1)(e)**: MRP syntax (`₹` or `Rs.` with mandatory `incl. of all taxes` declaration).
  * **Rule 6(1)(n)**: Consumer grievance cell (designation, address, telephone helpline, AND email ID).
  * **Rule 6(10)**: Country of Origin for imported commodities.
  * **Section 36 Penalties**: Fine up to ₹25,000 for 1st offence; ₹50,000 for 2nd offence; ₹1,00,000 or imprisonment up to 1 year for subsequent offences.

### 2. 📏 Pixel-to-Millimeter Calibration Module (`backend/calibration.py`)
* Automatically detects a physical reference object placed beside the commodity:
  * **Standard Credit / ID Card (ISO/IEC 7810 ID-1)**: $85.60\text{ mm} \times 53.98\text{ mm}$ (Aspect ratio $\approx 1.586$)
  * **Standard Indian Coins**: ₹1 (20mm), ₹2 (25mm), ₹5 (23mm), ₹10 (27mm)
* Computes exact **Pixels-Per-Millimeter (PPM)** scale ratio ($PPM = \text{pixels} / \text{mm}$).
* Measures actual physical numeral heights ($\text{mm}$) and Principal Display Panel (PDP) dimensions ($\text{cm}$) to verify compliance with **Rule 9 & Schedule II** statutory minimum font size thresholds.

### 3. 🌀 Spatial OCR & 3D De-Warping (`backend/dewarp_service.py`)
* **3D Cylindrical Unrolling**: Digitally unrolls curved bottles, cans, and cylindrical pouches using radial transformation to eliminate distortion and foreshortening.
* **Perspective Rectification**: 4-point homography transform to flatten skewed labels.
* **Grounded Spatial OCR**: Anchors every single extracted declaration to precise spatial bounding boxes $(x_1, y_1, x_2, y_2)$, eliminating LLM hallucinations.

### 4. 🔗 Hybrid QR Harmonization (`backend/qr_harmonizer.py`)
* Concurrently decodes on-pack QR codes and cross-verifies digital disclosure data against physical on-pack declarations.
* Detects dual pricing, net quantity mismatches, and broken digital links under the 2021/2022 electronic disclosure amendments.

### 5. 🔒 Tamper-Evident Geotagged PDF Audit Generator (`backend/pdf_service.py`)
* Compiles inspection findings into a tamper-evident PDF audit certificate using `ReportLab`:
  * **SHA-256 Cryptographic Hash**: Computed across inspection parameters, officer ID, and timestamp.
  * **Geotagged GPS Coordinates**: Latitude/Longitude of inspection premises.
  * **Visual Violation Heatmap**: Image overlay highlighting green (passed), yellow (missing), and red (violation) bounding boxes.
  * **Statutory Rule Matrix**: Itemized legal findings and Section 36 citations.

### 6. 💼 B2B Pre-Print Artwork Sandbox (`backend/b2b_sandbox.py`)
* Commercial pre-flight portal for packaging designers and pre-media houses.
* Simulates statutory audits on digital dielines/artwork before printing cylinder engraving, saving estimated ₹60,000 to ₹1,50,000 per packaging SKU in re-printing costs.

### 7. 📱 Offline-First React PWA (`frontend/`) & Streamlit Workbench (`backend/main.py`)
* **Offline-First React PWA**: Caches camera captures in zero-connectivity retail basements via **IndexedDB** and auto-syncs to the backend once network connectivity resumes.
* **Streamlit Advanced Workbench**: Immediate interactive testing of all calibration, de-warping, QR, and pre-print features.

---

## 🚀 How to Run

### 1. Run Automated Advanced Subsystem Tests
```powershell
& "C:\Users\aasho\AppData\Local\PackagingCompliance\venv\Scripts\python.exe" -B backend/test_advanced_pipeline.py
```

### 2. Launch FastAPI REST Server
```powershell
& "C:\Users\aasho\AppData\Local\PackagingCompliance\venv\Scripts\python.exe" -m uvicorn api:app --app-dir backend --port 8000 --reload
```
Interactive Swagger API docs available at: **`http://localhost:8000/docs`**

### 3. Launch Streamlit Interactive Testing Workbench
```powershell
& "C:\Users\aasho\AppData\Local\PackagingCompliance\venv\Scripts\python.exe" -m streamlit run backend/main.py
```
Workbench available at: **`http://localhost:8501`**

### 4. Frontend React PWA (Optional Development Mode)
```bash
cd frontend
npm install
npm run dev
```
PWA available at: **`http://localhost:3000`**

---

## 📡 Key REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/rules/validate` | Algorithmically validates declarations against Legal Metrology Rules, 2011 |
| `POST` | `/api/v1/calibrate` | Detects ID Card / Coins and returns PPM scale & measured font mm |
| `POST` | `/api/v1/dewarp` | Unrolls curved packaging cylinder and returns spatial bounding boxes |
| `POST` | `/api/v1/qr/harmonize` | Decodes on-pack QR and checks digital vs physical disclosure |
| `POST` | `/api/v1/audit/pdf` | Generates tamper-evident (SHA-256), geotagged PDF audit certificate |
| `POST` | `/api/v1/b2b/pre-print` | Pre-flight packaging dieline audit for packaging designers |
| `GET` | `/api/v1/inspections` | Query inspection dossiers from SQLite vault |
| `GET` | `/api/v1/analytics` | Executive compliance metrics and violation rankings |
