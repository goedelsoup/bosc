// Dependency-free client-side search over the render-time index
// (assets/search-index.json). All-terms substring match across title + body text;
// title hits rank first. No lunr, no CDN — works on a static GitHub Pages host.
(function () {
  "use strict";
  var root = document.body.getAttribute("data-root") || "";
  var box = document.getElementById("bosc-search");
  var panel = document.getElementById("bosc-search-results");
  if (!box || !panel) return;

  var index = null;
  function load() {
    if (index) return Promise.resolve(index);
    return fetch(root + "assets/search-index.json")
      .then(function (r) { return r.json(); })
      .then(function (d) { index = d; return d; })
      .catch(function () { index = []; return index; });
  }

  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // A ~140-char window around the first matched term, with the term marked.
  function snippet(text, terms) {
    var lower = text.toLowerCase();
    var at = -1, hit = "";
    for (var i = 0; i < terms.length; i++) {
      var p = lower.indexOf(terms[i]);
      if (p >= 0 && (at < 0 || p < at)) { at = p; hit = terms[i]; }
    }
    if (at < 0) return esc(text.slice(0, 140));
    var start = Math.max(0, at - 50);
    var frag = (start > 0 ? "…" : "") + text.slice(start, at + 90) + "…";
    var re = new RegExp("(" + hit.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
    return esc(frag).replace(re, "<mark>$1</mark>");
  }

  function render(hits, terms) {
    if (!hits.length) {
      panel.innerHTML = '<div class="search-empty">No matches</div>';
      panel.hidden = false;
      return;
    }
    panel.innerHTML = hits
      .map(function (d) {
        return (
          '<a class="search-hit" href="' + root + esc(d.url) + '">' +
          '<span class="search-hit-title">' + esc(d.title) + "</span>" +
          '<span class="search-hit-snip">' + snippet(d.text, terms) + "</span></a>"
        );
      })
      .join("");
    panel.hidden = false;
  }

  function run() {
    var q = box.value.trim().toLowerCase();
    if (q.length < 2) { panel.hidden = true; panel.innerHTML = ""; return; }
    var terms = q.split(/\s+/);
    load().then(function (docs) {
      var hits = [];
      for (var i = 0; i < docs.length; i++) {
        var d = docs[i];
        var title = (d.title || "").toLowerCase();
        var hay = title + " " + (d.text || "").toLowerCase();
        var ok = terms.every(function (t) { return hay.indexOf(t) >= 0; });
        if (!ok) continue;
        var score = (title.indexOf(q) >= 0 ? 0 : (terms.every(function (t) { return title.indexOf(t) >= 0; }) ? 1 : 2));
        hits.push([score, d]);
      }
      hits.sort(function (a, b) { return a[0] - b[0]; });
      render(hits.slice(0, 20).map(function (h) { return h[1]; }), terms);
    });
  }

  box.addEventListener("input", run);
  box.addEventListener("focus", run);
  box.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { box.blur(); panel.hidden = true; }
    if (e.key === "Enter") {
      var first = panel.querySelector("a.search-hit");
      if (first) window.location.href = first.getAttribute("href");
    }
  });
  document.addEventListener("click", function (e) {
    if (!panel.contains(e.target) && e.target !== box) panel.hidden = true;
  });
})();
