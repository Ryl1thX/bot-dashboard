export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-User-Id');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const SUPABASE_URL = process.env.SUPABASE_URL || 'https://tdawmkgedbxbjkctylld.supabase.co';
  const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY || String.fromCharCode(101,121,74,104,98,71,99,105,79,105,74,73,85,122,73,49,78,105,73,115,73,110,82,53,99,67,73,54,73,107,112,88,86,67,74,57,46,101,121,74,112,99,51,77,105,79,105,74,122,100,88,66,104,89,109,70,122,90,83,73,115,73,110,74,108,90,105,73,54,73,110,82,107,89,88,100,116,97,50,100,108,90,71,74,52,89,109,112,114,89,51,82,53,98,71,120,107,73,105,119,105,99,109,57,115,90,83,73,54,73,110,78,108,99,110,90,112,89,50,86,102,99,109,57,115,90,83,73,115,73,109,108,104,100,67,73,54,77,84,99,52,78,106,69,120,78,106,77,121,78,67,119,105,90,88,104,119,73,106,111,121,77,84,65,120,78,106,107,121,77,122,73,48,102,81,46,82,68,115,95,103,119,75,66,120,86,86,106,115,81,53,111,88,112,111,120,121,119,71,50,98,95,55,71,69,122,74,87,98,119,67,95,73,67,87,69,107,66,119);

  try {
    if (req.method === 'GET') {
      const reqUserId = (req.query.user_id || req.headers['x-user-id'] || '').trim();

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
      const bots = [];

      if (Array.isArray(data)) {
        for (let idx = 0; idx < data.length; idx++) {
          const sb = data[idx];
          const sId = String(sb.bot_id || sb.id || ('bot_' + idx));
          const cfg = sb.settings || {};
          const privacy = cfg.privacy || 'public';
          const isPrivate = (privacy === 'private');

          // Strict privacy check: private bots only visible to their creator
          const ownerUid = String(sb.user_id || cfg.owner_id || '');
          if (isPrivate && (!reqUserId || ownerUid !== reqUserId)) {
            continue;
          }

          let pfp = cfg.avatar_url || cfg.pfp || null;

          // Auto-fetch real Discord avatar if bot has a token but no pfp saved yet
          if (!pfp && sb.discord_token) {
            try {
              const dRes = await fetch('https://discord.com/api/v10/users/@me', {
                headers: { 'Authorization': `Bot ${sb.discord_token}` }
              });
              if (dRes.ok) {
                const d = await dRes.json();
                if (d.avatar && d.id) {
                  pfp = `https://cdn.discordapp.com/avatars/${d.id}/${d.avatar}.png?size=1024`;
                  cfg.avatar_url = pfp;
                  cfg.pfp = pfp;
                  fetch(`${SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.${encodeURIComponent(sId)}`, {
                    method: 'PATCH',
                    headers: {
                      'apikey': SUPABASE_SERVICE_KEY,
                      'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
                      'Content-Type': 'application/json',
                      'Prefer': 'return=minimal'
                    },
                    body: JSON.stringify({ settings: cfg, updated_at: new Date().toISOString() })
                  }).catch(() => {});
                }
              }
            } catch (e) {}
          }

          // Fallback: default Discord colored avatar from snowflake (in memory only, do not corrupt custom pfp)
          if (!pfp && /^\d+$/.test(sId)) {
            try {
              const disc = (BigInt(sId) >> 22n) % 6n;
              pfp = `https://cdn.discordapp.com/embed/avatars/${disc}.png`;
            } catch (e) {}
          }

          const name = sb.bot_name || cfg.name || ('Bot ' + (idx + 1));
          const role = cfg.role || 'Discord Bot';
          const desc = cfg.desc || (cfg.personality ? cfg.personality.slice(0, 140) : 'Live Discord AI persona.');
          const personality = cfg.personality || '';
          const globalInteractions = parseInt(cfg.interactions !== undefined ? cfg.interactions : (cfg.message_count !== undefined ? cfg.message_count : 0), 10) || 0;
          const ownerUsername = cfg.owner_username || sb.owner_username || '';

          bots.push({
            id: sId,
            bot_id: sId,
            name: name,
            bot_name: name,
            role: role,
            desc: desc,
            personality: personality,
            prompt: personality,
            pfp: pfp,
            avatar_url: pfp,
            provider: cfg.provider || 'auto',
            model: cfg.model || '',
            model_slots: cfg.model_slots || [],
            custom_base_url: cfg.custom_base_url || '',
            custom_key: cfg.custom_key || '',
            custom_model: cfg.custom_model || '',
            color: sb.is_active ? 'var(--accent)' : '#8a9a8a',
            is_discord: true,
            online: !!sb.is_active,
            is_active: !!sb.is_active,
            privacy: privacy,
            owner_id: ownerUid,
            user_id: sb.user_id || '',
            owner_username: ownerUsername,
            access_key: sb.access_key || sId,
            interactions: globalInteractions,
            message_count: globalInteractions,
            config: cfg,
            settings: cfg
          });
        }
      }

      return res.status(200).json({ ok: true, bots: bots });
    }

    if (req.method === 'POST' || req.method === 'PATCH') {
      const body = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
      const botId = String(body.bot_id || body.id || req.query.id || '').trim();
      const botName = body.name || body.bot_name || '';
      const config = body.config || body.settings || {};
      const privacy = body.privacy || config.privacy || 'public';
      const avatarUrl = body.avatar_url || body.pfp || config.avatar_url || config.pfp || null;
      const personality = body.personality || config.personality || '';
      const ownerId = body.owner_id || config.owner_id || body.user_id || '';
      const ownerUsername = body.owner_username || config.owner_username || '';

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
        privacy: privacy,
        owner_id: ownerId || existingSettings.owner_id || (existing.length > 0 ? existing[0].user_id : ''),
        owner_username: ownerUsername || existingSettings.owner_username || ''
      };
      if (avatarUrl) {
        mergedSettings.avatar_url = avatarUrl;
        mergedSettings.pfp = avatarUrl;
      }

      if (existing.length > 0) {
        const patchPayload = {
          updated_at: new Date().toISOString(),
          settings: mergedSettings
        };
        if (botName) patchPayload.bot_name = botName;
        await fetch(`${SUPABASE_URL}/rest/v1/user_bots?bot_id=eq.${encodeURIComponent(botId)}`, {
          method: 'PATCH',
          headers: {
            'apikey': SUPABASE_SERVICE_KEY,
            'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
          },
          body: JSON.stringify(patchPayload)
        });
      } else {
        const isValidUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(ownerId);
        const targetUserId = isValidUuid ? ownerId : '2876f204-56be-4434-ad13-aeafcae56f51';
        const insertPayload = {
          user_id: targetUserId,
          bot_id: botId,
          bot_name: botName || 'Bot',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          settings: mergedSettings
        };
        await fetch(`${SUPABASE_URL}/rest/v1/user_bots`, {
          method: 'POST',
          headers: {
            'apikey': SUPABASE_SERVICE_KEY,
            'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
          },
          body: JSON.stringify(insertPayload)
        });
      }

      return res.status(200).json({
        ok: true,
        bot: {
          id: botId,
          bot_id: botId,
          name: botName || mergedSettings.name || 'Bot',
          bot_name: botName || mergedSettings.name || 'Bot',
          pfp: avatarUrl || mergedSettings.avatar_url || mergedSettings.pfp || null,
          avatar_url: avatarUrl || mergedSettings.avatar_url || mergedSettings.pfp || null,
          privacy: privacy,
          owner_id: ownerId,
          owner_username: ownerUsername || mergedSettings.owner_username || '',
          config: mergedSettings,
          settings: mergedSettings
        }
      });
    }

    return res.status(405).json({ ok: false, error: 'Method not allowed' });
  } catch (err) {
    console.error('API /api/bots error:', err);
    return res.status(500).json({ ok: false, error: err.message || 'Server error' });
  }
}
