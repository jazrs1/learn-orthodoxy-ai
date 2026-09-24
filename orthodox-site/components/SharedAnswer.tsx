import Link from "next/link";
import { directionForLanguage, translations } from "../lib/i18n";
import { shareDate } from "../lib/share-page";
import type { Snapshot } from "../lib/share-store";
import AnswerWithSources from "./AnswerWithSources";
import { IconArrowForward } from "./Icons";

// A shared answer at /s/<id> (UI-030): the question, the answer as it was given, its sources, and
// how it was made. Set in the answer's own language, whatever language the rest of the page is in.
export default function SharedAnswer({ snapshot }: { snapshot: Snapshot }) {
  const language = snapshot.language;
  const t = translations[language];
  const date = shareDate(snapshot);

  return (
    <article className="shared-answer" lang={language} dir={directionForLanguage(language)}>
      <p className="shared-answer-label">{t.sharedAnswerLabel}</p>
      <h1 className="page-title shared-answer-question">{snapshot.question}</h1>
      <div className="shared-answer-body">
        <AnswerWithSources
          answerId={`shared-${snapshot.id}`}
          answer={snapshot.answer}
          sources={snapshot.sources}
          language={language}
        />
      </div>
      <footer className="shared-answer-footer">
        <p>{t.sharedFooter}.</p>
        <p>
          {t.sharedAnsweredOn.split("{date}")[0]}
          <time dateTime={date.iso}>{date.text}</time>
          {t.sharedAnsweredOn.split("{date}")[1]}
        </p>
      </footer>
      <div className="shared-answer-actions">
        <Link href="/" className="button button-primary">
          <span>{t.askYourOwn}</span>
          <IconArrowForward size={16} />
        </Link>
      </div>
    </article>
  );
}
