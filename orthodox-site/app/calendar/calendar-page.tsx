"use client";

import Form from "next/form";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { calendarHref, commemorationTitle, saintHref } from "../../components/calendar/labels";
import { useLocalToday } from "../../components/calendar/useLocalToday";
import { IconArrowForward } from "../../components/Icons";
import { useLanguage } from "../../components/LanguageProvider";
import PageDrawer from "../../components/PageDrawer";
import { addDays, weekday } from "../../lib/calendar/dates";
import type { MonthOption, MonthView } from "../../lib/calendar/month";
import { calendarStrings, fill } from "../../lib/calendar/strings";
import type { DayView } from "../../lib/calendar/view";
import type { Language } from "../../lib/i18n";
import { queueChatMessage } from "../../lib/pending-chat";

/** Set before a keyboard move crosses into another month, so the new page focuses that day. */
const FOCUS_KEY = "calendar:focus";

type Props = {
  month: MonthView;
  months: MonthOption[];
  initialDate: string;
  /** True when ?d= or ?m= chose the day; otherwise the page follows the visitor's own today. */
  dateFromUrl: boolean;
  clamped: boolean;
  serverToday: string;
  saintsSource: { name: string; url: string };
};

export default function CalendarPage({ month, months, initialDate, dateFromUrl, clamped, serverToday, saintsSource }: Props) {
  const { language, dir } = useLanguage();
  const strings = calendarStrings(language);
  const router = useRouter();
  const today = useLocalToday(serverToday);
  const [picked, setPicked] = useState<string | null>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const redirected = useRef(false);

  const byDate = new Map(month.days.map((day) => [day.date, day]));
  const inRange = (iso: string) => months.some((option) => option.value === iso.slice(0, 7));
  // Without a date in the URL the page opens on the visitor's today when it is in this month.
  const selected = picked ?? (!dateFromUrl && byDate.has(today) ? today : initialDate);
  const selectedDay = byDate.get(selected) ?? month.days[0];

  // Without a date in the URL, a visitor whose today is in another month (near midnight UTC) is
  // moved to it once.
  useEffect(() => {
    if (dateFromUrl || redirected.current || byDate.has(today) || !inRange(today)) return;
    redirected.current = true;
    router.replace(calendarHref(today));
  });

  // Finish a keyboard move that crossed into this month.
  useEffect(() => {
    let target: string | null = null;
    try {
      target = sessionStorage.getItem(FOCUS_KEY);
      sessionStorage.removeItem(FOCUS_KEY);
    } catch {
      target = null;
    }
    if (target) buttons.current.get(target)?.focus();
  }, []);

  function select(date: string, focus = false) {
    setPicked(date);
    window.history.replaceState(null, "", calendarHref(date));
    if (focus) buttons.current.get(date)?.focus();
  }

  function moveTo(date: string) {
    if (byDate.has(date)) {
      select(date, true);
    } else if (inRange(date)) {
      try {
        sessionStorage.setItem(FOCUS_KEY, date);
      } catch {
        // Focus simply stays on the page if storage is unavailable.
      }
      router.push(calendarHref(date), { scroll: false });
    }
  }

  function onGridKeyDown(event: KeyboardEvent<HTMLTableElement>) {
    const forward = dir === "rtl" ? -1 : 1;
    const day = weekday(selected);
    const moves: Record<string, number> = {
      ArrowRight: forward,
      ArrowLeft: -forward,
      ArrowDown: 7,
      ArrowUp: -7,
      Home: -day,
      End: 6 - day,
    };
    if (event.key in moves) {
      event.preventDefault();
      moveTo(addDays(selected, moves[event.key]));
    } else if (event.key === "PageDown" || event.key === "PageUp") {
      event.preventDefault();
      const target = event.key === "PageDown" ? month.next : month.previous;
      if (target) moveTo(`${target}-${String(Math.min(Number(selected.slice(8)), 28)).padStart(2, "0")}`);
    }
  }

  function goToToday() {
    if (byDate.has(today)) select(today, true);
    else if (inRange(today)) router.push(calendarHref(today));
  }

  const cells: Array<DayView | null> = [...Array(month.leadingBlanks).fill(null), ...month.days];
  while (cells.length % 7) cells.push(null);
  const weeks = Array.from({ length: cells.length / 7 }, (_, index) => cells.slice(index * 7, index * 7 + 7));

  return (
    <>
      <main className="calendar-page">
        <header className="calendar-header">
          <h1 className="page-title">{strings.pageTitle}</h1>
          <p className="page-subtitle">{strings.pageLead}</p>
          {clamped ? (
            <p className="calendar-note" role="status">
              {strings.outOfRange}
            </p>
          ) : null}
        </header>

        <div className="calendar-layout">
          <section className="calendar-month" aria-labelledby="calendar-month-title">
            <div className="calendar-toolbar">
              <div className="calendar-month-nav">
                <MonthLink target={month.previous} label={strings.previousMonth} direction="previous" />
                <h2 className="calendar-month-title" id="calendar-month-title">
                  <span>{month.label[language]}</span>
                  <span className="calendar-month-coptic">{month.coptic[language]}</span>
                </h2>
                <MonthLink target={month.next} label={strings.nextMonth} direction="next" />
              </div>
              <div className="calendar-tools">
                <Form action="/calendar" className="calendar-jump">
                  <label htmlFor="calendar-month-select" className="sr-only">
                    {strings.jumpToMonth}
                  </label>
                  <select id="calendar-month-select" name="m" defaultValue={month.month} className="calendar-select">
                    {months.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label[language]}
                      </option>
                    ))}
                  </select>
                  <button type="submit" className="button button-secondary">
                    {strings.go}
                  </button>
                </Form>
                <button type="button" className="button button-secondary" onClick={goToToday}>
                  {strings.goToToday}
                </button>
              </div>
            </div>

            <table role="grid" className="calendar-grid" aria-labelledby="calendar-month-title" onKeyDown={onGridKeyDown}>
              <thead>
                <tr>
                  {strings.weekdays.map((name, index) => (
                    <th key={name} scope="col" abbr={name}>
                      <span aria-hidden="true">{strings.weekdaysShort[index]}</span>
                      <span className="sr-only">{name}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weeks.map((week, row) => (
                  <tr key={row}>
                    {week.map((day, column) =>
                      day ? (
                        <td key={day.date} role="gridcell" aria-selected={day.date === selected}>
                          <DayCell
                            day={day}
                            language={language}
                            selected={day.date === selected}
                            isToday={day.date === today}
                            onSelect={() => select(day.date)}
                            register={(element) => {
                              if (element) buttons.current.set(day.date, element);
                              else buttons.current.delete(day.date);
                            }}
                          />
                        </td>
                      ) : (
                        <td key={`blank-${row}-${column}`} role="gridcell" className="calendar-blank" />
                      )
                    )}
                  </tr>
                ))}
              </tbody>
            </table>

            <ul className="calendar-legend">
              <li>
                <span className="calendar-mark calendar-mark-feast" aria-hidden="true" />
                {strings.legendFeast}
              </li>
              <li>
                <span className="calendar-mark calendar-mark-fast" aria-hidden="true" />
                {strings.legendFast}
              </li>
              <li>
                <span className="calendar-mark calendar-mark-free" aria-hidden="true" />
                {strings.legendFastFree}
              </li>
            </ul>
          </section>

          <DayDetail day={selectedDay} language={language} isToday={selectedDay.date === today} />
        </div>

        <footer className="calendar-sources">
          <h2 className="calendar-sources-title">{strings.attributionTitle}</h2>
          <p>
            {language === "ar" ? (
              strings.attributionDates
            ) : (
              <>
                Dates are calculated from the rules of the Coptic calendar and checked against the calendar of the{" "}
                <a href="https://suscopts.org/coptic-orthodox/fasts-and-feasts" rel="noopener">
                  Coptic Orthodox Metropolis of the Southern United States
                </a>
                .
              </>
            )}
          </p>
          <p>
            {strings.attributionSaints} (
            <a href={saintsSource.url} rel="noopener">
              {saintsSource.url.replace(/^https?:\/\//, "")}
            </a>
            ).
          </p>
        </footer>
      </main>
      <PageDrawer />
    </>
  );
}

function MonthLink({ target, label, direction }: { target: string | null; label: string; direction: "previous" | "next" }) {
  const icon = <IconArrowForward size={18} className={direction === "previous" ? "calendar-arrow-back" : undefined} />;
  if (!target) {
    return (
      <span className="calendar-month-link" aria-disabled="true" title={label}>
        {icon}
        <span className="sr-only">{label}</span>
      </span>
    );
  }
  return (
    <Link href={`/calendar?m=${target}`} className="calendar-month-link" aria-label={label} scroll={false}>
      {icon}
    </Link>
  );
}

type DayCellProps = {
  day: DayView;
  language: Language;
  selected: boolean;
  isToday: boolean;
  onSelect: () => void;
  register: (element: HTMLButtonElement | null) => void;
};

function DayCell({ day, language, selected, isToday, onSelect, register }: DayCellProps) {
  const strings = calendarStrings(language);
  const feast = day.observances[0];
  const saint = day.commemorations[0];
  const firstOfCopticMonth = day.coptic.day === 1 || day.dayNumber.en === "1";
  const label = [
    day.label[language],
    day.coptic.label[language],
    ...day.observances.map((observance) => observance.name[language]),
    day.fast?.name[language],
    isToday ? strings.todayMarker : undefined,
  ]
    .filter(Boolean)
    .join(language === "ar" ? "، " : ", ");

  return (
    <button
      ref={register}
      type="button"
      className={[
        "calendar-day",
        selected ? "calendar-day-selected" : "",
        isToday ? "calendar-day-today" : "",
        day.fastFree ? "calendar-day-free" : "",
      ].join(" ")}
      tabIndex={selected ? 0 : -1}
      aria-label={label}
      aria-current={isToday ? "date" : undefined}
      onClick={onSelect}
    >
      <span className="calendar-day-top">
        <span className="calendar-day-number">{day.dayNumber[language]}</span>
        <span className="calendar-day-coptic">
          {firstOfCopticMonth ? day.coptic.short[language] : day.coptic.dayNumber[language]}
        </span>
      </span>
      <span className="calendar-day-marks">
        {feast ? <span className="calendar-mark calendar-mark-feast" /> : null}
        {day.fast ? <span className="calendar-mark calendar-mark-fast" /> : null}
      </span>
      {feast ? <span className="calendar-day-feast">{feast.name[language]}</span> : null}
      {saint ? <span className="calendar-day-saint" {...commemorationTitle(saint, language, "short")} /> : null}
    </button>
  );
}

function DayDetail({ day, language, isToday }: { day: DayView; language: Language; isToday: boolean }) {
  const router = useRouter();
  const strings = calendarStrings(language);

  function ask(name: string) {
    queueChatMessage(fill(strings.saintQuestion, { name }));
    router.push("/chat");
  }

  return (
    <section className="calendar-detail" aria-labelledby="calendar-detail-title">
      <p className="section-label">{isToday ? strings.today : strings.selectedDay}</p>
      <h2 className="calendar-detail-title" id="calendar-detail-title">
        {day.label[language]}
      </h2>
      <p className="calendar-detail-coptic">{day.coptic.label[language]}</p>

      {day.observances.length ? (
        <>
          <h3 className="calendar-detail-heading">{strings.feasts}</h3>
          <ul className="calendar-detail-list">
            {day.observances.map((observance) => (
              <li key={observance.id} className={`calendar-observance calendar-observance-${observance.kind}`}>
                {observance.name[language]}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {day.suppressed.map((observance) => (
        <p key={observance.id} className="calendar-detail-note">
          {fill(strings.notCelebrated, { feast: observance.name[language] })}
        </p>
      ))}

      {day.fast ? (
        <p className="calendar-detail-fast">
          <span className="calendar-mark calendar-mark-fast" aria-hidden="true" />
          <span>
            <span className="calendar-detail-key">{strings.fast}:</span> {day.fast.name[language]}
          </span>
        </p>
      ) : day.fastFree ? (
        <p className="calendar-detail-fast">
          <span className="calendar-mark calendar-mark-free" aria-hidden="true" />
          <span>
            <span className="calendar-detail-key">{strings.fastFree}:</span> {day.fastFree.name[language]}
          </span>
        </p>
      ) : null}

      <h3 className="calendar-detail-heading">{strings.commemorations}</h3>
      {day.commemorations.length ? (
        <ol className="calendar-commemorations">
          {day.commemorations.map((entry) => {
            const indexName = entry.index?.[language];
            return (
              <li key={entry.id} className={`calendar-commemoration calendar-commemoration-${entry.kind}`}>
                <span className="calendar-commemoration-title" {...commemorationTitle(entry, language)} />
                {indexName ? (
                  <span className="calendar-commemoration-actions">
                    <Link href={saintHref(indexName)} className="text-link">
                      {strings.saintInIndex}
                    </Link>
                    <button type="button" className="text-link calendar-ask" onClick={() => ask(indexName)}>
                      {strings.askAboutSaint}
                      <IconArrowForward size={15} />
                    </button>
                  </span>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="calendar-detail-empty">{strings.noCommemorations}</p>
      )}
    </section>
  );
}
