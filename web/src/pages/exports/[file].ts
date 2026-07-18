import type { APIRoute, GetStaticPaths } from "astro";
import { type ExportRef, getExports, readBundleText } from "@watermark/core/bundle";

// Static download endpoints for the corpus-mirror graph exports (#1574): one route per
// `exports[]` entry in the active site's bundle manifest (RDF Turtle/JSON-LD, GraphML), served
// verbatim from the bundle with the export's own media type + an attachment disposition so a
// click downloads the file. `getStaticPaths` runs outside a per-site render, so it reads the
// reference (Lima) bundle — the wiki graph page these back is network-global. When the bundle
// carries no exports (a redirected/test export, a thin peer, a pre-1.28 fixture) it yields zero
// routes and the graph page degrades to no downloads.

const basename = (p: string): string => p.split("/").pop() ?? p;

export const getStaticPaths: GetStaticPaths = () =>
  getExports().map((ref) => ({ params: { file: basename(ref.path) }, props: { ref } }));

export const GET: APIRoute = ({ props }) => {
  const ref = props.ref as ExportRef;
  return new Response(readBundleText(ref.path), {
    headers: {
      "content-type": `${ref.media_type}; charset=utf-8`,
      "content-disposition": `attachment; filename="${basename(ref.path)}"`,
    },
  });
};
