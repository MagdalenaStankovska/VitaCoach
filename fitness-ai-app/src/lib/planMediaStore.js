const DB_NAME = "vitacoach_media";
const STORE_NAME = "plan_media";
const DB_VERSION = 1;

function openDb() {
    return new Promise((resolve, reject) => {
        if (typeof window === "undefined" || !window.indexedDB) {
            reject(new Error("IndexedDB unavailable"));
            return;
        }

        const req = window.indexedDB.open(DB_NAME, DB_VERSION);

        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: "key" });
            }
        };

        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error || new Error("Failed to open IndexedDB"));
    });
}

async function run(storeMode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, storeMode);
        const store = tx.objectStore(STORE_NAME);
        const req = fn(store);

        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error || new Error("IndexedDB request failed"));

        tx.oncomplete = () => db.close();
        tx.onerror = () => {
            db.close();
            reject(tx.error || new Error("IndexedDB transaction failed"));
        };
    });
}

export async function getPlanMedia(key) {
    if (!key) return null;
    try {
        const row = await run("readonly", (store) => store.get(key));
        return row?.media || null;
    } catch {
        return null;
    }
}

export async function getManyPlanMedia(keys) {
    const out = {};
    await Promise.all((keys || []).map(async (key) => {
        const media = await getPlanMedia(key);
        if (media) out[key] = media;
    }));
    return out;
}

export async function setPlanMedia(key, media) {
    if (!key || !media) return;
    try {
        await run("readwrite", (store) => store.put({ key, media }));
    } catch {
        // best-effort persistence
    }
}

export async function deletePlanMedia(key) {
    if (!key) return;
    try {
        await run("readwrite", (store) => store.delete(key));
    } catch {
        // best-effort delete
    }
}

export async function clearPlanMedia() {
    try {
        await run("readwrite", (store) => store.clear());
    } catch {
        // best-effort clear
    }
}

