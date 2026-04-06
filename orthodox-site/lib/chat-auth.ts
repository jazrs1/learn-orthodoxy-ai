import "server-only";

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const COOKIE_NAME = "orthodox_anon_session";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export async function getOrCreateAnonymousSessionId(
  response?: NextResponse,
  fallbackSessionId?: string
) {
  const cookieStore = await cookies();
  const existing = cookieStore.get(COOKIE_NAME)?.value;
  if (existing) return existing;

  const sessionId = fallbackSessionId || crypto.randomUUID();
  if (response) {
    response.cookies.set(COOKIE_NAME, sessionId, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: COOKIE_MAX_AGE,
    });
  }

  return sessionId;
}
