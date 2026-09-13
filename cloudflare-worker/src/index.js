const ALLOWED_ORIGINS = new Set([
  "https://liuyaxuan33.github.io",
  "http://127.0.0.1:4173",
  "http://localhost:4173",
]);

const recentRequests = new Map();
const COOLDOWN_MS = 8_000;

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.has(origin) ? origin : "https://liuyaxuan33.github.io",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...corsHeaders(origin) },
  });
}

function validSource(source) {
  return source && typeof source.citation === "string" && typeof source.text === "string";
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "";

    if (request.method === "OPTIONS") {
      if (!ALLOWED_ORIGINS.has(origin)) return new Response(null, { status: 403 });
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    if (url.pathname === "/health" && request.method === "GET") {
      return json({ ok: true, model: env.DEEPSEEK_MODEL || "deepseek-v4-flash" }, 200, origin);
    }

    if (url.pathname !== "/chat" || request.method !== "POST") {
      return json({ error: "Not found" }, 404, origin);
    }
    if (!ALLOWED_ORIGINS.has(origin)) return json({ error: "Origin not allowed" }, 403, origin);
    if (!env.DEEPSEEK_API_KEY) return json({ error: "DeepSeek secret is not configured" }, 503, origin);

    const clientId = request.headers.get("CF-Connecting-IP") || "unknown";
    const now = Date.now();
    const previous = recentRequests.get(clientId) || 0;
    if (now - previous < COOLDOWN_MS) {
      return json({ error: "请稍候几秒再提问" }, 429, origin);
    }
    recentRequests.set(clientId, now);
    if (recentRequests.size > 2_000) {
      for (const [key, timestamp] of recentRequests) {
        if (now - timestamp > 60_000) recentRequests.delete(key);
      }
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json({ error: "Invalid JSON" }, 400, origin);
    }

    const question = typeof body.question === "string" ? body.question.trim().slice(0, 500) : "";
    const sources = Array.isArray(body.sources) ? body.sources.filter(validSource).slice(0, 6) : [];
    if (!question || !sources.length) return json({ error: "问题或原文为空" }, 400, origin);

    const context = sources
      .map((source, index) => `[${index + 1}] ${source.citation}\n${source.text.slice(0, 2_400)}`)
      .join("\n\n");

    const upstream = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.DEEPSEEK_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: env.DEEPSEEK_MODEL || "deepseek-v4-flash",
        temperature: 0.15,
        max_tokens: 1_200,
        stream: false,
        messages: [
          {
            role: "system",
            content:
              "你是严谨的马克斯·韦伯著作检索助手。只能依据用户提供的原文回答，不得使用未提供的知识补足事实。先直接回答问题，再说明不同版本的表述差异（如有），并用[1]、[2]格式逐项标注来源。若原文不足以回答，明确说原文不足。使用简洁、准确的中文。",
          },
          {
            role: "user",
            content: `问题：${question}\n\n可用原文：\n${context}`,
          },
        ],
      }),
    });

    const result = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      const message = result?.error?.message || `DeepSeek API error (${upstream.status})`;
      return json({ error: message.slice(0, 300) }, upstream.status, origin);
    }

    const answer = result?.choices?.[0]?.message?.content;
    if (typeof answer !== "string" || !answer.trim()) {
      return json({ error: "DeepSeek 未返回回答" }, 502, origin);
    }
    return json({ answer: answer.trim(), model: result.model || env.DEEPSEEK_MODEL || "deepseek-v4-flash" }, 200, origin);
  },
};
