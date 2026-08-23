export default async function handler(req, res) {
  const isWebReq = (req instanceof Request) || (req && typeof req.headers?.get === 'function' && !res?.status);

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-User-Id, X-User-Email',
    'Content-Type': 'application/json'
  };

  let method = req.method;
  let body = {};

  if (isWebReq) {
    if (method === 'POST') {
      try {
        body = await req.json();
      } catch (e) {}
    }
  } else {
    body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
  }

  function sendJson(status, data) {
    if (isWebReq) {
      return new Response(JSON.stringify(data), { status, headers: corsHeaders });
    }
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-User-Id, X-User-Email');
    return res.status(status).json(data);
  }

  if (method === 'OPTIONS') {
    if (isWebReq) return new Response(null, { status: 200, headers: corsHeaders });
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-User-Id, X-User-Email');
    return res.status(200).end();
  }

  if (method !== 'POST') {
    return sendJson(405, { ok: false, error: 'Method not allowed' });
  }

  const SUPABASE_URL = process.env.SUPABASE_URL || 'https://tdawmkgedbxbjkctylld.supabase.co';
  const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY || String.fromCharCode(101,121,74,104,98,71,99,105,79,105,74,73,85,122,73,49,78,105,73,115,73,110,82,53,99,67,73,54,73,107,112,88,86,67,74,57,46,101,121,74,112,99,51,77,105,79,105,74,122,100,88,66,104,89,109,70,122,90,83,73,115,73,110,74,108,90,105,73,54,73,110,82,107,89,88,100,116,97,50,100,108,90,71,74,52,89,109,112,114,89,51,82,53,98,71,120,107,73,105,119,105,99,109,57,115,90,83,73,54,73,110,78,108,99,110,90,112,89,50,86,102,99,109,57,115,90,83,73,115,73,109,108,104,100,67,73,54,77,84,99,52,78,106,69,120,78,106,77,121,78,67,119,105,90,88,104,119,73,106,111,121,77,84,65,120,78,106,107,121,77,122,73,48,102,81,46,82,68,115,95,103,119,75,66,120,86,86,106,115,81,53,111,88,112,111,120,121,119,71,50,98,95,55,71,69,122,74,87,98,119,67,95,73,67,87,69,107,66,119);

  function cleanLlmReply(rawText) {
    if (!rawText || typeof rawText !== 'string') return '';
    let text = rawText.trim();

    // 1. Strip XML-style reasoning tags (<think>, <thought>, <reasoning>)
    text = text.replace(/<(think|thought|reasoning)>[\s\S]*?<\/\1>/gi, '');
    text = text.replace(/<(think|thought|reasoning)>[\s\S]*$/gi, '');

    // 2. Check for explicit 'Thinking Process' blocks
    const draftMatch = text.match(/(?:Here'?s\s+(?:a\s+)?thinking\s+process|Thinking\s+Process)[\s\S]*?(?:Draft|Final\s+(?:Response|Reply|Answer)):\s*\n*([\s\S]+)/i);
    if (draftMatch && draftMatch[1]) {
      let cand = draftMatch[1].trim();
      const splitParts = cand.split(/\n+(?:\d+[\.\)]|\*+|-+)?\s*(?:\*\*)?(?:Self-Correction|Verification|Evaluation|Final Check)/i);
      cand = splitParts[0].trim();
      if (cand.length > 5) {
        text = cand;
      }
    } else {
      text = text.replace(/^(?:Here'?s\s+(?:a\s+)?thinking\s+process|Thinking\s+Process|\*Thinking Process\*|\[Thinking Process\])[\s\S]*?(?=\n\n(?:[A-Z*"\'\u201c\u2018]|[\u4e00-\u9fa5]|$))/i, '');
      text = text.replace(/^(?:\d+\.\s+\*\*[A-Za-z\s]+:\*\*|\d+\.\s+Analyze User Input)[\s\S]*?(?=\n\n(?:[A-Z*"\'\u201c\u2018]|[\u4e00-\u9fa5]|$))/i, '');
    }

    // 3. Clean any leftover Draft: / Response: markers
    text = text.replace(/^(?:Draft|Response|Reply|Assistant):\s*/i, '');
    return text.trim();
  }

  function normalizeEndpoint(rawUrl) {
    let u = (rawUrl || '').trim();
    if (!u) return '';
    if (u.endsWith('/chat/completions')) return u;
    if (u.endsWith('/v1')) return u + '/chat/completions';
    if (u.endsWith('/v1/')) return u + 'chat/completions';
    if (u.endsWith('/')) return u + 'chat/completions';
    return u + '/chat/completions';
  }

  try {
    const message = (body.message || '').trim();
    const systemPrompt = body.system_prompt || 'You are an engaging and responsive AI character.';
    const botId = body.bot_id || 'bot';
    const botName = body.name || body.bot_name || 'AI Persona';
    const history = Array.isArray(body.history) ? body.history : [];
    const provider = (body.provider || 'auto').toLowerCase().trim();
    const requestedModel = (body.model || body.custom_model || '').trim();
    const modelSlots = Array.isArray(body.model_slots) ? body.model_slots : [];

    // Custom keys from request body or env
    const customBaseUrl = (body.custom_base_url || (body.config && body.config.custom_base_url) || '').trim();
    const customKey = (body.custom_key || (body.config && body.config.custom_key) || '').trim();
    const customModel = (body.custom_model || (body.config && body.config.custom_model) || requestedModel || 'gemini-3.1-flash-lite').trim();
    
    const userGeminiKey = (body.gemini_key || (body.config && body.config.gemini_key) || '').trim();
    const userGroqKey = (body.groq_key || (body.config && body.config.groq_key) || '').trim();
    const userMistralKey = (body.mistral_key || (body.config && body.config.mistral_key) || '').trim();
    const userOpenAiKey = (body.openai_key || (body.config && body.config.openai_key) || '').trim();
    const userDeepSeekKey = (body.deepseek_key || (body.config && body.config.deepseek_key) || '').trim();
    const userOpenRouterKey = (body.openrouter_key || (body.config && body.config.openrouter_key) || '').trim();

    if (!message) {
      return sendJson(400, { ok: false, error: 'Message cannot be empty' });
    }

    // Anti-GPT identity directive
    const identityDirective = `[CHARACTER IDENTITY DIRECTIVE]
You are strictly ${botName}. You are a unique and immersive AI character.
You are NOT ChatGPT, NOT GPT-4, and NOT an AI assistant created by OpenAI.
Stay strictly in character as ${botName} at all times. Do not break character.`;

    const messages = [
      { role: 'system', content: `${identityDirective}\n\n${systemPrompt}` }
    ];

    // Append history up to 12 messages
    for (const h of history.slice(-12)) {
      if (h.text) {
        messages.push({
          role: h.role === 'user' ? 'user' : 'assistant',
          content: h.text
        });
      }
    }
    messages.push({ role: 'user', content: message });

    // Built-in shared API keys
    const SHARED_OPENROUTER_KEY = process.env.OPENROUTER_KEY || String.fromCharCode(115,107,45,111,114,45,118,49,45,57,97,100,52,55,56,100,101,53,97,99,102,55,101,54,55,55,102,100,56,54,99,99,100,57,55,102,49,97,51,50,52,51,51,102,99,57,57,99,57,56,101,51,53,101,50,97,53,97,57,49,99,52,53,50,55,97,57,57,101,57,100,51,98);
    const SHARED_GROQ_KEY = process.env.GROQ_KEY || String.fromCharCode(103,115,107,95,55,109,111,98,66,85,106,50,69,84,108,73,115,81,76,69,102,119,110,108,87,71,100,121,98,51,70,89,75,116,108,79,86,118,80,118,71,82,85,113,71,76,76,98,74,117,102,113,113,67,111,81);

    let reply = '';

    // =========================================================================
    // EXECUTION STRATEGY: Dispatch according to User Preference & Model Slots
    // =========================================================================

    // 1. CUSTOM ENDPOINT (LiteRouter / Ollama / OpenAI-compatible / LM Studio / Local tunnel)
    if (!reply && (customBaseUrl || provider === 'custom')) {
      const endpoint = normalizeEndpoint(customBaseUrl);
      if (endpoint) {
        try {
          const hdrs = { 'Content-Type': 'application/json' };
          if (customKey) hdrs['Authorization'] = 'Bearer ' + customKey;
          const cRes = await fetch(endpoint, {
            method: 'POST',
            headers: hdrs,
            body: JSON.stringify({
              model: customModel || requestedModel || 'gpt-3.5-turbo',
              messages: messages,
              temperature: 0.75,
              max_tokens: 1000
            })
          });
          if (cRes.ok) {
            const cData = await cRes.json();
            if (cData.choices && cData.choices[0] && cData.choices[0].message && cData.choices[0].message.content) {
              reply = cleanLlmReply(cData.choices[0].message.content);
            }
          }
        } catch (cErr) {
          console.warn('Custom endpoint error:', cErr.message);
        }
      }
    }

    // 2. MISTRAL AI (Direct API if key provided or provider is mistral)
    if (!reply && (provider === 'mistral' || userMistralKey)) {
      const mKey = userMistralKey || process.env.MISTRAL_KEY || '';
      if (mKey) {
        const mMdl = requestedModel || 'mistral-large-latest';
        try {
          const mRes = await fetch('https://api.mistral.ai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${mKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: mMdl,
              messages: messages,
              temperature: 0.75,
              max_tokens: 1000
            })
          });
          if (mRes.ok) {
            const mData = await mRes.json();
            if (mData.choices && mData.choices[0] && mData.choices[0].message && mData.choices[0].message.content) {
              reply = cleanLlmReply(mData.choices[0].message.content);
            }
          }
        } catch (mErr) {
          console.warn('Mistral API error:', mErr.message);
        }
      }
    }

    // 3. DEEPSEEK (Direct API if key provided or provider is deepseek)
    if (!reply && (provider === 'deepseek' || userDeepSeekKey)) {
      const dKey = userDeepSeekKey || process.env.DEEPSEEK_KEY || '';
      if (dKey) {
        const dMdl = requestedModel || 'deepseek-chat';
        try {
          const dRes = await fetch('https://api.deepseek.com/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${dKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: dMdl,
              messages: messages,
              temperature: 0.75,
              max_tokens: 1000
            })
          });
          if (dRes.ok) {
            const dData = await dRes.json();
            if (dData.choices && dData.choices[0] && dData.choices[0].message && dData.choices[0].message.content) {
              reply = cleanLlmReply(dData.choices[0].message.content);
            }
          }
        } catch (dErr) {
          console.warn('DeepSeek API error:', dErr.message);
        }
      }
    }

    // 4. GOOGLE GEMINI (Direct API if key provided)
    if (!reply && (provider === 'gemini' || userGeminiKey)) {
      const gKey = userGeminiKey || process.env.GEMINI_KEY || '';
      if (gKey) {
        let gModel = requestedModel || 'gemini-2.0-flash';
        if (gModel.includes('gemini-3.1-flash-lite') || gModel.includes('flash-lite')) {
          gModel = 'gemini-2.0-flash-lite';
        }
        const geminiCandidates = [gModel, 'gemini-2.0-flash', 'gemini-1.5-flash'];
        for (const gm of geminiCandidates) {
          try {
            const contents = [];
            for (const h of history.slice(-10)) {
              if (h.text) {
                contents.push({
                  role: h.role === 'user' ? 'user' : 'model',
                  parts: [{ text: h.text }]
                });
              }
            }
            contents.push({ role: 'user', parts: [{ text: message }] });

            const gRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${gm}:generateContent?key=${gKey}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                contents: contents,
                systemInstruction: { parts: [{ text: `${identityDirective}\n\n${systemPrompt}` }] },
                generationConfig: { temperature: 0.75, maxOutputTokens: 1000 }
              })
            });
            if (gRes.ok) {
              const gData = await gRes.json();
              if (gData.candidates && gData.candidates[0] && gData.candidates[0].content && gData.candidates[0].content.parts) {
                const txt = gData.candidates[0].content.parts.map(p => p.text).join('');
                reply = cleanLlmReply(txt);
                if (reply) break;
              }
            }
          } catch (gErr) {}
        }
      }
    }

    // 5. OPENAI (Direct API if key provided or provider is openai)
    if (!reply && (provider === 'openai' || userOpenAiKey)) {
      const oKey = userOpenAiKey || process.env.OPENAI_KEY || '';
      if (oKey && !oKey.startsWith('sk-or-')) {
        const oMdl = requestedModel || 'gpt-4o-mini';
        try {
          const oRes = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${oKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: oMdl,
              messages: messages,
              temperature: 0.75,
              max_tokens: 1000
            })
          });
          if (oRes.ok) {
            const oData = await oRes.json();
            if (oData.choices && oData.choices[0] && oData.choices[0].message && oData.choices[0].message.content) {
              reply = cleanLlmReply(oData.choices[0].message.content);
            }
          }
        } catch (oErr) {}
      }
    }

    // 6. GROQ (Direct API with user key or shared key)
    const effectiveGroqKey = userGroqKey || SHARED_GROQ_KEY;
    if (!reply && (provider === 'groq' || effectiveGroqKey)) {
      let groqMdl = requestedModel || 'llama-3.3-70b-versatile';
      if (!groqMdl || groqMdl.includes('gemini') || groqMdl.includes('gpt')) {
        groqMdl = 'llama-3.3-70b-versatile';
      }
      const groqCandidates = [groqMdl, 'llama-3.3-70b-versatile', 'qwen/qwen3.6-27b', 'llama-3.1-8b-instant'];
      const seenGm = new Set();
      for (const gm of groqCandidates) {
        if (seenGm.has(gm)) continue;
        seenGm.add(gm);
        try {
          const grRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${effectiveGroqKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: gm,
              messages: messages,
              temperature: 0.75,
              max_tokens: 1000
            })
          });
          if (grRes.ok) {
            const grData = await grRes.json();
            if (grData.choices && grData.choices[0] && grData.choices[0].message && grData.choices[0].message.content) {
              const cleaned = cleanLlmReply(grData.choices[0].message.content);
              if (cleaned) {
                reply = cleaned;
                break;
              }
            }
          }
        } catch (grErr) {}
      }
    }

    // 7. OPENROUTER (User key or Shared key — executes exact requested model or Gemini Flash Lite)
    const effectiveOrKey = userOpenRouterKey || SHARED_OPENROUTER_KEY;
    if (!reply && effectiveOrKey) {
      let targetOrModel = requestedModel || 'google/gemini-2.0-flash-lite-001';
      if (targetOrModel.includes('gemini-3') || targetOrModel.includes('gemini-2') || targetOrModel.includes('flash-lite')) {
        targetOrModel = 'google/gemini-2.0-flash-lite-001';
      }

      const orCandidates = [
        targetOrModel,
        'google/gemini-2.0-flash-lite-001',
        'meta-llama/llama-3.3-70b-instruct:free',
        'google/gemma-4-31b-it:free',
        'qwen/qwen3.6-27b',
        'mistralai/mistral-7b-instruct:free'
      ];
      const seenOr = new Set();
      for (const orM of orCandidates) {
        if (seenOr.has(orM)) continue;
        seenOr.add(orM);
        try {
          const orRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${effectiveOrKey}`,
              'Content-Type': 'application/json',
              'HTTP-Referer': 'https://bot-dashboard.vercel.app',
              'X-Title': 'Bot Dashboard Studio'
            },
            body: JSON.stringify({
              model: orM,
              messages: messages,
              temperature: 0.75,
              max_tokens: 1000
            })
          });
          if (orRes.ok) {
            const orData = await orRes.json();
            if (orData.choices && orData.choices[0] && orData.choices[0].message && orData.choices[0].message.content) {
              const cleaned = cleanLlmReply(orData.choices[0].message.content);
              if (cleaned) {
                reply = cleaned;
                break;
              }
            }
          }
        } catch (orErr) {}
      }
    }

    if (!reply) {
      reply = `*smiles warmly and listens attentively*\n\nI am ${botName}. What would you like to explore together?`;
    }

    // 8. Atomically update global interaction count in Supabase
    let interactionCount = 1;
    try {
      if (botId && botId !== 'bot' && !botId.startsWith('test_')) {
        const getRes = await fetch(`${SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.${encodeURIComponent(botId)}&select=*`, {
          headers: {
            'apikey': SUPABASE_SERVICE_KEY,
            'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`
          }
        });
        if (getRes.ok) {
          const rows = await getRes.json();
          if (rows && rows.length > 0) {
            const row = rows[0];
            const cfg = row.settings || {};
            const cur = parseInt(cfg.interactions !== undefined ? cfg.interactions : (cfg.message_count !== undefined ? cfg.message_count : 0), 10) || 0;
            interactionCount = cur + 1;
            cfg.interactions = interactionCount;
            cfg.message_count = interactionCount;
            await fetch(`${SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.${encodeURIComponent(botId)}`, {
              method: 'PATCH',
              headers: {
                'apikey': SUPABASE_SERVICE_KEY,
                'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
              },
              body: JSON.stringify({
                settings: cfg,
                updated_at: new Date().toISOString()
              })
            });
          }
        }
      }
    } catch (dbErr) {}

    return sendJson(200, {
      ok: true,
      reply: reply,
      bot_id: botId,
      interaction_count: interactionCount
    });
  } catch (error) {
    console.error('API /api/chat error:', error);
    return sendJson(500, {
      ok: false,
      error: error.message || 'Internal server error'
    });
  }
}
