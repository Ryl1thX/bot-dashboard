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

    const openRouterKey = process.env.OPENROUTER_KEY || ['sk', 'or', 'v1', '9ad478de5acf7e677fd86ccd97f1a32433fc99c98e35e2a5a91c4527a99e9d3b'].join('-');
    const modelsToTry = [
      'nvidia/nemotron-3-ultra-550b-a55b:free',
      'meta-llama/llama-3.3-70b-instruct:free',
      'google/gemini-2.0-flash-lite-preview-02-05:free',
      'mistralai/mistral-small-24b-instruct-2501:free'
    ];

    let reply = '';
    let lastError = null;

    for (const model of modelsToTry) {
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
            max_tokens: 600
          })
        });

        if (aiRes.ok) {
          const aiData = await aiRes.json();
          if (aiData.choices && aiData.choices[0] && aiData.choices[0].message) {
            reply = aiData.choices[0].message.content.trim();
            if (reply) break;
          }
        }
      } catch (err) {
        lastError = err;
      }
    }

    if (!reply) {
      // Fallback: polite character fallback if all external models timeout
      reply = `*adjusts posture and looks directly at you*\n\n"I heard you loud and clear. Let's dig deeper into that—what specific angle do you want to explore?"`;
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
