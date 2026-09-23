import { NextResponse } from "next/server";
import { backendConfigError } from "../../../../lib/backend";
import {
  BackendSaintResponse,
  saintDetailBackendBody,
  saintDetailFromBackend,
  saintErrorReply,
} from "../../../../lib/saint-detail";
import { eventStreamResponse, fetchBackendStream, isEventStream, relayStream } from "../../../../lib/stream-proxy";

export const runtime = "nodejs";
export const maxDuration = 60;

// The saints pane's answer streamed like the chat's (UI-029): the same backend /chat/stream and
// relay, with `done` carrying the saint detail /api/saint-detail returns. Nothing is saved.
export async function POST(request: Request) {
  const backendBody = await saintDetailBackendBody(request);
  if (!backendBody) {
    return NextResponse.json({ error: "Saint name is required." }, { status: 400 });
  }
  const configError = backendConfigError();
  if (configError) {
    return NextResponse.json({ error: configError }, { status: 500 });
  }

  const upstream = new AbortController();
  let backendResponse: Response;
  try {
    backendResponse = await fetchBackendStream(request, backendBody, upstream);
    if (!backendResponse.ok) {
      const data = (await backendResponse.json().catch(() => ({}))) as { detail?: string };
      return NextResponse.json(
        { error: data.detail || "Unable to load saint details right now." },
        { status: backendResponse.status >= 400 ? backendResponse.status : 502 }
      );
    }
    if (!isEventStream(backendResponse)) {
      return NextResponse.json(saintDetailFromBackend((await backendResponse.json()) as BackendSaintResponse));
    }
  } catch (error) {
    return saintErrorReply(error);
  }

  return eventStreamResponse(
    relayStream<BackendSaintResponse>(backendResponse.body, upstream, async (payload) => saintDetailFromBackend(payload))
  );
}
