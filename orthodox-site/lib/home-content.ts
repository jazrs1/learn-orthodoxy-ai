import type { Language } from "./i18n";

// Landing-page copy (UI-009, UI-014). Example questions are ones the eval set shows the library
// answers well (CAT-01, CAT-08, CAT-15, CAT-18, SNT-08, KW-03 and AR-01/02/04/07/08/10).

export type HomeContent = {
  /** Set under the wordmark in spaced small caps. */
  tagline: string;
  /** One or two lines under the wordmark (UI-021); it says "with sources shown", the AI note doesn't repeat it. */
  lead: string;
  /** Quiet note under the question box. */
  aiNote: string;
  examplesLabel: string;
  examples: string[];
  exploreTitle: string;
  catechismCard: { title: string; text: string; cta: string };
  saintsCard: { title: string; text: string; cta: string };
  howTitle: string;
  howSteps: Array<{ title: string; text: string }>;
  noteTitle: string;
  notes: string[];
  noteLink: string;
};

export const HOME_CONTENT: Record<Language, HomeContent> = {
  en: {
    tagline: "A Coptic Orthodox Study Guide",
    lead:
      "Ask about Church teaching and the lives of the saints. Answers come only from Fr. Tadros Malaty's books and the catechism, with sources shown.",
    aiNote: "Answers are prepared by AI from these books.",
    examplesLabel: "Begin with a question",
    examples: [
      "Why is prayer essential in the Coptic Orthodox life?",
      "What does the Coptic Orthodox Church teach about the Eucharist?",
      "Who was St. Moses the Black?",
      "Why does the Coptic Orthodox Church place such emphasis on fasting?",
      "What is the Jesus Prayer?",
      "Who was St. Anthony, the Father of the Monks?",
    ],
    exploreTitle: "Explore",
    catechismCard: {
      title: "Catechism topics",
      text: "Prayer, salvation, the sacraments, repentance, the Church and fasting, each with ready questions.",
      cta: "Browse topics",
    },
    saintsCard: {
      title: "Saints and Fathers",
      text: "Look up more than a thousand entries from the Encyclopedia of the Saints and Fathers of the Church.",
      cta: "Find a saint",
    },
    howTitle: "How it works",
    howSteps: [
      {
        title: "Ask in English or Arabic",
        text: "Type a question the way you would ask a Sunday school servant.",
      },
      {
        title: "It reads a fixed library",
        text:
          "The Catechism of the Coptic Orthodox Church, the Encyclopedia of the Saints and Fathers of the Church, and Fr. Tadros Malaty's writings published by Mind of Christ Light.",
      },
      {
        title: "Every answer cites its sources",
        text: "Numbered markers point to the book, volume and page, so you can check what you read.",
      },
    ],
    noteTitle: "Before you start",
    notes: [
      "This is an AI. It can misread or oversimplify, so check important points against the cited pages.",
      "It only knows these books. When they don't cover a question, it says so instead of guessing.",
      "It is a study aid, not a spiritual father. For personal guidance, speak with your priest or father of confession.",
    ],
    noteLink: "About the sources",
  },
  ar: {
    tagline: "دليل دراسي قبطي أرثوذكسي",
    lead:
      "اسأل عن تعليم الكنيسة وسير القديسين. تأتي الإجابات فقط من كتب القمص تادرس يعقوب ملطي والتعليم الكنسي، مع ذكر مصادرها.",
    aiNote: "يُعِدّ الذكاء الاصطناعي الإجابات من هذه الكتب.",
    examplesLabel: "ابدأ بسؤال",
    examples: [
      "من هو الأنبا موسى الأسود؟",
      "ما هي أهمية الصلاة الربانية؟",
      "ما هو سر المعمودية وما هي بركاته؟",
      "من هو مارمرقس الرسول؟",
      "ما هو سر الشركة في الإفخارستيا؟",
      "من هو الأنبا أنطونيوس أب الرهبان؟",
    ],
    exploreTitle: "استكشف",
    catechismCard: {
      title: "موضوعات التعليم الكنسي",
      text: "الصلاة والخلاص والأسرار والتوبة والكنيسة والصوم، ولكل موضوع أسئلة جاهزة.",
      cta: "تصفّح الموضوعات",
    },
    saintsCard: {
      title: "القديسون والآباء",
      text: "ابحث في أكثر من ألف سيرة من قاموس آباء الكنيسة وقديسيها.",
      cta: "ابحث عن قديس",
    },
    howTitle: "كيف يعمل",
    howSteps: [
      {
        title: "اسأل بالعربية أو بالإنجليزية",
        text: "اكتب سؤالك كما تسأل خادم مدارس الأحد.",
      },
      {
        title: "يقرأ من مكتبة محددة",
        text: "كاتيكيزم الكنيسة القبطية الأرثوذكسية، وقاموس آباء الكنيسة وقديسيها للقمص تادرس يعقوب ملطي.",
      },
      {
        title: "كل إجابة تذكر مصادرها",
        text: "أرقام صغيرة داخل الإجابة تشير إلى الكتاب والصفحة، لتتحقّق بنفسك مما تقرأ.",
      },
    ],
    noteTitle: "قبل أن تبدأ",
    notes: [
      "هذا نظام ذكاء اصطناعي، وقد يخطئ الفهم أو يبسّط أكثر من اللازم، فراجع النقاط المهمة في الصفحات المذكورة.",
      "لا يعرف إلا هذه الكتب. إذا لم تتناول الكتب سؤالك، يقول ذلك بدلًا من التخمين.",
      "هو وسيلة للدراسة وليس أبًا روحيًا. للإرشاد الشخصي تحدّث مع كاهنك أو أب اعترافك.",
    ],
    noteLink: "عن المصادر",
  },
};
