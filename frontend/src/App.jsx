import React, { useState, useEffect } from 'react';
import { saveOfflineDraft, getPendingDrafts, syncPendingDrafts } from './offlineStorage';

export default function App() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingDrafts, setPendingDrafts] = useState([]);
  const [activeTab, setActiveTab] = useState('inspect');
  const [syncStatus, setSyncStatus] = useState('');

  // Form state
  const [productName, setProductName] = useState('Masala Potato Chips');
  const [mrp, setMrp] = useState('20.00');
  const [netQty, setNetQty] = useState('50');
  const [unit, setUnit] = useState('g');
  const [mfgDate, setMfgDate] = useState('08/2026');
  const [consumerPhone, setConsumerPhone] = useState('1800-419-5555');
  const [consumerEmail, setConsumerEmail] = useState('care@chips.in');
  const [refObject, setRefObject] = useState('CREDIT_CARD');
  
  // Results state
  const [auditResult, setAuditResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Monitor network connectivity
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      triggerAutoSync();
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    loadPendingCount();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const loadPendingCount = async () => {
    try {
      const drafts = await getPendingDrafts();
      setPendingDrafts(drafts);
    } catch (e) {
      console.warn('Error loading pending drafts:', e);
    }
  };

  const triggerAutoSync = async () => {
    setSyncStatus('Syncing offline inspection queue...');
    try {
      const res = await syncPendingDrafts('http://localhost:8000');
      await loadPendingCount();
      setSyncStatus(`Sync completed: ${res.length} inspections uploaded.`);
      setTimeout(() => setSyncStatus(''), 4000);
    } catch (e) {
      setSyncStatus('Auto-sync failed. Retrying when network stabilizes.');
    }
  };

  const handleRunAudit = async () => {
    setIsLoading(true);
    const payload = {
      product_name: productName,
      generic_name: 'Potato Chips',
      manufacturer_name: 'Apex Snacks Pvt Ltd',
      manufacturer_address: 'Plot 14, Sector 68, IMT Manesar, Gurugram 122051',
      net_quantity_value: parseFloat(netQty),
      net_quantity_unit: unit,
      net_quantity_raw: `${netQty} ${unit}`,
      mrp_value: parseFloat(mrp),
      mrp_raw: `MRP ₹ ${mrp} (incl. of all taxes)`,
      mrp_inclusive_taxes_mentioned: true,
      month_year_of_mfg: mfgDate,
      consumer_care_phone: consumerPhone,
      consumer_care_email: consumerEmail,
      pdp_height_cm: 18.0,
      pdp_width_cm: 12.0,
      numeral_height_mm: 3.5
    };

    if (!isOnline) {
      // Offline mode: cache in IndexedDB
      await saveOfflineDraft({
        productName,
        declarations: payload,
        referenceObject: refObject
      });
      await loadPendingCount();
      setAuditResult({
        overall_status: 'QUEUED_OFFLINE',
        compliance_score: 100.0,
        total_checks: 9,
        passed_checks: 9,
        failed_checks: 0,
        violations: [],
        check_results: [],
        offlineNotice: 'Captured in offline retail basement. Record securely queued in local IndexedDB. Will auto-sync once online.'
      });
      setIsLoading(false);
      return;
    }

    try {
      const resp = await fetch('http://localhost:8000/api/v1/rules/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      setAuditResult(data);
    } catch (err) {
      // Fallback to local storage if API call fails
      await saveOfflineDraft({
        productName,
        declarations: payload,
        referenceObject: refObject
      });
      await loadPendingCount();
      setAuditResult({
        overall_status: 'QUEUED_OFFLINE',
        compliance_score: 100.0,
        violations: [],
        offlineNotice: 'Backend server unreachable. Queued safely in local browser storage.'
      });
    }
    setIsLoading(false);
  };

  return (
    <div style={{ fontFamily: 'system-ui, -apple-system, sans-serif', backgroundColor: '#f1f5f9', minHeight: '100vh', padding: '24px' }}>
      {/* Top Header */}
      <header style={{ backgroundColor: '#0f172a', color: 'white', padding: '20px 24px', borderRadius: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '22px', fontWeight: 'bold' }}>⚖️ Legal Metrology Compliance Field Portal</h1>
          <p style={{ margin: '4px 0 0 0', color: '#93c5fd', fontSize: '13px' }}>Offline-First PWA for Field Officers & Compliance Auditors</p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ backgroundColor: isOnline ? '#166534' : '#991b1b', color: 'white', padding: '6px 14px', borderRadius: '20px', fontSize: '12px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: isOnline ? '#4ade80' : '#f87171' }}></span>
            {isOnline ? 'Online (API Ready)' : 'Offline (Basement Mode)'}
          </span>
          {pendingDrafts.length > 0 && (
            <span style={{ backgroundColor: '#d97706', color: 'white', padding: '6px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 'bold' }}>
              Pending Sync: {pendingDrafts.length}
            </span>
          )}
        </div>
      </header>

      {syncStatus && (
        <div style={{ backgroundColor: '#dbeafe', color: '#1e40af', padding: '10px 16px', borderRadius: '8px', marginBottom: '16px', fontWeight: '500', fontSize: '14px' }}>
          🔄 {syncStatus}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <button onClick={() => setActiveTab('inspect')} style={{ padding: '10px 18px', borderRadius: '8px', border: 'none', backgroundColor: activeTab === 'inspect' ? '#1e3a8a' : '#e2e8f0', color: activeTab === 'inspect' ? 'white' : '#334155', fontWeight: 'bold', cursor: 'pointer' }}>
          📸 Live Packaging Inspection
        </button>
        <button onClick={() => setActiveTab('queue')} style={{ padding: '10px 18px', borderRadius: '8px', border: 'none', backgroundColor: activeTab === 'queue' ? '#1e3a8a' : '#e2e8f0', color: activeTab === 'queue' ? 'white' : '#334155', fontWeight: 'bold', cursor: 'pointer' }}>
          🗄️ Offline Storage Queue ({pendingDrafts.length})
        </button>
      </div>

      {activeTab === 'inspect' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '24px' }}>
          {/* Left: Input Form */}
          <div style={{ backgroundColor: 'white', padding: '24px', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h2 style={{ fontSize: '17px', fontWeight: 'bold', margin: '0 0 16px 0', color: '#0f172a' }}>1. Physical Reference & Declarations</h2>
            
            <label style={{ display: 'block', marginBottom: '12px', fontSize: '13px', fontWeight: '600' }}>
              Reference Object for Pixel-to-mm Calibration:
              <select value={refObject} onChange={(e) => setRefObject(e.target.value)} style={{ width: '100%', padding: '8px', marginTop: '4px', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                <option value="CREDIT_CARD">Standard ID / Credit Card (85.60 x 53.98 mm)</option>
                <option value="COIN_10_INR">Indian ₹10 Coin (27.0 mm diameter)</option>
                <option value="COIN_5_INR">Indian ₹5 Coin (23.0 mm diameter)</option>
                <option value="COIN_1_INR">Indian ₹1 Coin (20.0 mm diameter)</option>
              </select>
            </label>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <label style={{ fontSize: '13px', fontWeight: '600' }}>
                Maximum Retail Price (₹):
                <input type="text" value={mrp} onChange={(e) => setMrp(e.target.value)} style={{ width: '100%', padding: '8px', marginTop: '4px', borderRadius: '6px', border: '1px solid #cbd5e1' }} />
              </label>
              <label style={{ fontSize: '13px', fontWeight: '600' }}>
                Net Quantity:
                <div style={{ display: 'flex', gap: '6px' }}>
                  <input type="text" value={netQty} onChange={(e) => setNetQty(e.target.value)} style={{ width: '60%', padding: '8px', marginTop: '4px', borderRadius: '6px', border: '1px solid #cbd5e1' }} />
                  <select value={unit} onChange={(e) => setUnit(e.target.value)} style={{ width: '40%', padding: '8px', marginTop: '4px', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                    <option value="g">g</option>
                    <option value="kg">kg</option>
                    <option value="ml">ml</option>
                    <option value="l">l</option>
                    <option value="gms">gms (Illegal)</option>
                  </select>
                </div>
              </label>
            </div>

            <label style={{ display: 'block', marginBottom: '12px', fontSize: '13px', fontWeight: '600' }}>
              Month & Year of Mfg/Packing:
              <input type="text" value={mfgDate} onChange={(e) => setMfgDate(e.target.value)} style={{ width: '100%', padding: '8px', marginTop: '4px', borderRadius: '6px', border: '1px solid #cbd5e1' }} />
            </label>

            <label style={{ display: 'block', marginBottom: '12px', fontSize: '13px', fontWeight: '600' }}>
              Consumer Helpline Telephone:
              <input type="text" value={consumerPhone} onChange={(e) => setConsumerPhone(e.target.value)} style={{ width: '100%', padding: '8px', marginTop: '4px', borderRadius: '6px', border: '1px solid #cbd5e1' }} />
            </label>

            <button onClick={handleRunAudit} disabled={isLoading} style={{ width: '100%', padding: '12px', borderRadius: '8px', border: 'none', backgroundColor: '#2563eb', color: 'white', fontWeight: 'bold', fontSize: '15px', cursor: 'pointer', marginTop: '12px' }}>
              {isLoading ? 'Auditing...' : isOnline ? '🔍 Run Online Statutory Audit' : '💾 Queue in Offline Storage'}
            </button>
          </div>

          {/* Right: Audit Result */}
          <div style={{ backgroundColor: 'white', padding: '24px', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h2 style={{ fontSize: '17px', fontWeight: 'bold', margin: '0 0 16px 0', color: '#0f172a' }}>2. Statutory Evaluation Dossier</h2>
            
            {auditResult ? (
              <div>
                <div style={{ padding: '16px', borderRadius: '8px', backgroundColor: auditResult.overall_status === 'COMPLIANT' ? '#f0fdf4' : (auditResult.overall_status === 'QUEUED_OFFLINE' ? '#eff6ff' : '#fef2f2'), border: `2px solid ${auditResult.overall_status === 'COMPLIANT' ? '#22c55e' : (auditResult.overall_status === 'QUEUED_OFFLINE' ? '#3b82f6' : '#ef4444')}`, marginBottom: '18px' }}>
                  <div style={{ fontSize: '18px', fontWeight: 'bold', color: auditResult.overall_status === 'COMPLIANT' ? '#166534' : (auditResult.overall_status === 'QUEUED_OFFLINE' ? '#1e40af' : '#991b1b') }}>
                    {auditResult.overall_status === 'QUEUED_OFFLINE' ? '💾 QUEUED IN OFFLINE STORAGE' : `STATUS: ${auditResult.overall_status}`}
                  </div>
                  <p style={{ margin: '4px 0 0 0', fontSize: '13px' }}>
                    {auditResult.offlineNotice || `Compliance Score: ${auditResult.compliance_score?.toFixed(1)}% | Passed Checks: ${auditResult.passed_checks}/${auditResult.total_checks}`}
                  </p>
                </div>

                {auditResult.violations && auditResult.violations.length > 0 && (
                  <div>
                    <h3 style={{ fontSize: '14px', fontWeight: 'bold', color: '#991b1b' }}>Flagged Statutory Violations:</h3>
                    {auditResult.violations.map((v, i) => (
                      <div key={i} style={{ padding: '10px', backgroundColor: '#fef2f2', borderLeft: '3px solid #ef4444', marginBottom: '8px', borderRadius: '0 4px 4px 0' }}>
                        <div style={{ fontWeight: 'bold', fontSize: '13px' }}>{v.title}</div>
                        <div style={{ fontSize: '12px', color: '#475569' }}>{v.description}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#64748b' }}>
                <p>No inspection run yet. Enter declarations on the left and click Audit.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'queue' && (
        <div style={{ backgroundColor: 'white', padding: '24px', borderRadius: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 'bold', margin: 0 }}>Offline Inspection Storage Queue</h2>
            <button onClick={triggerAutoSync} disabled={!isOnline || pendingDrafts.length === 0} style={{ padding: '8px 16px', backgroundColor: isOnline ? '#16a34a' : '#94a3b8', color: 'white', border: 'none', borderRadius: '6px', fontWeight: 'bold', cursor: isOnline ? 'pointer' : 'not-allowed' }}>
              🔄 Sync All to Server
            </button>
          </div>
          {pendingDrafts.length === 0 ? (
            <p style={{ color: '#64748b' }}>No pending offline drafts. All inspections are synchronized.</p>
          ) : (
            <div>
              {pendingDrafts.map((d) => (
                <div key={d.id} style={{ padding: '12px', border: '1px solid #e2e8f0', borderRadius: '8px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>{d.productName}</strong>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Saved at: {d.savedAt}</div>
                  </div>
                  <span style={{ backgroundColor: '#fef3c7', color: '#92400e', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold' }}>PENDING SYNC</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
