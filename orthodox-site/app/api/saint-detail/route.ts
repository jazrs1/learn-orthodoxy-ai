import { NextResponse } from "next/server";
import { backendConfigError, backendFetch } from "../../../lib/backend";
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
  can_learn_more?: boolean;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SaintDetailRequest;
  const name = body.name?.trim() || "";
  const language = normalizeLanguage(body.language);

  if (!name) {
    return NextResponse.json({ error: "Saint name is required." }, { status: 400 });
  }

  const configError = backendConfigError();
  if (configError) {
    return NextResponse.json({ error: configError }, { status: 500 });
  }

  try {
    const backendQuestion = language === "ar" ? `من هو ${name}؟` : `search saint: ${name}`;

    const backendResponse = await backendFetch("/chat", {
      request,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: backendQuestion,
        history: [],
        top_k: 8,
        mode: "saints",
        language,
      }),
      timeoutMs: 20000,
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
      canLearnMore: data.can_learn_more === true,
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
