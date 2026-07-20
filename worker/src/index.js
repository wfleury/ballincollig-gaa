/**
 * Cloudflare Worker proxy for gaacork.ie admin-ajax.php.
 *
 * CloudFront WAF blocks admin-ajax.php requests from GitHub Actions
 * datacenter IPs. This Worker proxies those requests from Cloudflare's
 * edge network, which is not blocked.
 *
 * Deploy:  npx wrangler deploy
 * Usage:   GET https://<worker>.workers.dev/?action=fixtures&club_id=1986&...
 */

const TARGET = 'https://gaacork.ie/wp-admin/admin-ajax.php';

// Simple shared-secret auth to prevent abuse
function checkAuth(request, env) {
  const key = env.PROXY_KEY;
  if (!key) return true; // no key configured = open (dev mode)
  const provided = new URL(request.url).searchParams.get('key')
    || request.headers.get('X-Proxy-Key');
  return provided === key;
}

export default {
  async fetch(request, env) {
    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET',
          'Access-Control-Allow-Headers': 'X-Proxy-Key',
        },
      });
    }

    if (request.method !== 'GET') {
      return new Response('Method not allowed', { status: 405 });
    }

    if (!checkAuth(request, env)) {
      return new Response('Unauthorized', { status: 401 });
    }

    // Forward query params (minus our auth key) to admin-ajax.php
    const url = new URL(request.url);
    url.searchParams.delete('key');
    const targetUrl = `${TARGET}?${url.searchParams.toString()}`;

    try {
      const resp = await fetch(targetUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
          'Referer': 'https://gaacork.ie/clubprofile/',
          'Accept': 'text/html, */*; q=0.01',
          'X-Requested-With': 'XMLHttpRequest',
        },
      });

      return new Response(resp.body, {
        status: resp.status,
        headers: {
          'Content-Type': resp.headers.get('Content-Type') || 'text/html',
          'Access-Control-Allow-Origin': '*',
          'X-Proxied-Status': resp.status.toString(),
        },
      });
    } catch (err) {
      return new Response(`Proxy error: ${err.message}`, { status: 502 });
    }
  },
};
