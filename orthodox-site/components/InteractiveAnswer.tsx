"use client";

import { useMemo } from "react";
import { isValidSaintName, normalizeSaintKey } from "./saintNameUtils";

type InteractiveAnswerProps = {
  answer: string;
  entities?: string[];
  saintLookup?: Set<string>;
};

type Segment = {
  text: string;
  bold: boolean;
};

function parseBoldSegments(text: string): Segment[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts
    .filter(Boolean)
    .map((part) => {
      const isBold = part.startsWith("**") && part.endsWith("**");
      return {
        text: isBold ? part.slice(2, -2) : part,
        bold: isBold,
      };
    });
}

function handleNameClick(name: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent("chat:insertText", {
      detail: name.trim(),
    })
  );
}

export default function InteractiveAnswer({
  answer,
  entities = [],
  saintLookup = new Set<string>(),
}: InteractiveAnswerProps) {
  const clickableNames = useMemo(() => {
    return new Set(
      entities
        .filter((entity) => isValidSaintName(entity, saintLookup))
        .map(normalizeSaintKey)
        .filter(Boolean)
    );
  }, [entities, saintLookup]);

  const lines = answer.split("\n");

  return (
    <div className="interactive-answer">
      {lines.map((line, lineIndex) => {
        if (!line.trim()) {
          return <div key={`line-${lineIndex}`} className="answer-spacer" />;
        }

        const segments = parseBoldSegments(line);

        return (
          <p key={`line-${lineIndex}`} className="answer-line">
            {segments.map((segment, segmentIndex) => {
              if (!segment.bold) {
                return <span key={`seg-${lineIndex}-${segmentIndex}`}>{segment.text}</span>;
              }

              const normalized = normalizeSaintKey(segment.text);
              if (!clickableNames.has(normalized) || !isValidSaintName(segment.text, saintLookup)) {
                return <span key={`seg-${lineIndex}-${segmentIndex}`}>{segment.text}</span>;
              }

              return (
                <button
                  key={`seg-${lineIndex}-${segmentIndex}`}
                  type="button"
                  className="answer-name-button"
                  onClick={() => handleNameClick(segment.text)}
                >
                  <strong>{segment.text}</strong>
                </button>
              );
            })}
          </p>
        );
      })}
    </div>
  );
}
