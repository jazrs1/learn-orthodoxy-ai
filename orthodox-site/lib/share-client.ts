// Sharing an answer's link from the browser (UI-030). Phones open the system share sheet with the
// question as the title; elsewhere, or where the sheet isn't available, the link is copied.
//
// Both the share sheet and the clipboard need a recent tap, and the link is only known once the
// server has made it. So the clipboard is handed the pending link at once (Safari accepts a
// promise), and if a browser still refuses, the caller keeps the link for the next tap.

export type ShareOutcome = "shared" | "copied" | "cancelled" | "needs-tap";

export class ShareLinkError extends Error {
  status: number;
  constructor(status: number) {
    super(`share link failed (${status})`);
    this.status = status;
  }
}

/** Asks the server for a link to this answer; resolves to the full URL. */
export async function createShareLink(messageId: string): Promise<string> {
  const response = await fetch("/api/share", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // The page dates the answer by the sharer's calendar (UI-034).
    body: JSON.stringify({ messageId, timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone }),
  });
  const data = (await response.json().catch(() => ({}))) as { path?: unknown };
  if (!response.ok || typeof data.path !== "string") throw new ShareLinkError(response.status);
  return new URL(data.path, window.location.origin).toString();
}

export function prefersShareSheet(): boolean {
  return (
    typeof navigator.share === "function" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(pointer: coarse)").matches
  );
}

async function copyText(text: Promise<string>): Promise<void> {
  if (typeof ClipboardItem !== "undefined" && typeof navigator.clipboard?.write === "function") {
    try {
      const blob = text.then((value) => new Blob([value], { type: "text/plain" }));
      await navigator.clipboard.write([new ClipboardItem({ "text/plain": blob })]);
      return;
    } catch {
      // Older engines take only ready values; try the plain call below.
    }
  }
  await navigator.clipboard.writeText(await text);
}

/** Call straight from the click. Rejects only when the link itself couldn't be made. */
export async function shareLink(link: Promise<string>, title: string): Promise<ShareOutcome> {
  if (prefersShareSheet()) {
    const url = await link;
    try {
      await navigator.share({ title, url });
      return "shared";
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return "cancelled";
      // No share sheet after all (or the tap is too old for it): copy instead.
      try {
        await navigator.clipboard.writeText(url);
        return "copied";
      } catch {
        return "needs-tap";
      }
    }
  }
  try {
    await copyText(link);
    return "copied";
  } catch {
    await link; // a failed link is the error to report, not the clipboard
    return "needs-tap";
  }
}
