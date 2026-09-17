"use client";

import { HOME_CONTENT } from "../lib/home-content";
import { IconArrowForward } from "./Icons";
import { useLanguage } from "./LanguageProvider";

type ExampleQuestionsProps = {
  onPick: (question: string) => void;
  disabled?: boolean;
  /** Visible label above the list; defaults to the landing page's "Begin with a question". */
  label?: string;
  limit?: number;
};

// Example questions set like a table of contents: one clickable row per question, with a
// dotted leader and hairline separators (UI-014).
export default function ExampleQuestions({ onPick, disabled = false, label, limit }: ExampleQuestionsProps) {
  const { language } = useLanguage();
  const content = HOME_CONTENT[language];
  const questions = typeof limit === "number" ? content.examples.slice(0, limit) : content.examples;
  const labelId = `examples-${language}`;

  return (
    <div className="example-questions">
      <p className="section-label" id={labelId}>
        {label ?? content.examplesLabel}
      </p>
      <ul className="toc-list" aria-labelledby={labelId}>
        {questions.map((question) => (
          <li key={question}>
            <button type="button" className="toc-row" onClick={() => onPick(question)} disabled={disabled}>
              <span className="toc-text">{question}</span>
              <span className="toc-leader" aria-hidden="true" />
              <IconArrowForward size={16} className="toc-arrow" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
