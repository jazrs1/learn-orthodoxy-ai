import { NextResponse } from "next/server";
import type { SourceRef } from "../../../lib/chat-types";
import { Language, normalizeLanguage } from "../../../lib/i18n";

export const runtime = "nodejs";

type SaintDetailRequest = {
  name?: string;
  language?: Language;
};

type BackendChatResponse = {
  answer?: string;
  entities?: string[];
  options?: string[];
  sources?: SourceRef[];
};

function backendUrl() {
  const value = process.env.ORTHODOX_API_URL || process.env.NEXT_PUBLIC_API_URL || "";
  return value.trim().replace(/\/+$/, "");
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SaintDetailRequest;
  const name = body.name?.trim() || "";
  const language = normalizeLanguage(body.language);

  if (!name) {
    return NextResponse.json({ error: "Saint name is required." }, { status: 400 });
  }

  const apiBaseUrl = backendUrl();
  if (!apiBaseUrl) {
    return NextResponse.json(
      {
        error: "The backend API URL is not configured. Set ORTHODOX_API_URL or NEXT_PUBLIC_API_URL.",
      },
      { status: 500 }
    );
  }

  try {
    const backendQuestion = language === "ar" ? `من هو ${name}؟` : `search saint: ${name}`;
    console.log("SAINT_DETAIL_PAYLOAD", { name, language, question: backendQuestion });

    const backendResponse = await fetch(`${apiBaseUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: backendQuestion,
        history: [],
        top_k: 8,
        mode: "saints",
        language,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(20000),
    });

    const data = (await backendResponse.json().catch(() => ({}))) as BackendChatResponse & { detail?: string };
    if (!backendResponse.ok) {
      return NextResponse.json(
        { error: data.detail || "Unable to load saint details right now." },
        { status: backendResponse.status >= 400 ? backendResponse.status : 502 }
      );
    }

    return NextResponse.json({
      answer: data.answer || "",
      entities: Array.isArray(data.entities) ? data.entities : [],
      options: Array.isArray(data.options) ? data.options : [],
      sources: Array.isArray(data.sources) ? data.sources : [],
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error && error.name !== "TimeoutError"
            ? error.message
            : "Unable to reach the Orthodox AI backend right now.",
      },
      { status: 500 }
    );
  }
}
