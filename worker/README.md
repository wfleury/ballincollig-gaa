# gaacork-proxy — Cloudflare Worker

Proxies `admin-ajax.php` requests to gaacork.ie from Cloudflare's edge network,
bypassing CloudFront WAF that blocks GitHub Actions datacenter IPs.

## Setup (one-time)

1. Create a free [Cloudflare account](https://dash.cloudflare.com/sign-up)
2. Install Wrangler:
   ```bash
   cd worker
   npm install
   ```
3. Login:
   ```bash
   npx wrangler login
   ```
4. Deploy:
   ```bash
   npx wrangler deploy
   ```
   Note the deployed URL (e.g. `https://gaacork-proxy.<you>.workers.dev`)

5. Set a secret auth key (optional but recommended):
   ```bash
   npx wrangler secret put PROXY_KEY
   # Enter a random string when prompted
   ```

6. Add GitHub repo secrets:
   - `PROXY_URL` = `https://gaacork-proxy.<you>.workers.dev`
   - `PROXY_KEY` = the same key you set in step 5

## How it works

The Worker receives the same query parameters as `admin-ajax.php`:
```
GET https://gaacork-proxy.<you>.workers.dev/?action=fixtures&club_id=1986&team_id=327535&...&key=<secret>
```

It forwards the request to `https://gaacork.ie/wp-admin/admin-ajax.php` with appropriate headers and returns the HTML response.

## Free tier limits

- 100,000 requests/day (we use ~1-3/day)
- 10ms CPU time per request (plenty for a proxy)
