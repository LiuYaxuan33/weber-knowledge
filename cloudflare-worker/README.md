# Weber DeepSeek proxy

Cloudflare Worker proxy for the public Weber search page. It accepts only the GitHub Pages origin, limits request size and output tokens, and reads `DEEPSEEK_API_KEY` from an encrypted Worker secret.

After creating the Worker, add `DEEPSEEK_API_KEY` under **Settings → Variables and Secrets** as type **Secret**. Never commit the key.
