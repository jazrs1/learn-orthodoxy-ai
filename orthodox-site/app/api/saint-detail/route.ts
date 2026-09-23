import { NextResponse } from "next/server";
import { backendConfigError, backendFetch } from "../../../lib/backend";
import {
  BackendSaintResponse,
  saintDetailBackendBody,
  saintDetailFromBackend,
  saintErrorReply,
} from "../../../lib/saint-detail";

export const runtime = "nodejs";

// The saints pane's answer in one reply. The pane streams through /api/saint-detail/stream and
// falls back to this route when the stream can't start (UI-029).
export async function POST(request: Request) {
  const backendBody = await saintDetailBackendBody(request);
  if (!backendBody) {
    return NextResponse.json({ error: "Saint name is required." }, { status: 400 });
  }

  const configError = backendConfigError();
  if (configError) {
    return NextResponse.json({ error: configError }, { status: 500 });
  }

  try {
    const backendResponse = await backendFetch("/chat", {
      request,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: backendBody,
      timeoutMs: 20000,
    });

    const data = (await backendResponse.json().catch(() => ({}))) as BackendSaintResponse & { detail?: string };
    if (!backendResponse.ok) {
      return NextResponse.json(
        { error: data.detail || "Unable to load saint details right now." },
        { status: backendResponse.status >= 400 ? backendResponse.status : 502 }
      );
    }

    return NextResponse.json(saintDetailFromBackend(data));
  } catch (error) {
    return saintErrorReply(error);
  }
}
