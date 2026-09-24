import { NextResponse } from "next/server";
import { clientIpFromRequest } from "../../../lib/backend";
import { getOrCreateAnonymousSessionId } from "../../../lib/chat-auth";
import { query } from "../../../lib/db";
import { allowShareRequest, ipHash, loadShareableAnswer, saveSnapshot } from "../../../lib/share-store";

export const runtime = "nodejs";

// POST {messageId} → {path: "/s/<id>"} (UI-030). The snapshot is made from the stored answer and
// the question before it, for a visitor's own conversation only; the browser sends nothing but
// the answer's ID. Limited per client (SHARE_RATE_LIMIT per SHARE_RATE_WINDOW_MINUTES).
export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { messageId?: unknown };
  const messageId = typeof body.messageId === "string" ? body.messageId.trim() : "";
  if (!messageId || messageId.length > 100) {
    return NextResponse.json({ error: "An answer to share is required." }, { status: 400 });
  }

  const sessionId = await getOrCreateAnonymousSessionId();
  const db = { query };
  try {
    const secret = process.env.SHARE_RATE_SECRET || process.env.ORTHODOX_API_KEY || "";
    if (!(await allowShareRequest(db, ipHash(clientIpFromRequest(request), secret)))) {
      return NextResponse.json({ error: "Too many links. Please try again in a few minutes." }, { status: 429 });
    }
    const content = await loadShareableAnswer(db, sessionId, messageId);
    if (!content) {
      return NextResponse.json({ error: "This answer can't be shared." }, { status: 404 });
    }
    const { id, reused } = await saveSnapshot(db, content);
    return NextResponse.json({ path: `/s/${id}`, reused });
  } catch (error) {
    console.error("sharing an answer failed", error);
    return NextResponse.json({ error: "Couldn't create a link right now." }, { status: 500 });
  }
}
