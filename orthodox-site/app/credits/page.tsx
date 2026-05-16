"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ChatSidebar from "../../components/ChatSidebar";
import { useLanguage } from "../../components/LanguageProvider";
import frTadrosImage from "../../images/frtadros.webp";
import { deleteConversationRequest, fetchConversationList } from "../../lib/chat-client";
import type { ConversationSummary } from "../../lib/chat-types";

export default function CreditsPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const router = useRouter();
  const { language, t } = useLanguage();
  const isArabic = language === "ar";

  useEffect(() => {
    function handleOpenSidebar() {
      setMobileSidebarOpen(true);
    }

    window.addEventListener("chat:openSidebar", handleOpenSidebar);
    return () => {
      window.removeEventListener("chat:openSidebar", handleOpenSidebar);
    };
  }, []);

  useEffect(() => {
    if (!mobileSidebarOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileSidebarOpen]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const nextConversations = await fetchConversationList();
        if (!cancelled) {
          setConversations(nextConversations);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load chats.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  function openSession(sessionId: string) {
    setMobileSidebarOpen(false);
    router.push(`/chat?chat=${encodeURIComponent(sessionId)}`);
  }

  function startNewChat() {
    setMobileSidebarOpen(false);
    router.push("/chat");
  }

  async function deleteSession(sessionId: string) {
    try {
      await deleteConversationRequest(sessionId);
      setConversations((prev) => prev.filter((conversation) => conversation.id !== sessionId));
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete chat.");
    }
  }

  return (
    <>
      <main className={`page-shell credits-page ${isArabic ? "credits-page-ar" : ""}`}>
        <h1 className="page-title">{isArabic ? "كلمة شكر وتقدير" : "Credits"}</h1>

        {isArabic ? (
          <article className="credits-content" aria-label="كلمة شكر وتقدير">
            <p>
              موقع LearnOrthodoxy.net هو موقع قام بتطويره مجموعة من الشباب والخدام المحبين
              لنشر إيمان الكنيسة القبطية الأرثوذكسية. واستجابة للاهتمام العالمي المتزايد
              بالأرثوذكسية، قمنا بتأسيس هذا الموقع ليكون متاحاً للجميع ليتعلموا عن الإيمان
              من مصادر موثوقة.
            </p>

            <p>
              محتوانا مأخوذ بشكل أساسي من مؤلفات القمص تادرس يعقوب ملطي، الكاهن واللاهوتي
              البارز بكنيسة الشهيد العظيم مار جرجس بسپورتنج في الإسكندرية، مصر. يُعد قدس
              القمص تادرس كاتباً غزيراً الإنتاج، اشتُهر بتبسيط علم الآبائيات (Patristics)
              والتفسير الكتابي للمؤمنين المعاصرين، لا سيما من خلال منظور مدرسة الإسكندرية
              اللاهوتية.
            </p>

            <p>
              لقد كرس القمص تادرس حياته لجعل التراث اللاهوتي والروحي العميق للكنيسة الأولى
              متاحاً وبسيطاً. يركز أسلوبه في الكتابة على تفكر &quot;مدرسة الإسكندرية&quot;،
              مشدداً على المعاني الرمزية والروحية للكتاب المقدس كما علم بها آباء كبار مثل
              القديس كليمنضوس الإسكندري والعلامة أوريجانوس.
            </p>

            <p>تشمل أعماله عدة مجالات، أبرزها:</p>

            <ul className="credits-dash-list">
              <li>
                التفاسير الآبائية: قدم تفاسير شاملة لكل سفر من أسفار الكتاب المقدس تقريباً،
                جامعاً شتات تفسيرات آباء الكنيسة الأولى في قالب رعوي متماسك.
              </li>
              <li>
                التقليد الكنسي والليتورجي: كتب باستفاضة عن معاني الأعياد القبطية، والقداس
                الإلهي، وتاريخ الكنيسة.
              </li>
              <li>
                المواد التعليمية: تركز سلسلة &quot;الكاتيكيزم&quot; (الموعوظين) التي أعدها
                على تعليم الإيمان للشباب والخدام، لضمان الحفاظ على الهوية القبطية الأرثوذكسية
                عبر الأجيال، سواء في مصر أو في بلاد المهجر.
              </li>
            </ul>

            <p>
              يتمتع القمص تادرس بتقدير كبير لقدرته على جسر الهوة بين اللاهوت الأكاديمي
              العميق والحياة الروحية المعاشة، مع بقائه دائماً متجذراً في الإيمان الأرثوذكسي
              الأصيل.
            </p>

            <p>ونحن نتقدم بخالص الشكر للقمص تادرس وتلاميذه لمدادنا بالمواد المستخدمة، وهي:</p>

            <ul className="credits-dash-list">
              <li>موسوعة كاتيكيزم الكنيسة القبطية الأرثوذكسية (٧ كتب).</li>
              <li>قاموس آباء الكنيسة وقديسيها (٤ مجلدات).</li>
            </ul>

            <p>يمكن العثور على أعمال القمص تادرس على:</p>

            <ul className="credits-dash-list">
              <li>
                <a
                  className="credits-link"
                  href="https://www.amazon.com/stores/Fr.-Tadros-Y.-Malaty/author/B06XFDNRXY"
                  target="_blank"
                  rel="noreferrer"
                >
                  أمازون للكتب
                </a>
              </li>
              <li>
                Mind of Christ Light (MoCL): مؤسسة تهدف للكرازة بالمسيح، النور الحقيقي،
                كما تسلمناه في الكتاب المقدس وفهمناه من خلال التقليد الحي للكنيسة المسلم
                من الآباء. وأحد الركائز الأساسية لهذه الرسالة هو الحفاظ على تراث كتابات
                القمص تادرس يعقوب ملطي وترجمتها ونشرها.{" "}
                <a className="credits-link" href="https://www.mindofchristlight.com/" target="_blank" rel="noreferrer">
                  mindofchristlight.com
                </a>
                .
              </li>
            </ul>

            <p className="credits-doxology">ولإلهنا المجد في كنيسته المقدسة من الآن وإلى الأبد. آمين.</p>

            <figure className="credits-portrait">
              <Image
                src={frTadrosImage}
                alt="القمص تادرس يعقوب ملطي"
                sizes="(max-width: 720px) 82vw, 320px"
                priority
              />
              <figcaption>القمص تادرس يعقوب ملطي</figcaption>
            </figure>
          </article>
        ) : (
          <article className="credits-content" aria-label="Credits and source acknowledgements">
            <p>
              LearnOrthodoxy.net is a platform developed by youth and servants dedicated to
              spreading the faith of the Coptic Orthodox Church. To meet the growing global
              interest in Orthodoxy, we have created this resource where everyone can learn about
              the faith from trusted sources.
            </p>

            <p>
              Our content is primarily adopted from the works of Fr. Tadros Yacoub Malaty,
              a prominent priest and theologian from St. George Coptic Orthodox Church in
              Alexandria, Egypt. Fr. Tadros is a prolific writer known for making Patristics
              and Biblical exegesis accessible to the modern faithful, specifically through
              the lens of the Alexandrian School.
            </p>

            <p>
              Fr. Tadros has dedicated his life to making the complex theological and spiritual
              heritage of the Early Church accessible to the modern faithful. His writing style
              often focuses on the &quot;Alexandrian School&quot; of thought, emphasizing the allegorical
              and spiritual meanings of Holy Scripture as taught by fathers such as St. Clement
              of Alexandria and Origen.
            </p>

            <p>His work spans several categories, most notably:</p>

            <ul className="credits-dash-list">
              <li>
                <strong>Patristic Commentaries:</strong> He has authored comprehensive commentaries
                on almost every book of the Bible, synthesizing the interpretations of the early
                Church Fathers into a cohesive and pastoral format.
              </li>
              <li>
                <strong>Church Tradition and Liturgy:</strong> He has written extensively on the
                meaning of the Coptic Feasts, the Divine Liturgy, and the history of the Church.
              </li>
              <li>
                <strong>Educational Materials:</strong> His Catechism series focuses on teaching
                the faith to youth and servants, ensuring that the Coptic Orthodox identity is
                preserved across generations, both in Egypt and the diaspora.
              </li>
            </ul>

            <p>
              Fr. Tadros is highly regarded for his ability to bridge the gap between deep academic
              theology and practical, lived spirituality, always remaining rooted in the authentic
              Orthodox faith.
            </p>

            <p>
              We are grateful to Fr. Tadros and his disciples for supplying us with the materials
              used to feed our platform, which are:
            </p>

            <ul className="credits-dash-list">
              <li>Catechism of the Coptic Orthodox Church (7 books)</li>
              <li>Encyclopedia of the Saints and Fathers of the Church (4 volumes)</li>
            </ul>

            <p>Fr. Tadros&apos;s work can be found on:</p>

            <ol className="credits-number-list">
              <li>
                Amazon Bookstore:{" "}
                <a
                  className="credits-link"
                  href="https://www.amazon.com/stores/Fr.-Tadros-Y.-Malaty/author/B06XFDNRXY"
                  target="_blank"
                  rel="noreferrer"
                >
                  https://www.amazon.com/stores/Fr.-Tadros-Y.-Malaty/author/B06XFDNRXY
                </a>
              </li>
              <li>
                Mind of Christ Light: MoCL exists to proclaim Christ, the true Light, as received
                in Holy Scripture and understood through the living Tradition of the Church, handed
                down by the Fathers of the church. A central pillar of this mission is the
                preservation, translation, and sharing of the legacy of the writings of Fr. Tadros
                Y. Malaty. More information at{" "}
                <a className="credits-link" href="https://www.mindofchristlight.com/" target="_blank" rel="noreferrer">
                  mindofchristlight.com
                </a>
                .
              </li>
            </ol>

            <p className="credits-doxology">
              To our God be the glory in His Holy Church now and forever. Amen.
            </p>

            <figure className="credits-portrait">
              <Image
                src={frTadrosImage}
                alt="Fr. Tadros Yacoub Malaty"
                sizes="(max-width: 720px) 82vw, 320px"
                priority
              />
              <figcaption>Fr. Tadros Yacoub Malaty</figcaption>
            </figure>
          </article>
        )}
      </main>

      <div className="credits-mobile-sidebar">
        <button
          type="button"
          className={`chat-sidebar-overlay ${mobileSidebarOpen ? "chat-sidebar-overlay-visible" : ""}`}
          onClick={() => setMobileSidebarOpen(false)}
          aria-label={t("closeChatsPanel")}
        />
        <ChatSidebar
          sessions={conversations}
          onSelectSession={openSession}
          onNewChat={startNewChat}
          onDeleteSession={deleteSession}
          showAppNav
          loading={loading}
          error={error}
          isMobileOpen={mobileSidebarOpen}
          onClose={() => setMobileSidebarOpen(false)}
        />
      </div>
    </>
  );
}
