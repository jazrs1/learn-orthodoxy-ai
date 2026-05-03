"use client";

import { Suspense, useEffect, useRef } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

const SOURCE_FILES = [
  { file: "saints1.pdf", label: "Saints Volume 1" },
  { file: "saints2.pdf", label: "Saints Volume 2" },
  { file: "saints3.pdf", label: "Saints Volume 3" },
  { file: "saints4.pdf", label: "Saints Volume 4" },
  { file: "catechism1.pdf", label: "Catechism Volume 1" },
  { file: "catechism2.pdf", label: "Catechism Volume 2" },
];

function SourcesPageContent() {
  const searchParams = useSearchParams();
  const selectedSourceRef = useRef<HTMLDivElement>(null);
  const selectedPdfParam = searchParams.get("pdf") || "";
  const selectedPageParam = searchParams.get("page") || "";
  const selectedPdf = SOURCE_FILES.some((entry) => entry.file === selectedPdfParam)
    ? selectedPdfParam
    : "";
  const selectedPage = Number.parseInt(selectedPageParam, 10);
  const hasSelectedPage = Number.isFinite(selectedPage) && selectedPage > 0;
  const selectedPdfUrl = selectedPdf
    ? `/pdfs/${selectedPdf}${hasSelectedPage ? `#page=${selectedPage}` : ""}`
    : "";

  useEffect(() => {
    if (!selectedPdf) return;

    requestAnimationFrame(() => {
      selectedSourceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [selectedPdf, selectedPage]);

  return (
    <section className="page-shell">
      <h1 className="page-title">Sources</h1>
      <p className="page-subtitle">
        Chat responses are grounded in the saints and catechism source documents. Clickable
        citations in chat route here with file and page context.
      </p>

      <div className="sources-grid">
        {SOURCE_FILES.map(({ file, label }) => (
          <article key={file} className="source-card">
            <h2>{label}</h2>
            <p>
              {file.startsWith("catechism")
                ? "Orthodox catechism reference volume."
                : "Orthodox saints reference volume."}
            </p>
            <Link href={`/sources?pdf=${encodeURIComponent(file)}`} className="source-card-link">
              Open source context
            </Link>
            <a className="source-card-link" href={`/pdfs/${file}`} target="_blank" rel="noreferrer">
              Open PDF file
            </a>
          </article>
        ))}
      </div>

      {selectedPdf ? (
        <div id="selected-source" ref={selectedSourceRef}>
          <div className="selected-source-banner">
            <span className="selected-source-label">Selected citation</span>
            <strong>{selectedPdf}</strong>
            {hasSelectedPage ? <span>Page {selectedPage}</span> : null}
            <a className="source-card-link" href={selectedPdfUrl} target="_blank" rel="noreferrer">
              Open PDF in new tab
            </a>
          </div>

          <div className="source-preview-card">
            <iframe
              title={`Preview ${selectedPdf}`}
              src={selectedPdfUrl}
              className="source-preview-frame"
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default function SourcesPage() {
  return (
    <Suspense fallback={<section className="page-shell" />}>
      <SourcesPageContent />
    </Suspense>
  );
}
