const PREFIX = "motgu-contentengine:idempotency:";

function storageKey(key: string): string {
  return `${PREFIX}${key}`;
}

export function getOrCreateIdempotencyKey(key: string): string {
  if (typeof window === "undefined") return crypto.randomUUID();
  const storage = window.sessionStorage;
  const existing = storage.getItem(storageKey(key));
  if (existing) return existing;
  const created = crypto.randomUUID();
  storage.setItem(storageKey(key), created);
  return created;
}

export function clearIdempotencyKey(key: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(storageKey(key));
}
