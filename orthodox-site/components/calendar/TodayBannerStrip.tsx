"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { calendarStrings, fill, moreCommemorations } from "../../lib/calendar/strings";
import { localCalendarDateScript } from "../../lib/calendar/today";
import type { DayView } from "../../lib/calendar/view";
import type { Language } from "../../lib/i18n";
import { queueChatMessage } from "../../lib/pending-chat";
import { useLanguage } from "../LanguageProvider";
import { calendarHref, commemorationTitle, dayHeadline, saintHref } from "./labels";
import { useLocalToday } from "./useLocalToday";

/**
 * Renders every candidate day and shows the visitor's (CAL-005). The inline script right after the
 * strip picks the day before the first paint, so nothing moves; after hydration React reads the
 * same local date and keeps the DOM as the script left it.
 */
export default function TodayBannerStrip({ days, serverToday }: { days: DayView[]; serverToday: string }) {
  const { language } = useLanguage();
  const today = useLocalToday(serverToday);
  const shown = days.some((day) => day.date === today);
  const strings = calendarStrings(language);

  const pickScript =
    `(function(){var t=(${localCalendarDateScript()})();var s=document.currentScript;` +
    `var b=s&&s.previousElementSibling;if(!b)return;var d=b.querySelectorAll("[data-day]"),f=false;` +
    `for(var i=0;i<d.length;i++){var m=d[i].getAttribute("data-day")===t;d[i].hidden=!m;if(m)f=true}b.hidden=!f})()`;

  return (
    <>
      <aside className="today-banner" aria-label={strings.bannerLabel} hidden={!shown} suppressHydrationWarning>
        {days.map((day) => (
          <div key={day.date} data-day={day.date} hidden={day.date !== today} suppressHydrationWarning>
            <BannerDay day={day} language={language} />
          </div>
        ))}
      </aside>
      <script dangerouslySetInnerHTML={{ __html: pickScript }} />
    </>
  );
}

function BannerDay({ day, language }: { day: DayView; language: Language }) {
  const router = useRouter();
  const strings = calendarStrings(language);
  const headline = dayHeadline(day, language);
  const [first, ...rest] = day.commemorations;
  const indexName = first?.index?.[language];

  function askAboutSaint() {
    if (!indexName) return;
    queueChatMessage(fill(strings.saintQuestion, { name: indexName }));
    router.push("/chat");
  }

  return (
    <>
      <p className="today-banner-line">
        <span className="today-banner-label">{strings.today}</span>
        <Link
          href={calendarHref(day.date)}
          className="today-banner-date"
          aria-label={`${day.label[language]}, ${day.coptic.label[language]}. ${strings.openDay}`}
        >
          {day.coptic.label[language]}
        </Link>
        {headline ? (
          <>
            <span className="today-banner-sep" aria-hidden="true">
              ·
            </span>
            <span className="today-banner-observance">{headline}</span>
          </>
        ) : null}
      </p>
      {first ? (
        <p className="today-banner-line today-banner-saint">
          {indexName ? (
            <Link href={saintHref(indexName)} className="today-banner-saint-link" {...commemorationTitle(first, language)} />
          ) : (
            <span {...commemorationTitle(first, language)} />
          )}
          {rest.length ? (
            <Link href={calendarHref(day.date)} className="today-banner-more">
              {moreCommemorations(rest.length, language)}
            </Link>
          ) : null}
          {indexName ? (
            <button type="button" className="today-banner-ask" onClick={askAboutSaint}>
              {strings.askAboutSaint}
            </button>
          ) : null}
        </p>
      ) : null}
    </>
  );
}
