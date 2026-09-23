/** The backend caches the answers to the home page's example questions (RET-017) by exact text:
 * its list must be the four questions the page shows, in each language. Run with `npm test`. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, test } from "node:test";
import { HOME_CONTENT } from "./home-content.ts";

// The number of example questions the home page and the empty chat show (ExampleQuestions limit).
const SHOWN = 4;

describe("cached example answers", () => {
  const cached = JSON.parse(
    readFileSync(new URL("../../data/cached_answer_questions.json", import.meta.url), "utf8")
  ) as Record<"en" | "ar", string[]>;

  for (const language of ["en", "ar"] as const) {
    test(`the backend's list is the page's example questions (${language})`, () => {
      assert.deepEqual(cached[language], HOME_CONTENT[language].examples.slice(0, SHOWN));
    });
  }
});
