export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const SUPABASE_URL = process.env.SUPABASE_URL || 'https://tdawmkgedbxbjkctylld.supabase.co';
  const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY || [
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
    'eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRkYXdta2dlZGJ4YmprY3R5bGxkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjExNjMyNCwiZXhwIjoyMTAxNjkyMzI0fQ',
    'r_Xz7g3lY0a3Z78yZ_UomG8dF7B_3d0K8tZ2hR4oY7U'
  ].join('.');

  try {
    if (req.method === 'GET') {
      const resp = await fetch(`${SUPABASE_URL}/rest/v1/user_bots?select=*&order=created_at.desc`, {
        headers: {
          'apikey': SUPABASE_SERVICE_KEY,
          'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
          'Content-Type': 'application/json'
        }
      });
      if (!resp.ok) {
        return res.status(resp.status).json({ ok: false, error: 'Failed to fetch bots' });
      }
      const data = await resp.json();
      return res.status(200).json(data);
    }

    if (req.method === 'POST' || req.method === 'PATCH') {
      const body = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
      const botId = String(body.bot_id || body.id || req.query.id || '').trim();
      const botName = body.name || body.bot_name || '';
      const config = body.config || {};
      const privacy = body.privacy || config.privacy || 'public';
      const avatarUrl = body.avatar_url || body.pfp || config.avatar_url || config.pfp || null;
      const personality = body.personality || config.personality || '';

      if (!botId) {
        return res.status(400).json({ ok: false, error: 'Missing bot_id' });
      }

      // Fetch existing record first
      const getRes = await fetch(`${SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.${encodeURIComponent(botId)}&select=*`, {
        headers: {
          'apikey': SUPABASE_SERVICE_KEY,
          'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`
        }
      });

      let existing = [];
      if (getRes.ok) {
        existing = await getRes.json();
      }

      const existingSettings = (existing.length > 0 && existing[0].settings) ? existing[0].settings : {};
      const mergedSettings = {
        ...existingSettings,
        ...config,
        name: botName || existingSettings.name || 'Bot',
        personality: personality || existingSettings.personality || '',
        privacy: privacy
      };
      if (avatarUrl) {
        mergedSettings.avatar_url = avatarUrl;
        mergedSettings.pfp = avatarUrl;
      }

      const patchPayload = {
        updated_at: new Date().toISOString(),
        settings: mergedSettings
      };
      if (botName) patchPayload.bot_name = botName;

      let patchRes;
      if (existing.length > 0) {
        patchRes = await fetch(`${SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.${encodeURIComponent(botId)}`, {
          method: 'PATCH',
          headers: {
            'apikey': SUPABASE_SERVICE_KEY,
            'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
          },
          body: JSON.stringify(patchPayload)
        });
      }

      return res.status(200).json({
        ok: true,
        bot_id: botId,
        privacy: privacy,
        settings: mergedSettings
      });
    }

    return res.status(405).json({ ok: false, error: 'Method not allowed' });
  } catch (err) {
    console.error('API /api/bots error:', err);
    return res.status(500).json({ ok: false, error: err.message || 'Server error' });
  }
}
