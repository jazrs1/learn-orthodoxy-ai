import { Language } from "./i18n";

type SaintAliasRecord = {
  canonical: string;
  englishAliases: string[];
  arabicAliases: string[];
};

const MANUAL_SAINT_ALIASES: SaintAliasRecord[] = [
  {
    canonical: "St. Mary",
    englishAliases: [
      "Saint Mary",
      "St. Mary Theotokos",
      "St. Mary, the Virgin Theotokos",
      "St. Mary the Virgin",
      "Virgin Mary",
      "Holy Virgin Mary",
      "Theotokos",
      "Mother of God",
    ],
    arabicAliases: ["السيدة العذراء مريم", "العذراء مريم"],
  },
  {
    canonical: "St. Mark",
    englishAliases: [
      "Saint Mark",
      "St. Mark the Evangelist",
      "Saint Mark the Evangelist",
      "Mark the Evangelist",
      "St. Mark the Apostle",
      "Saint Mark the Apostle",
    ],
    arabicAliases: ["مارمرقس", "القديس مارمرقس الرسول"],
  },
  {
    canonical: "St. Anthony the Great",
    englishAliases: [
      "Saint Anthony the Great",
      "St. Anthony, Father of the Monks",
      "Saint Anthony, Father of the Monks",
      "St. Abba Anthony the Great",
      "St. Abba Anthony",
      "Abba Anthony",
      "Anthony the Great",
    ],
    arabicAliases: ["الأنبا أنطونيوس", "الأنبا أنطونيوس الكبير"],
  },
  {
    canonical: "St. Athanasius",
    englishAliases: [
      "Saint Athanasius",
      "St. Athanasius the Apostolic",
      "Saint Athanasius the Apostolic",
      "St. Athanasius of Alexandria",
      "Athanasius the Apostolic",
    ],
    arabicAliases: ["أثناسيوس الرسولي", "البابا أثناسيوس"],
  },
  {
    canonical: "St. Cyril",
    englishAliases: [
      "Saint Cyril",
      "St. Cyril of Alexandria",
      "Saint Cyril of Alexandria",
      "St. Cyril the Great",
      "Pope Cyril",
    ],
    arabicAliases: ["كيرلس", "البابا كيرلس"],
  },
];

function normalizeName(value: string) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

export function displaySaintName(name: string, language: Language) {
  const trimmed = name.trim();
  if (language !== "ar") return trimmed;

  const key = normalizeName(trimmed);
  const aliasRecord = MANUAL_SAINT_ALIASES.find((record) => {
    const names = [record.canonical, ...record.englishAliases];
    return names.some((value) => normalizeName(value) === key);
  });

  return aliasRecord?.arabicAliases[0] || trimmed;
}
