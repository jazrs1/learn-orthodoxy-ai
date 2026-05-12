import Image from "next/image";
import frTadrosImage from "../../images/frtadros.webp";

export default function CreditsPage() {
  return (
    <main className="page-shell credits-page">
      <h1 className="page-title">Credits</h1>

      <article className="credits-content" aria-label="Credits and source acknowledgements">
        <div className="credits-intro-grid">
          <div className="credits-copy">
            <p>
              LearnOrthodoxy.net is a platform developed by youth and servants dedicated to
              spreading the faith of the Coptic Orthodox Church. To meet the growing global
              interest in Orthodoxy, we have created this resource where everyone can learn
              about the faith from trusted sources.
            </p>

            <p>
              Our content is primarily adopted from the works of Fr. Tadros Yacoub Malaty,
              a prominent priest and theologian from St. George Coptic Orthodox Church in
              Alexandria, Egypt. Fr. Tadros is a prolific writer known for making Patristics
              and Biblical exegesis accessible to the modern faithful, specifically through
              the lens of the Alexandrian School.
            </p>
          </div>

          <figure className="credits-portrait">
            <Image
              src={frTadrosImage}
              alt="Fr. Tadros Yacoub Malaty"
              sizes="(max-width: 720px) 100vw, 280px"
              priority
            />
            <figcaption>Fr. Tadros Yacoub Malaty</figcaption>
          </figure>
        </div>

        <p>
          Fr. Tadros has dedicated his life to making the complex theological and spiritual
          heritage of the Early Church accessible to the modern faithful. His writing style
          often focuses on the "Alexandrian School" of thought, emphasizing the allegorical
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

        <p>Fr. Tadros's work can be found on:</p>

        <ol className="credits-number-list">
          <li>
            Amazon Bookstore:{" "}
            <a
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
            Y. Malaty. More information at:{" "}
            <a href="https://www.mindofchristlight.com/" target="_blank" rel="noreferrer">
              https://www.mindofchristlight.com/
            </a>
          </li>
        </ol>

        <p className="credits-doxology">
          To our God be the glory in His Holy Church now and forever. Amen.
        </p>
      </article>
    </main>
  );
}
