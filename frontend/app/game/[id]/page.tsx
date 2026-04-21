import GamePageClient from "./GamePageClient";

// No pages are pre-generated at build time; the CDN routes unmatched paths
// to the app shell and useParams() resolves the ID client-side at runtime.
export function generateStaticParams() {
  return [];
}

export default function GamePage() {
  return <GamePageClient />;
}
