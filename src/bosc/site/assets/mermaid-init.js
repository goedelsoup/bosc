// Render Mermaid diagrams.
//
// The page shell (templates/base.html) loads Mermaid from a CDN, then runs it
// here. pymdownx superfences emits each diagram as <pre class="mermaid"><code>…
// </code></pre>; Mermaid wants the raw graph text directly inside the .mermaid
// element, so we lift the <code> text out first (reading textContent also
// unescapes the HTML entities for us).
window.addEventListener("load", function () {
  if (!window.mermaid) return;
  document.querySelectorAll("pre.mermaid, div.mermaid").forEach(function (el) {
    var code = el.querySelector("code");
    if (code) el.textContent = code.textContent;
  });
  window.mermaid.initialize({ startOnLoad: false });
  window.mermaid.run({ querySelector: "pre.mermaid, div.mermaid" });
});
