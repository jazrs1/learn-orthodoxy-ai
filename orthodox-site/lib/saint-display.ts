import { Language } from "./i18n";

const EXACT_ARABIC_NAMES: Record<string, string> = {
  "st. mary": "القديسة مريم",
  "st. mary magdalene": "القديسة مريم المجدلية",
  "st. mary, the armenian": "القديسة مريم الأرمنية",
  "st. mary, the egyptian": "القديسة مريم المصرية",
  "st. mary, the virgin theotokos": "القديسة مريم العذراء والدة الإله",
  "st. anthony the great": "القديس أنطونيوس الكبير",
  "st. anthony, father of the monks": "القديس أنطونيوس أب الرهبان",
  "st. athanasius the apostolic": "القديس أثناسيوس الرسولي",
  "st. cyril of alexandria": "القديس كيرلس الإسكندري",
  "st. mark the evangelist": "القديس مرقس الإنجيلي",
  "st. john the baptist": "القديس يوحنا المعمدان",
  "st. john the theologian": "القديس يوحنا اللاهوتي",
  "st. john chrysostom": "القديس يوحنا ذهبي الفم",
};

const WORD_ARABIC_NAMES: Record<string, string> = {
  abba: "أبا",
  abraham: "إبراهيم",
  achillas: "أرشيلاوس",
  adam: "آدم",
  alexander: "الإسكندر",
  alexandria: "الإسكندرية",
  alexandrian: "الإسكندري",
  anba: "أنبا",
  andrew: "أندراوس",
  anna: "حنة",
  anne: "حنة",
  anthony: "أنطونيوس",
  antony: "أنطونيوس",
  apollo: "أبوللو",
  apostle: "الرسول",
  apostles: "الرسل",
  apostolic: "الرسولي",
  archangel: "رئيس الملائكة",
  armenian: "الأرمني",
  ascetic: "الناسك",
  athanasius: "أثناسيوس",
  augustine: "أغسطينوس",
  baptist: "المعمدان",
  barnabas: "برنابا",
  barbara: "بربارة",
  basil: "باسيليوس",
  bishop: "الأسقف",
  bishops: "الأساقفة",
  bishoy: "بيشوي",
  catherine: "كاترين",
  celestine: "كلستين",
  christopher: "خريستوفر",
  chrysostom: "ذهبي الفم",
  clement: "كليمنت",
  confessor: "المعترف",
  confessors: "المعترفون",
  coptic: "القبطي",
  cyprian: "كبريانوس",
  cyril: "كيرلس",
  damascus: "دمشق",
  daniel: "دانيال",
  david: "داود",
  demiana: "دميانة",
  desert: "البرية",
  didymus: "ديديموس",
  dioscorus: "ديسقورس",
  egypt: "مصر",
  egyptian: "المصري",
  elijah: "إيليا",
  elisha: "أليشع",
  ephrem: "إفرام",
  epiphanius: "إبيفانيوس",
  evangelist: "الإنجيلي",
  father: "أب",
  fathers: "الآباء",
  george: "جورج",
  gregory: "غريغوريوس",
  great: "الكبير",
  hermas: "هرماس",
  hermit: "الناسك",
  holy: "القديس",
  ignatius: "إغناطيوس",
  irene: "إيريني",
  isaac: "إسحق",
  israelite: "الإسرائيلية",
  jacob: "يعقوب",
  jerome: "جيروم",
  jerusalem: "أورشليم",
  joachim: "يواقيم",
  john: "يوحنا",
  joseph: "يوسف",
  julius: "يوليوس",
  justin: "يوستينوس",
  king: "الملك",
  luke: "لوقا",
  magdalene: "المجدلية",
  marina: "مارينا",
  mark: "مرقس",
  martyr: "الشهيد",
  martyrs: "الشهداء",
  mary: "مريم",
  matthew: "متى",
  mercurius: "مرقوريوس",
  michael: "ميخائيل",
  mina: "مينا",
  monk: "الراهب",
  monks: "الرهبان",
  moses: "موسى",
  of: "من",
  pachomius: "باخوميوس",
  pantaleon: "بندلايمون",
  patriarch: "البطريرك",
  paul: "بولس",
  peter: "بطرس",
  philip: "فيلبس",
  polycarp: "بوليكاربوس",
  pope: "البابا",
  prophet: "النبي",
  queen: "الملكة",
  repentant: "التائبة",
  roman: "الروماني",
  rome: "روما",
  sarah: "سارة",
  shenouda: "شنودة",
  shut: "الحبيسة",
  simon: "سمعان",
  soldier: "الجندي",
  stephen: "استفانوس",
  syrian: "السرياني",
  the: "",
  theodore: "تادرس",
  theologian: "اللاهوتي",
  theotokos: "والدة الإله",
  thomas: "توما",
  virgin: "العذراء",
};

const FEMININE_NAME_PATTERN =
  /\b(mary|demiana|barbara|catherine|irene|marina|sarah|anna|anne|queen|virgin)\b/i;

const DIGRAPHS: Array<[string, string]> = [
  ["ch", "تش"],
  ["sh", "ش"],
  ["th", "ث"],
  ["ph", "ف"],
  ["kh", "خ"],
  ["gh", "غ"],
  ["ou", "و"],
  ["oo", "و"],
  ["ee", "ي"],
  ["ea", "ي"],
  ["ai", "اي"],
  ["ei", "ي"],
  ["ie", "ي"],
  ["io", "يو"],
  ["ia", "يا"],
  ["us", "وس"],
];

const LETTERS: Record<string, string> = {
  a: "ا",
  b: "ب",
  c: "ك",
  d: "د",
  e: "ي",
  f: "ف",
  g: "ج",
  h: "ه",
  i: "ي",
  j: "ج",
  k: "ك",
  l: "ل",
  m: "م",
  n: "ن",
  o: "و",
  p: "ب",
  q: "ق",
  r: "ر",
  s: "س",
  t: "ت",
  u: "و",
  v: "ف",
  w: "و",
  x: "كس",
  y: "ي",
  z: "ز",
};

function normalizeName(value: string) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function transliterateLatinWord(value: string) {
  const normalized = value.toLowerCase().replace(/[^a-z']/g, "");
  if (!normalized) return value;

  let output = "";
  let remaining = normalized.replace(/'/g, "");
  while (remaining) {
    const pair = DIGRAPHS.find(([latin]) => remaining.startsWith(latin));
    if (pair) {
      output += pair[1];
      remaining = remaining.slice(pair[0].length);
      continue;
    }

    output += LETTERS[remaining[0]] || remaining[0];
    remaining = remaining.slice(1);
  }

  return output;
}

function translateWord(value: string) {
  const key = value.toLowerCase().replace(/[^a-z']/g, "");
  if (!key) return value;
  return WORD_ARABIC_NAMES[key] ?? transliterateLatinWord(key);
}

function translateNameContent(value: string) {
  const tokens = value.match(/[A-Za-z']+|\d+|[(),.-]/g) || [value];
  return tokens
    .map((token) => {
      if (token === ",") return "،";
      if (token === "-") return "-";
      if (token === "." || token === "(" || token === ")") return token;
      if (/^\d+$/.test(token)) return token;
      return translateWord(token);
    })
    .filter((token) => token.trim())
    .join(" ")
    .replace(/\s+([،.)])/g, "$1")
    .replace(/([(])\s+/g, "$1")
    .replace(/\s+-\s+/g, " - ")
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
    return `${title} ${translateNameContent(withoutPrefix)}`.trim();
  }

  return translateNameContent(trimmed) || trimmed;
}
