/**
 * Every feast, fast and season the calendar can mark, with its English and Arabic name (CAL-002).
 * The generator writes only these ids into the data file; the UI looks the names up here.
 */

export type ObservanceKind =
  /** The seven major feasts of the Lord. */
  | "major-feast"
  /** The seven minor feasts of the Lord. */
  | "minor-feast"
  /** Other feasts the Church keeps (Nayrouz, the Cross, the Apostles, the Assumption…). */
  | "feast"
  /** Days of Holy Week and similar days that are neither feasts nor fasts in themselves. */
  | "observance"
  | "fast"
  /** Periods in which the Wednesday and Friday fasts are not kept. */
  | "fast-free";

export type ObservanceName = { en: string; ar: string };

export const OBSERVANCES = {
  // Major feasts of the Lord
  annunciation: { kind: "major-feast", en: "The Annunciation", ar: "عيد البشارة المجيد" },
  nativity: { kind: "major-feast", en: "The Nativity of Christ", ar: "عيد الميلاد المجيد" },
  theophany: { kind: "major-feast", en: "Theophany", ar: "عيد الغطاس المجيد" },
  "palm-sunday": { kind: "major-feast", en: "Palm Sunday", ar: "أحد الشعانين" },
  resurrection: { kind: "major-feast", en: "The Resurrection (Pascha)", ar: "عيد القيامة المجيد" },
  ascension: { kind: "major-feast", en: "The Ascension", ar: "عيد الصعود المجيد" },
  pentecost: { kind: "major-feast", en: "Pentecost", ar: "عيد العنصرة" },

  // Minor feasts of the Lord
  circumcision: { kind: "minor-feast", en: "The Circumcision of Christ", ar: "عيد الختان" },
  cana: { kind: "minor-feast", en: "The Wedding at Cana", ar: "عيد عرس قانا الجليل" },
  presentation: { kind: "minor-feast", en: "The Entrance of the Lord into the Temple", ar: "عيد دخول السيد المسيح الهيكل" },
  "covenant-thursday": { kind: "minor-feast", en: "Covenant Thursday", ar: "خميس العهد" },
  "thomas-sunday": { kind: "minor-feast", en: "Thomas Sunday", ar: "أحد توما" },
  "entry-into-egypt": { kind: "minor-feast", en: "The Entry of the Lord into Egypt", ar: "عيد دخول السيد المسيح أرض مصر" },
  transfiguration: { kind: "minor-feast", en: "The Transfiguration", ar: "عيد التجلي" },

  // Other feasts
  nayrouz: { kind: "feast", en: "Nayrouz (Coptic New Year)", ar: "عيد النيروز (رأس السنة القبطية)" },
  "feast-of-the-cross": { kind: "feast", en: "The Feast of the Cross", ar: "عيد الصليب المجيد" },
  "appearance-of-the-cross": { kind: "feast", en: "The Feast of the Cross (its appearance)", ar: "عيد ظهور الصليب المجيد" },
  "jonah-feast": { kind: "feast", en: "The Feast of Jonah (Nineveh)", ar: "فصح يونان" },
  "st-mark": { kind: "feast", en: "The Martyrdom of St. Mark the Evangelist", ar: "استشهاد القديس مار مرقس الرسول" },
  "apostles-feast": { kind: "feast", en: "The Feast of the Apostles (Sts. Peter and Paul)", ar: "عيد الرسل (استشهاد القديسين بطرس وبولس)" },
  assumption: { kind: "feast", en: "The Assumption of St. Mary's Body", ar: "عيد صعود جسد السيدة العذراء" },

  // Holy Week and the days around it
  "lazarus-saturday": { kind: "observance", en: "Lazarus Saturday", ar: "سبت لعازر" },
  "holy-monday": { kind: "observance", en: "Monday of Holy Pascha", ar: "اثنين البصخة" },
  "holy-tuesday": { kind: "observance", en: "Tuesday of Holy Pascha", ar: "ثلاثاء البصخة" },
  "holy-wednesday": { kind: "observance", en: "Wednesday of Holy Pascha", ar: "أربعاء البصخة" },
  "good-friday": { kind: "observance", en: "Good Friday", ar: "الجمعة العظيمة" },
  "joyous-saturday": { kind: "observance", en: "Joyous Saturday", ar: "سبت الفرح" },

  // Fasts
  "jonah-fast": { kind: "fast", en: "Jonah's Fast", ar: "صوم يونان" },
  "great-lent": { kind: "fast", en: "Great Lent", ar: "الصوم الكبير" },
  "holy-week-fast": { kind: "fast", en: "Holy Week fast", ar: "صوم أسبوع الآلام" },
  "apostles-fast": { kind: "fast", en: "The Apostles' Fast", ar: "صوم الرسل" },
  "st-mary-fast": { kind: "fast", en: "St. Mary's Fast", ar: "صوم السيدة العذراء" },
  "nativity-fast": { kind: "fast", en: "The Nativity Fast", ar: "صوم الميلاد" },
  "wednesday-friday": { kind: "fast", en: "Wednesday and Friday fast", ar: "صوم الأربعاء والجمعة" },

  // Fast-free periods
  "holy-fifty": { kind: "fast-free", en: "The Holy Fifty Days (no fasting)", ar: "الخماسين المقدسة (لا صوم)" },
  "nativity-to-theophany": {
    kind: "fast-free",
    en: "Nativity to Theophany (no fasting)",
    ar: "من الميلاد إلى الغطاس (لا صوم)",
  },
} as const satisfies Record<string, ObservanceName & { kind: ObservanceKind }>;

export type ObservanceId = keyof typeof OBSERVANCES;

export function observanceName(id: ObservanceId, language: "en" | "ar"): string {
  return OBSERVANCES[id][language];
}

export function observanceKind(id: ObservanceId): ObservanceKind {
  return OBSERVANCES[id].kind;
}

/** Feasts first (major, minor, other), then observances; used to pick the one a small cell shows. */
const KIND_RANK: Record<ObservanceKind, number> = {
  "major-feast": 0,
  "minor-feast": 1,
  feast: 2,
  observance: 3,
  fast: 4,
  "fast-free": 5,
};

export function compareObservances(a: ObservanceId, b: ObservanceId): number {
  return KIND_RANK[observanceKind(a)] - KIND_RANK[observanceKind(b)];
}
