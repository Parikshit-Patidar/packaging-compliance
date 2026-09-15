/**
 * IndexedDB Offline Storage & Auto-Sync Engine
 * Allows retail basement inspections without internet connectivity;
 * caches image captures and automatically synchronizes to FastAPI backend when online.
 */

const DB_NAME = 'LegalMetrologyOfflineDB';
const DB_VERSION = 1;
const STORE_NAME = 'pending_inspections';

export function openOfflineDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveOfflineDraft(draftData) {
  const db = await openOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const record = {
      ...draftData,
      savedAt: new Date().toISOString(),
      synced: false
    };
    const req = store.add(record);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function getPendingDrafts() {
  const db = await openOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result.filter((item) => !item.synced));
    req.onerror = () => reject(req.error);
  });
}

export async function markDraftSynced(id) {
  const db = await openOfflineDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const req = store.delete(id);
    req.onsuccess = () => resolve(true);
    req.onerror = () => reject(req.error);
  });
}

export async function syncPendingDrafts(apiBaseUrl = 'http://localhost:8000') {
  const pending = await getPendingDrafts();
  const results = [];
  
  for (const draft of pending) {
    try {
      const response = await fetch(`${apiBaseUrl}/api/v1/rules/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft.declarations)
      });
      if (response.ok) {
        const auditResult = await response.json();
        await markDraftSynced(draft.id);
        results.push({ id: draft.id, success: true, result: auditResult });
      }
    } catch (err) {
      console.warn('Sync failed for draft:', draft.id, err);
      results.push({ id: draft.id, success: false, error: err.message });
    }
  }
  return results;
}
