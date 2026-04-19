const KEY = "rsv.sessionId";

export function getSessionId(): string {
  let sid = localStorage.getItem(KEY);
  if (!sid) {
    sid =
      (globalThis.crypto?.randomUUID?.() ?? `sid-${Date.now().toString(36)}`)
        .replace(/-/g, "")
        .slice(0, 12);
    localStorage.setItem(KEY, sid);
  }
  return sid;
}
