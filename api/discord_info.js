export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const token = (req.query.token || (req.body && req.body.token) || '').trim();
  if (!token) {
    return res.status(400).json({ ok: false, error: 'Missing token' });
  }

  try {
    const dRes = await fetch('https://discord.com/api/v10/users/@me', {
      headers: { 'Authorization': 'Bot ' + token }
    });

    if (!dRes.ok) {
      const errText = await dRes.text();
      return res.status(dRes.status).json({ ok: false, error: 'Discord API error: ' + errText });
    }

    const d = await dRes.json();
    let avatarUrl = null;
    if (d.avatar && d.id) {
      avatarUrl = `https://cdn.discordapp.com/avatars/${d.id}/${d.avatar}.png?size=1024`;
    } else if (d.id) {
      try {
        const disc = (BigInt(d.id) >> 22n) % 6n;
        avatarUrl = `https://cdn.discordapp.com/embed/avatars/${disc}.png`;
      } catch (e) {
        avatarUrl = 'https://cdn.discordapp.com/embed/avatars/0.png';
      }
    }

    return res.status(200).json({
      ok: true,
      id: d.id,
      username: d.username,
      discriminator: d.discriminator,
      avatar: d.avatar,
      avatar_url: avatarUrl,
      bot: d.bot
    });
  } catch (err) {
    return res.status(500).json({ ok: false, error: err.message || 'Internal server error' });
  }
}
