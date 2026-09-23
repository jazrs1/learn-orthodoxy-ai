import "server-only";

import { NextResponse } from "next/server";
import type { SaintDetail, SourceRef } from "./chat-types";
import { Language, normalizeLanguage } from "./i18n";
import { backendSaintSelection, namesakesFromBackend, optionsFromBackend } from "./message-options";

// The saints pane's answer, shared by /api/saint-detail and /api/saint-detail/stream (UI-029).
// It is not saved to a conversation.

type SaintDetailRequest = {
  name?: string;
  language?: Language;
  saintId?: string;
  namesakesOf?: string;
};

export type BackendSaintResponse = {
  answer?: string;
  entities?: string[];
  options?: string[];
  option_ids?: string[];
  namesakes?: { label?: string; name?: string } | null;
  sources?: SourceRef[];
  can_learn_more?: boolean;
};

/** The backend request for a saint, or null when no name was given. */
export async function saintDetailBackendBody(request: Request): Promise<string | null> {
  const body = (await request.json().catch(() => ({}))) as SaintDetailRequest;
  const name = body.name?.trim() || "";
  if (!name) return null;
  // A menu choice carries the entry's ID; a name from the saints list or a calendar link is
  // resolved by its exact name, never shown a menu for (RET-010).
  const saintSelection = backendSaintSelection({ saintId: body.saintId, namesakesOf: body.namesakesOf, saintName: name });
  const language = normalizeLanguage(body.language);
  return JSON.stringify({
    question: language === "ar" ? `من هو ${name}؟` : `search saint: ${name}`,
    history: [],
    top_k: 8,
    mode: "saints",
    language,
    ...saintSelection,
  });
}

export function saintDetailFromBackend(data: BackendSaintResponse): SaintDetail {
  return {
    answer: data.answer || "",
    entities: Array.isArray(data.entities) ? data.entities : [],
    ...optionsFromBackend(data),
    namesakes: namesakesFromBackend(data) ?? null,
    sources: Array.isArray(data.sources) ? data.sources : [],
    canLearnMore: data.can_learn_more === true,
  };
}

/** A request that threw (timeout, network): the error reply. */
export function saintErrorReply(error: unknown) {
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
