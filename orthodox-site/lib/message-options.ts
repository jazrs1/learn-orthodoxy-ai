/**
 * Options under an assistant message: follow-up questions, and saint choices from a namesake
 * menu (RET-010). A saint choice carries the entry's ID (the backend's `option_ids`), and
 * choosing it sends that ID, so the backend selects that exact entry instead of matching the
 * chip text against the saints index again (which is how "St. Athanasius the Apostolic" kept
 * bringing the same menu back).
 */

import type { NamesakeLink } from "./chat-types";
import type { Language } from "./i18n";

export type MessageOption = { label: string; saintId?: string };

/** The `options` jsonb column: plain strings (follow-up questions, and menus saved before
 * RET-010), `{ label, saintId }` for a saint choice, and at most one `{ label, namesakesOf }` for
 * the "Looking for a different St. X?" link (RET-011). */
export type StoredOption = string | { label: string; saintId?: string } | { label: string; namesakesOf: string };

export function encodeStoredOptions(
  options: string[] = [],
  optionIds: string[] = [],
  namesakes?: NamesakeLink
): StoredOption[] {
  const stored: StoredOption[] = options.map((label, index) =>
    optionIds[index] ? { label, saintId: optionIds[index] } : label
  );
  return namesakes ? [...stored, { label: namesakes.label, namesakesOf: namesakes.name }] : stored;
}

export function decodeStoredOptions(raw: unknown): { options: string[]; optionIds: string[]; namesakes?: NamesakeLink } {
  const options: string[] = [];
  const optionIds: string[] = [];
  let namesakes: NamesakeLink | undefined;
  if (!Array.isArray(raw)) return { options, optionIds };
  for (const item of raw) {
    if (typeof item === "string") {
      options.push(item);
      optionIds.push("");
    } else if (item && typeof item === "object" && typeof (item as { label?: unknown }).label === "string") {
      const { label, saintId, namesakesOf } = item as { label: string; saintId?: unknown; namesakesOf?: unknown };
      if (typeof namesakesOf === "string") {
        namesakes = { label, name: namesakesOf };
        continue;
      }
      options.push(label);
      optionIds.push(typeof saintId === "string" ? saintId : "");
    }
  }
  return namesakes ? { options, optionIds, namesakes } : { options, optionIds };
}

export function normalizeOptionText(option: string) {
  return option
    .trim()
    .replace(/^You might also ask:\s*/i, "")
    .replace(/^يمكنك أيضًا أن تسأل[:：]\s*/i, "")
    .replace(/^[-–—•]\s*/, "")
    .trim();
}

export function looksLikeQuestionOption(option: string) {
  return (
    option.includes("?") ||
    option.includes("؟") ||
    /^(هل|كيف|لماذا|ما|ماذا|متى|أين|من)\b/i.test(option) ||
    /^(i\s+(?:would\s+like|want)|would|how|why|what|when|where|who|which|can|should|do|does|is|are)\b/i.test(option)
  );
}

export function followUpToUserMessage(option: string) {
  const cleaned = option.trim().replace(/[?？]\s*$/, "").trim();
  const replacements: Array<[RegExp, string]> = [
    [/^would\s+you\s+like\s+to\s+/i, "I would like to "],
    [/^would\s+you\s+like\s+/i, "I would like "],
    [/^do\s+you\s+want\s+to\s+/i, "I want to "],
    [/^do\s+you\s+want\s+/i, "I want "],
  ];

  for (const [pattern, replacement] of replacements) {
    if (pattern.test(cleaned)) {
      return cleaned.replace(pattern, replacement).trim();
    }
  }

  return cleaned;
}

/**
 * The options to show: up to two follow-up questions, else the saint choices. An option with a
 * saint ID is always a saint choice; one without (menus saved before RET-010) is one when
 * `isSaintName` recognises it.
 */
export function visibleMessageOptions(
  options: string[] | undefined,
  optionIds: string[] | undefined,
  isSaintName: (label: string) => boolean
): MessageOption[] {
  const saintOptions: MessageOption[] = [];
  const questionOptions: MessageOption[] = [];
  const seen = new Set<string>();

  (options || []).forEach((option, index) => {
    const label = normalizeOptionText(option);
    if (!label) return;
    const saintId = optionIds?.[index] || "";

    if (saintId || isSaintName(label)) {
      const key = saintId ? `id:${saintId}` : label.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      saintOptions.push(saintId ? { label, saintId } : { label });
    } else if (looksLikeQuestionOption(label)) {
      const key = followUpToUserMessage(label).toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      questionOptions.push({ label });
    }
  });

  return questionOptions.length ? questionOptions.slice(0, 2) : saintOptions;
}

export type SaintSelection = {
  question: string;
  mode: "saints";
  /** The entry chosen from a menu: the backend selects it by this ID. */
  saintId?: string;
  /** A choice without an ID (a menu saved before RET-010): resolved by its exact name. */
  saintName?: string;
};

/** The chat request for a saint choice. The question is only what the conversation shows and
 * keeps; the entry is selected by `saintId`. */
export function saintSelectionRequest(option: MessageOption, language: Language): SaintSelection {
  const label = option.label.trim();
  return {
    question: language === "ar" ? `من هو ${label}؟` : `search saint: ${label}`,
    mode: "saints",
    ...(option.saintId ? { saintId: option.saintId } : { saintName: label }),
  };
}

/** The "Looking for a different St. X?" link of a backend reply, when it has one. */
export function namesakesFromBackend(data: { namesakes?: unknown }): NamesakeLink | undefined {
  const link = data.namesakes as { label?: unknown; name?: unknown } | null | undefined;
  return link && typeof link.label === "string" && typeof link.name === "string" && link.label && link.name
    ? { label: link.label, name: link.name }
    : undefined;
}

/** A backend reply's options and their entry IDs, kept aligned by position (`option_ids` is
 * sent only with saint menus). */
export function optionsFromBackend(data: { options?: unknown; option_ids?: unknown }): {
  options: string[];
  optionIds: string[];
} {
  const rawOptions = Array.isArray(data.options) ? data.options : [];
  const rawIds = Array.isArray(data.option_ids) ? data.option_ids : [];
  const options: string[] = [];
  const optionIds: string[] = [];
  rawOptions.forEach((option, index) => {
    if (typeof option !== "string") return;
    options.push(option);
    optionIds.push(typeof rawIds[index] === "string" ? (rawIds[index] as string) : "");
  });
  return { options, optionIds };
}

/** The chat request behind "Looking for a different St. X?": the menu of that name's other saints. */
export function namesakesRequest(link: NamesakeLink) {
  return { question: link.label, mode: "saints" as const, namesakesOf: link.name };
}

/** The backend fields for a saint choice: the entry ID when there is one, else the menu of a
 * name's other saints (the namesakes link), else the exact name. */
export function backendSaintSelection(body: { saintId?: unknown; saintName?: unknown; namesakesOf?: unknown }): {
  saint_id?: string;
  saint_name?: string;
  namesakes_of?: string;
} {
  const saintId = typeof body.saintId === "string" ? body.saintId.trim().slice(0, 200) : "";
  if (saintId) return { saint_id: saintId };
  const namesakesOf = typeof body.namesakesOf === "string" ? body.namesakesOf.trim().slice(0, 200) : "";
  if (namesakesOf) return { namesakes_of: namesakesOf };
  const saintName = typeof body.saintName === "string" ? body.saintName.trim().slice(0, 300) : "";
  return saintName ? { saint_name: saintName } : {};
}
