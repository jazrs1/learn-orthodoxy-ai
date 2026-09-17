import { ApiError } from "./chat-client";
import type { TranslationKey } from "./i18n";

/**
 * Maps a failed chat request to a message a learner can act on. Server text (which can name
 * environment variables or internal hosts) is never shown (UI-008).
 */
export function chatErrorKey(error: unknown): TranslationKey {
  if (error instanceof ApiError) {
    if (error.status === 429) return "errorBusy";
    if (error.status === 400 && /too long/i.test(error.message)) return "errorTooLong";
    return "errorGeneric";
  }
  // fetch() rejects with a TypeError when the network is down.
  if (error instanceof TypeError) return "errorOffline";
  return "errorGeneric";
}
