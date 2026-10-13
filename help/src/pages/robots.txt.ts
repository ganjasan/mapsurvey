import type { APIRoute } from 'astro';

// Production allows everything and points at the sitemap Starlight generates.
// Previews are kept out of the index with a per-page `noindex` meta tag instead
// (astro.config.mjs), because a Disallow here would also hide that tag from crawlers.
export const GET: APIRoute = ({ site }) => {
  const sitemap = new URL('sitemap-index.xml', site).href;
  return new Response(`User-agent: *\nAllow: /\n\nSitemap: ${sitemap}\n`, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
};
