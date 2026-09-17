"use client";

import { HOME_CONTENT } from "../lib/home-content";
import { useLanguage } from "./LanguageProvider";

type ExampleQuestionsProps = {
  onPick: (question: string) => void;
  disabled?: boolean;
  /** Visible label above the chips; defaults to the landing page's "Try one of these". */
  label?: string;
  limit?: number;
};

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
      <ul className="example-questions-list" aria-labelledby={labelId}>
        {questions.map((question) => (
          <li key={question}>
            <button
              type="button"
              className="message-option-chip example-question"
              onClick={() => onPick(question)}
              disabled={disabled}
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
