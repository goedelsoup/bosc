/**
 * PDF.js fallback reader (epic #274 / D1). The primary PDF tier is a native
 * `<object type="application/pdf">`; this canvas reader is the on-demand fallback for
 * browsers that won't inline a PDF (notably mobile). Lazy-hydrated (`client:visible`
 * inside a closed `<details>`), so pdf.js only loads when a reader opens it.
 *
 * Security: the corpus is adversarial source material, so `isEvalSupported: false`
 * (defense against CVE-2024-4367-class PDF JS) and we never run PDF-embedded scripts.
 */
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useRef, useState } from "react";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

type Status = "loading" | "ready" | "error";

export default function PdfViewer({ src, label }: { src: string; label?: string }): JSX.Element {
  const pagesRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;
    const task = pdfjs.getDocument({ url: src, isEvalSupported: false });
    (async () => {
      try {
        const doc = await task.promise;
        const container = pagesRef.current;
        if (!container || cancelled) return;
        container.replaceChildren();
        for (let n = 1; n <= doc.numPages; n++) {
          const page = await doc.getPage(n);
          if (cancelled) return;
          const viewport = page.getViewport({ scale: 1.3 });
          const canvas = document.createElement("canvas");
          canvas.className = "pdfjs-page";
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          container.appendChild(canvas);
          const ctx = canvas.getContext("2d");
          if (ctx) await page.render({ canvasContext: ctx, viewport }).promise;
        }
        if (!cancelled) setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
      task.destroy();
    };
  }, [src]);

  return (
    <div className="pdfjs-viewer">
      {status === "loading" && <p className="docview-note">Rendering {label ?? "the PDF"}…</p>}
      {status === "error" && (
        <p className="docview-note">
          Couldn’t render this PDF in-browser.{" "}
          <a href={src} download>
            Download it
          </a>{" "}
          instead.
        </p>
      )}
      <div ref={pagesRef} className="pdfjs-pages" />
    </div>
  );
}
