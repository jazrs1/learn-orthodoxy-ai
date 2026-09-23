import { NextResponse } from "next/server";
import { backendConfigError } from "../../../../lib/backend";
import {
  BackendSaintResponse,
  saintDetailBackendBody,
  saintDetailFromBackend,
  saintErrorReply,
} from "../../../../lib/saint-detail";
import { RouteTiming } from "../../../../lib/route-timing";
import {
  eventStreamResponse,
  fetchBackendStream,
  isEventStream,
  relayStream,
  timingHeaders,
} from "../../../../lib/stream-proxy";

export const runtime = "nodejs";
export const maxDuration = 60;

// The saints pane's answer streamed like the chat's (UI-029): the same backend /chat/stream and
// relay, with `done` carrying the saint detail /api/saint-detail returns. Nothing is saved.
export async function POST(request: Request) {
  const timing = new RouteTiming("saint_detail_stream");
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
    backendResponse = await timing.time("backend_headers", () => fetchBackendStream(request, backendBody, upstream));
    timing.set({ request_id: backendResponse.headers.get("x-request-id") });
    if (!backendResponse.ok) {
      const data = (await backendResponse.json().catch(() => ({}))) as { detail?: string };
      return NextResponse.json(
        { error: data.detail || "Unable to load saint details right now." },
        { status: backendResponse.status >= 400 ? backendResponse.status : 502 }
      );
    }
    if (!isEventStream(backendResponse)) {
      const detail = saintDetailFromBackend((await backendResponse.json()) as BackendSaintResponse);
      timing.set({ streamed: false });
      timing.log();
      return NextResponse.json(detail, { headers: timingHeaders(timing, backendResponse) });
    }
  } catch (error) {
    return saintErrorReply(error);
  }

  const headers = timingHeaders(timing, backendResponse);
  return eventStreamResponse(
    relayStream<BackendSaintResponse>(
      backendResponse.body,
      upstream,
      async (payload, emit) => {
        timing.mark("done");
        emit("done", saintDetailFromBackend(payload));
      },
      {
        onFirstDelta: () => timing.mark("first_delta"),
        onEnd: (outcome) => {
          timing.set({ streamed: true, outcome });
          timing.log();
        },
      }
    ),
    headers
  );
}
