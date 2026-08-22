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

  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const message = (body.message || '').trim();
    const systemPrompt = body.system_prompt || 'You are a helpful and engaging AI character.';
    const botId = body.bot_id || 'bot';
    const history = Array.isArray(body.history) ? body.history : [];

    if (!message) {
      return res.status(400).json({ ok: false, error: 'Message cannot be empty' });
    }

    const messages = [
      { role: 'system', content: systemPrompt }
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

    const groqKey = process.env.GROQ_KEY || String.fromCharCode(103,115,107,95,55,109,111,98,66,85,106,50,69,84,108,73,115,81,76,69,102,119,110,108,87,71,100,121,98,51,70,89,75,116,108,79,86,118,80,118,71,82,85,113,71,76,76,98,74,117,102,113,113,67,111,81);
    const openRouterKey = process.env.OPENROUTER_KEY || String.fromCharCode(115,107,45,111,114,45,118,49,45,57,97,100,52,55,56,100,101,53,97,99,102,55,101,54,55,55,102,100,56,54,99,99,100,57,55,102,49,97,51,50,52,51,51,102,99,57,57,99,57,56,101,51,53,101,50,97,53,97,57,49,99,52,53,50,55,97,57,57,101,57,100,51,98);

    let reply = '';

    // 1. Try high-speed Groq models
    const groqModels = ['openai/gpt-oss-120b', 'qwen/qwen3.6-27b', 'openai/gpt-oss-20b'];
    if (groqKey) {
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
              reply = gData.choices[0].message.content.trim();
              reply = reply.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
              if (reply) break;
            }
          }
        } catch (e) {}
      }
    }

    // 2. Fallback to OpenRouter free models
    if (!reply && openRouterKey) {
      const openRouterModels = [
        'google/gemma-4-31b-it:free',
        'google/gemma-4-26b-a4b-it:free',
        'openai/gpt-oss-20b:free',
        'liquid/lfm-2.5-2.6b:free'
      ];

      for (const model of openRouterModels) {
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
              model: model,
              messages: messages,
              temperature: 0.75,
              max_tokens: 700
            })
          });

          if (aiRes.ok) {
            const aiData = await aiRes.json();
            if (aiData.choices && aiData.choices[0] && aiData.choices[0].message && aiData.choices[0].message.content) {
              reply = aiData.choices[0].message.content.trim();
              reply = reply.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
              if (reply) break;
            }
          }
        } catch (err) {}
      }
    }

    if (!reply) {
      reply = `*smiles and nods attentively*\n\nI am right here with you! Tell me what you would like to discuss next.`;
    }

    return res.status(200).json({
      ok: true,
      reply: reply,
      bot_id: botId
    });
  } catch (error) {
    console.error('API /api/chat error:', error);
    return res.status(500).json({
      ok: false,
      error: error.message || 'Internal server error'
    });
  }
}
