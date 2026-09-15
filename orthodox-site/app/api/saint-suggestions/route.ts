import { NextRequest, NextResponse } from "next/server";
import { backendConfigError, backendFetch, backendUrl } from "../../../lib/backend";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const configError = backendConfigError();
  if (configError) {
    return NextResponse.json({ error: configError }, { status: 500 });
  }

  const upstreamUrl = new URL(`${backendUrl()}/saint-suggestions`);
  request.nextUrl.searchParams.forEach((value, key) => {
    upstreamUrl.searchParams.set(key, value);
  });

  try {
    const response = await backendFetch(upstreamUrl.toString(), {
      request,
      timeoutMs: 15000,
    });

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error && error.name !== "TimeoutError"
            ? error.message
            : "Unable to reach the saint suggestions service right now.",
      },
      { status: 500 }
    );
  }
}
