/**
 * Past chats listed once per title (UI-020). Asking the same question twice made two chats with the
 * same title, so the list repeated itself ("What is prayer?" three times). The list keeps the most
 * recent chat of each title (the list comes newest first) and always the open one, in the place of
 * its title. Older chats of the same title are only hidden from the list; nothing is deleted.
 */
export function titleKey(title: string): string {
  return (title || "")
    .normalize("NFKC")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/[\s?؟.!]+$/u, "")
    .toLowerCase();
}

export function uniqueByTitle<T extends { id: string; title: string }>(sessions: T[], activeId = ""): T[] {
  const shown: T[] = [];
  const slot = new Map<string, number>();
  for (const session of sessions) {
    const key = titleKey(session.title);
    if (!key) {
      shown.push(session); // untitled chats are not merged
      continue;
    }
    const at = slot.get(key);
    if (at === undefined) {
      slot.set(key, shown.length);
      shown.push(session);
    } else if (session.id === activeId) {
      shown[at] = session;
    }
  }
  return shown;
}
