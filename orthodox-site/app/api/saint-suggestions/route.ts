import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

function backendUrl() {
  const value = process.env.ORTHODOX_API_URL || process.env.NEXT_PUBLIC_API_URL || "";
  return value.trim().replace(/\/+$/, "");
}

export async function GET(request: NextRequest) {
  const apiBaseUrl = backendUrl();
  if (!apiBaseUrl) {
    return NextResponse.json(
      {
        error: "The backend API URL is not configured. Set ORTHODOX_API_URL or NEXT_PUBLIC_API_URL.",
      },
      { status: 500 }
    );
  }

  const upstreamUrl = new URL(`${apiBaseUrl}/saint-suggestions`);
  request.nextUrl.searchParams.forEach((value, key) => {
    upstreamUrl.searchParams.set(key, value);
  });

  try {
    const response = await fetch(upstreamUrl, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
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
