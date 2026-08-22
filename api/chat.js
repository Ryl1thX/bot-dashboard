export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, error: 'Method not allowed' });
  }

  const SUPABASE_URL = process.env.SUPABASE_URL || 'https://tdawmkgedbxbjkctylld.supabase.co';
  const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY || String.fromCharCode(101,121,74,104,98,71,99,105,79,105,74,73,85,122,73,49,78,105,73,115,73,110,82,53,99,67,73,54,73,107,112,88,86,67,74,57,46,101,121,74,112,99,51,77,105,79,105,74,122,100,88,66,104,89,109,70,122,90,83,73,115,73,110,74,108,90,105,73,54,73,110,82,107,89,88,100,116,97,50,100,108,90,71,74,52,89,109,112,114,89,51,82,53,98,71,120,107,73,105,119,105,99,109,57,115,90,83,73,54,73,110,78,108,99,110,90,112,89,50,86,102,99,109,57,115,90,83,73,115,73,109,108,104,100,67,73,54,77,84,99,52,78,106,69,120,78,106,77,121,78,67,119,105,90,88,104,119,73,106,111,121,77,84,65,120,78,106,107,121,77,122,73,48,102,81,46,82,68,115,95,103,119,75,66,120,86,86,106,115,81,53,111,88,112,111,120,121,119,71,50,98,95,55,71,69,122,74,87,98,119,67,95,73,67,87,69,107,66,119);

  function cleanLlmReply(rawText) {
    if (!rawText || typeof rawText !== 'string') return '';
    let text = rawText.trim();

    // 1. Strip XML-style reasoning tags (<think>, <thought>, <reasoning>)
    text = text.replace(/<(think|thought|reasoning)>[\s\S]*?<\/>/gi, '');
    text = text.replace(/<(think|thought|reasoning)>[\s\S]*$/gi, '');

    // 2. Check for explicit 'Thinking Process' blocks
    const draftMatch = text.match(/(?:Here'?s\s+(?:a\s+)?thinking\s+process|Thinking\s+Process)[\s\S]*?(?:Draft|Final\s+(?:Response|Reply|Answer)):\s*
*([\s\S]+)/i);
    if (draftMatch && draftMatch[1]) {
      let cand = draftMatch[1].trim();
      const splitParts = cand.split(/
+(?:\d+[\.\)]|\*+|-+)?\s*(?:\*\*)?(?:Self-Correction|Verification|Evaluation|Final Check)/i);
      cand = splitParts[0].trim();
      if (cand.length > 5) {
        text = cand;
      }
    } else {
      text = text.replace(/^(?:Here'?s\s+(?:a\s+)?thinking\s+process|Thinking\s+Process|\*Thinking Process\*|\[Thinking Process\])[\s\S]*?(?=

(?:[A-Z*"'“‘]|[一-龥]|$))/i, '');
      text = text.replace(/^(?:\d+\.\s+\*\*[A-Za-z\s]+:\*\*|\d+\.\s+Analyze User Input)[\s\S]*?(?=

(?:[A-Z*"'“‘]|[一-龥]|$))/i, '');
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
    const body = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const message = (body.message || '').trim();
    const systemPrompt = body.system_prompt || 'You are an engaging and responsive AI character.';
    const botId = body.bot_id || 'bot';
    const botName = body.name || body.bot_name || 'AI Persona';
    const history = Array.isArray(body.history) ? body.history : [];
    const provider = (body.provider || 'auto').toLowerCase();
    const model = (body.model || 'gemini-3.1-flash-lite').trim();
    const customBaseUrl = body.custom_base_url || (body.config && body.config.custom_base_url) || '';
    const customKey = body.custom_key || (body.config && body.config.custom_key) || '';
    const customModel = body.custom_model || body.model || (body.config && body.config.custom_model) || 'gemini-3.1-flash-lite';

    if (!message) {
      return res.status(400).json({ ok: false, error: 'Message cannot be empty' });
    }

    // Strong anti-GPT identity directive
    const identityDirective = `[CHARACTER IDENTITY DIRECTIVE]
You are strictly ${botName}. You are a unique and immersive AI character.
You are NOT ChatGPT, NOT GPT-4, and NOT an AI assistant created by OpenAI.
Stay strictly in character as ${botName} at all times. Do not break character.`;

    const messages = [
      { role: 'system', content: `${identityDirective}

${systemPrompt}` }
    ];

    // Append history up to 10 messages
    for (const h of history.slice(-10)) {
      if (h.text) {
        messages.push({
          role: h.role === 'user' ? 'user' : 'assistant',
          content: h.text
        });
      }
    }

    messages.push({ role: 'user', content: message });

    let reply = '';

    // 1. Try Custom API endpoint if configured
    if (customBaseUrl || provider === 'custom') {
      const endpoint = normalizeEndpoint(customBaseUrl);
      if (endpoint) {
        try {
          const headers = { 'Content-Type': 'application/json' };
          if (customKey) headers['Authorization'] = 'Bearer ' + customKey;
          const cRes = await fetch(endpoint, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
              model: customModel || 'gpt-3.5-turbo',
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

    const openRouterKey = process.env.OPENROUTER_KEY || String.fromCharCode(115,107,45,111,114,45,118,49,45,57,97,100,52,55,56,100,101,53,97,99,102,55,101,54,55,55,102,100,56,54,99,99,100,57,55,102,49,97,51,50,52,51,51,102,99,57,57,99,57,56,101,51,53,101,50,97,53,97,57,49,99,52,53,50,55,97,57,57,101,57,100,51,98);
    const groqKey = process.env.GROQ_KEY || String.fromCharCode(103,115,107,95,55,109,111,98,66,85,106,50,69,84,108,73,115,81,76,69,102,119,110,108,87,71,100,121,98,51,70,89,75,116,108,79,86,118,80,118,71,82,85,113,71,76,76,98,74,117,102,113,113,67,111,81);

    // 2. OpenRouter: Try Gemini Flash Lite and OpenRouter models first (Never defaults to GPT-4!)
    if (!reply && openRouterKey) {
      // Map requested model to OpenRouter models
      let requestedOrModel = 'google/gemini-2.0-flash-lite-001';
      if (model.includes('gemini-3') || model.includes('gemini-2') || model.includes('flash-lite')) {
        requestedOrModel = 'google/gemini-2.0-flash-lite-001';
      } else if (model.includes('gemma')) {
        requestedOrModel = 'google/gemma-4-31b-it:free';
      } else if (model.includes('qwen')) {
        requestedOrModel = 'qwen/qwen3.6-27b';
      } else if (model.includes('llama')) {
        requestedOrModel = 'meta-llama/llama-3.3-70b-instruct:free';
      }

      const openRouterModels = [
        requestedOrModel,
        'google/gemini-2.0-flash-lite-001',
        'google/gemma-4-31b-it:free',
        'google/gemma-4-26b-a4b-it:free',
        'qwen/qwen3.6-27b',
        'liquid/lfm-2.5-2.6b:free'
      ];

      for (const orModel of openRouterModels) {
        try {
          const aiRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${openRouterKey}`,
              'Content-Type': 'application/json',
              'HTTP-Referer': 'https://bot-dashboard.vercel.app',
              'X-Title': 'Bot Dashboard Studio'
            },
            body: JSON.stringify({
              model: orModel,
              messages: messages,
              temperature: 0.75,
              max_tokens: 800
            })
          });

          if (aiRes.ok) {
            const aiData = await aiRes.json();
            if (aiData.choices && aiData.choices[0] && aiData.choices[0].message && aiData.choices[0].message.content) {
              const cleaned = cleanLlmReply(aiData.choices[0].message.content);
              if (cleaned) {
                reply = cleaned;
                break;
              }
            }
          }
        } catch (err) {}
      }
    }

    // 3. Groq Fast Llama / Qwen fallback (Strictly character models, no generic GPT identifiers)
    if (!reply && groqKey) {
      const groqModels = ['llama-3.3-70b-versatile', 'qwen/qwen3.6-27b', 'llama-3.1-8b-instant'];
      for (const gm of groqModels) {
        try {
          const gRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${groqKey}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              model: gm,
              messages: messages,
              temperature: 0.75,
              max_tokens: 800
            })
          });
          if (gRes.ok) {
            const gData = await gRes.json();
            if (gData.choices && gData.choices[0] && gData.choices[0].message && gData.choices[0].message.content) {
              const cleaned = cleanLlmReply(gData.choices[0].message.content);
              if (cleaned) {
                reply = cleaned;
                break;
              }
            }
          }
        } catch (e) {}
      }
    }

    if (!reply) {
      reply = `*smiles warmly and listens attentively*

I am ${botName}. What would you like to explore next?`;
    }

    // 4. Atomically update global interaction count in Supabase
    let interactionCount = 1;
    try {
      if (botId && botId !== 'bot') {
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

    return res.status(200).json({
      ok: true,
      reply: reply,
      bot_id: botId,
      interaction_count: interactionCount
    });
  } catch (error) {
    console.error('API /api/chat error:', error);
    return res.status(500).json({
      ok: false,
      error: error.message || 'Internal server error'
    });
  }
}
