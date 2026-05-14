import { Language } from "./i18n";

const EXACT_ARABIC_NAMES: Record<string, string> = {
  "st. mary": "القديسة مريم",
  "st. mary magdalene": "القديسة مريم المجدلية",
  "st. mary, the armenian": "القديسة مريم الأرمنية",
  "st. mary, the egyptian": "القديسة مريم المصرية",
  "st. mary, the israelite": "القديسة مريم الإسرائيلية",
  "st. mary, the repentant": "القديسة مريم التائبة",
  "st. mary, the shut-in ascetic": "القديسة مريم الناسكة الحبيسة",
  "st. mary, the virgin confessor": "القديسة مريم العذراء المعترفة",
  "st. mary, the virgin theotokos": "القديسة مريم العذراء والدة الإله",
  "st. anthony the great": "القديس أنطونيوس الكبير",
  "st. anthony, father of the monks": "القديس أنطونيوس أب الرهبان",
  "st. athanasius": "القديس أثناسيوس",
  "st. athanasius the apostolic": "القديس أثناسيوس الرسولي",
  "st. cyril of alexandria": "القديس كيرلس الإسكندري",
  "st. mark": "القديس مرقس",
  "st. mark the evangelist": "القديس مرقس الإنجيلي",
  "st. george": "القديس جورج",
  "st. mina": "القديس مينا",
  "st. demiana": "القديسة دميانة",
  "st. bishoy": "القديس بيشوي",
  "st. shenouda": "القديس شنودة",
  "st. pachomius": "القديس باخوميوس",
  "st. paul": "القديس بولس",
  "st. peter": "القديس بطرس",
  "st. john the baptist": "القديس يوحنا المعمدان",
  "st. john the theologian": "القديس يوحنا اللاهوتي",
  "st. john chrysostom": "القديس يوحنا ذهبي الفم",
};

const WORD_ARABIC_NAMES: Record<string, string> = {
  abba: "أبا",
  anba: "أنبا",
  apostle: "الرسول",
  apostolic: "الرسولي",
  armenian: "الأرمني",
  ascetic: "الناسك",
  athanasius: "أثناسيوس",
  anthony: "أنطونيوس",
  baptist: "المعمدان",
  barbara: "بربارة",
  bishoy: "بيشوي",
  catherine: "كاترين",
  chrysostom: "ذهبي الفم",
  clement: "كليمنت",
  confessor: "المعترف",
  cyril: "كيرلس",
  demiana: "دميانة",
  egyptian: "المصري",
  evangelist: "الإنجيلي",
  george: "جورج",
  great: "الكبير",
  hermas: "هرماس",
  ignatius: "إغناطيوس",
  john: "يوحنا",
  magdalene: "المجدلية",
  mark: "مرقس",
  mary: "مريم",
  mina: "مينا",
  monk: "الراهب",
  moses: "موسى",
  pachomius: "باخوميوس",
  paul: "بولس",
  peter: "بطرس",
  polycarp: "بوليكاربوس",
  pope: "البابا",
  repentant: "التائب",
  shenouda: "شنودة",
  the: "",
  theologian: "اللاهوتي",
  theotokos: "والدة الإله",
  virgin: "العذراء",
};

const FEMININE_NAME_PATTERN = /\b(mary|demiana|barbara|catherine|irene|marina|sarah)\b/i;

function normalizeName(value: string) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function translateWords(value: string) {
  return value
    .split(/(\s+|,\s*|-\s*)/)
    .map((part) => {
      const word = part.trim().toLowerCase();
      if (!word || /^(,|-)$/.test(word)) return part;
      return WORD_ARABIC_NAMES[word] ?? part;
    })
    .join("")
    .replace(/\s+,/g, "،")
    .replace(/,\s*/g, "، ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function displaySaintName(name: string, language: Language) {
  if (language !== "ar") return name;

  const trimmed = name.trim();
  const exact = EXACT_ARABIC_NAMES[normalizeName(trimmed)];
  if (exact) return exact;

  const withoutPrefix = trimmed.replace(/^(?:st\.?|saint)\s+/i, "").trim();
  if (withoutPrefix !== trimmed) {
    const title = FEMININE_NAME_PATTERN.test(withoutPrefix) ? "القديسة" : "القديس";
    return `${title} ${translateWords(withoutPrefix)}`.trim();
  }

  return translateWords(trimmed) || trimmed;
}
