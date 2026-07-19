# DNS — indie-trader.com (Netlify)

Site: `spiffy-tiramisu-613b09`  
Netlify subdomain: `https://spiffy-tiramisu-613b09.netlify.app`  
Custom domain (Netlify primary): `indie-trader.com`

Configure these records at the **registrar / DNS host** that owns `indie-trader.com`.

## Recommended (ALIAS / ANAME / flattened CNAME)

If your provider supports apex ALIAS (Cloudflare CNAME flattening, DNSimple ALIAS, etc.):

| Type | Host | Value | TTL |
|------|------|--------|-----|
| **ALIAS** (or ANAME / flattened CNAME) | `@` | `apex-loadbalancer.netlify.com` | 3600 or Auto |
| **CNAME** | `www` | `spiffy-tiramisu-613b09.netlify.app` | 3600 or Auto |

## Fallback (classic A record)

| Type | Host | Value | TTL |
|------|------|--------|-----|
| **A** | `@` | `75.2.60.5` | 3600 |
| **CNAME** | `www` | `spiffy-tiramisu-613b09.netlify.app` | 3600 |

Prefer ALIAS when available — more resilient than a hard-coded IP.

## After saving

1. Confirm the domain is attached in Netlify → Domain management (already set as primary).
2. Wait for propagation (minutes to a few hours).
3. Check:

```bash
dig indie-trader.com
dig www.indie-trader.com
# or PowerShell:
Resolve-DnsName indie-trader.com
Resolve-DnsName www.indie-trader.com
```

4. Netlify auto-provisions Let’s Encrypt once DNS points correctly.
5. Optional: enable HTTPS-only + force `www` → apex (or reverse) in Netlify domain settings.

## Not done in-repo

Registrar DNS cannot be changed from this repository. Whoever holds the domain account must apply the rows above.
