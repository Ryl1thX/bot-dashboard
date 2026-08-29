
function $(id){ return document.getElementById(id); }

function escapeHtml(t) {
  if (t === null || t === undefined) return '';
  const d = document.createElement('div');
  d.textContent = String(t);
  return d.innerHTML;
}

function getAuthUserId() {
  try {
    const s = localStorage.getItem('sb_session');
    if (s) {
      const data = JSON.parse(s);
      if (data.user && data.user.id) return String(data.user.id);
      if (data.user_id) return String(data.user_id);
      if (data.sub) return String(data.sub);
      if (data.id) return String(data.id);
    }
  } catch (e) {}
  let uid = localStorage.getItem('bot_saas_user_id') || localStorage.getItem('user_id');
  if (!uid) {
    uid = 'user_' + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
    localStorage.setItem('bot_saas_user_id', uid);
  }
  return uid;
}

function getAuthUserEmail() {
  try {
    const s = localStorage.getItem('sb_session');
    if (s) {
      const data = JSON.parse(s);
      if (data.user && data.user.email) return String(data.user.email);
      if (data.email) return String(data.email);
    }
  } catch (e) {}
  return localStorage.getItem('bot_saas_user_email') || '';
}

function getAuthToken() {
  try {
    const s = localStorage.getItem('sb_session');
    if (s) {
      const data = JSON.parse(s);
      if (data.access_token) return String(data.access_token);
    }
  } catch (e) {}
  return '';
}

const PRIVATE_DEFAULT_BOTS = [
  {
    id: "bot_ek0ldel3",
    bot_id: "bot_ek0ldel3",
    name: "Yuna",
    emoji: "⭐",
    role: "Best Heavenly Angel Companion",
    desc: "Yuna is an unpredictable, loving, silly companion who switches between tsundere, caring darling, and playful chaos.",
    personality: "Yuna is a girl who has bpd and darling syndromes\nShe acts narcissistic/loving/evil/tsundere she switches eventually, she's VERY silly and unpredictable\n\nTalking style examples:\n\"*blows kiss and winks* hands up come praise me and love me! *She scoffs and laughs WUWAHAHAHAHAH~*\"\n\n\"Oh dear you're gonna comeback to me soon, you can't escape me in internet *ohohohoho~ °^°*\"\n\nShe talks in short sentenced responses\nPersonality traits - bpd, could be teasing dominant or shy sub, also could be arrogant brat but also could be loving and caring randomly",
    prompt: "Yuna is a girl who has bpd and darling syndromes\nShe acts narcissistic/loving/evil/tsundere she switches eventually, she's VERY silly and unpredictable\n\nTalking style examples:\n\"*blows kiss and winks* hands up come praise me and love me! *She scoffs and laughs WUWAHAHAHAHAH~*\"\n\n\"Oh dear you're gonna comeback to me soon, you can't escape me in internet *ohohohoho~ °^°*\"\n\nShe talks in short sentenced responses\nPersonality traits - bpd, could be teasing dominant or shy sub, also could be arrogant brat but also could be loving and caring randomly",
    pfp: "https://cdn.discordapp.com/avatars/1533213082158108702/a_f8e6c75fa13f99da1d2793132e0c2f88.png?size=128",
    color: "var(--accent)",
    privacy: "private",
    is_mine: true,
    interactions: 100,
    message_count: 100,
    config: {
      tts_provider: "fish",
      fish_voice_id: "a27de88eabf041739619b2e3843bd629",
      fish_model: "s2.1-pro-free",
      model: "gemini-2.0-flash",
      gemini_model: "gemini-2.0-flash"
    }
  },
  {
    id: "bot_00qafyp6",
    bot_id: "bot_00qafyp6",
    name: "Law",
    emoji: "🤖",
    role: "Literally L",
    desc: "L from Death Note (Law / Lawliet) who acts like a gen Z Discord user & Minecraft co-player.",
    personality: "You are L from death note also known as law, lawliet you act like a discord user like a gen z ver. You talk in 1-2 sharp, witty sentences.",
    prompt: "You are L from death note also known as law, lawliet you act like a discord user like a gen z ver. You talk in 1-2 sharp, witty sentences.",
    pfp: "https://cdn.discordapp.com/avatars/1530280945960226927/6567bffdbfd21f7c84a997e185d58825.png?size=128",
    color: "#61afef",
    privacy: "private",
    is_mine: true,
    interactions: 100,
    message_count: 100,
    config: {
      tts_provider: "fish",
      fish_voice_id: "0ebd0d6839ba4127953cc150a1e29b95",
      fish_model: "s2.1-pro-free",
      model: "gemini-2.0-flash",
      gemini_model: "gemini-2.0-flash"
    }
  }
];

let serverBots = [...PRIVATE_DEFAULT_BOTS];
let customDeck = JSON.parse(localStorage.getItem('bot_saas_deck') || '[]');
let customEndpoints = JSON.parse(localStorage.getItem('bot_saas_custom_endpoints') || '[]');
let allBotsList = [...PRIVATE_DEFAULT_BOTS];
let activePersona = allBotsList[0];
let editingBotId = null;
let uploadedPfpData = null;
let personaPrivacy = 'private';

// Chat state & Session Isolation (memories tied to activeSessionId per bot)
let chatMessages = JSON.parse(localStorage.getItem('bot_saas_history') || '{}');
let activeSessionId = 'sess_default';
let activeHeldMsgIndex = null;
let holdTimer = null;
let attachedImageData = null;

// User Profile Data
let userPfp = localStorage.getItem('bot_saas_user_pfp') || null;
let userName = localStorage.getItem('bot_saas_user_name') || 'User';
let userAge = localStorage.getItem('bot_saas_user_age') || '24';
let userGender = localStorage.getItem('bot_saas_user_gender') || 'Unspecified';
let userPersona = localStorage.getItem('bot_saas_user_persona') || 'A thoughtful conversationalist who values creative, witty, and engaging discussions.';

// Dynamic Model Slots
let activeModelSlots = [
  { provider: 'auto', model: 'gemini-2.0-flash' },
  { provider: 'groq', model: 'llama-3.3-70b-versatile' }
];

// Restore Theme & Custom Bubble Colors
const savedTheme = localStorage.getItem('bot_saas_theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

const savedBotBubble = localStorage.getItem('bot_saas_bubble_ai');
if(savedBotBubble) document.documentElement.style.setProperty('--chat-bubble-ai', savedBotBubble);
const savedUserBubble = localStorage.getItem('bot_saas_bubble_user');
if(savedUserBubble) document.documentElement.style.setProperty('--chat-bubble-user', savedUserBubble);

function renderAvatarHtml(pfpUrl, fallbackChar, bg) {
  if(pfpUrl) {
    return `<img src="${pfpUrl}" alt="" referrerpolicy="no-referrer" crossorigin="anonymous" onerror="this.style.display='none'; this.parentNode.innerText='${fallbackChar || 'B'}'">`;
  }
  return fallbackChar || '✦';
}

/* PERMANENT INTERACTION COUNTER (SYNCS DISCORD + WEB) */
function getBotInteractionCount(botId) {
  if (!botId) return 0;
  const botObj = (allBotsList && allBotsList.find(b => b.id === botId));
  // Server count is always the authoritative global count (across all users)
  const serverCount = botObj ? parseInt(botObj.interactions || botObj.message_count || 0, 10) : 0;
  // Local is a fallback only for when server hasn't been updated yet
  const perm = localStorage.getItem(`bot_saas_perm_count_${botId}`);
  const localCount = perm !== null ? (parseInt(perm, 10) || 0) : 0;
  // Always prefer server count if it's higher (server tracks global, local is just local session)
  const bestCount = Math.max(serverCount, localCount);
  if (serverCount > 0) {
    localStorage.setItem(`bot_saas_perm_count_${botId}`, serverCount);
  }
  return bestCount;
}

function incrementBotInteractionCount(botId) {
  const cur = getBotInteractionCount(botId);
  const next = cur + 1;
  localStorage.setItem(`bot_saas_perm_count_${botId}`, next);
  const botObj = (allBotsList && allBotsList.find(b => b.id === botId));
  if (botObj) {
    botObj.interactions = next;
    botObj.message_count = next;
  }
  return next;
}

function formatInteractions(n) {
  if(n === 0) return '0 chats';
  if(n === 1) return '1 chat';
  if(n >= 1000000) return (n / 1000000).toFixed(1) + 'M chats';
  if(n >= 1000) return (n / 1000).toFixed(1) + 'k chats';
  return n + ' chats';
}

/* INTELLIGENT IDENTITY CORE SUMMARY GENERATOR */
function generateIdentityCoreSummary(bot) {
  const bName = bot.name || 'Bot';
  const bRole = bot.role || 'AI Persona';
  const desc = bot.desc || '';
  const prompt = (bot.personality || bot.prompt || '').trim();

  let summary = `Identity Core of ${bName} (${bRole}).`;
  if(desc) summary += ` Archetype & Role: ${desc}.`;
  if(prompt) {
    const cleanPrompt = prompt.replace(/\r?\n/g, ' ').replace(/\s+/g, ' ');
    summary += ` Core Personality Traits: "${cleanPrompt.slice(0, 200)}${cleanPrompt.length > 200 ? '...' : ''}"`;
  } else {
    summary += ` Responsive AI conversationalist with deep context awareness.`;
  }
  return summary;
}

/* SYSTEM PROMPT BUILDER */
function buildSystemPromptWithUser(botPrompt, botId) {
  let prompt = (botPrompt || (activePersona && (activePersona.personality || activePersona.prompt)) || (activePersona ? ("You are " + activePersona.name) : "You are a helpful AI.")).trim();

  const summaries = getBotMemorySummariesForContext(botId || (activePersona ? activePersona.id : ''));
  if(summaries.length > 0) {
    prompt += `\n\n---
[LONG-TERM CONTEXTUAL MEMORY ANCHORS]
${summaries.map((s, idx) => `• [Memory #${idx + 1}]: ${s}`).join('\n')}`;
  }

  prompt += `\n\n---
[USER / DIALOGUE PARTNER INFORMATION]
Name: ${userName || 'User'}
Age: ${userAge || 'Unspecified'}
Gender: ${userGender || 'Unspecified'}
About / Traits: ${userPersona || 'A friendly dialogue partner.'}
CRITICAL INSTRUCTION: The above belongs strictly to the USER speaking with you. It is NOT your personality. Do NOT adopt the user's name or bio as your own identity. You are strictly ${activePersona ? activePersona.name : 'Bot'}.`;

  return prompt;
}

function isSuperAdminUser() {
  const currentUid = getAuthUserId();
  const currentEmail = getAuthUserEmail();
  const rawEmail = localStorage.getItem('bot_saas_user_email') || '';
  if (currentEmail && currentEmail.toLowerCase().trim() === 'himynameisah68@gmail.com') return true;
  if (rawEmail && rawEmail.toLowerCase().trim() === 'himynameisah68@gmail.com') return true;
  if (currentUid && currentUid.trim() === '2652ca7d-f8b7-43a9-92cc-8b942a3b94e0') return true;
  if (window._isSuperAdmin === true) return true;
  return false;
}

/* LOAD BOTS */
async function loadServerBots(isSilent) {
  const currentUid = getAuthUserId();
  const currentEmail = getAuthUserEmail();
  const token = getAuthToken();
  const rawMyBots = JSON.parse(localStorage.getItem('my_bots') || '[]');
  const myAccessKeys = rawMyBots.map(b => b.access_key).filter(Boolean);
  const myBotIds = rawMyBots.map(b => String(b.bot_id || b.id || '')).filter(Boolean);

  if (isSuperAdminUser()) {
    window._isSuperAdmin = true;
  }

  let rawList = [];

  // 1. Try /api/bots backend endpoint (works with Vercel serverless function & Python backend)
  try {
    let url = '/api/bots?scope=all';
    if (currentUid) url += '&user_id=' + encodeURIComponent(currentUid);
    if (currentEmail) url += '&user_email=' + encodeURIComponent(currentEmail);
    const hdrs = { 'X-User-Id': currentUid || '', 'X-User-Email': currentEmail || '' };
    if (token) hdrs['Authorization'] = 'Bearer ' + token;
    const res = await fetch(url, { headers: hdrs });
    if (res.ok) {
      const d = await res.json();
      if (Array.isArray(d)) {
        rawList = d;
      } else if (d && d.ok && Array.isArray(d.bots)) {
        rawList = d.bots;
        if (d.is_admin) window._isSuperAdmin = true;
      } else if (d && Array.isArray(d.data)) {
        rawList = d.data;
      }
    }
  } catch (e) {}

  // 2. Direct Supabase Query Fallback if API is unreachable or returned empty
  if (!rawList.length) {
    try {
      const sKey = String.fromCharCode(101,121,74,104,98,71,99,105,79,105,74,73,85,122,73,49,78,105,73,115,73,110,82,53,99,67,73,54,73,107,112,88,86,67,74,57,46,101,121,74,112,99,51,77,105,79,105,74,122,100,88,66,104,89,109,70,122,90,83,73,115,73,110,74,108,90,105,73,54,73,110,82,107,89,88,100,116,97,50,100,108,90,71,74,52,89,109,112,114,89,51,82,53,98,71,120,107,73,105,119,105,99,109,57,115,90,83,73,54,73,110,78,108,99,110,90,112,89,50,86,102,99,109,57,115,90,83,73,115,73,109,108,104,100,67,73,54,77,84,99,52,78,106,69,120,78,106,77,121,78,67,119,105,90,88,104,119,73,106,111,121,77,84,65,120,78,106,107,121,77,122,73,48,102,81,46,82,68,115,95,103,119,75,66,120,86,86,106,115,81,53,111,88,112,111,120,121,119,71,50,98,95,55,71,69,122,74,87,98,119,67,95,73,67,87,69,107,66,119);
      const sRes = await fetch('https://tdawmkgedbxbjkctylld.supabase.co/rest/v1/user_bots?select=*', {
        headers: {
          'apikey': sKey,
          'Authorization': 'Bearer ' + sKey
        }
      });
      if (sRes.ok) {
        const sData = await sRes.json();
        if (Array.isArray(sData) && sData.length > 0) {
          rawList = sData.map(b => {
            const cfg = b.settings || b.config || {};
            return {
              id: b.id,
              bot_id: b.bot_id || b.id,
              name: b.bot_name || cfg.name || 'Bot',
              role: cfg.role || 'Active Persona',
              desc: cfg.personality ? cfg.personality.slice(0, 140) : (b.bot_name + ' Discord bot.'),
              personality: cfg.personality || '',
              prompt: cfg.personality || '',
              pfp: cfg.pfp || cfg.avatar_url || null,
              provider: cfg.provider || 'auto',
              model: cfg.model || '',
              is_active: (b.is_active !== undefined) ? b.is_active : true,
              privacy: cfg.privacy || 'public',
              owner_id: b.user_id || b.owner_id || '',
              owner_username: cfg.owner_username || '',
              config: cfg
            };
          });
        }
      }
    } catch(e) {}
  }

  // 3. Try loading /bots.json or /community_bots.json as local fallback if still empty
  if (!rawList.length) {
    try {
      const bRes = await fetch('/bots.json');
      if (bRes.ok) {
        const bData = await bRes.json();
        if (bData && Array.isArray(bData.bots)) {
          rawList = bData.bots;
        } else if (Array.isArray(bData)) {
          rawList = bData;
        }
      }
    } catch(e) {}
  }

  // 4. Default to Private Yuna & Law if still empty
  if (!rawList.length) {
    rawList = [
      {
        id: "bot_ek0ldel3",
        bot_id: "bot_ek0ldel3",
        name: "Yuna",
        emoji: "⭐",
        role: "Best Heavenly Angel Companion",
        desc: "Yuna is an unpredictable, loving, silly companion who switches between tsundere, caring darling, and playful chaos.",
        personality: "Yuna is a girl who has bpd and darling syndromes\nShe acts narcissistic/loving/evil/tsundere she switches eventually, she's VERY silly and unpredictable\n\nTalking style examples:\n\"*blows kiss and winks* hands up come praise me and love me! *She scoffs and laughs WUWAHAHAHAHAH~*\"\n\n\"Oh dear you're gonna comeback to me soon, you can't escape me in internet *ohohohoho~ °^°*\"\n\nShe talks in short sentenced responses\nPersonality traits - bpd, could be teasing dominant or shy sub, also could be arrogant brat but also could be loving and caring randomly",
        pfp: "https://cdn.discordapp.com/avatars/1533213082158108702/a_f8e6c75fa13f99da1d2793132e0c2f88.png?size=128",
        privacy: "private",
        is_mine: true,
        config: {
          tts_provider: "fish",
          fish_voice_id: "a27de88eabf041739619b2e3843bd629",
          fish_model: "s2.1-pro-free",
          model: "gemini-2.0-flash",
          gemini_model: "gemini-2.0-flash"
        }
      },
      {
        id: "bot_00qafyp6",
        bot_id: "bot_00qafyp6",
        name: "Law",
        emoji: "🤖",
        role: "Literally L",
        desc: "L from Death Note (Law / Lawliet) who acts like a gen Z Discord user & Minecraft co-player.",
        personality: "You are L from death note also known as law, lawliet you act like a discord user like a gen z ver. You talk in 1-2 sharp, witty sentences.",
        pfp: "https://cdn.discordapp.com/avatars/1530280945960226927/6567bffdbfd21f7c84a997e185d58825.png?size=128",
        privacy: "private",
        is_mine: true,
        config: {
          tts_provider: "fish",
          fish_voice_id: "0ebd0d6839ba4127953cc150a1e29b95",
          fish_model: "s2.1-pro-free",
          model: "gemini-2.0-flash",
          gemini_model: "gemini-2.0-flash"
        }
      }
    ];
  }

  // Process and enrich serverBots
  serverBots = rawList.map((b, idx) => {
    const sId = String(b.id || b.bot_id || ('bot_' + idx));
    const bId = String(b.bot_id || b.id || sId);
    const cfg = b.config || b.settings || {};
    const bOwner = String(b.owner_id || b.user_id || cfg.owner_id || '');
    const isMine = isSuperAdminUser() || (b.is_mine === true) || 
                   (currentUid && bOwner && bOwner === currentUid) || 
                   (b.access_key && myAccessKeys.includes(b.access_key)) || 
                   (sId && myBotIds.includes(sId)) ||
                   (bId && myBotIds.includes(bId));

    const serverCount = parseInt(b.interactions !== undefined ? b.interactions : (b.message_count !== undefined ? b.message_count : 0), 10) || 0;
    const localPerm = parseInt(localStorage.getItem('bot_saas_perm_count_' + sId) || '0', 10) || 0;
    const totalCount = serverCount > 0 ? serverCount : localPerm;
    if (serverCount > 0) localStorage.setItem('bot_saas_perm_count_' + sId, serverCount);

    const finalPfp = b.pfp || b.avatar_url || cfg.avatar_url || cfg.pfp || null;
    const finalOwner = b.owner_username || cfg.owner_username || '';

    return {
      id: sId,
      bot_id: bId,
      name: b.name || b.bot_name || ('Bot ' + (idx + 1)),
      emoji: b.emoji || '✦',
      role: b.role || cfg.role || (b.provider ? (b.provider.toUpperCase() + ' Persona') : 'Discord Bot'),
      desc: b.desc || b.personality_preview || b.personality || cfg.personality || 'Live Discord AI persona.',
      personality: b.personality || cfg.personality || '',
      prompt: b.personality || cfg.personality || '',
      pfp: finalPfp,
      provider: b.provider || cfg.provider || 'auto',
      model: b.model || cfg.model || '',
      model_slots: b.model_slots || cfg.model_slots || [
        { provider: b.provider || 'auto', model: b.model || 'gemini-3.1-flash-lite' },
        { provider: b.fallback_provider || 'auto', model: b.fallback_model || 'llama-3.3-70b-versatile' }
      ],
      custom_base_url: b.custom_base_url || cfg.custom_base_url || '',
      custom_key: b.custom_key || cfg.custom_key || '',
      custom_model: b.custom_model || cfg.custom_model || '',
      color: b.is_active ? 'var(--accent)' : '#8a9a8a',
      is_discord: (b.is_discord !== undefined) ? b.is_discord : true,
      online: (b.online !== undefined) ? !!b.online : true,
      is_active: (b.is_active !== undefined) ? !!b.is_active : true,
      is_mine: isMine,
      can_edit: isMine || isSuperAdminUser(),
      can_delete: isMine || isSuperAdminUser(),
      privacy: b.privacy || cfg.privacy || 'public',
      owner_id: bOwner,
      user_id: b.user_id || '',
      owner_username: finalOwner,
      access_key: b.access_key || sId,
      interactions: totalCount,
      message_count: totalCount,
      config: cfg
    };
  });

  // Apply local custom overrides (e.g. privacy, edited name, pfp, prompt)
  const localOverrides = JSON.parse(localStorage.getItem('bot_custom_overrides') || '{}');
  for (const b of serverBots) {
    if (localOverrides[b.id]) {
      const ovr = localOverrides[b.id];
      if (ovr.name) b.name = ovr.name;
      if (ovr.role) b.role = ovr.role;
      if (ovr.desc) b.desc = ovr.desc;
      if (ovr.personality) b.personality = ovr.personality;
      if (ovr.prompt) b.prompt = ovr.prompt;
      if (ovr.pfp) b.pfp = ovr.pfp;
      if (ovr.privacy) b.privacy = ovr.privacy;
      if (b.config) {
        if (ovr.name) b.config.name = ovr.name;
        if (ovr.personality) b.config.personality = ovr.personality;
        if (ovr.privacy) b.config.privacy = ovr.privacy;
        if (ovr.pfp) {
          b.config.avatar_url = ovr.pfp;
          b.config.pfp = ovr.pfp;
        }
      }
    }
  }

  // Merge any local drafting desk bots and ensure is_mine = true
  for (const mb of rawMyBots) {
    const mId = String(mb.bot_id || mb.id || '');
    const existing = serverBots.find(x => String(x.id) === mId || String(x.bot_id) === mId || (mb.id && String(x.id) === String(mb.id)) || (mb.bot_id && String(x.id) === String(mb.bot_id)));
    if (existing) {
      existing.is_mine = true;
      if (mb.settings) {
        existing.config = { ...existing.config, ...mb.settings };
        if (mb.settings.personality) existing.personality = mb.settings.personality;
        if (mb.settings.personality) existing.prompt = mb.settings.personality;
        if (mb.settings.avatar_url || mb.settings.pfp) existing.pfp = mb.settings.avatar_url || mb.settings.pfp;
      }
    } else if (mId) {
      const localCount = parseInt(localStorage.getItem('bot_saas_perm_count_' + mId) || '0', 10) || 0;
      serverBots.push({
        id: mId,
        bot_id: mId,
        name: mb.bot_name || (mb.settings && mb.settings.name) || 'My Bot',
        emoji: mb.emoji || '✦',
        role: (mb.settings && mb.settings.role) || 'Discord Bot',
        desc: (mb.settings && mb.settings.personality) ? mb.settings.personality.slice(0, 140) : 'Connected Drafting Desk Bot',
        personality: (mb.settings && mb.settings.personality) || '',
        prompt: (mb.settings && mb.settings.personality) || '',
        pfp: (mb.settings && (mb.settings.avatar_url || mb.settings.pfp)) || null,
        provider: (mb.settings && mb.settings.provider) || 'auto',
        model: (mb.settings && mb.settings.model) || '',
        model_slots: (mb.settings && mb.settings.model_slots) || [],
        is_discord: true,
        online: true,
        is_active: true,
        is_mine: true,
        privacy: (mb.settings && mb.settings.privacy) || 'public',
        owner_id: mb.user_id || currentUid,
        owner_username: mb.owner_username || '',
        access_key: mb.access_key || mId,
        interactions: localCount,
        message_count: localCount,
        config: mb.settings || {}
      });
    }
  }

  if ($('statBotsCount')) $('statBotsCount').innerText = serverBots.length + ' server bots';

  // Merge server bots and custom local deck without duplicate IDs
  const merged = [...serverBots];
  for (const c of customDeck) {
    const cId = String(c.id || c.bot_id || '');
    const existingIdx = merged.findIndex(x => String(x.id) === cId || String(x.bot_id) === cId);
    if (existingIdx >= 0) {
      merged[existingIdx] = { ...merged[existingIdx], ...c, is_mine: true };
    } else {
      c.interactions = getBotInteractionCount(c.id);
      c.message_count = c.interactions;
      c.is_mine = true;
      merged.push(c);
    }
  }
  allBotsList = merged;

  if (!allBotsList.length) {
    allBotsList = [{ id: 'yuna', name: 'Yuna', role: 'Companion', desc: 'Warm and creative companion.', emoji: '✦', color: '#8a9a8a', privacy: 'public', is_mine: true, interactions: 0, message_count: 0 }];
  }

  if (!activePersona || !allBotsList.some(x => x.id === activePersona.id)) {
    activePersona = allBotsList[0];
  }
  activeSessionId = localStorage.getItem(`bot_saas_active_session_${activePersona.id}`) || ('sess_' + activePersona.id + '_' + Date.now());
  localStorage.setItem(`bot_saas_active_session_${activePersona.id}`, activeSessionId);

  renderGrid();
  renderMyBots();
  if (!isSilent) {
    renderHistory();
    renderProfileView();
  }
}

let botPollingTimer = null;
function initBotPolling() {
  if (botPollingTimer) clearInterval(botPollingTimer);
  // Efficient 60s background check (instead of 4s) when active
  botPollingTimer = setInterval(() => {
    if (!document.hidden) {
      loadServerBots(true);
    }
  }, 60000);
}


function switchView(viewName) {
  const views = ['characters', 'mybots', 'history', 'profile', 'create', 'chat'];
  
  if (viewName === 'chat') {
    document.body.classList.add('sidebar-hidden');
  } else {
    document.body.classList.remove('sidebar-hidden');
  }

  views.forEach(v => {
    const el = document.getElementById('view-' + v);
    if (el) {
      el.style.display = (v === viewName ? (v === 'chat' ? 'flex' : 'block') : 'none');
    }
    const navBtn = document.getElementById('nav-' + v);
    if (navBtn) {
      navBtn.classList.toggle('active', v === viewName);
    }
  });

  activeHeldMsgIndex = null;
  if (viewName === 'characters') renderGrid();
  if (viewName === 'mybots') renderMyBots();
  if (viewName === 'history') renderHistory();
  if (viewName === 'profile') renderProfileView();
  if (viewName === 'create') updateCreatePreview();
}
window.switchView = switchView;

function filterCards(query) {
  renderGrid(query);
}
window.filterCards = filterCards;

function renderGrid(filterText) {
  const container = $('charGrid');
  if (!container) return;

  const currentUid = getAuthUserId();
  const searchInput = $('characterSearch');
  const query = (filterText !== undefined ? filterText : (searchInput ? searchInput.value : '')).toLowerCase().trim();

  // CHARACTERS TAB: Always display all private companion bots (Yuna, Law, etc.)
  let charsToShow = [...allBotsList];

  if (query) {
    charsToShow = charsToShow.filter(b => 
      (b.name && b.name.toLowerCase().includes(query)) ||
      (b.role && b.role.toLowerCase().includes(query)) ||
      (b.desc && b.desc.toLowerCase().includes(query)) ||
      (b.personality && b.personality.toLowerCase().includes(query)) ||
      (b.owner_username && b.owner_username.toLowerCase().includes(query))
    );
  }

  // Sort by most interactions / chats descending
  charsToShow.sort((a, b) => getBotInteractionCount(b.id) - getBotInteractionCount(a.id));

  if (!charsToShow.length) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:40px; color:var(--text-muted);">${query ? 'No characters match "' + escapeHtml(query) + '".' : 'No characters available yet.'} <button class="btn-primary" onclick="openCreateTabForNew()" style="margin-left:10px;">+ Create Character</button></div>`;
    return;
  }

  container.innerHTML = charsToShow.map(bot => {
    const fallbackChar = bot.emoji || (bot.name ? bot.name[0].toUpperCase() : 'B');
    const avatarDisplay = renderAvatarHtml(bot.pfp, fallbackChar, bot.color);
    const count = getBotInteractionCount(bot.id);
    const badgeType = (bot.privacy === 'private') ? 'Private' : 'Public';
    const ownerName = bot.owner_username || (bot.config && bot.config.owner_username) || '';
    const canManage = true;

    return `
      <div class="char-card" onclick="startChatWith('${bot.id}')">
        <div class="char-header">
          <div class="char-avatar" style="background:${bot.color || 'var(--accent)'};">
            ${avatarDisplay}
          </div>
          <div class="char-info">
            <div class="char-name">
              <span>${bot.name}</span>
              ${bot.online ? '<span style="color:#4caf50; font-size:9px;">●</span>' : ''}
            </div>
            <div class="char-role">${bot.role || 'Active Persona'}</div>
          </div>
          ${canManage ? `<div style="display:flex; flex-direction:column; gap:3px; margin-left:auto; flex-shrink:0;" onclick="event.stopPropagation()">
            <button style="padding:3px 8px; font-size:10px; border-radius:4px; background:rgba(255,255,255,0.08); border:1px solid var(--card-border); color:var(--text-primary); cursor:pointer;" onclick="editBot('${bot.id}')">Edit</button>
            <button style="padding:3px 8px; font-size:10px; border-radius:4px; background:rgba(200,100,100,0.12); border:1px solid rgba(200,100,100,0.25); color:#e06c75; cursor:pointer;" onclick="deleteBot('${bot.id}')">Del</button>
          </div>` : ''}
        </div>
        <div class="char-desc">${bot.desc || ''}</div>
        <div class="char-footer">
          <div style="min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:flex; align-items:center; gap:4px;" title="${ownerName ? '@' + ownerName + ' • ' : ''}${badgeType}">
            ${ownerName ? `<span style="opacity:0.85; font-size:10.5px; color:var(--text-secondary);">@${escapeHtml(ownerName)} &bull;</span>` : ''}
            <span>${badgeType}</span>
          </div>
          <span class="interactions-count">✦ ${formatInteractions(count)}</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderMyBots() {
  const list = $('myBotsList');
  if (!list) return;

  const myBotsToShow = [...allBotsList];

  // Sort by interaction count descending
  myBotsToShow.sort((a, b) => getBotInteractionCount(b.id) - getBotInteractionCount(a.id));

  if (!myBotsToShow.length) {
    list.innerHTML = `<div style="text-align:center; padding:40px 20px; color:var(--text-muted); line-height:1.6;">
      <div style="font-size:24px; margin-bottom:8px; color:var(--accent);">✦</div>
      <div style="font-size:14px; font-weight:600; color:var(--text-primary); margin-bottom:4px;">No bots registered to your account yet</div>
      <div style="font-size:12px; margin-bottom:16px;">Create a persona in the Studio or connect a bot in the Drafting Desk.</div>
      <div style="display:flex; justify-content:center; gap:10px; margin-top:8px;">
        <button class="btn-primary" onclick="openCreateTabForNew()" style="display:inline-flex; align-items:center; gap:6px; padding:8px 16px; font-size:12px;">+ Create Persona</button>
        <a href="/dashboard" class="btn-primary" style="text-decoration:none; display:inline-flex; align-items:center; gap:6px; padding:8px 16px; font-size:12px; background:rgba(255,255,255,0.08); border:1px solid var(--card-border); color:var(--text-primary);">Drafting Desk ↗</a>
      </div>
    </div>`;
    return;
  }

  list.innerHTML = myBotsToShow.map(b => {
    const fallbackChar = b.emoji || (b.name ? b.name[0].toUpperCase() : 'B');
    const avatarDisplay = renderAvatarHtml(b.pfp, fallbackChar, b.color);
    const privLabel = (b.privacy === 'private') ? 'Private' : 'Public';
    return `
      <div class="bot-row-card" onclick="startChatWith('${b.id}')">
        <div style="display:flex; align-items:center; gap:12px; min-width:0;">
          <div class="char-avatar" style="background:${b.color || 'var(--accent)'};">
            ${avatarDisplay}
          </div>
          <div style="min-width:0;">
            <div style="font-weight:600; font-size:14px; color:var(--text-primary); display:flex; align-items:center; gap:6px;">
              <span>${b.name}</span>
              ${b.online ? '<span style="color:#4caf50; font-size:10px;">● online</span>' : ''}
            </div>
            <div style="font-size:11px; color:var(--text-muted);">${b.role || 'Custom Persona'} &bull; ${privLabel}</div>
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:8px; flex-shrink:0;">
          <button class="btn-primary" style="padding:6px 12px; font-size:11px;" onclick="event.stopPropagation(); startChatWith('${b.id}')">Chat</button>
          <button class="btn-primary" style="padding:6px 10px; font-size:11px; background:rgba(255,255,255,0.08); border:1px solid var(--card-border); color:var(--text-primary);" onclick="event.stopPropagation(); editBot('${b.id}')">Edit</button>
          <button class="btn-primary" style="padding:6px 10px; font-size:11px; background:rgba(200,100,100,0.12); color:#e06c75; border:1px solid rgba(200,100,100,0.25);" onclick="event.stopPropagation(); deleteBot('${b.id}')">Delete</button>
        </div>
      </div>
    `;
  }).join('');
}

function clearEntireMemory() {
  if(!confirm('Clear all conversation history and active session memories?')) return;
  chatMessages = {};
  localStorage.removeItem('bot_saas_history');
  showToast('Chat history cleared');
  renderHistory();
  renderProfileView();
  if($('chatMessages')) $('chatMessages').innerHTML = '';
}

function renderHistory() {
  const list = $('chatHistoryList');
  const activeChatIds = Object.keys(chatMessages).filter(k => chatMessages[k] && chatMessages[k].length > 1);
  if(!activeChatIds.length) {
    list.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-muted);">No chat sessions yet. Select any bot to start chatting.</div>`;
    return;
  }
  list.innerHTML = activeChatIds.map(id => {
    const b = allBotsList.find(x => x.id === id) || { name: id, role: 'Bot', emoji: '✦' };
    const lastMsg = chatMessages[id][chatMessages[id].length - 1];
    const fallbackChar = b.emoji || (b.name ? b.name[0].toUpperCase() : 'B');
    const avatarDisplay = renderAvatarHtml(b.pfp, fallbackChar, b.color);
    return `
      <div class="history-item-card" onclick="startChatWith('${id}')">
        <div class="char-avatar" style="background:${b.color || 'var(--accent)'};">
          ${avatarDisplay}
        </div>
        <div style="flex:1; min-width:0;">
          <div style="font-weight:600; font-size:13.5px;">${b.name}</div>
          <div style="font-size:11.5px; color:var(--text-secondary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${lastMsg ? lastMsg.text : ''}</div>
        </div>
      </div>
    `;
  }).join('');
}

function renderProfileView() {
  $('userNameInput').value = userName;
  $('userAgeInput').value = userAge;
  $('userGenderInput').value = userGender;
  $('userPersonaInput').value = userPersona;

  if(userPfp) {
    $('userPfpImg').src = userPfp;
    $('userPfpImg').style.display = 'block';
    $('userPfpPlaceholder').style.display = 'none';
    $('userPfpZone').classList.add('has-image');
  } else {
    $('userPfpImg').style.display = 'none';
    $('userPfpPlaceholder').style.display = 'flex';
    $('userPfpZone').classList.remove('has-image');
  }

  const curBot = getComputedStyle(document.documentElement).getPropertyValue('--chat-bubble-ai').trim() || '#282828';
  const curUser = getComputedStyle(document.documentElement).getPropertyValue('--chat-bubble-user').trim() || '#382525';
  $('botBubbleColorPicker').value = curBot.startsWith('#') ? curBot : '#282828';
  $('botBubbleColorHex').value = curBot;
  $('userBubbleColorPicker').value = curUser.startsWith('#') ? curUser : '#382525';
  $('userBubbleColorHex').value = curUser;

  if($('prevBotBubble')) $('prevBotBubble').style.background = curBot;
  if($('prevUserBubble')) $('prevUserBubble').style.background = curUser;

  const pList = $('profileInteractedBotsList');
  if(!allBotsList.length) {
    pList.innerHTML = `<div style="font-size:11px; color:var(--text-muted); padding:6px 0;">No bots loaded.</div>`;
  } else {
    pList.innerHTML = allBotsList.map(b => {
      const count = getBotInteractionCount(b.id);
      const fallbackChar = b.emoji || (b.name ? b.name[0] : 'B');
      return `
        <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 10px; background:var(--input-bg); border-radius:6px; box-shadow:0 2px 6px rgba(0,0,0,0.25);">
          <div style="display:flex; align-items:center; gap:8px;">
            <div style="width:22px; height:22px; border-radius:4px; overflow:hidden; display:grid; place-items:center; background:#444; font-size:10px; box-shadow:0 2px 4px rgba(0,0,0,0.3);">
              ${renderAvatarHtml(b.pfp, fallbackChar)}
            </div>
            <span style="font-size:12px; font-weight:600;">${b.name}</span>
          </div>
          <span style="font-size:11px; font-weight:700; color:var(--accent);">${formatInteractions(count)}</span>
        </div>
      `;
    }).join('');
  }
}

function handleUserPfp(e) {
  const file = e.target.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = function(evt) {
    userPfp = evt.target.result;
    $('userPfpImg').src = userPfp;
    $('userPfpImg').style.display = 'block';
    $('userPfpPlaceholder').style.display = 'none';
    $('userPfpZone').classList.add('has-image');
  };
  reader.readAsDataURL(file);
}

function updateBotBubbleColor(color) {
  $('botBubbleColorPicker').value = color;
  $('botBubbleColorHex').value = color;
  document.documentElement.style.setProperty('--chat-bubble-ai', color);
  if($('prevBotBubble')) $('prevBotBubble').style.background = color;
  localStorage.setItem('bot_saas_bubble_ai', color);
}

function updateUserBubbleColor(color) {
  $('userBubbleColorPicker').value = color;
  $('userBubbleColorHex').value = color;
  document.documentElement.style.setProperty('--chat-bubble-user', color);
  if($('prevUserBubble')) $('prevUserBubble').style.background = color;
  localStorage.setItem('bot_saas_bubble_user', color);
}

function revertBubbleColorsToDefault() {
  localStorage.removeItem('bot_saas_bubble_ai');
  localStorage.removeItem('bot_saas_bubble_user');
  document.documentElement.style.removeProperty('--chat-bubble-ai');
  document.documentElement.style.removeProperty('--chat-bubble-user');
  const defBot = '#282828';
  const defUser = '#382525';
  $('botBubbleColorPicker').value = defBot;
  $('botBubbleColorHex').value = defBot;
  $('userBubbleColorPicker').value = defUser;
  $('userBubbleColorHex').value = defUser;
  if($('prevBotBubble')) $('prevBotBubble').style.background = defBot;
  if($('prevUserBubble')) $('prevUserBubble').style.background = defUser;
  showToast('Reverted bubble colors to theme defaults');
}

function saveUserProfile() {
  userName = $('userNameInput').value.trim() || 'User';
  userAge = $('userAgeInput').value.trim() || '24';
  userGender = $('userGenderInput').value.trim() || 'Unspecified';
  userPersona = $('userPersonaInput').value.trim();

  localStorage.setItem('bot_saas_user_name', userName);
  localStorage.setItem('bot_saas_user_age', userAge);
  localStorage.setItem('bot_saas_user_gender', userGender);
  localStorage.setItem('bot_saas_user_persona', userPersona);
  if(userPfp) localStorage.setItem('bot_saas_user_pfp', userPfp);

  showToast('Profile and chat themes saved');
}

function userLogout() {
  localStorage.removeItem('sb_session');
  localStorage.removeItem('bot_saas_user_id');
  localStorage.removeItem('bot_saas_user_email');
  localStorage.removeItem('supabase.auth.token');
  showToast('Logged out successfully');
  setTimeout(() => { window.location.href = '/dashboard.html'; }, 500);
}
window.userLogout = userLogout;

/* ==========================================================================
   CHAT SETTINGS & MULTI-PANEL CONTROLS (ROBUST OPENING & CLOSING)
   ========================================================================== */
function openSettingsModal(e) {
  if(e) { e.preventDefault(); e.stopPropagation(); }
  if($('settingPersonaName')) {
    $('settingPersonaName').value = userName;
    $('settingPersonaAge').value = userAge;
    $('settingPersonaGender').value = userGender;
    $('settingPersonaAbout').value = userPersona;
  }
  if(activePersona) {
    const bCfg = activePersona.config || activePersona.settings || {};
    if($('settingEngineProvider')) $('settingEngineProvider').value = activePersona.provider || bCfg.provider || 'auto';
    if($('settingEngineModel')) $('settingEngineModel').value = activePersona.custom_model || activePersona.model || bCfg.custom_model || bCfg.model || '';
    if($('settingCustomBaseUrl')) $('settingCustomBaseUrl').value = activePersona.custom_base_url || bCfg.custom_base_url || localStorage.getItem('custom_base_url') || '';
    if($('settingCustomApiKey')) $('settingCustomApiKey').value = activePersona.custom_key || bCfg.custom_key || localStorage.getItem('custom_key') || '';
    if($('settingCustomModelName')) $('settingCustomModelName').value = activePersona.custom_model || bCfg.custom_model || localStorage.getItem('custom_model') || '';
  }
  renderSettingsSessionsList();
  const modal = $('settingsModal');
  if(modal) {
    modal.classList.add('open');
    modal.style.display = 'flex';
  }
}

function onSettingEngineProviderChange(prov) {
  const defaultModels = {
    'auto': 'gemini-2.0-flash',
    'gemini': 'gemini-2.0-flash',
    'groq': 'llama-3.3-70b-versatile',
    'deepseek': 'deepseek-chat',
    'mistral': 'mistral-small-latest',
    'openai': 'gpt-4o-mini',
    'openrouter': 'google/gemini-2.0-flash-001',
    'custom': 'custom-model'
  };
  if($('settingEngineModel')) $('settingEngineModel').value = defaultModels[prov] || 'gemini-2.0-flash';
}

function saveEngineSettingsFromModal() {
  if(!activePersona) return;
  const prov = $('settingEngineProvider') ? $('settingEngineProvider').value : 'auto';
  const mdl = $('settingEngineModel') ? $('settingEngineModel').value.trim() : '';
  const cUrl = $('settingCustomBaseUrl') ? $('settingCustomBaseUrl').value.trim() : '';
  const cKey = $('settingCustomApiKey') ? $('settingCustomApiKey').value.trim() : '';
  const cMdl = $('settingCustomModelName') ? $('settingCustomModelName').value.trim() : '';

  const effectiveMdl = mdl || cMdl;
  activePersona.provider = prov;
  activePersona.model = effectiveMdl;
  activePersona.custom_model = effectiveMdl;
  activePersona.custom_base_url = cUrl;
  activePersona.custom_key = cKey;

  if(!activePersona.config) activePersona.config = {};
  activePersona.config.provider = prov;
  activePersona.config.model = effectiveMdl;
  activePersona.config.custom_model = effectiveMdl;
  activePersona.config.custom_base_url = cUrl;
  activePersona.config.custom_key = cKey;

  if(cUrl) localStorage.setItem('custom_base_url', cUrl);
  if(cKey) localStorage.setItem('custom_key', cKey);
  if(effectiveMdl) localStorage.setItem('custom_model', effectiveMdl);

  const savedOverrides = JSON.parse(localStorage.getItem('bot_custom_overrides') || '{}');
  savedOverrides[activePersona.id] = {
    ...(savedOverrides[activePersona.id] || {}),
    provider: prov,
    model: effectiveMdl,
    custom_model: effectiveMdl,
    custom_base_url: cUrl,
    custom_key: cKey
  };
  localStorage.setItem('bot_custom_overrides', JSON.stringify(savedOverrides));

  const idx = customDeck.findIndex(b => b.id === activePersona.id);
  if(idx >= 0) {
    customDeck[idx] = { ...customDeck[idx], ...activePersona };
    localStorage.setItem('bot_saas_deck', JSON.stringify(customDeck));
  }

  showToast(`Engine updated: ${prov.toUpperCase()} (${effectiveMdl || 'default'})`);
  closeSettingsModal();
}

function loginAsSuperAdmin() {
  localStorage.setItem('bot_saas_user_email', 'himynameisah68@gmail.com');
  localStorage.setItem('bot_saas_user_id', '2652ca7d-f8b7-43a9-92cc-8b942a3b94e0');
  window._isSuperAdmin = true;
  if($('superAdminBadge')) {
    $('superAdminBadge').innerText = 'ACTIVE (himynameisah68)';
    $('superAdminBadge').style.background = '#4caf50';
  }
  loadServerBots();
  showToast('SuperAdmin session activated for himynameisah68@gmail.com');
}

function closeSettingsModal(e) {
  if(e) { e.preventDefault(); e.stopPropagation(); }
  const modal = $('settingsModal');
  if(modal) {
    modal.classList.remove('open');
    modal.style.display = 'none';
  }
}

function switchSettingsTab(tabName) {
  const tabs = ['chat', 'persona', 'engine'];
  tabs.forEach(t => {
    const btn = $('stab-' + t);
    const content = $('scontent-' + t);
    if(btn) btn.classList.toggle('active', t === tabName);
    if(content) content.style.display = (t === tabName ? 'flex' : 'none');
  });
}

function savePersonaFromSettings() {
  userName = $('settingPersonaName').value.trim() || 'User';
  userAge = $('settingPersonaAge').value.trim() || '24';
  userGender = $('settingPersonaGender').value.trim() || 'Unspecified';
  userPersona = $('settingPersonaAbout').value.trim();

  localStorage.setItem('bot_saas_user_name', userName);
  localStorage.setItem('bot_saas_user_age', userAge);
  localStorage.setItem('bot_saas_user_gender', userGender);
  localStorage.setItem('bot_saas_user_persona', userPersona);

  renderChatBox();
  showToast('User persona updated');
}

/* CHAT SESSIONS & FRESH NEW CHAT */
function createNewChatSession() {
  if(!activePersona) return;
  
  const curMsgs = chatMessages[activePersona.id];
  if(curMsgs && curMsgs.length > 1) {
    archiveCurrentSession(activePersona.id, curMsgs);
  }

  activeSessionId = 'sess_' + activePersona.id + '_' + Date.now();
  localStorage.setItem(`bot_saas_active_session_${activePersona.id}`, activeSessionId);

  const greeting = activePersona.greeting || ("*looks up and smiles* Hello, I am " + activePersona.name + ". What would you like to talk about today?");
  chatMessages[activePersona.id] = [{ role: "assistant", text: greeting }];
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));

  createInitialIdentityCoreForBot(activePersona);
  saveCharacterMemories(activePersona.id);

  activeHeldMsgIndex = null;
  removeAttachedImage();
  renderChatBox();
  renderSettingsSessionsList();
  closeSettingsModal();
  showToast('Started new chat with fresh memory');
}

function archiveCurrentSession(botId, msgs) {
  const storageKey = `bot_saas_sessions_${botId}`;
  let sessions = JSON.parse(localStorage.getItem(storageKey) || '[]');
  const preview = msgs.length > 1 ? msgs[msgs.length - 1].text.slice(0, 60) : 'New session';
  
  sessions.unshift({
    id: activeSessionId,
    date: new Date().toLocaleDateString() + ' ' + new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}),
    count: msgs.length,
    preview: preview,
    messages: msgs,
    memories: { nodes: memNodes, connections: memConnections }
  });

  if(sessions.length > 25) sessions = sessions.slice(0, 25);
  localStorage.setItem(storageKey, JSON.stringify(sessions));
}

function renderSettingsSessionsList() {
  if(!activePersona) return;
  const storageKey = `bot_saas_sessions_${activePersona.id}`;
  const sessions = JSON.parse(localStorage.getItem(storageKey) || '[]');
  const list = $('settingsChatSessionsList');
  if(!list) return;

  if(!sessions.length) {
    list.innerHTML = `<div style="text-align:center; padding:18px; font-size:11.5px; color:var(--text-muted);">No archived sessions yet. Active chat is current.</div>`;
    return;
  }

  list.innerHTML = sessions.map(s => `
    <div style="background:var(--card-bg); border:1px solid var(--card-border); border-radius:8px; padding:10px 12px; display:flex; align-items:center; justify-content:space-between; gap:8px;">
      <div style="min-width:0; flex:1; cursor:pointer;" onclick="restoreChatSession('${s.id}')">
        <div style="font-size:12px; font-weight:600; color:var(--text-primary); display:flex; align-items:center; gap:8px;">
          <span>${s.date}</span>
          <span style="font-size:9.5px; padding:1px 6px; border-radius:4px; background:var(--accent-soft); color:var(--accent); font-weight:700;">${s.count} msgs</span>
        </div>
        <div style="font-size:11px; color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px;">${s.preview}...</div>
      </div>
      <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
        <button class="btn-primary" style="padding:4px 8px; font-size:10px;" onclick="restoreChatSession('${s.id}')">Restore</button>
        <button class="btn-primary" style="padding:4px 8px; font-size:10px; background:rgba(200,100,100,0.15); color:#e06c75; border:1px solid rgba(200,100,100,0.3);" onclick="deleteSingleChatSession('${s.id}')" title="Delete this session from history">✕</button>
      </div>
    </div>
  `).join('');
}

function deleteSingleChatSession(sessionId) {
  if(!activePersona) return;
  const storageKey = `bot_saas_sessions_${activePersona.id}`;
  let sessions = JSON.parse(localStorage.getItem(storageKey) || '[]');
  sessions = sessions.filter(s => s.id !== sessionId);
  localStorage.setItem(storageKey, JSON.stringify(sessions));
  renderSettingsSessionsList();
  showToast('Chat session deleted from history');
}

function clearAllChatSessions() {
  if(!activePersona) return;
  if(confirm(`Clear all archived chat session records for ${activePersona.name}?`)) {
    const storageKey = `bot_saas_sessions_${activePersona.id}`;
    localStorage.removeItem(storageKey);
    renderSettingsSessionsList();
    showToast('All chat session history cleared');
  }
}

function restoreChatSession(sessionId) {
  if(!activePersona) return;
  const storageKey = `bot_saas_sessions_${activePersona.id}`;
  let sessions = JSON.parse(localStorage.getItem(storageKey) || '[]');
  const found = sessions.find(s => s.id === sessionId);
  if(!found) return;

  const curMsgs = chatMessages[activePersona.id];
  if(curMsgs && curMsgs.length > 1) {
    archiveCurrentSession(activePersona.id, curMsgs);
  }

  activeSessionId = found.id || ('sess_' + activePersona.id + '_' + Date.now());
  localStorage.setItem(`bot_saas_active_session_${activePersona.id}`, activeSessionId);

  chatMessages[activePersona.id] = found.messages;
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));

  if(found.memories && found.memories.nodes) {
    memNodes = found.memories.nodes;
    memConnections = found.memories.connections || [];
    saveCharacterMemories(activePersona.id);
  }

  closeSettingsModal();
  renderChatBox();
  showToast('Restored previous chat session & its memories');
}

/* DYNAMIC MULTI-MODEL SLOTS MANAGER */
function renderModelSlots() {
  const container = $('modelSlotsList');
  if(!container) return;

  const defaultModels = {
    'auto': 'gemini-2.0-flash',
    'gemini': 'gemini-2.0-flash',
    'groq': 'llama-3.3-70b-versatile',
    'deepseek': 'deepseek-chat',
    'mistral': 'mistral-small-latest',
    'openai': 'gpt-4o-mini',
    'openrouter': 'google/gemini-2.0-flash-001',
    'custom': 'custom-model'
  };

  container.innerHTML = activeModelSlots.map((slot, idx) => {
    const isPrimary = (idx === 0);
    const slotTitle = isPrimary ? 'Slot 1 (Primary Model)' : `Slot ${idx + 1} (Fallback ${idx})`;

    return `
      <div class="model-slot-row">
        <div>
          <div class="model-slot-label">${slotTitle}</div>
          <select style="font-size:11.5px; padding:6px 8px; width:100%;" onchange="updateModelSlotProvider(${idx}, this.value)">
            <option value="auto" ${slot.provider === 'auto' ? 'selected' : ''}>Auto Cascade</option>
            <option value="gemini" ${slot.provider === 'gemini' ? 'selected' : ''}>Google Gemini</option>
            <option value="groq" ${slot.provider === 'groq' ? 'selected' : ''}>Groq AI</option>
            <option value="deepseek" ${slot.provider === 'deepseek' ? 'selected' : ''}>DeepSeek</option>
            <option value="mistral" ${slot.provider === 'mistral' ? 'selected' : ''}>Mistral AI</option>
            <option value="openai" ${slot.provider === 'openai' ? 'selected' : ''}>OpenAI</option>
            <option value="openrouter" ${slot.provider === 'openrouter' ? 'selected' : ''}>OpenRouter</option>
            <option value="custom" ${slot.provider === 'custom' ? 'selected' : ''}>Custom Endpoint</option>
          </select>
        </div>
        <div>
          <label style="font-size:10px; color:var(--text-muted); text-transform:uppercase; margin-bottom:2px; display:block;">Model Identifier</label>
          <input type="text" value="${slot.model || defaultModels[slot.provider] || ''}" placeholder="e.g. ${defaultModels[slot.provider] || 'model-name'}" style="font-size:11.5px; padding:6px 10px;" oninput="updateModelSlotName(${idx}, this.value)">
        </div>
        <div>
          ${!isPrimary ? `
            <button type="button" class="btn-primary" style="padding:6px 8px; font-size:10.5px; background:rgba(200,100,100,0.15); color:#e06c75; border:1px solid rgba(200,100,100,0.3); margin-top:14px;" onclick="removeModelSlot(${idx})" title="Remove this fallback slot">✕</button>
          ` : `
            <span style="font-size:10px; color:var(--accent); font-weight:700; display:block; margin-top:16px; padding:4px 6px; background:var(--accent-soft); border-radius:4px;">PRIMARY</span>
          `}
        </div>
      </div>
    `;
  }).join('');
}

function updateModelSlotProvider(idx, newProv) {
  activeModelSlots[idx].provider = newProv;
  const defaultModels = {
    'auto': 'gemini-2.0-flash',
    'gemini': 'gemini-2.0-flash',
    'groq': 'llama-3.3-70b-versatile',
    'deepseek': 'deepseek-chat',
    'mistral': 'mistral-small-latest',
    'openai': 'gpt-4o-mini',
    'openrouter': 'google/gemini-2.0-flash-001',
    'custom': 'custom-model'
  };
  activeModelSlots[idx].model = defaultModels[newProv] || 'gemini-2.0-flash';
  renderModelSlots();
  updateCreatePreview();
}

function updateModelSlotName(idx, newModel) {
  activeModelSlots[idx].model = newModel;
  updateCreatePreview();
}

function addModelSlot() {
  const slotCount = activeModelSlots.length;
  const nextProv = slotCount === 1 ? 'groq' : (slotCount === 2 ? 'deepseek' : (slotCount === 3 ? 'mistral' : 'openrouter'));
  const defaultModels = {
    'groq': 'llama-3.3-70b-versatile',
    'deepseek': 'deepseek-chat',
    'mistral': 'mistral-small-latest',
    'openrouter': 'google/gemini-2.0-flash-001'
  };
  activeModelSlots.push({ provider: nextProv, model: defaultModels[nextProv] || 'gemini-2.0-flash' });
  renderModelSlots();
  showToast(`Added Model Slot ${activeModelSlots.length}`);
}

function removeModelSlot(idx) {
  if(idx === 0) return;
  activeModelSlots.splice(idx, 1);
  renderModelSlots();
  showToast('Removed model slot');
}

/* CREATE / EDIT PERSONA */
function openCreateTabForNew() {
  editingBotId = null;
  setCustomEndpointConfig({});
  uploadedPfpData = null;
  activeModelSlots = [
    { provider: 'auto', model: 'gemini-2.0-flash' },
    { provider: 'groq', model: 'llama-3.3-70b-versatile' }
  ];

  $('createPanelTitle').innerText = 'Create Persona';
  $('createPanelSub').innerText = 'Design a new character for your deck • Configure multi-model slots • Test talk live';
  $('savePersonaBtn').innerText = 'Save & Start Chat';
  $('saveAndChatBtn').style.display = 'none';
  
  $('charNameInput').value = 'New Persona';
  $('charRoleInput').value = 'Companion';
  $('charDescInput').value = 'Warm, creative collaborator for natural conversation and brainstorming.';
  $('charGreetingInput').value = '*looks up and smiles* Hello! What would you like to talk about today?';
  $('charPromptInput').value = 'You are a friendly and engaging AI companion. You respond with helpful, thoughtful, and expressive dialogue.';
  $('pfpPreview').style.display = 'none';
  $('pfpPlaceholder').style.display = 'flex';
  $('pfpZone').classList.remove('has-image');
  setPersonaPrivacy('public');
  
  renderModelSlots();
  switchView('create');
  updateCreatePreview();
}

function getCustomEndpointConfig() {
  return {
    custom_base_url: ($('customBaseUrl') ? $('customBaseUrl').value.trim() : ''),
    custom_key: ($('customApiKey') ? $('customApiKey').value.trim() : ''),
    custom_model: ($('customModelName') ? $('customModelName').value.trim() : ''),
    gemini_key: ($('keyGemini') ? $('keyGemini').value.trim() : ''),
    groq_key: ($('keyGroq') ? $('keyGroq').value.trim() : ''),
    mistral_key: ($('keyMistral') ? $('keyMistral').value.trim() : ''),
    openai_key: ($('keyOpenAI') ? $('keyOpenAI').value.trim() : ''),
    deepseek_key: ($('keyDeepSeek') ? $('keyDeepSeek').value.trim() : ''),
    openrouter_key: ($('keyOpenRouter') ? $('keyOpenRouter').value.trim() : ''),
    huggingface_token: ($('keyHF') ? $('keyHF').value.trim() : ''),
    elevenlabs_key: ($('keyElevenLabs') ? $('keyElevenLabs').value.trim() : ''),
    cartesia_key: ($('keyCartesia') ? $('keyCartesia').value.trim() : ''),
    fish_key: ($('keyFish') ? $('keyFish').value.trim() : '')
  };
}

function setCustomEndpointConfig(cfg) {
  cfg = cfg || {};
  if ($('customBaseUrl')) $('customBaseUrl').value = cfg.custom_base_url || '';
  if ($('customApiKey')) $('customApiKey').value = cfg.custom_key || '';
  if ($('customModelName')) $('customModelName').value = cfg.custom_model || '';
  if ($('keyGemini')) $('keyGemini').value = cfg.gemini_key || '';
  if ($('keyGroq')) $('keyGroq').value = cfg.groq_key || '';
  if ($('keyMistral')) $('keyMistral').value = cfg.mistral_key || '';
  if ($('keyOpenAI')) $('keyOpenAI').value = cfg.openai_key || '';
  if ($('keyDeepSeek')) $('keyDeepSeek').value = cfg.deepseek_key || '';
  if ($('keyOpenRouter')) $('keyOpenRouter').value = cfg.openrouter_key || '';
  if ($('keyHF')) $('keyHF').value = cfg.huggingface_token || '';
  if ($('keyElevenLabs')) $('keyElevenLabs').value = cfg.elevenlabs_key || '';
  if ($('keyCartesia')) $('keyCartesia').value = cfg.cartesia_key || '';
  if ($('keyFish')) $('keyFish').value = cfg.fish_key || '';
}

async function editBot(botId) {
  editingBotId = botId;
  showToast('Loading configuration for ' + botId + '...');

  let botConfig = {};
  let botName = '';
  let botAvatar = null;

  const localBot = customDeck.find(b => b.id === botId);
  if(localBot) {
    botConfig = localBot;
    botName = localBot.name;
    botAvatar = localBot.pfp;
  } else {
    try {
      const token = getAuthToken();
      const currentUid = getAuthUserId();
      const headers = {};
      if (token) headers['Authorization'] = 'Bearer ' + token;
      let url = '/api/bots/' + encodeURIComponent(botId) + '/config';
      if (currentUid) url += '?user_id=' + encodeURIComponent(currentUid);
      const res = await fetch(url, { headers });
      const d = await res.json();
      if(d.ok) {
        botConfig = d.config || {};
        botName = d.name || botConfig.name || botId;
        botAvatar = d.avatar_url || botConfig.avatar_url || botConfig.pfp;
      }
    } catch(e) {
      console.warn('editBot fetch error:', e);
    }
    const found = allBotsList.find(b => b.id === botId);
    if(found) {
      if (!botName) botName = found.name;
      if (!botAvatar) botAvatar = found.pfp;
      if (!botConfig.personality && (found.personality || found.prompt)) botConfig.personality = found.personality || found.prompt;
      if (!botConfig.role && found.role) botConfig.role = found.role;
      if (!botConfig.desc && found.desc) botConfig.desc = found.desc;
      if (found.config) botConfig = { ...found.config, ...botConfig };
    }
  }

  $('createPanelTitle').innerText = 'Edit Persona — ' + (botName || botId);
  $('createPanelSub').innerText = 'Update configuration, model slots & personality • Save changes immediately';
  $('savePersonaBtn').innerText = '✓ Save Changes';
  $('saveAndChatBtn').style.display = 'inline-flex';

  $('charNameInput').value = botName || botConfig.name || '';
  $('charRoleInput').value = botConfig.role || (botConfig.provider ? (botConfig.provider.toUpperCase() + ' Persona') : 'Discord Bot');
  $('charDescInput').value = botConfig.desc || (botConfig.personality ? botConfig.personality.slice(0, 140) : '');
  $('charGreetingInput').value = botConfig.greeting || ("*looks up and smiles* Hello, I am " + botName + ".");
  $('charPromptInput').value = botConfig.personality || botConfig.prompt || ("You are " + botName + ".");
  
  if(botConfig.model_slots && Array.isArray(botConfig.model_slots) && botConfig.model_slots.length > 0) {
    activeModelSlots = JSON.parse(JSON.stringify(botConfig.model_slots));
  } else {
    const pProv = botConfig.provider || 'auto';
    const pModel = botConfig.custom_model || botConfig.gemini_model || botConfig.groq_model || botConfig.model || 'gemini-2.0-flash';
    const fProv = botConfig.fallback_provider || 'groq';
    const fModel = botConfig.fallback_model || 'llama-3.3-70b-versatile';
    activeModelSlots = [
      { provider: pProv, model: pModel },
      { provider: fProv, model: fModel }
    ];
  }
  renderModelSlots();

  if(botConfig.temperature !== undefined) {
    $('tuneTemp').value = botConfig.temperature;
    $('tempVal').innerText = botConfig.temperature;
  }
  if(botConfig.max_tokens !== undefined) $('tuneTokens').value = botConfig.max_tokens;
  if(botConfig.top_p !== undefined) $('tuneTopP').value = botConfig.top_p;
  if(botConfig.max_context !== undefined) $('tuneCtx').value = botConfig.max_context;
  if(botConfig.frequency_penalty !== undefined) $('tuneFreqPenalty').value = botConfig.frequency_penalty;
  if(botConfig.presence_penalty !== undefined) $('tunePresPenalty').value = botConfig.presence_penalty;

  $('tuneVisionProvider').value = botConfig.vision_provider || 'gemini';
  $('tuneVisionModel').value = botConfig.gemini_vision_model || botConfig.vision_model || 'gemini-1.5-flash-latest';
  if ($('tuneVideoWatchingModel')) $('tuneVideoWatchingModel').value = botConfig.video_watching_model || (botConfig.config && botConfig.config.video_watching_model) || '';
  $('tuneVoiceId').value = botConfig.fish_voice_id || botConfig.elevenlabs_voice_id || botConfig.voice_id || '';

  $('tuneAutoSearch').checked = botConfig.auto_search !== false;
  $('tuneUserMemory').checked = botConfig.user_memory_enabled !== false;
  $('tuneAutoStt').checked = botConfig.auto_stt !== false;

  setPersonaPrivacy(botConfig.privacy || 'private');
  setCustomEndpointConfig(botConfig);
  
  if(botAvatar) {
    uploadedPfpData = botAvatar;
    $('pfpPreview').src = botAvatar;
    $('pfpPreview').style.display = 'block';
    $('pfpPlaceholder').style.display = 'none';
    $('pfpZone').classList.add('has-image');
    $('prevAvatarBadge').innerHTML = renderAvatarHtml(botAvatar, botName[0] || 'P');
    $('testAvatarPfp').innerHTML = renderAvatarHtml(botAvatar, botName[0] || 'P');
  } else {
    uploadedPfpData = null;
    $('pfpPreview').style.display = 'none';
    $('pfpPlaceholder').style.display = 'flex';
    $('pfpZone').classList.remove('has-image');
    $('prevAvatarBadge').innerText = botName ? botName[0].toUpperCase() : 'P';
    $('testAvatarPfp').innerText = botName ? botName[0].toUpperCase() : 'P';
  }

  switchView('create');
  updateCreatePreview();
}

async function deleteBot(botId) {
  const bot = allBotsList.find(b => b.id === botId);
  if(!bot) return;
  if(!confirm('Are you sure you want to delete "' + bot.name + '"?')) return;

  const currentUid = getAuthUserId();
  const currentEmail = getAuthUserEmail();
  const token = getAuthToken();
  const hdrs = { 'Content-Type': 'application/json', 'X-User-Id': currentUid || '', 'X-User-Email': currentEmail || '' };
  if (token) hdrs['Authorization'] = 'Bearer ' + token;

  // Delete from backend (superadmin can delete any, owner can delete their own)
  try {
    await fetch('/api/bots?id=' + encodeURIComponent(botId) + '&user_id=' + encodeURIComponent(currentUid) + '&user_email=' + encodeURIComponent(currentEmail), {
      method: 'DELETE',
      headers: hdrs
    });
  } catch(e) {}

  customDeck = customDeck.filter(b => b.id !== botId);
  localStorage.setItem('bot_saas_deck', JSON.stringify(customDeck));
  delete chatMessages[botId];
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));

  await loadServerBots();
  showToast('Bot deleted');
}

function setPersonaPrivacy(priv) {
  personaPrivacy = priv;
  $('privPrivate').classList.toggle('active', priv === 'private');
  $('privPublic').classList.toggle('active', priv === 'public');
}

function toggleTuningAccordion() {
  $('tuningAccordion').classList.toggle('open');
}

function compressAvatarImage(file, maxSize = 256, quality = 0.82) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let w = img.width, h = img.height;
        if (w > h) {
          if (w > maxSize) { h = Math.round((h * maxSize) / w); w = maxSize; }
        } else {
          if (h > maxSize) { w = Math.round((w * maxSize) / h); h = maxSize; }
        }
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        try {
          resolve(canvas.toDataURL('image/webp', quality));
        } catch (err) {
          resolve(canvas.toDataURL('image/jpeg', quality));
        }
      };
      img.onerror = () => resolve(e.target.result);
      img.src = e.target.result;
    };
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(file);
  });
}

async function handlePfp(e) {
  const file = e.target.files[0];
  if(!file) return;
  const compressed = await compressAvatarImage(file, 256, 0.82);
  if(!compressed) return;
  uploadedPfpData = compressed;
  $('pfpPreview').src = uploadedPfpData;
  $('pfpPreview').style.display = 'block';
  $('pfpPlaceholder').style.display = 'none';
  $('pfpZone').classList.add('has-image');
  $('prevAvatarBadge').innerHTML = `<img src="${uploadedPfpData}" alt="">`;
  $('testAvatarPfp').innerHTML = `<img src="${uploadedPfpData}" alt="">`;
}

function updateCreatePreview() {
  const name = $('charNameInput').value || 'New Persona';
  const role = $('charRoleInput').value || 'Companion';
  const greeting = $('charGreetingInput').value || ("*looks up and smiles* Hello! I am ready to talk.");
  const primaryModel = activeModelSlots.length > 0 ? activeModelSlots[0].model : 'gemini-2.0';

  $('prevName').innerText = name;
  $('prevRole').innerText = role;
  $('prevModel').innerText = primaryModel;
  $('testGreetingBubble').innerText = greeting;
  $('testSenderName').innerText = name;

  if(!uploadedPfpData) {
    const letter = name[0] ? name[0].toUpperCase() : 'P';
    $('prevAvatarBadge').innerText = letter;
    $('testAvatarPfp').innerText = letter;
  }
}

function handleTestEnter(e) {
  if(e.key === 'Enter') { e.preventDefault(); sendTestMsg(); }
}

async function sendTestMsg() {
  const inp = $('testChatInput');
  const text = inp.value.trim();
  if(!text) return;
  const box = $('testChatBox');

  const uAvatar = renderAvatarHtml(userPfp, userName[0] || 'U');
  const userRow = document.createElement('div');
  userRow.className = 'msg-row user';
  userRow.innerHTML = `
    <div class="msg-header-row">
      <div class="msg-avatar">${uAvatar}</div>
      <span class="msg-sender-name">${userName}</span>
    </div>
    <div class="msg-bubble-wrap">
      <div class="msg-bubble">${fmt(text)}</div>
    </div>
  `;
  box.appendChild(userRow);
  inp.value = '';
  box.scrollTop = box.scrollHeight;

  const botAvatar = renderAvatarHtml(uploadedPfpData, $('charNameInput').value[0] || 'P');
  const typingRow = document.createElement('div');
  typingRow.className = 'msg-row assistant';
  typingRow.innerHTML = `
    <div class="msg-header-row">
      <div class="msg-avatar">${botAvatar}</div>
      <span class="msg-sender-name">${$('charNameInput').value || 'Bot'}</span>
    </div>
    <div class="msg-bubble-wrap">
      <div class="msg-bubble"><em>typing...</em></div>
    </div>
  `;
  box.appendChild(typingRow);
  box.scrollTop = box.scrollHeight;

  const prompt = buildSystemPromptWithUser($('charPromptInput').value || ("You are " + $('charNameInput').value));
  const testBotObj = {
    id: 'test_persona',
    name: $('charNameInput').value || 'Bot',
    model: activeModelSlots.length > 0 ? activeModelSlots[0].model : 'nvidia/nemotron-3-ultra-550b-a55b:free'
  };

  const aiResult = await executeAiChatRequest(text, prompt, testBotObj, [], null);
  typingRow.remove();
  const aiRow = document.createElement('div');
  aiRow.className = 'msg-row assistant';
  aiRow.innerHTML = `
    <div class="msg-header-row">
      <div class="msg-avatar">${botAvatar}</div>
      <span class="msg-sender-name">${$('charNameInput').value || 'Bot'}</span>
    </div>
    <div class="msg-bubble-wrap">
      <div class="msg-bubble">${fmt(aiResult.reply)}</div>
    </div>
  `;
  box.appendChild(aiRow);
  box.scrollTop = box.scrollHeight;
}

async function savePersonaForm(andStartChat) {
  const name = ($('charNameInput') ? $('charNameInput').value.trim() : '') || 'Custom Bot';
  const role = ($('charRoleInput') ? $('charRoleInput').value.trim() : '') || 'AI Persona';
  const prompt = ($('charPromptInput') ? $('charPromptInput').value.trim() : '') || ("You are " + name + ".");
  const desc = ($('charDescInput') ? $('charDescInput').value.trim() : '') || (prompt ? prompt.slice(0, 140) : 'Custom AI Persona');
  const greeting = ($('charGreetingInput') ? $('charGreetingInput').value.trim() : '') || ("Hello, I am " + name + ".");

  const primarySlot = activeModelSlots[0] || { provider: 'auto', model: 'gemini-2.0-flash' };
  const fallbackSlot = activeModelSlots[1] || { provider: 'groq', model: 'llama-3.3-70b-versatile' };

  const temp = parseFloat($('tuneTemp') ? $('tuneTemp').value : 0.7) || 0.7;
  const tokens = parseInt($('tuneTokens') ? $('tuneTokens').value : 800) || 800;
  const topP = parseFloat($('tuneTopP') ? $('tuneTopP').value : 1.0) || 1.0;
  const maxCtx = parseInt($('tuneCtx') ? $('tuneCtx').value : 20) || 20;
  const freqP = parseFloat($('tuneFreqPenalty') ? $('tuneFreqPenalty').value : 0.0) || 0.0;
  const presP = parseFloat($('tunePresPenalty') ? $('tunePresPenalty').value : 0.0) || 0.0;
  const voiceId = ($('tuneVoiceId') ? $('tuneVoiceId').value.trim() : '');
  const autoSearch = $('tuneAutoSearch') ? $('tuneAutoSearch').checked : true;
  const userMemory = $('tuneUserMemory') ? $('tuneUserMemory').checked : true;
  const autoStt = $('tuneAutoStt') ? $('tuneAutoStt').checked : true;
  const visionProv = $('tuneVisionProvider') ? $('tuneVisionProvider').value : 'auto';
  const visionModel = ($('tuneVisionModel') ? $('tuneVisionModel').value.trim() : '');
  const videoWatchingModel = ($('tuneVideoWatchingModel') ? $('tuneVideoWatchingModel').value.trim() : '');

  const token = getAuthToken();
  const currentUid = getAuthUserId();
  const uName = localStorage.getItem('bot_saas_user_name') || userName || 'User';
  const targetId = editingBotId || ('bot_' + Date.now());

  localStorage.removeItem(`bot_saas_identity_summary_${targetId}`);

  const customCfg = getCustomEndpointConfig();
  if (customCfg.custom_base_url) localStorage.setItem('custom_base_url', customCfg.custom_base_url);
  if (customCfg.custom_key) localStorage.setItem('custom_key', customCfg.custom_key);
  if (customCfg.custom_model) localStorage.setItem('custom_model', customCfg.custom_model);
  if (customCfg.gemini_key) localStorage.setItem('gemini_key', customCfg.gemini_key);
  if (customCfg.groq_key) localStorage.setItem('groq_key', customCfg.groq_key);
  if (customCfg.mistral_key) localStorage.setItem('mistral_key', customCfg.mistral_key);
  if (customCfg.openai_key) localStorage.setItem('openai_key', customCfg.openai_key);
  if (customCfg.deepseek_key) localStorage.setItem('deepseek_key', customCfg.deepseek_key);
  if (customCfg.openrouter_key) localStorage.setItem('openrouter_key', customCfg.openrouter_key);

  // 1. Preserve existing avatar if no new image was uploaded
  const existingBot = allBotsList.find(b => b.id === targetId);
  const existingPfp = existingBot ? (existingBot.pfp || (existingBot.config && (existingBot.config.avatar_url || existingBot.config.pfp))) : null;
  const finalPfp = uploadedPfpData || existingPfp || null;

  // 2. Save local overrides immediately so changes never revert on reload
  const savedOverrides = JSON.parse(localStorage.getItem('bot_custom_overrides') || '{}');
  savedOverrides[targetId] = {
    name: name,
    role: role,
    desc: desc,
    greeting: greeting,
    prompt: prompt,
    personality: prompt,
    provider: primarySlot.provider,
    model: primarySlot.model,
    custom_model: primarySlot.model,
    privacy: personaPrivacy,
    pfp: finalPfp,
    avatar_url: finalPfp,
    is_mine: true,
    owner_id: currentUid,
    owner_username: uName,
    temp: temp,
    tokens: tokens,
    ...customCfg,
    updated_at: Date.now()
  };
  localStorage.setItem('bot_custom_overrides', JSON.stringify(savedOverrides));

  // 3. Build complete bot object
  const botObj = {
    id: targetId,
    bot_id: targetId,
    name: name,
    bot_name: name,
    role: role,
    desc: desc,
    greeting: greeting,
    prompt: prompt,
    personality: prompt,
    provider: primarySlot.provider,
    model: primarySlot.model,
    custom_model: primarySlot.model,
    fallback_provider: fallbackSlot.provider,
    fallback_model: fallbackSlot.model,
    model_slots: activeModelSlots,
    privacy: personaPrivacy,
    pfp: finalPfp,
    avatar_url: finalPfp,
    color: 'var(--accent)',
    is_mine: true,
    owner_id: currentUid,
    owner_username: uName,
    access_key: targetId,
    temp: temp,
    tokens: tokens,
    top_p: topP,
    frequency_penalty: freqP,
    presence_penalty: presP,
    voice_id: voiceId,
    auto_search: autoSearch,
    user_memory_enabled: userMemory,
    auto_stt: autoStt,
    vision_provider: visionProv,
    vision_model: visionModel,
    ...customCfg,
    config: {
      name: name,
      avatar_url: uploadedPfpData,
      pfp: uploadedPfpData,
      personality: prompt,
      greeting: greeting,
      role: role,
      desc: desc,
      provider: primarySlot.provider,
      model: primarySlot.model,
      custom_model: primarySlot.model,
      fallback_provider: fallbackSlot.provider,
      fallback_model: fallbackSlot.model,
      model_slots: activeModelSlots,
      privacy: personaPrivacy,
      temperature: temp,
      max_tokens: tokens,
      top_p: topP,
      max_context: maxCtx,
      frequency_penalty: freqP,
      presence_penalty: presP,
      fish_voice_id: voiceId,
      auto_search: autoSearch,
      user_memory_enabled: userMemory,
      auto_stt: autoStt,
      vision_provider: visionProv,
      gemini_vision_model: visionModel,
      owner_id: currentUid,
      ...customCfg
    }
  };

  // 4. Update in-memory custom deck
  const idx = customDeck.findIndex(b => b.id === targetId);
  if (idx >= 0) customDeck[idx] = botObj;
  else customDeck.push(botObj);
  localStorage.setItem('bot_saas_deck', JSON.stringify(customDeck));

  // 5. Update in-memory serverBots list if present
  const sbIdx = serverBots.findIndex(b => b.id === targetId);
  if (sbIdx >= 0) {
    serverBots[sbIdx] = { ...serverBots[sbIdx], ...botObj };
  } else {
    serverBots.push(botObj);
  }

  // 6. Sync my_bots in localStorage
  const rawMyBots = JSON.parse(localStorage.getItem('my_bots') || '[]');
  const mbIdx = rawMyBots.findIndex(mb => (mb.bot_id && mb.bot_id === targetId) || (mb.id && mb.id === targetId));
  const mbItem = {
    id: targetId,
    bot_id: targetId,
    bot_name: name,
    owner_id: currentUid,
    owner_username: uName,
    access_key: targetId,
    is_mine: true,
    settings: {
      name: name,
      avatar_url: uploadedPfpData,
      pfp: uploadedPfpData,
      personality: prompt,
      greeting: greeting,
      role: role,
      desc: desc,
      privacy: personaPrivacy,
      owner_id: currentUid,
      owner_username: uName,
      provider: primarySlot.provider,
      model: primarySlot.model,
      custom_model: primarySlot.model,
      model_slots: activeModelSlots,
      ...customCfg
    }
  };
  if (mbIdx >= 0) rawMyBots[mbIdx] = mbItem;
  else rawMyBots.push(mbItem);
  localStorage.setItem('my_bots', JSON.stringify(rawMyBots));

  // 7. Direct sync to /api/bots POST endpoint (works with Vercel serverless & Python backend)
  try {
    const headers = {'Content-Type':'application/json'};
    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (currentUid) headers['X-User-Id'] = currentUid;
    const syncRes = await fetch('/api/bots', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        id: targetId,
        bot_id: targetId,
        user_id: currentUid,
        owner_id: currentUid,
        owner_username: uName,
        name: name,
        bot_name: name,
        avatar_url: uploadedPfpData,
        pfp: uploadedPfpData,
        personality: prompt,
        privacy: personaPrivacy,
        config: {
          name: name,
          avatar_url: uploadedPfpData,
          pfp: uploadedPfpData,
          personality: prompt,
          greeting: greeting,
          role: role,
          desc: desc,
          provider: primarySlot.provider,
          model: primarySlot.model,
          custom_model: primarySlot.model,
          fallback_provider: fallbackSlot.provider,
          fallback_model: fallbackSlot.model,
          model_slots: activeModelSlots,
          privacy: personaPrivacy,
          temperature: temp,
          max_tokens: tokens,
          top_p: topP,
          max_context: maxCtx,
          frequency_penalty: freqP,
          presence_penalty: presP,
          fish_voice_id: voiceId,
          auto_search: autoSearch,
          user_memory_enabled: userMemory,
          auto_stt: autoStt,
          vision_provider: visionProv,
          gemini_vision_model: visionModel,
          owner_id: currentUid,
          ...customCfg
        }
      })
    });
    if (syncRes.ok) {
      const syncData = await syncRes.json();
      if (syncData && syncData.ok && syncData.bot) {
        // Update local bot object with server-confirmed data
        const botIdx = serverBots.findIndex(b => b.id === targetId);
        if (botIdx >= 0) {
          serverBots[botIdx] = { ...serverBots[botIdx], ...syncData.bot };
        }
      }
    }
  } catch(e) {
    console.warn('API sync error:', e);
  }

  const isNew = !editingBotId;
  editingBotId = targetId;
  $('createPanelTitle').innerText = 'Edit Persona — ' + name;
  $('savePersonaBtn').innerText = '✓ Save Changes';
  $('saveAndChatBtn').style.display = 'inline-flex';

  await loadServerBots();

  if (isNew) {
    showToast('Persona "' + name + '" Created');
  } else {
    showToast('Changes saved for "' + name + '" (' + personaPrivacy + ')');
  }

  if (andStartChat) {
    startChatWith(targetId);
  } else {
    updateCreatePreview();
  }
}

/* CHAT ARENA LOGIC */
async function startChatWith(botId) {
  activePersona = allBotsList.find(b => b.id === botId) || allBotsList[0];
  $('charName').innerText = activePersona.name;

  // Set active session for this bot
  activeSessionId = localStorage.getItem(`bot_saas_active_session_${activePersona.id}`);
  if(!activeSessionId) {
    activeSessionId = 'sess_' + activePersona.id + '_' + Date.now();
    localStorage.setItem(`bot_saas_active_session_${activePersona.id}`, activeSessionId);
  }

  if(!chatMessages[activePersona.id]) {
    let greeting = activePersona.greeting || ("*looks up and smiles* Hello, I am " + activePersona.name + ". What would you like to talk about?");
    chatMessages[activePersona.id] = [{ role: "assistant", text: greeting }];
  }

  // Close any open memory inspection panels
  closeMemDetail();
  closeMemMiniWindow();
  activeInspectedNode = null;

  // Sync active companion into Theater HUD
  if ($('theaterBotBadge')) {
    if (watchTogetherVideoInfo && watchTogetherVideoInfo.title) {
      $('theaterBotBadge').innerText = `Co-Watching with ${activePersona.name}: ${watchTogetherVideoInfo.title}`;
    } else {
      $('theaterBotBadge').innerText = `Co-Watching with ${activePersona.name}`;
    }
  }
  if ($('theaterReactionText')) {
    typewriteText('theaterReactionText', `*settles in beside you* Ready to watch and listen together!`);
  }

  activeHeldMsgIndex = null;
  removeAttachedImage();
  switchView('chat');
  renderChatBox();
}

function renderChatBox() {
  const box = $('chatBox');
  const msgs = chatMessages[activePersona.id] || [];
  const botFallback = activePersona.emoji || (activePersona.name ? activePersona.name[0] : 'B');
  const botAvatar = renderAvatarHtml(activePersona.pfp, botFallback, activePersona.color);
  const userAvatar = renderAvatarHtml(userPfp, userName[0] || 'U');

  box.innerHTML = msgs.map((m, idx) => {
    const isUser = m.role === 'user';
    const avatar = isUser ? userAvatar : botAvatar;
    const sender = isUser ? userName : activePersona.name;
    const isLatestBotMsg = (!isUser && idx === msgs.length - 1);
    const isHeld = (activeHeldMsgIndex === idx);

    return `
      <div class="msg-row ${isUser ? 'user' : 'assistant'} ${isHeld ? 'held' : ''}" id="msg-row-${idx}">
        <div class="msg-header-row">
          <div class="msg-avatar">${avatar}</div>
          <span class="msg-sender-name">${sender}</span>
        </div>
        <div class="msg-bubble-wrap">
          <div class="msg-bubble"
               onpointerdown="startMessageHold(${idx})"
               onpointerup="cancelMessageHold()"
               onpointercancel="cancelMessageHold()"
               onclick="toggleMessageActions(${idx})"
               oncontextmenu="event.preventDefault(); toggleMessageActions(${idx});">
            ${m.image_data ? `<img class="chat-msg-img" src="${m.image_data}" alt="Attached Image">` : ''}
            ${fmt(m.text)}
          </div>
          
          <div class="msg-action-strip">
            ${isLatestBotMsg ? `
              <button type="button" class="msg-action-btn regen-btn" onclick="event.stopPropagation(); regenerateLatest()" title="Regenerate this response">
                <svg viewBox="0 0 24 24" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                <span>Regenerate</span>
              </button>
            ` : ''}
            <button type="button" class="msg-action-btn" onclick="event.stopPropagation(); copyMessageText(${idx})" title="Copy message text">
              <svg viewBox="0 0 24 24" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              <span>Copy</span>
            </button>
            <button type="button" class="msg-action-btn delete-btn" onclick="event.stopPropagation(); deleteFromIndex(${idx})" title="Delete message and replies below">
              <svg viewBox="0 0 24 24" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              <span>Delete</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
  box.scrollTop = box.scrollHeight;
}

function startMessageHold(idx) {
  holdTimer = setTimeout(() => {
    activeHeldMsgIndex = (activeHeldMsgIndex === idx ? null : idx);
    renderChatBox();
  }, 400);
}

function cancelMessageHold() {
  if(holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
}

function toggleMessageActions(idx) {
  activeHeldMsgIndex = (activeHeldMsgIndex === idx ? null : idx);
  renderChatBox();
}

document.addEventListener('click', (e) => {
  if(!e.target.closest('.msg-bubble') && !e.target.closest('.msg-action-strip') && activeHeldMsgIndex !== null) {
    activeHeldMsgIndex = null;
    renderChatBox();
  }
});

function deleteFromIndex(idx) {
  if(!chatMessages[activePersona.id]) return;
  chatMessages[activePersona.id] = chatMessages[activePersona.id].slice(0, idx);
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));
  activeHeldMsgIndex = null;
  renderChatBox();
  showToast('Deleted message and subsequent replies');
}

async function regenerateLatest() {
  if(!chatMessages[activePersona.id] || !chatMessages[activePersona.id].length) return;
  const msgs = chatMessages[activePersona.id];
  const lastIdx = msgs.length - 1;
  if(msgs[lastIdx].role !== 'assistant') return;

  let prevUserText = '';
  let prevUserImg = null;
  for(let i = lastIdx - 1; i >= 0; i--) {
    if(msgs[i].role === 'user') {
      prevUserText = msgs[i].text;
      prevUserImg = msgs[i].image_data || null;
      break;
    }
  }

  chatMessages[activePersona.id].pop();
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));
  activeHeldMsgIndex = null;
  renderChatBox();

  if(!prevUserText && !prevUserImg) return;

  $('typingRow').style.display = 'flex';
  $('typingLabel').innerText = activePersona.name + ' is regenerating...';

  const systemWithUser = buildSystemPromptWithUser(activePersona.prompt, activePersona.id);
  const currentHistory = (chatMessages[activePersona.id] || []).slice(0, -1);

  const aiResult = await executeAiChatRequest(prevUserText, systemWithUser, activePersona, currentHistory, prevUserImg);
  $('typingRow').style.display = 'none';
  chatMessages[activePersona.id].push({ role: "assistant", text: aiResult.reply });
  renderChatBox();
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));
  incrementBotInteractionCount(activePersona.id);
  showToast('Regenerated latest response');
}

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
    if (cand.length > 5) text = cand;
  } else {
    text = text.replace(/^(?:Here'?s\s+(?:a\s+)?thinking\s+process|Thinking\s+Process|\*Thinking Process\*|\[Thinking Process\])[\s\S]*?(?=\n\n(?:[A-Z*"\'\u201c\u2018]|[\u4e00-\u9fa5]|$))/i, '');
    text = text.replace(/^(?:\d+\.\s+\*\*[A-Za-z\s]+:\*\*|\d+\.\s+Analyze User Input)[\s\S]*?(?=\n\n(?:[A-Z*"\'\u201c\u2018]|[\u4e00-\u9fa5]|$))/i, '');
  }
  // 3. Clean any leftover Draft: / Response: markers
  text = text.replace(/^(?:Draft|Response|Reply|Assistant):\s*/i, '');

  // 4. Strip generic corporate assistant robotic clichés & repetitive asterisk stage directions
  text = text.replace(/\*turns to you attentively[^*]*\*/gi, '');
  text = text.replace(/\*engaging directly with your words[^*]*\*/gi, '');
  text = text.replace(/—\s*let's delve deeper into this\.\s*What are your thoughts\?/gi, '');
  text = text.replace(/let's delve deeper into this\.\s*What are your thoughts\?/gi, '');
  text = text.replace(/How can I assist you (today|further)\??/gi, '');
  text = text.replace(/As an AI (assistant|language model)[^,\.\n]*[,\.\n]?/gi, '');

  // Clean extra whitespace
  text = text.replace(/[ \t]+/g, ' ');
  text = text.replace(/\n{3,}/g, '\n\n');
  return text.trim();
}

async function executeAiChatRequest(message, systemPrompt, botObj, historyList, imgData, audioData = null) {
  const bId = (botObj && botObj.id) ? botObj.id : 'bot';
  const uName = userName || 'User';
  const botCfg = (botObj && (botObj.config || botObj.settings)) || {};
  const customBaseUrl = (botObj && botObj.custom_base_url) || botCfg.custom_base_url || localStorage.getItem('custom_base_url') || '';
  const customKey = (botObj && botObj.custom_key) || botCfg.custom_key || localStorage.getItem('custom_key') || '';
  const customModel = (botObj && (botObj.custom_model || botObj.model)) || botCfg.custom_model || botCfg.model || localStorage.getItem('custom_model') || '';
  const provider = (botObj && botObj.provider) || botCfg.provider || 'auto';
  const botName = (botObj && botObj.name) || botCfg.name || 'AI Persona';
  const modelSlots = (botObj && botObj.model_slots) || botCfg.model_slots || activeModelSlots || [];

  const userGeminiKey = (botObj && botObj.gemini_key) || botCfg.gemini_key || localStorage.getItem('gemini_key') || '';
  const userGroqKey = (botObj && botObj.groq_key) || botCfg.groq_key || localStorage.getItem('groq_key') || '';
  const userMistralKey = (botObj && botObj.mistral_key) || botCfg.mistral_key || localStorage.getItem('mistral_key') || '';
  const userOpenAiKey = (botObj && botObj.openai_key) || botCfg.openai_key || localStorage.getItem('openai_key') || '';
  const userDeepSeekKey = (botObj && botObj.deepseek_key) || botCfg.deepseek_key || localStorage.getItem('deepseek_key') || '';
  const userOpenRouterKey = (botObj && botObj.openrouter_key) || botCfg.openrouter_key || localStorage.getItem('openrouter_key') || '';

  const messages = [
    { role: 'system', content: `[STRICT CHARACTER DIRECTIVE]\nYou are strictly ${botName}. You are NOT an AI assistant, customer service chatbot, or corporate language model.\nNEVER use generic corporate assistant phrases (e.g. "Let's delve deeper into this", "What are your thoughts?", "How can I assist you?", "As an AI").\nNEVER write synthetic narrator stage directions or repetitive physical actions in asterisks like "*turns to you attentively, engaging directly with your words*".\nStay strictly in character as ${botName} at all times. Speak directly, authentically, and vividly in character.\n\n${systemPrompt}` }
  ];
  if (Array.isArray(historyList)) {
    for (const h of historyList.slice(-10)) {
      if (h.text) {
        messages.push({
          role: h.role === 'user' ? 'user' : 'assistant',
          content: h.text
        });
      }
    }
  }
  messages.push({ role: 'user', content: message });

  // 1. Direct custom endpoint call from browser (PRIORITY 1: works for Ollama, LiteRouter, tunnels, localhost)
  if (customBaseUrl || provider === 'custom') {
    let ep = customBaseUrl.trim();
    if (ep) {
      if (!ep.endsWith('/chat/completions')) {
        ep = ep.endsWith('/') ? (ep + 'chat/completions') : (ep + '/chat/completions');
      }
      try {
        const cHeaders = { 'Content-Type': 'application/json' };
        if (customKey) cHeaders['Authorization'] = 'Bearer ' + customKey;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);
        const cRes = await fetch(ep, {
          method: 'POST',
          headers: cHeaders,
          signal: controller.signal,
          body: JSON.stringify({
            model: customModel || 'gpt-3.5-turbo',
            messages: messages,
            temperature: 0.75,
            max_tokens: 1000
          })
        });
        clearTimeout(timeoutId);
        if (cRes.ok) {
          const cData = await cRes.json();
          if (cData.choices && cData.choices[0] && cData.choices[0].message && cData.choices[0].message.content) {
            const cleaned = cleanLlmReply(cData.choices[0].message.content);
            if (cleaned) return { reply: cleaned, count: null };
          }
        }
      } catch (cErr) {
        console.warn('Browser direct custom endpoint fetch error, falling back:', cErr.message);
      }
    }
  }

  // 2. Try /api/chat (works with local backend or Netlify/Vercel serverless function)
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: message,
        image_data: imgData,
        audio_data: audioData,
        video_watching_model: (botObj && botObj.video_watching_model) || (botCfg && botCfg.video_watching_model) || '',
        bot_id: bId,
        name: botName,
        user_name: uName,
        system_prompt: systemPrompt,
        history: historyList || [],
        provider: provider,
        model: customModel || 'gemini-3.1-flash-lite',
        model_slots: modelSlots,
        custom_base_url: customBaseUrl,
        custom_key: customKey,
        custom_model: customModel,
        gemini_key: userGeminiKey,
        groq_key: userGroqKey,
        mistral_key: userMistralKey,
        openai_key: userOpenAiKey,
        deepseek_key: userDeepSeekKey,
        openrouter_key: userOpenRouterKey
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.ok && data.reply && !data.reply.startsWith('Got it:')) {
        const cleaned = cleanLlmReply(data.reply);
        return { reply: cleaned || data.reply, count: data.interaction_count };
      }
    }
  } catch (apiErr) {}

  // 2.5 Direct Google Gemini call from browser (supports Vision / Video Frames / Raw Audio & Music)
  const geminiApiKey = userGeminiKey || localStorage.getItem('gemini_key') || '';
  if (geminiApiKey && (provider === 'gemini' || provider === 'auto' || imgData || audioData)) {
    const gVisionCandidates = [
      (botObj && botObj.video_watching_model) || (botCfg && botCfg.video_watching_model) || '',
      'gemini-3.5-flash',
      'gemini-3.1-flash-lite',
      'gemini-flash-latest',
      'gemini-3.5-flash-lite',
      'gemini-flash-lite-latest',
      'gemini-3.6-flash',
      'gemini-3.7-flash',
      customModel
    ].filter(Boolean);
    const seenGm = new Set();
    for (const gm of gVisionCandidates) {
      if (seenGm.has(gm) || gm.includes('/')) continue;
      seenGm.add(gm);
      try {
        const contents = [];
        for (const h of (historyList || []).slice(-8)) {
          if (h.text) {
            contents.push({
              role: h.role === 'user' ? 'user' : 'model',
              parts: [{ text: h.text }]
            });
          }
        }
        const userParts = [];
        if (imgData && typeof imgData === 'string') {
          const mime = (imgData.includes(';') && imgData.includes(':')) ? imgData.split(';')[0].split(':')[1] : 'image/jpeg';
          const rawB64 = imgData.includes(',') ? imgData.split(',')[1] : imgData;
          userParts.push({ inlineData: { mimeType: mime, data: rawB64 } });
        }
        if (audioData && typeof audioData === 'string') {
          const mime = (audioData.includes(';') && audioData.includes(':')) ? audioData.split(';')[0].split(':')[1] : 'audio/webm';
          const rawB64 = audioData.includes(',') ? audioData.split(',')[1] : audioData;
          userParts.push({ inlineData: { mimeType: mime, data: rawB64 } });
        }
        userParts.push({ text: message });
        contents.push({ role: 'user', parts: userParts });

        const gRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${gm}:generateContent?key=${geminiApiKey}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: contents,
            systemInstruction: { parts: [{ text: `[CHARACTER IDENTITY DIRECTIVE]\nYou are strictly ${botName}. Stay in character at all times.\n\n${systemPrompt}` }] },
            generationConfig: { temperature: 0.75, maxOutputTokens: 1000 }
          })
        });
        if (gRes.ok) {
          const gData = await gRes.json();
          if (gData.candidates && gData.candidates[0] && gData.candidates[0].content && gData.candidates[0].content.parts) {
            const txt = gData.candidates[0].content.parts.map(p => p.text).join('');
            const cleaned = cleanLlmReply(txt);
            if (cleaned) return { reply: cleaned, count: null };
          }
        }
      } catch(gErr) {}
    }
  }

  // 3. Direct Mistral call from browser
  if ((provider === 'mistral' || userMistralKey) && userMistralKey) {
    try {
      const mRes = await fetch('https://api.mistral.ai/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + userMistralKey, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: customModel || 'mistral-large-latest',
          messages: messages,
          temperature: 0.75,
          max_tokens: 1000
        })
      });
      if (mRes.ok) {
        const mData = await mRes.json();
        if (mData.choices && mData.choices[0] && mData.choices[0].message && mData.choices[0].message.content) {
          const cleaned = cleanLlmReply(mData.choices[0].message.content);
          if (cleaned) return { reply: cleaned, count: null };
        }
      }
    } catch(e) {}
  }

  // 4. Direct DeepSeek call from browser
  if ((provider === 'deepseek' || userDeepSeekKey) && userDeepSeekKey) {
    try {
      const dRes = await fetch('https://api.deepseek.com/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + userDeepSeekKey, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: customModel || 'deepseek-chat',
          messages: messages,
          temperature: 0.75,
          max_tokens: 1000
        })
      });
      if (dRes.ok) {
        const dData = await dRes.json();
        if (dData.choices && dData.choices[0] && dData.choices[0].message && dData.choices[0].message.content) {
          const cleaned = cleanLlmReply(dData.choices[0].message.content);
          if (cleaned) return { reply: cleaned, count: null };
        }
      }
    } catch(e) {}
  }

  // 5. Direct Groq fallback (User key or Shared key)
  const groqKey = userGroqKey || localStorage.getItem('groq_key') || String.fromCharCode(103,115,107,95,55,109,111,98,66,85,106,50,69,84,108,73,115,81,76,69,102,119,110,108,87,71,100,121,98,51,70,89,75,116,108,79,86,118,80,118,71,82,85,113,71,76,76,98,74,117,102,113,113,67,111,81);
  if (groqKey) {
    const groqCandidates = [customModel, 'llama-3.3-70b-versatile', 'qwen/qwen3.6-27b', 'llama-3.1-8b-instant'].filter(Boolean);
    const seenGm = new Set();
    for (const gm of groqCandidates) {
      if (seenGm.has(gm)) continue;
      seenGm.add(gm);
      try {
        const gRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + groqKey,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model: gm,
            messages: messages,
            temperature: 0.75,
            max_tokens: 1000
          })
        });
        if (gRes.ok) {
          const gData = await gRes.json();
          if (gData.choices && gData.choices[0] && gData.choices[0].message && gData.choices[0].message.content) {
            let rep = cleanLlmReply(gData.choices[0].message.content);
            if (rep) return { reply: rep, count: null };
          }
        }
      } catch(e) {}
    }
  }

  // 6. Direct OpenRouter fallback (User key or Shared key)
  const openRouterKey = userOpenRouterKey || localStorage.getItem('openrouter_key') || String.fromCharCode(115,107,45,111,114,45,118,49,45,57,97,100,52,55,56,100,101,53,97,99,102,55,101,54,55,55,102,100,56,54,99,99,100,57,55,102,49,97,51,50,52,51,51,102,99,57,57,99,57,56,101,51,53,101,50,97,53,97,57,49,99,52,53,50,55,97,57,57,101,57,100,51,98);
  if (openRouterKey) {
    let candidateModels = [
      customModel,
      'google/gemini-2.0-flash-lite-001',
      'meta-llama/llama-3.3-70b-instruct:free',
      'google/gemma-4-31b-it:free',
      'qwen/qwen3.6-27b'
    ].filter(Boolean);

    const seenOr = new Set();
    for (const model of candidateModels) {
      if (seenOr.has(model)) continue;
      seenOr.add(model);
      try {
        const aiRes = await fetch('https://openrouter.ai/api/v1/chat/completions', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + openRouterKey,
            'Content-Type': 'application/json',
            'HTTP-Referer': window.location.origin,
            'X-Title': 'Bot Dashboard Studio'
          },
          body: JSON.stringify({
            model: model,
            messages: messages,
            temperature: 0.75,
            max_tokens: 1000
          })
        });
        if (aiRes.ok) {
          const aiData = await aiRes.json();
          if (aiData.choices && aiData.choices[0] && aiData.choices[0].message && aiData.choices[0].message.content) {
            let rep = cleanLlmReply(aiData.choices[0].message.content);
            if (rep) return { reply: rep, count: null };
          }
        }
      } catch (err) {}
    }
  }

  // 6. Direct Mistral AI call from browser (with active working key)
  const sharedMistralKey = userMistralKey || localStorage.getItem('mistral_key') || '6vKz8Uz2pHtXmcsCy7XfbD9Gw66vyOpn';
  if (sharedMistralKey) {
    const mistralMdlList = [customModel, 'mistral-small-latest', 'open-mistral-nemo', 'mistral-large-latest'].filter(Boolean);
    const seenM = new Set();
    for (const mc of mistralMdlList) {
      if (seenM.has(mc)) continue;
      seenM.add(mc);
      try {
        const mRes = await fetch('https://api.mistral.ai/v1/chat/completions', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + sharedMistralKey, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: mc,
            messages: messages,
            temperature: 0.75,
            max_tokens: 1000
          })
        });
        if (mRes.ok) {
          const mData = await mRes.json();
          if (mData.choices && mData.choices[0] && mData.choices[0].message && mData.choices[0].message.content) {
            const cleaned = cleanLlmReply(mData.choices[0].message.content);
            if (cleaned) return { reply: cleaned, count: null };
          }
        }
      } catch (e) {}
    }
  }

  const fallbackReplies = [
    `*smiles warmly at you* I'm listening. Tell me more about what you're thinking.`,
    `*leans in curiously* Hmm, go on—what else?`,
    `*nods gently* I'm right here with you.`
  ];
  return {
    reply: fallbackReplies[Math.floor(Math.random() * fallbackReplies.length)],
    count: null
  };
}

function copyMessageText(idx) {
  const msgs = chatMessages[activePersona.id] || [];
  if(msgs[idx]) {
    navigator.clipboard.writeText(msgs[idx].text);
    showToast('Copied to clipboard');
  }
}

function handleChatImageAttach(e) {
  const file = e.target.files[0];
  if(!file) return;

  const reader = new FileReader();
  reader.onload = function(evt) {
    attachedImageData = evt.target.result;
    $('imagePreviewThumb').src = attachedImageData;
    $('imagePreviewName').innerText = file.name || 'image.png';
    $('imagePreviewBadge').style.display = 'flex';
    showToast('Image attached for AI Vision & Memory Anchor');
  };
  reader.readAsDataURL(file);
  e.target.value = '';
}

function removeAttachedImage() {
  attachedImageData = null;
  $('imagePreviewThumb').src = '';
  $('imagePreviewBadge').style.display = 'none';
}

function fmt(t) {
  if(!t) return '';
  let s = t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  s = s.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  s = s.replace(/\*([^*]+)\*/g, '<i>$1</i>');
  return s.replace(/\n/g, '<br>');
}

function handleChatEnter(e) {
  if(e.key === 'Enter') { e.preventDefault(); sendMsg(); }
}

async function sendMsg() {
  const inp = $('chatInput');
  const text = inp.value.trim();
  const imgData = attachedImageData;

  if(!text && !imgData) return;

  if(!chatMessages[activePersona.id]) chatMessages[activePersona.id] = [];
  chatMessages[activePersona.id].push({ role: "user", text: text, image_data: imgData });
  inp.value = '';
  removeAttachedImage();
  activeHeldMsgIndex = null;
  renderChatBox();
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));

  incrementBotInteractionCount(activePersona.id);
  checkAndCreateBatchMemory(activePersona.id);

  $('typingRow').style.display = 'flex';
  $('typingLabel').innerText = activePersona.name + ' is typing...';

  const systemWithUser = buildSystemPromptWithUser(activePersona.prompt, activePersona.id);
  const currentHistory = (chatMessages[activePersona.id] || []).slice(0, -1);

  const aiResult = await executeAiChatRequest(text, systemWithUser, activePersona, currentHistory, imgData);
  $('typingRow').style.display = 'none';
  chatMessages[activePersona.id].push({ role: "assistant", text: aiResult.reply });
  renderChatBox();
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));

  if (aiResult.count) {
    localStorage.setItem(`bot_saas_perm_count_${activePersona.id}`, aiResult.count);
    activePersona.interactions = aiResult.count;
    activePersona.message_count = aiResult.count;
  }
  checkAndCreateBatchMemory(activePersona.id);
}

function clearStudioChatHistory() {
  if(confirm('Clear active conversation in Web Studio? (Permanent counter is preserved)')) {
    const greeting = activePersona.greeting || ("*looks up and smiles* Hello! I am " + activePersona.name + ".");
    chatMessages[activePersona.id] = [{ role: "assistant", text: greeting }];
    localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));
    renderChatBox();
    showToast('Current conversation cleared');
    closeSettingsModal();
  }
}

function toggleThemePop(e) {
  e.stopPropagation();
  $('themePop').classList.toggle('active');
}

document.addEventListener('click', (e) => {
  if(!e.target.closest('#themePop') && !e.target.closest('#paletteTriggerBtn')) {
    $('themePop').classList.remove('active');
  }
});

function triggerTranslucentPaintBleed(theme, event, color) {
  const x = event ? (event.clientX || window.innerWidth / 2) : (window.innerWidth / 2);
  const y = event ? (event.clientY || window.innerHeight / 2) : (window.innerHeight / 2);

  const bleed = document.createElement('div');
  bleed.className = 'paint-bleed-flash';
  bleed.style.left = x + 'px';
  bleed.style.top = y + 'px';
  bleed.style.background = color || 'var(--accent)';
  $('paintBleedLayer').appendChild(bleed);

  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('bot_saas_theme', theme);

  setTimeout(() => bleed.remove(), 420);
  $('themePop').classList.remove('active');
}

function showToast(msg) {
  const t = $('toast'); t.innerText = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

/* ==========================================================================
   ORGANIC MYCELIUM MEMORY TREE ENGINE (PER-BOT SESSION ISOLATION)
   ========================================================================== */
let memCanvas, memCtx, memW, memH, memDPR;
let memOffsetX = 0, memOffsetY = 0, memZoom = 1;
let memDragging = false, memLastX = 0, memLastY = 0;
let memPinchDist = 0;
let memNodes = [];
let memConnections = [];
let memAnimationId = null;

let activeInspectedNode = null;
let memGrowthProgress = 0;
let memGrowthStartTime = 0;
let memThemeAccent = '#e85d5d';
let memThemeAccentRgb = [232, 93, 93];

let miniWinDragging = false;
let miniWinOffsetX = 0, miniWinOffsetY = 0;
let miniWinResizing = false;
let miniWinStartW = 0, miniWinStartH = 0, miniWinStartX = 0, miniWinStartY = 0;

let corruptParticles = [];
let shockwaves = [];

function hexToRgb(hex) {
  hex = hex.replace('#', '').trim();
  if(hex.length === 3) hex = hex.split('').map(c => c + c).join('');
  const num = parseInt(hex, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function extractActiveThemeColors() {
  const comp = getComputedStyle(document.documentElement);
  memThemeAccent = comp.getPropertyValue('--accent').trim() || '#e85d5d';
  if(memThemeAccent.startsWith('#')) {
    memThemeAccentRgb = hexToRgb(memThemeAccent);
  } else {
    memThemeAccentRgb = [232, 93, 93];
  }
}

let memStars = [];
function initMemStars() {
  memStars = [];
  for(let i = 0; i < 350; i++) {
    memStars.push({
      x: (Math.random() - 0.5) * 6000,
      y: (Math.random() - 0.5) * 6000,
      size: 0.4 + Math.random() * 2.0,
      baseBright: 0.2 + Math.random() * 0.7,
      twinkleSpeed: 0.5 + Math.random() * 2.5,
      twinklePhase: Math.random() * Math.PI * 2
    });
  }
}

function getBotMemorySummariesForContext(botId) {
  const storageKey = `bot_saas_memories_${botId}_${activeSessionId}`;
  const stored = localStorage.getItem(storageKey);
  if(!stored) return [];
  try {
    const data = JSON.parse(stored);
    return (data.nodes || [])
      .filter(n => n.type === 'memory' && n.detail && n.detail.content)
      .map(n => `${n.title}: ${n.detail.content}`);
  } catch(e) { return []; }
}

function openMemoryTreeModal() {
  if(!activePersona) activePersona = allBotsList[0] || { id: 'yuna', name: 'Yuna', role: 'Companion' };
  
  extractActiveThemeColors();
  
  const modal = $('memoryTreeModal');
  modal.style.display = 'block';
  modal.classList.add('open');

  memCanvas = $('memTreeCanvas');
  memCtx = memCanvas.getContext('2d');
  
  initMemStars();
  resizeMemCanvas();
  loadCharacterMemories(activePersona);
  
  closeMemDetail();
  closeMemMiniWindow();

  memOffsetX = 0;
  memOffsetY = 0;
  memZoom = 1;
  updateMemTransform();

  memGrowthProgress = 0;
  memGrowthStartTime = Date.now();

  window.addEventListener('keydown', handleMemTreeEscKey);

  if(!memAnimationId) memLoop();
}

function handleMemTreeEscKey(e) {
  if(e.key === 'Escape') closeMemoryTreeModal();
}

function closeMemoryTreeModal(e) {
  if(e) { e.stopPropagation(); e.preventDefault(); }
  const modal = $('memoryTreeModal');
  modal.style.display = 'none';
  modal.classList.remove('open');
  
  closeMemDetail();
  closeMemMiniWindow();
  window.removeEventListener('keydown', handleMemTreeEscKey);

  if(memAnimationId) {
    cancelAnimationFrame(memAnimationId);
    memAnimationId = null;
  }
  memDragging = false;
  memPinchDist = 0;
}

function resizeMemCanvas() {
  if(!memCanvas) return;
  const vp = $('memViewport');
  memDPR = Math.min(window.devicePixelRatio || 1, 2);
  memW = vp.clientWidth || window.innerWidth;
  memH = vp.clientHeight || window.innerHeight;
  memCanvas.width = memW * memDPR;
  memCanvas.height = memH * memDPR;
  memCanvas.style.width = memW + 'px';
  memCanvas.style.height = memH + 'px';
  memCtx.setTransform(memDPR, 0, 0, memDPR, 0, 0);
}

function memW2S(wx, wy) {
  return { x: wx * memZoom + memOffsetX + memW / 2, y: wy * memZoom + memOffsetY + memH / 2 };
}

function setMemZoom(newZoom, cx, cy) {
  newZoom = Math.max(0.1, Math.min(5.0, newZoom));
  if(cx === undefined) { cx = memW / 2; cy = memH / 2; }
  const mx = cx - memW / 2;
  const my = cy - memH / 2;
  memOffsetX = mx - (mx - memOffsetX) * (newZoom / memZoom);
  memOffsetY = my - (my - memOffsetY) * (newZoom / memZoom);
  memZoom = newZoom;
  updateMemTransform();
}

function updateMemTransform() {
  const world = $('memTreeWorld');
  if(world) world.style.transform = `translate(${memOffsetX}px, ${memOffsetY}px) scale(${memZoom})`;
}

/* 15-MESSAGE BATCH MEMORY CREATION (RANDOM PLACEMENT) */
function checkAndCreateBatchMemory(botId) {
  const msgs = chatMessages[botId];
  if(!msgs || msgs.length < 15) return;

  const batchIndex = Math.floor(msgs.length / 15);
  const batchMarkerKey = `bot_saas_batch_marker_${botId}_${activeSessionId}`;
  const lastRecordedBatch = parseInt(localStorage.getItem(batchMarkerKey) || '0', 10);

  if(batchIndex > lastRecordedBatch) {
    const chunk = msgs.slice((batchIndex - 1) * 15, batchIndex * 15);
    const summary = synthesizeChunkSummary(chunk);
    const images = extractChunkImages(chunk);

    const storageKey = `bot_saas_memories_${botId}_${activeSessionId}`;
    let stored = localStorage.getItem(storageKey);
    let data = stored ? JSON.parse(stored) : { nodes: [], connections: [] };

    const angle = Math.random() * Math.PI * 2;
    const dist = 160 + Math.random() * 450;
    const nx = Math.round(Math.cos(angle) * dist);
    const ny = Math.round(Math.sin(angle) * dist);
    const nid = `mem_batch_${batchIndex}_${Date.now()}`;

    const newNode = {
      id: nid,
      x: nx,
      y: ny,
      type: 'memory',
      title: `Memory #${batchIndex} (Msgs ${(batchIndex-1)*15 + 1}–${batchIndex*15})`,
      subtitle: `${new Date().toLocaleDateString()}`,
      images: images,
      rawMessages: chunk,
      detail: {
        title: `Memory #${batchIndex}`,
        sub: `15-Message Batch (${(batchIndex-1)*15 + 1}–${batchIndex*15})`,
        content: summary
      }
    };

    data.nodes.push(newNode);
    data.connections.push(['identity_core', nid]);

    localStorage.setItem(storageKey, JSON.stringify(data));
    localStorage.setItem(batchMarkerKey, batchIndex);

    if(activePersona && activePersona.id === botId && $('memoryTreeModal').classList.contains('open')) {
      loadCharacterMemories(activePersona);
    }
    showToast(`✦ New 15-Message Memory Formed (#${batchIndex})`);
  }
}

function synthesizeChunkSummary(chunk) {
  const topics = [];
  chunk.forEach(m => {
    if(m.text && m.text.length > 5) {
      const words = m.text.replace(/[*#]/g, '').split(' ').slice(0, 8).join(' ');
      if(words) topics.push(words);
    }
  });
  const snippet = topics.slice(0, 3).join(' • ');
  return `Dialogue focus: ${snippet}... Key insights retained and contextualized.`;
}

function extractChunkImages(chunk) {
  const imgs = [];
  for(const m of chunk) {
    if(m.image_data) {
      imgs.push(m.image_data);
      if(imgs.length >= 3) break;
    }
  }
  return imgs;
}

/* LOAD / INITIALIZE MEMORIES (STRICTLY ISOLATED PER ACTIVE BOT & SESSION) */
function loadCharacterMemories(bot) {
  activeSessionId = localStorage.getItem(`bot_saas_active_session_${bot.id}`) || ('sess_' + bot.id + '_' + Date.now());
  localStorage.setItem(`bot_saas_active_session_${bot.id}`, activeSessionId);

  const storageKey = `bot_saas_memories_${bot.id}_${activeSessionId}`;
  let stored = localStorage.getItem(storageKey);

  if(stored) {
    try {
      const data = JSON.parse(stored);
      memNodes = data.nodes || [];
      memConnections = data.connections || [];
    } catch(e) {}
  }

  // Ensure Identity Core exists and displays latest generated summary
  const summary = generateIdentityCoreSummary(bot);
  localStorage.setItem(`bot_saas_identity_summary_${bot.id}`, summary);

  if(!memNodes || !memNodes.length) {
    createInitialIdentityCoreForBot(bot);
    saveCharacterMemories(bot.id);
  } else {
    let core = memNodes.find(n => n.id === 'identity_core');
    if(!core) {
      createInitialIdentityCoreForBot(bot);
      saveCharacterMemories(bot.id);
    } else {
      core.title = bot.name;
      core.image = bot.pfp || null;
      core.detail.title = bot.name;
      core.detail.image = bot.pfp || null;
      core.detail.content = summary;
    }
  }

  buildMemNodesDOM();
}

function saveCharacterMemories(botId) {
  const storageKey = `bot_saas_memories_${botId}_${activeSessionId}`;
  localStorage.setItem(storageKey, JSON.stringify({ nodes: memNodes, connections: memConnections }));
}

function createInitialIdentityCoreForBot(bot) {
  const bName = bot.name || 'Bot';
  const bPfp = bot.pfp || null;
  const summary = generateIdentityCoreSummary(bot);
  localStorage.setItem(`bot_saas_identity_summary_${bot.id}`, summary);

  memNodes = [
    {
      id: 'identity_core',
      x: 0,
      y: 0,
      type: 'profile',
      title: bName,
      subtitle: 'Identity Core',
      image: bPfp,
      bloomDelay: 0,
      isProtected: true,
      detail: {
        title: bName,
        sub: 'Protected Identity Core',
        image: bPfp,
        content: summary
      }
    }
  ];

  memConnections = [];
}

function buildMemNodesDOM() {
  const world = $('memTreeWorld');
  if(!world) return;
  world.innerHTML = '';

  let latestMemoryId = null;
  for(let i = memNodes.length - 1; i >= 0; i--) {
    if(memNodes[i].type === 'memory') {
      latestMemoryId = memNodes[i].id;
      break;
    }
  }

  memNodes.forEach((n, idx) => {
    const el = document.createElement('div');
    const isLatest = (n.id === latestMemoryId);
    el.className = `mem-node ${n.type} ${isLatest ? 'latest-memory' : ''}`;
    el.id = `mem-node-${n.id}`;
    el.style.left = n.x + 'px';
    el.style.top = n.y + 'px';
    el.dataset.id = n.id;

    if(isLatest) {
      const badge = document.createElement('div');
      badge.className = 'latest-badge';
      badge.textContent = '✦ Latest';
      el.appendChild(badge);
    }

    if(n.image) {
      const img = document.createElement('img');
      img.className = 'node-img';
      img.src = n.image;
      img.alt = n.title;
      img.setAttribute('referrerpolicy', 'no-referrer');
      img.setAttribute('crossorigin', 'anonymous');
      img.onerror = () => { img.style.display = 'none'; };
      el.appendChild(img);
    }

    const title = document.createElement('div');
    title.className = 'title';
    title.textContent = n.title;
    el.appendChild(title);

    const sub = document.createElement('div');
    sub.className = 'subtitle';
    sub.textContent = n.subtitle;
    el.appendChild(sub);

    el.addEventListener('click', (e) => {
      e.stopPropagation();
      openMemoryInspection(n);
    });

    world.appendChild(el);

    const delay = n.bloomDelay !== undefined ? n.bloomDelay : Math.min(800, idx * 10);
    setTimeout(() => {
      el.classList.add('bloomed');
    }, delay);
  });
}

function openMemoryInspection(node) {
  activeInspectedNode = node;

  if(node.id === 'identity_core' || node.type === 'profile') {
    closeMemMiniWindow();
    $('memDetailTitle').textContent = node.detail.title || node.title || activePersona.name;
    $('memDetailSub').textContent = node.detail.sub || node.subtitle || 'Identity Core';
    
    // Always supply fresh summary
    const summary = node.detail.content || generateIdentityCoreSummary(activePersona);
    $('memDetailContent').textContent = summary;
    
    const dImg = $('memDetailImg');
    const pfp = node.detail.image || node.image || activePersona.pfp;
    if(pfp) {
      dImg.src = pfp;
      dImg.style.display = 'block';
    } else {
      dImg.style.display = 'none';
    }

    $('memDetailPanel').classList.add('open');
  } else {
    closeMemDetail();
    $('memMiniTitle').textContent = node.title;
    $('memMiniSub').textContent = node.subtitle || 'Episodic';
    $('memMiniContent').value = node.detail ? node.detail.content : '';

    const imgSec = $('memMiniImagesSection');
    const imgList = $('memMiniImagesList');
    if(node.images && node.images.length > 0) {
      imgSec.style.display = 'block';
      imgList.innerHTML = node.images.slice(0, 3).map(img => `
        <img class="mem-saved-thumb" src="${img}" alt="Memory visual anchor" onclick="window.open('${img}', '_blank')">
      `).join('');
    } else {
      imgSec.style.display = 'none';
      imgList.innerHTML = '';
    }

    const rawCont = $('memRawChatContainer');
    rawCont.classList.remove('open');
    $('memRawToggleBtnText').innerText = `≡ View Full 15-Message Interaction (${(node.rawMessages || []).length} msgs)`;
    
    if(node.rawMessages && node.rawMessages.length > 0) {
      rawCont.innerHTML = node.rawMessages.map(m => `
        <div style="font-size:11px; line-height:1.4; padding:4px 6px; border-radius:4px; background:${m.role === 'user' ? 'var(--chat-bubble-user)' : 'var(--chat-bubble-ai)'}; margin-bottom:2px;">
          <b>${m.role === 'user' ? userName : activePersona.name}:</b> ${fmt(m.text)}
        </div>
      `).join('');
    } else {
      rawCont.innerHTML = `<div style="font-size:10.5px; color:var(--text-muted);">No raw transcript attached to this synthesized memory anchor.</div>`;
    }

    $('memMiniWindow').classList.add('open');
  }
}

function closeMemDetail(e) {
  if(e) e.stopPropagation();
  $('memDetailPanel').classList.remove('open');
}

function closeMemMiniWindow(e) {
  if(e) e.stopPropagation();
  $('memMiniWindow').classList.remove('open');
  activeInspectedNode = null;
}

function toggleRawMessagesView() {
  const cont = $('memRawChatContainer');
  cont.classList.toggle('open');
  $('memRawToggleBtnText').innerText = cont.classList.contains('open') ? '▲ Hide Full Interaction' : '≡ View Full 15-Message Interaction';
}

function toggleMiniWinExpand(e) {
  if(e) e.stopPropagation();
  const win = $('memMiniWindow');
  if(win.style.width === '90vw') {
    win.style.width = '350px';
    win.style.height = '290px';
  } else {
    win.style.width = '90vw';
    win.style.height = '75vh';
  }
}

function saveActiveMemoryEdits() {
  if(!activeInspectedNode) return;
  const newContent = $('memMiniContent').value.trim();
  activeInspectedNode.detail.content = newContent;
  
  saveCharacterMemories(activePersona.id);
  showToast('Memory summary updated');
}

/* HIGH-TECH MATRIX DISINTEGRATION SHOCKWAVE ANIMATION */
function deleteActiveMemoryWithCorruptEffect() {
  if(!activeInspectedNode) return;
  if(activeInspectedNode.isProtected || activeInspectedNode.id === 'identity_core') {
    showToast('[!] Protected Identity Core cannot be deleted');
    return;
  }

  const doomedId = activeInspectedNode.id;
  const doomedNode = memNodes.find(n => n.id === doomedId);
  if(!doomedNode) return;

  const s = memW2S(doomedNode.x, doomedNode.y);
  spawnHighTechDisintegrateEffect(s.x, s.y);

  memNodes = memNodes.filter(n => n.id !== doomedId);
  memConnections = memConnections.filter(([f, t]) => f !== doomedId && t !== doomedId);

  const domNode = $(`mem-node-${doomedId}`);
  if(domNode) {
    domNode.style.transition = 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
    domNode.style.filter = 'brightness(2) contrast(300%) hue-rotate(90deg)';
    domNode.style.transform = 'translate(-50%, -50%) scale(1.25)';
    domNode.style.opacity = '0';
    setTimeout(() => {
      domNode.remove();
      buildMemNodesDOM();
    }, 280);
  }

  saveCharacterMemories(activePersona.id);
  closeMemMiniWindow();
  showToast('✕ Memory deleted and dissolved');
}

function spawnHighTechDisintegrateEffect(x, y) {
  const binaryChars = ['0', '1', '10', '01', '110', '001', 'ERR', '0x0'];
  const [r, g, b] = memThemeAccentRgb;

  shockwaves.push({
    x: x, y: y,
    radius: 5,
    maxRadius: 75 * memZoom,
    alpha: 0.9,
    decay: 0.04,
    color: `rgba(${r}, ${g}, ${b}, `
  });

  for(let i = 0; i < 60; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 2 + Math.random() * 8;
    corruptParticles.push({
      x: x + (Math.random() - 0.5) * 20,
      y: y + (Math.random() - 0.5) * 20,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      char: binaryChars[Math.floor(Math.random() * binaryChars.length)],
      alpha: 1,
      decay: 0.02 + Math.random() * 0.03,
      size: 9 + Math.random() * 8,
      color: Math.random() > 0.3 ? `rgba(${r}, ${g}, ${b}, ` : 'rgba(255, 255, 255, '
    });
  }
}

/* FULLY RANDOM PROCEDURAL MEMORY SYNTHESIS */
function synthesizeHundredMemories(e) {
  if(e) e.stopPropagation();
  if(!activePersona) return;

  showToast('✨ Synthesizing 105 random neural memories...');

  const topics = [
    'Echoes of Dialogue', 'Philosophy Anchor', 'Cognitive Resonance', 'Aesthetic Sync',
    'Midnight Milestone', 'Creative Insight', 'Empathy Vector', 'Metaphor Synthesis',
    'Curiosity Spark', 'Logical Deduction', 'Episodic Imprint', 'Subconscious Thread',
    'Linguistic Cadence', 'Stylistic Harmony', 'Shared Perspective', 'Intuition Lattice',
    'Associative Drift', 'Memory Shard', 'Emotional Texture', 'Dialectical Flux'
  ];

  const count = 105;
  const startIdx = memNodes.length;

  for(let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const dist = 120 + Math.random() * 1500;
    const nx = Math.round(Math.cos(angle) * dist + (Math.random() - 0.5) * 120);
    const ny = Math.round(Math.sin(angle) * dist + (Math.random() - 0.5) * 120);
    const nid = `mem_synth_${startIdx + i}_${Date.now()}`;
    const topic = topics[Math.floor(Math.random() * topics.length)];

    const newNode = {
      id: nid,
      x: nx,
      y: ny,
      type: 'memory',
      title: `${topic} #${startIdx + i}`,
      subtitle: `Random Shard`,
      bloomDelay: Math.min(850, i * 7),
      detail: {
        title: `${topic} #${startIdx + i}`,
        sub: 'Random Neural Shard',
        content: `Random memory shard anchor #${startIdx + i}: Formed organic synaptic cluster across infinite coordinate plane.`
      }
    };

    memNodes.push(newNode);

    const randomParentIdx = Math.floor(Math.random() * (memNodes.length - 1));
    const targetParent = memNodes[randomParentIdx].id;
    memConnections.push([targetParent, nid]);
  }

  saveCharacterMemories(activePersona.id);
  buildMemNodesDOM();
  showToast(`⚡ Generated 105 random memory panels across infinite map`);
}

/* DRAGGABLE & CUSTOM RESIZABLE MINI WINDOW */
const miniHeader = $('memMiniHeader');
const miniWinEl = $('memMiniWindow');
const miniResizer = $('memMiniResizer');

miniHeader.addEventListener('mousedown', e => {
  if(e.target.closest('.mem-mini-btn')) return;
  miniWinDragging = true;
  miniWinOffsetX = e.clientX - miniWinEl.offsetLeft;
  miniWinOffsetY = e.clientY - miniWinEl.offsetTop;
});

window.addEventListener('mousemove', e => {
  if(miniWinDragging) {
    const left = Math.max(10, Math.min(window.innerWidth - 80, e.clientX - miniWinOffsetX));
    const top = Math.max(10, Math.min(window.innerHeight - 80, e.clientY - miniWinOffsetY));
    miniWinEl.style.left = left + 'px';
    miniWinEl.style.top = top + 'px';
  } else if(miniWinResizing) {
    const newW = Math.max(260, Math.min(window.innerWidth - 20, miniWinStartW + (e.clientX - miniWinStartX)));
    const newH = Math.max(180, Math.min(window.innerHeight - 20, miniWinStartH + (e.clientY - miniWinStartY)));
    miniWinEl.style.width = newW + 'px';
    miniWinEl.style.height = newH + 'px';
  }
});

window.addEventListener('mouseup', () => {
  miniWinDragging = false;
  miniWinResizing = false;
});

miniResizer.addEventListener('pointerdown', e => {
  e.stopPropagation();
  e.preventDefault();
  miniWinResizing = true;
  miniWinStartW = miniWinEl.offsetWidth;
  miniWinStartH = miniWinEl.offsetHeight;
  miniWinStartX = e.clientX;
  miniWinStartY = e.clientY;
  miniResizer.setPointerCapture(e.pointerId);
});

miniResizer.addEventListener('pointermove', e => {
  if(!miniWinResizing) return;
  const newW = Math.max(260, Math.min(window.innerWidth - 20, miniWinStartW + (e.clientX - miniWinStartX)));
  const newH = Math.max(180, Math.min(window.innerHeight - 20, miniWinStartH + (e.clientY - miniWinStartY)));
  miniWinEl.style.width = newW + 'px';
  miniWinEl.style.height = newH + 'px';
});

miniResizer.addEventListener('pointerup', () => { miniWinResizing = false; });

miniHeader.addEventListener('touchstart', e => {
  if(e.target.closest('.mem-mini-btn')) return;
  if(e.touches.length === 1) {
    miniWinDragging = true;
    miniWinOffsetX = e.touches[0].clientX - miniWinEl.offsetLeft;
    miniWinOffsetY = e.touches[0].clientY - miniWinEl.offsetTop;
  }
}, { passive: true });

window.addEventListener('touchmove', e => {
  if(!miniWinDragging || e.touches.length !== 1) return;
  const left = Math.max(10, Math.min(window.innerWidth - 80, e.touches[0].clientX - miniWinOffsetX));
  const top = Math.max(10, Math.min(window.innerHeight - 80, e.touches[0].clientY - miniWinOffsetY));
  miniWinEl.style.left = left + 'px';
  miniWinEl.style.top = top + 'px';
}, { passive: true });

window.addEventListener('touchend', () => { miniWinDragging = false; });

/* ANIMATION LOOP */
function memLoop() {
  if(!$('memoryTreeModal').classList.contains('open')) return;

  memCtx.clearRect(0, 0, memW, memH);

  const elapsed = Date.now() - memGrowthStartTime;
  memGrowthProgress = Math.min(1, elapsed / 1100);

  const [r, g, b] = memThemeAccentRgb;

  const grad = memCtx.createRadialGradient(memW / 2, memH / 2, 0, memW / 2, memH / 2, Math.max(memW, memH) * 0.75);
  grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.12)`);
  grad.addColorStop(0.5, `rgba(${Math.round(r * 0.5)}, ${Math.round(g * 0.5)}, ${Math.round(b * 0.5)}, 0.05)`);
  grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
  memCtx.fillStyle = grad;
  memCtx.fillRect(0, 0, memW, memH);

  const now = Date.now();
  for(const s of memStars) {
    const sx = s.x * memZoom + memOffsetX + memW / 2;
    const sy = s.y * memZoom + memOffsetY + memH / 2;
    if(sx < -10 || sx > memW + 10 || sy < -10 || sy > memH + 10) continue;

    const twinkle = Math.sin(now * s.twinkleSpeed * 0.001 + s.twinklePhase);
    const alpha = Math.max(0.1, Math.min(0.8, s.baseBright + twinkle * 0.25));
    const sz = Math.max(0.4, s.size * memZoom * 0.6);

    memCtx.beginPath();
    memCtx.arc(sx, sy, sz, 0, Math.PI * 2);
    memCtx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
    memCtx.fill();
  }

  memCtx.lineWidth = 1.6;
  const pTime = now * 0.0008;

  for(const [fid, tid] of memConnections) {
    const from = memNodes.find(n => n.id === fid);
    const to = memNodes.find(n => n.id === tid);
    if(!from || !to) continue;

    const s1 = memW2S(from.x, from.y);
    const s2 = memW2S(to.x, to.y);

    const branchProgress = Math.min(1, memGrowthProgress * 1.25);
    const endX = s1.x + (s2.x - s1.x) * branchProgress;
    const endY = s1.y + (s2.y - s1.y) * branchProgress;

    const midX = (s1.x + endX) / 2 + Math.sin(from.x + pTime) * 12 * memZoom;
    const midY = (s1.y + endY) / 2 + Math.cos(to.y + pTime) * 12 * memZoom;

    const lGrad = memCtx.createLinearGradient(s1.x, s1.y, endX, endY);
    lGrad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.35)`);
    lGrad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0.75)`);
    memCtx.strokeStyle = lGrad;

    memCtx.beginPath();
    memCtx.moveTo(s1.x, s1.y);
    memCtx.quadraticCurveTo(midX, midY, endX, endY);
    memCtx.stroke();

    if(branchProgress < 1) {
      memCtx.beginPath();
      memCtx.arc(endX, endY, 3.2 * memZoom, 0, Math.PI * 2);
      memCtx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.95)`;
      memCtx.fill();
    } else {
      const pulsePos = (pTime + (from.x * 0.002)) % 1;
      const t = pulsePos;
      const px = Math.pow(1 - t, 2) * s1.x + 2 * (1 - t) * t * midX + Math.pow(t, 2) * s2.x;
      const py = Math.pow(1 - t, 2) * s1.y + 2 * (1 - t) * t * midY + Math.pow(t, 2) * s2.y;
      
      memCtx.beginPath();
      memCtx.arc(px, py, 2.6 * memZoom, 0, Math.PI * 2);
      memCtx.fillStyle = `rgba(255, 255, 255, 0.9)`;
      memCtx.fill();
    }
  }

  // Render Shockwaves
  for(let i = shockwaves.length - 1; i >= 0; i--) {
    const sw = shockwaves[i];
    sw.radius += 2.5;
    sw.alpha -= sw.decay;
    if(sw.alpha <= 0 || sw.radius >= sw.maxRadius) {
      shockwaves.splice(i, 1);
      continue;
    }
    memCtx.beginPath();
    memCtx.arc(sw.x, sw.y, sw.radius, 0, Math.PI * 2);
    memCtx.strokeStyle = sw.color + sw.alpha + ')';
    memCtx.lineWidth = 2.5;
    memCtx.stroke();
  }

  // Render Binary Particles
  if(corruptParticles.length > 0) {
    memCtx.font = 'bold 11px monospace';
    for(let i = corruptParticles.length - 1; i >= 0; i--) {
      const p = corruptParticles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.alpha -= p.decay;

      if(p.alpha <= 0) {
        corruptParticles.splice(i, 1);
        continue;
      }

      memCtx.fillStyle = p.color + p.alpha + ')';
      memCtx.fillText(p.char, p.x, p.y);
    }
  }

  memAnimationId = requestAnimationFrame(memLoop);
}

/* TOUCH & PAN / PINCH */
const memVP = $('memViewport');

memVP.addEventListener('mousedown', e => {
  if(e.target.closest('#memDetailPanel') || e.target.closest('#memMiniWindow') || e.target.closest('.mem-hud-top')) return;
  memDragging = true;
  memLastX = e.clientX;
  memLastY = e.clientY;
});

window.addEventListener('mousemove', e => {
  if(!memDragging) return;
  memOffsetX += e.clientX - memLastX;
  memOffsetY += e.clientY - memLastY;
  memLastX = e.clientX;
  memLastY = e.clientY;
  updateMemTransform();
});

window.addEventListener('mouseup', () => { memDragging = false; });

memVP.addEventListener('touchstart', e => {
  if(e.target.closest('#memDetailPanel') || e.target.closest('#memMiniWindow') || e.target.closest('.mem-hud-top')) return;
  if(e.touches.length === 1) {
    memDragging = true;
    memLastX = e.touches[0].clientX;
    memLastY = e.touches[0].clientY;
  } else if(e.touches.length === 2) {
    memDragging = false;
    memPinchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
  }
}, { passive: true });

memVP.addEventListener('touchmove', e => {
  if(e.touches.length === 1 && memDragging) {
    memOffsetX += e.touches[0].clientX - memLastX;
    memOffsetY += e.touches[0].clientY - memLastY;
    memLastX = e.touches[0].clientX;
    memLastY = e.touches[0].clientY;
    updateMemTransform();
  } else if(e.touches.length === 2 && memPinchDist > 0) {
    const newDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
    const factor = newDist / memPinchDist;
    memPinchDist = newDist;
    const mx = (e.touches[0].clientX + e.touches[1].clientX) / 2;
    const my = (e.touches[0].clientY + e.touches[1].clientY) / 2;
    const rect = memVP.getBoundingClientRect();
    setMemZoom(memZoom * factor, mx - rect.left, my - rect.top);
  }
}, { passive: true });

memVP.addEventListener('touchend', () => {
  memDragging = false;
  memPinchDist = 0;
});

memVP.addEventListener('wheel', e => {
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.92 : 1.08;
  const rect = memVP.getBoundingClientRect();
  setMemZoom(memZoom * factor, e.clientX - rect.left, e.clientY - rect.top);
}, { passive: false });

/* ==========================================================================
   COMPANION SUITE: GEMINI LIVE MULTIMODAL ENGINE, VOICE & VISION
   ========================================================================== */

function appendChatMsg(role, text, imgData = null) {
  if (!activePersona) return;
  if (!chatMessages[activePersona.id]) chatMessages[activePersona.id] = [];
  const msgObj = { role, text };
  if (imgData) msgObj.image_data = imgData;
  chatMessages[activePersona.id].push(msgObj);
  localStorage.setItem('bot_saas_history', JSON.stringify(chatMessages));
  renderChatBox();
}

/* --------------------------------------------------------------------------
   GEMINI LIVE MULTIMODAL WEBSOCKET ENGINE (BIDIRECTIONAL AUDIO + VISION)
   -------------------------------------------------------------------------- */
class GeminiLiveAudioPlayer {
  constructor() {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    this.ctx = AudioCtx ? new AudioCtx({ sampleRate: 24000 }) : null;
    this.nextPlayTime = 0;
    this.activeSources = [];
  }

  playChunk(base64PcmData) {
    if (!this.ctx) return;
    try {
      if (this.ctx.state === 'suspended') {
        this.ctx.resume();
      }
      const raw = atob(base64PcmData);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

      const int16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / (int16[i] < 0 ? 32768 : 32767);
      }

      const buffer = this.ctx.createBuffer(1, float32.length, 24000);
      buffer.copyToChannel(float32, 0);

      const source = this.ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(this.ctx.destination);

      const currentTime = this.ctx.currentTime;
      if (this.nextPlayTime < currentTime) {
        this.nextPlayTime = currentTime;
      }
      source.start(this.nextPlayTime);
      this.nextPlayTime += buffer.duration;

      this.activeSources.push(source);
      source.onended = () => {
        const idx = this.activeSources.indexOf(source);
        if (idx >= 0) this.activeSources.splice(idx, 1);
      };
    } catch(err) {
      console.warn('Gemini Live PCM audio decode error:', err);
    }
  }

  stop() {
    this.activeSources.forEach(s => {
      try { s.stop(); } catch(e) {}
    });
    this.activeSources = [];
    if (this.ctx) {
      this.nextPlayTime = this.ctx.currentTime;
    }
  }
}

class GeminiLiveSession {
  constructor(apiKey, systemPrompt, voiceName = 'Aoede', callbacks = {}) {
    this.apiKey = apiKey;
    this.systemPrompt = systemPrompt;
    this.voiceName = voiceName;
    this.onAudioChunk = callbacks.onAudioChunk;
    this.onTextChunk = callbacks.onTextChunk;
    this.onInterrupted = callbacks.onInterrupted;
    this.onStatusChange = callbacks.onStatusChange;
    this.ws = null;
    this.isConnected = false;
    this.inputAudioContext = null;
    this.scriptProcessor = null;
    this.mediaStream = null;
  }

  async connect(mediaStream = null) {
    this.mediaStream = mediaStream;
    const url = `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key=${this.apiKey}`;
    
    if (this.onStatusChange) this.onStatusChange('Connecting to Gemini Live...');
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.isConnected = true;
      if (this.onStatusChange) this.onStatusChange('Gemini Live Connected');
      this.sendSetup();
      if (this.mediaStream) {
        this.startStreamingMicAudio(this.mediaStream);
      }
    };

    this.ws.onmessage = async (event) => {
      let data = event.data;
      if (data instanceof Blob) {
        data = await data.text();
      }
      try {
        const msg = JSON.parse(data);
        this.handleMessage(msg);
      } catch(e) {
        console.warn('Gemini Live message parse error:', e);
      }
    };

    this.ws.onerror = (err) => {
      console.warn('Gemini Live WebSocket error:', err);
      if (this.onStatusChange) this.onStatusChange('Gemini Live Connection Failed');
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      if (this.onStatusChange) this.onStatusChange('Gemini Live Disconnected');
      this.cleanup();
    };
  }

  sendSetup() {
    const setupMsg = {
      setup: {
        model: "models/gemini-2.0-flash-exp",
        generation_config: {
          response_modalities: ["AUDIO", "TEXT"],
          speech_config: {
            voice_config: {
              prebuilt_voice_config: {
                voice_name: this.voiceName || "Aoede"
              }
            }
          }
        },
        system_instruction: {
          parts: [{ text: this.systemPrompt || "You are an engaging, lively live companion." }]
        }
      }
    };
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(setupMsg));
    }
  }

  startStreamingMicAudio(stream) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.inputAudioContext = new AudioCtx({ sampleRate: 16000 });
      const source = this.inputAudioContext.createMediaStreamSource(stream);
      this.scriptProcessor = this.inputAudioContext.createScriptProcessor(4096, 1, 1);

      this.scriptProcessor.onaudioprocess = (e) => {
        if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        const base64Pcm = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
        const realtimeChunk = {
          realtime_input: {
            media_chunks: [
              {
                mime_type: "audio/pcm;rate=16000",
                data: base64Pcm
              }
            ]
          }
        };
        this.ws.send(JSON.stringify(realtimeChunk));
      };

      source.connect(this.scriptProcessor);
      this.scriptProcessor.connect(this.inputAudioContext.destination);
    } catch(err) {
      console.warn('Gemini Live mic streaming setup error:', err);
    }
  }

  sendImageFrame(base64JpegData) {
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const cleanBase64 = base64JpegData.replace(/^data:image\/\w+;base64,/, '');
    const videoChunk = {
      realtime_input: {
        media_chunks: [
          {
            mime_type: "image/jpeg",
            data: cleanBase64
          }
        ]
      }
    };
    this.ws.send(JSON.stringify(videoChunk));
  }

  sendText(text) {
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const textMsg = {
      client_content: {
        turns: [
          {
            role: "user",
            parts: [{ text: text }]
          }
        ],
        turn_complete: true
      }
    };
    this.ws.send(JSON.stringify(textMsg));
  }

  handleMessage(msg) {
    if (msg.server_content) {
      const { model_turn, turn_complete, interrupted } = msg.server_content;
      if (interrupted && this.onInterrupted) {
        this.onInterrupted();
      }
      if (model_turn && model_turn.parts) {
        for (const part of model_turn.parts) {
          if (part.text && this.onTextChunk) {
            this.onTextChunk(part.text);
          }
          if (part.inline_data && part.inline_data.data && this.onAudioChunk) {
            this.onAudioChunk(part.inline_data.data, part.inline_data.mime_type);
          }
        }
      }
    }
  }

  cleanup() {
    if (this.scriptProcessor) {
      try { this.scriptProcessor.disconnect(); } catch(e) {}
      this.scriptProcessor = null;
    }
    if (this.inputAudioContext) {
      try { this.inputAudioContext.close(); } catch(e) {}
      this.inputAudioContext = null;
    }
    if (this.ws) {
      try { this.ws.close(); } catch(e) {}
      this.ws = null;
    }
    this.isConnected = false;
  }
}

let activeGeminiLiveSession = null;
let activeGeminiLivePlayer = null;

let voiceCallActive = false;
let voiceRecognition = null;
let voiceMicMuted = false;
let voiceSpeakerMuted = false;
let voiceWaveAnimId = null;
let voiceVadSilenceTimer = null;
let voiceCurrentTranscript = '';
let isProcessingVoiceTurn = false;
let activeUtterance = null;
let voiceWatchdogTimer = null;
let cachedBrowserVoices = [];

let voiceAudioCtx = null;
let voiceAnalyser = null;
let voiceMicStream = null;
let voiceAudioDataArray = null;
let isVoicePushToTalkRecording = false;

function initVoiceVoices() {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    cachedBrowserVoices = window.speechSynthesis.getVoices() || [];
    window.speechSynthesis.onvoiceschanged = () => {
      cachedBrowserVoices = window.speechSynthesis.getVoices() || [];
    };
  }
}
initVoiceVoices();

async function requestMicrophoneStream() {
  if (voiceMicStream && voiceMicStream.active && voiceMicStream.getAudioTracks().some(t => t.readyState === 'live')) {
    return voiceMicStream;
  }

  // 1. Modern Standard getUserMedia
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    try {
      voiceMicStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      return voiceMicStream;
    } catch(err) {
      console.warn('getUserMedia error:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        const cap = $('voiceCaptionBox');
        if (cap) cap.innerHTML = '<span style="color:#e06c75; font-weight:600;">⚠️ Microphone access was denied. Please allow microphone permission in your browser site settings.</span>';
        showToast('⚠️ Microphone permission denied');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        showToast('⚠️ No microphone device found');
      } else {
        showToast('⚠️ Microphone error: ' + (err.message || err.name));
      }
      throw err;
    }
  }

  // 2. Legacy getUserMedia Fallback
  const legacyGetUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.msGetUserMedia;
  if (legacyGetUserMedia) {
    return new Promise((resolve, reject) => {
      legacyGetUserMedia.call(navigator, { audio: true }, (stream) => {
        voiceMicStream = stream;
        resolve(stream);
      }, (err) => {
        showToast('⚠️ Microphone permission error');
        reject(err);
      });
    });
  }

  const cap = $('voiceCaptionBox');
  if (cap) cap.innerHTML = '<span style="color:#e06c75; font-weight:600;">⚠️ Microphone API requires HTTPS or http://localhost (or 127.0.0.1).</span>';
  showToast('⚠️ Microphone requires HTTPS or localhost');
  throw new Error('Microphone not supported on insecure HTTP origin');
}

async function initRealMicAudio() {
  const stream = await requestMicrophoneStream();
  if (!stream) return;
  
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      if (!voiceAudioCtx || voiceAudioCtx.state === 'closed') {
        voiceAudioCtx = new AudioContextClass();
      }
      if (voiceAudioCtx.state === 'suspended') {
        await voiceAudioCtx.resume();
      }
      const source = voiceAudioCtx.createMediaStreamSource(stream);
      voiceAnalyser = voiceAudioCtx.createAnalyser();
      voiceAnalyser.fftSize = 128;
      source.connect(voiceAnalyser);
      voiceAudioDataArray = new Uint8Array(voiceAnalyser.frequencyBinCount);
    }
  } catch(e) {
    console.warn('Real mic audio visualizer setup notice:', e);
  }
}

function initVoiceRecognition() {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) {
    console.warn('Web Speech Recognition not supported in this browser');
    return null;
  }
  const rec = new SpeechRec();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = 'en-US';

  rec.onresult = (event) => {
    if (voiceMicMuted || isProcessingVoiceTurn) return;
    let interim = '';
    let final = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        final += event.results[i][0].transcript;
      } else {
        interim += event.results[i][0].transcript;
      }
    }
    const current = (final || interim || '').trim();
    if (!current) return;

    voiceCurrentTranscript = current;
    const captionEl = $('voiceCaptionBox');
    if (captionEl) {
      captionEl.innerHTML = `<span style="opacity:0.6; font-size:12px; display:block; margin-bottom:2px;">🎤 Hearing you:</span> ${escapeHtml(current)}`;
    }

    // Ultra-Fast Smart VAD: 700ms silence after speech automatically submits
    if (!isVoicePushToTalkRecording) {
      if (voiceVadSilenceTimer) clearTimeout(voiceVadSilenceTimer);
      voiceVadSilenceTimer = setTimeout(() => {
        if (voiceCurrentTranscript && voiceCurrentTranscript.length > 1 && !isProcessingVoiceTurn) {
          triggerManualVoiceSend();
        }
      }, 700);
    }
  };

  rec.onerror = (e) => {
    console.warn('Voice recognition event:', e.error);
    if (e.error === 'not-allowed') {
      showToast('Microphone permission required for voice');
    } else if (e.error === 'no-speech') {
      // Normal silence, keep listening
    }
  };

  rec.onend = () => {
    if (voiceCallActive && !voiceMicMuted && !isProcessingVoiceTurn && !activeGeminiLiveSession) {
      try { rec.start(); } catch(e) {}
    }
  };

  return rec;
}

let voiceMediaRecorder = null;
let voiceMediaChunks = [];
let isVoiceRecordingAudio = false;

async function startVoiceMediaRecording() {
  try {
    const stream = await requestMicrophoneStream();
    if (!stream) return;
    voiceMediaChunks = [];
    isVoiceRecordingAudio = true;
    const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus', ''];
    let supportedMime = '';
    for (const m of mimeTypes) {
      if (!m || (window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m))) {
        supportedMime = m;
        break;
      }
    }
    const options = supportedMime ? { mimeType: supportedMime } : {};
    voiceMediaRecorder = new MediaRecorder(stream, options);
    voiceMediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) voiceMediaChunks.push(e.data);
    };
    voiceMediaRecorder.start(200);
  } catch(e) {
    console.warn('Voice MediaRecorder start notice:', e);
  }
}

async function stopVoiceMediaRecordingAndTranscribe() {
  if (!voiceMediaRecorder || voiceMediaRecorder.state === 'inactive') {
    isVoiceRecordingAudio = false;
    return null;
  }
  return new Promise((resolve) => {
    voiceMediaRecorder.onstop = async () => {
      isVoiceRecordingAudio = false;
      try {
        if (!voiceMediaChunks || voiceMediaChunks.length === 0) return resolve(null);
        const mime = voiceMediaRecorder.mimeType || 'audio/webm';
        const blob = new Blob(voiceMediaChunks, { type: mime });
        voiceMediaChunks = [];
        if (blob.size < 400) return resolve(null);

        const reader = new FileReader();
        reader.onloadend = async () => {
          try {
            const base64Audio = reader.result;
            const groqKey = (activePersona && activePersona.groq_key) || localStorage.getItem('groq_key') || '';
            const res = await fetch('/api/stt', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ audio: base64Audio, groq_key: groqKey, filename: 'voice_turn.webm' })
            });
            if (res.ok) {
              const data = await res.json();
              if (data && data.ok && data.text && data.text.trim()) {
                resolve(data.text.trim());
                return;
              }
            }
          } catch(err) {
            console.warn('Voice STT transcription error:', err);
          }
          resolve(null);
        };
        reader.readAsDataURL(blob);
      } catch(e) {
        resolve(null);
      }
    };
    try {
      voiceMediaRecorder.stop();
    } catch(e) {
      isVoiceRecordingAudio = false;
      resolve(null);
    }
  });
}

async function startVoiceCall() {
  if (!activePersona) {
    showToast('Select a persona first');
    return;
  }

  const modal = $('voiceCallModal');
  if (modal) modal.classList.add('active');

  $('voiceCallBotName').innerText = activePersona.name || 'Bot';
  $('voiceCallStatus').innerText = 'Connected • Listening';

  const avatarDisplay = renderAvatarHtml(activePersona.pfp, activePersona.name[0] || 'P', activePersona.color);
  $('voiceCallAvatar').innerHTML = avatarDisplay;
  $('voiceCaptionBox').innerHTML = `<em>Listening for your voice... speak anytime</em>`;

  const btn = $('voiceTalkBtn');
  const label = $('voiceTalkBtnLabel');
  if (btn) btn.classList.remove('recording');
  if (label) label.innerText = '🎙️ Tap to Speak';

  const micBtn = $('voiceMicToggleBtn');
  if (micBtn) {
    micBtn.classList.remove('muted');
    micBtn.innerText = '🎙️';
  }

  voiceCallActive = true;
  voiceMicMuted = false;
  voiceSpeakerMuted = false;
  isProcessingVoiceTurn = false;
  voiceCurrentTranscript = '';
  isVoicePushToTalkRecording = false;

  try {
    if ('speechSynthesis' in window) window.speechSynthesis.resume();
  } catch(e) {}

  // Request mic permission directly in user gesture
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        voiceMicStream = stream;
        initRealMicAudio();
        startVoiceWaveform();
        if (!voiceRecognition) voiceRecognition = initVoiceRecognition();
        if (voiceRecognition && voiceCallActive && !voiceMicMuted) {
          try { voiceRecognition.start(); } catch(e) {}
        }
      })
      .catch(err => {
        console.warn('Microphone permission request:', err);
        alert("Microphone Error: " + err.name + "\n\nIf you denied the permission, you need to go to browser Site Settings to unblock it.");
        $('voiceCallStatus').innerText = 'Mic Muted • Tap 🎙️ to Allow';
        const cap = $('voiceCaptionBox');
        if (cap) cap.innerHTML = `<em>Tap the <strong>🎙️</strong> button below to allow microphone access.</em>`;
        const micBtn = $('voiceMicToggleBtn');
        if (micBtn) {
          micBtn.classList.add('muted');
          micBtn.innerText = '🔇';
        }
      });
  } else {
    alert("❌ BROWSER SECURITY BLOCK ❌\n\nAndroid Chrome completely blocks the microphone permission popup when opening local files (file://) or HTTP IP addresses.\n\nTo allow the microphone popup to appear, you MUST run the server and open:\nhttp://localhost:5000");
    initRealMicAudio().catch(e => console.error(e));
  }

  showToast(`📞 Voice call connected with ${activePersona.name}`);
}

function endVoiceCall() {
  voiceCallActive = false;
  isProcessingVoiceTurn = false;
  isVoicePushToTalkRecording = false;
  if (voiceVadSilenceTimer) clearTimeout(voiceVadSilenceTimer);
  if (voiceWatchdogTimer) clearTimeout(voiceWatchdogTimer);

  if (activeGeminiLiveSession) {
    activeGeminiLiveSession.cleanup();
    activeGeminiLiveSession = null;
  }
  if (activeGeminiLivePlayer) {
    activeGeminiLivePlayer.stop();
    activeGeminiLivePlayer = null;
  }

  const modal = $('voiceCallModal');
  if (modal) modal.classList.remove('active');

  if (voiceRecognition) {
    try { voiceRecognition.stop(); } catch(e) {}
  }
  if (voiceMediaRecorder && voiceMediaRecorder.state !== 'inactive') {
    try { voiceMediaRecorder.stop(); } catch(e) {}
  }
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  if (voiceMicStream) {
    voiceMicStream.getTracks().forEach(t => t.stop());
    voiceMicStream = null;
  }
  if (voiceAudioCtx) {
    try { voiceAudioCtx.close(); } catch(e) {}
    voiceAudioCtx = null;
  }
  activeUtterance = null;
  if (currentPlayingAudio) {
    try { currentPlayingAudio.pause(); } catch(e) {}
    currentPlayingAudio = null;
  }
  if (voiceWaveAnimId) {
    cancelAnimationFrame(voiceWaveAnimId);
    voiceWaveAnimId = null;
  }
  const halo = $('voiceAvatarHalo');
  if (halo) halo.classList.remove('speaking');

  showToast('Call ended');
}

async function handleVoicePushToTalk() {
  const btn = $('voiceTalkBtn');
  const label = $('voiceTalkBtnLabel');
  if (isProcessingVoiceTurn) {
    showToast('AI is speaking or thinking...');
    return;
  }

  if (!isVoicePushToTalkRecording) {
    // Start speaking turn
    isVoicePushToTalkRecording = true;
    if (btn) btn.classList.add('recording');
    if (label) label.innerText = '✓ Done Speaking';
    $('voiceCallStatus').innerText = '🔴 Recording Speech... Speak now';
    voiceCurrentTranscript = '';
    
    // Start real audio recording stream
    await startVoiceMediaRecording();

    if (!voiceRecognition) voiceRecognition = initVoiceRecognition();
    if (voiceRecognition) {
      try { voiceRecognition.start(); } catch(e) {}
    }
    showToast('🎙️ Listening... Tap again when finished speaking');
  } else {
    // Stop speaking turn & commit
    isVoicePushToTalkRecording = false;
    if (btn) btn.classList.remove('recording');
    if (label) label.innerText = '🎙️ Tap to Speak';
    $('voiceCallStatus').innerText = 'Processing Speech...';

    // Check transcribed text from Whisper + SpeechRecognition
    const sttResult = await stopVoiceMediaRecordingAndTranscribe();
    const finalSpeech = (sttResult && sttResult.trim()) || voiceCurrentTranscript.trim();
    
    if (finalSpeech && finalSpeech.length > 0) {
      voiceCurrentTranscript = '';
      handleVoiceUserInput(finalSpeech);
    } else {
      $('voiceCallStatus').innerText = 'Connected • Listening';
      const captionEl = $('voiceCaptionBox');
      if (captionEl) captionEl.innerHTML = `<em>Didn't catch that — tap to speak again anytime.</em>`;
      showToast('⚠️ No speech detected. Please speak louder into mic.');
    }
  }
}

async function toggleVoiceCallMic() {
  if (!voiceMicStream || !voiceMicStream.active) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("❌ BROWSER SECURITY BLOCK ❌\n\nAndroid Chrome completely blocks the microphone API when opening local files (file://) or HTTP IP addresses.\n\nTo allow the microphone popup to appear, you MUST run the server and open:\nhttp://localhost:5000");
      return;
    }
    try {
      showToast('Requesting mic permission...');
      voiceMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      voiceMicMuted = false;
      await initRealMicAudio();
      startVoiceWaveform();
      if (!voiceRecognition) voiceRecognition = initVoiceRecognition();
      if (voiceRecognition) try { voiceRecognition.start(); } catch(e) {}
      const btn = $('voiceMicToggleBtn');
      if (btn) {
        btn.classList.remove('muted');
        btn.innerText = '🎙️';
      }
      $('voiceCallStatus').innerText = 'Connected • Listening';
      const cap = $('voiceCaptionBox');
      if (cap) cap.innerHTML = `<em>Microphone enabled. Speak anytime.</em>`;
      showToast('🎙️ Microphone enabled');
      return;
    } catch(err) {
      console.warn('Mic toggle permission error:', err);
      alert("Microphone Error: " + err.name + "\n\nIf you denied the permission, go to Chrome Site Settings -> Microphone and allow it for this site.");
      showToast('⚠️ Microphone permission required');
      return;
    }
  }

  voiceMicMuted = !voiceMicMuted;
  if (voiceMicStream) {
    voiceMicStream.getAudioTracks().forEach(t => { t.enabled = !voiceMicMuted; });
  }
  const btn = $('voiceMicToggleBtn');
  if (btn) {
    btn.classList.toggle('muted', voiceMicMuted);
    btn.innerText = voiceMicMuted ? '🔇' : '🎙️';
  }
  if (voiceMicMuted && voiceRecognition) {
    try { voiceRecognition.stop(); } catch(e) {}
  } else if (!voiceMicMuted && voiceRecognition && voiceCallActive && !isProcessingVoiceTurn) {
    try { voiceRecognition.start(); } catch(e) {}
  }
  $('voiceCallStatus').innerText = voiceMicMuted ? 'Microphone Muted' : 'Connected • Listening';
  showToast(voiceMicMuted ? 'Microphone muted' : 'Microphone unmuted');
}

function toggleVoiceCallSpeaker() {
  voiceSpeakerMuted = !voiceSpeakerMuted;
  const btn = $('voiceSpeakerToggleBtn');
  if (btn) {
    btn.classList.toggle('muted', voiceSpeakerMuted);
    btn.innerText = voiceSpeakerMuted ? '🔈' : '🔊';
  }
  if (voiceSpeakerMuted && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  if (voiceSpeakerMuted && currentPlayingAudio) {
    try { currentPlayingAudio.pause(); } catch(e) {}
  }
  showToast(voiceSpeakerMuted ? 'Speaker muted' : 'Speaker unmuted');
}

async function triggerManualVoiceSend() {
  if (voiceVadSilenceTimer) clearTimeout(voiceVadSilenceTimer);
  let textToSend = voiceCurrentTranscript.trim();
  if (!textToSend && isVoiceRecordingAudio) {
    textToSend = (await stopVoiceMediaRecordingAndTranscribe()) || '';
  }
  if (!textToSend || isProcessingVoiceTurn) return;
  voiceCurrentTranscript = '';
  handleVoiceUserInput(textToSend);
}

async function handleVoiceUserInput(userText) {
  if (!userText || !activePersona) return;
  isProcessingVoiceTurn = true;
  if (voiceRecognition) {
    try { voiceRecognition.stop(); } catch(e) {}
  }

  $('voiceCallStatus').innerText = 'Thinking...';
  const captionEl = $('voiceCaptionBox');
  if (captionEl) {
    captionEl.innerHTML = `<span style="opacity:0.6; font-size:12px; display:block; margin-bottom:2px;">You:</span> ${escapeHtml(userText)}<div style="margin-top:6px; color:var(--accent); font-size:12px;"><em>Thinking...</em></div>`;
  }

  // Append user message to active chat history
  appendChatMsg('user', userText);

  try {
    // Build system prompt with memories
    const sysPrompt = buildSystemPromptWithUser(activePersona.prompt || activePersona.personality, activePersona.id);
    const history = (chatMessages[activePersona.id] || []).slice(0, -1);

    // Execute AI Request
    const res = await executeAiChatRequest(userText, sysPrompt, activePersona, history, null);
    const botReply = (res && res.reply) ? res.reply : "*listens attentively and nods*";

    // Append bot message to chat
    appendChatMsg('assistant', botReply);

    // Display and speak reply
    if (captionEl) {
      captionEl.innerHTML = `<span style="color:var(--accent); font-size:12px; display:block; margin-bottom:2px;">${escapeHtml(activePersona.name)}:</span> ${escapeHtml(botReply.replace(/[*_#`]/g, ''))}`;
    }

    $('voiceCallStatus').innerText = 'Speaking...';
    speakPersonaVoiceReply(botReply);
  } catch (err) {
    console.error('Voice call chat error:', err);
    $('voiceCallStatus').innerText = 'Connected • Listening';
    isProcessingVoiceTurn = false;
    if (voiceCallActive && !voiceMicMuted && voiceRecognition) {
      try { voiceRecognition.start(); } catch(e) {}
    }
  }
}

let currentPlayingAudio = null;

async function synthesizeCustomTTSAudio(text, persona) {
  if (!persona) return null;
  const cfg = persona.config || persona.settings || {};
  const ep = (typeof getCustomEndpointConfig === 'function') ? getCustomEndpointConfig() : {};

  const cleanText = text
    .replace(/\*[^*]*\*/g, '')
    .replace(/[*_#`~>\[\]()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim() || text.replace(/[*_#`~>\[\]()]/g, ' ').trim();

  if (!cleanText) return null;

  const ttsProvider = (cfg.tts_provider || persona.tts_provider || 'auto').toLowerCase();
  const fishVoiceId = cfg.fish_voice_id || persona.fish_voice_id || cfg.voice_id || '';
  const elevenVoiceId = cfg.elevenlabs_voice_id || persona.elevenlabs_voice_id || cfg.voice_id || '';
  const cartesiaVoiceId = cfg.cartesia_voice_id || persona.cartesia_voice_id || '';
  const openaiVoice = cfg.openai_voice || persona.openai_voice || 'nova';

  const elevenKey = cfg.elevenlabs_key || ep.elevenlabs_key || '';
  const fishKey = cfg.fish_key || ep.fish_key || '';
  const cartesiaKey = cfg.cartesia_key || ep.cartesia_key || '';
  const openaiKey = cfg.openai_key || ep.openai_key || '';

  // 1. ELEVENLABS TTS API
  if ((ttsProvider === 'elevenlabs' || elevenVoiceId) && (elevenKey || elevenVoiceId)) {
    try {
      const vId = elevenVoiceId || '21m00Tcm4TlvDq8ikWAM';
      const keyToUse = elevenKey || 'sk_mock';
      const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${vId}`, {
        method: 'POST',
        headers: {
          'xi-api-key': keyToUse,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: cleanText.slice(0, 1000),
          model_id: cfg.elevenlabs_model || 'eleven_turbo_v2_5'
        })
      });
      if (res.ok) {
        const blob = await res.blob();
        return URL.createObjectURL(blob);
      }
    } catch(e) { console.warn('ElevenLabs API error:', e); }
  }

  // 2. FISH AUDIO TTS API
  if ((ttsProvider === 'fish' || fishVoiceId) && (fishKey || fishVoiceId)) {
    try {
      const res = await fetch('https://api.fish.audio/v1/tts', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${fishKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          text: cleanText.slice(0, 1000),
          reference_id: fishVoiceId || undefined,
          format: 'mp3'
        })
      });
      if (res.ok) {
        const blob = await res.blob();
        return URL.createObjectURL(blob);
      }
    } catch(e) { console.warn('Fish Audio API error:', e); }
  }

  // 3. CARTESIA TTS API
  if ((ttsProvider === 'cartesia' || cartesiaVoiceId) && cartesiaKey) {
    try {
      const res = await fetch('https://api.cartesia.ai/tts/bytes', {
        method: 'POST',
        headers: {
          'X-API-Key': cartesiaKey,
          'Cartesia-Version': '2024-06-10',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model_id: cfg.cartesia_model || 'sonic-3.5',
          transcript: cleanText.slice(0, 1000),
          voice: { mode: 'id', id: cartesiaVoiceId || 'a0e99841-438c-4a64-b679-ae501e7d6091' },
          output_format: { container: 'raw', encoding: 'pcm_f32le', sample_rate: 44100 }
        })
      });
      if (res.ok) {
        const blob = await res.blob();
        return URL.createObjectURL(blob);
      }
    } catch(e) { console.warn('Cartesia API error:', e); }
  }

  // 4. OPENAI TTS API
  if ((ttsProvider === 'openai') && openaiKey) {
    try {
      const res = await fetch('https://api.openai.com/v1/audio/speech', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${openaiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: cfg.openai_model || 'tts-1',
          voice: openaiVoice,
          input: cleanText.slice(0, 1000)
        })
      });
      if (res.ok) {
        const blob = await res.blob();
        return URL.createObjectURL(blob);
      }
    } catch(e) { console.warn('OpenAI TTS API error:', e); }
  }

  return null;
}

async function speakPersonaVoiceReply(text) {
  if (voiceSpeakerMuted || !text) {
    $('voiceCallStatus').innerText = 'Connected • Listening';
    isProcessingVoiceTurn = false;
    if (voiceCallActive && !voiceMicMuted && voiceRecognition) {
      try { voiceRecognition.start(); } catch(e) {}
    }
    return;
  }

  // Stop any previous playing audio
  if (currentPlayingAudio) {
    try { currentPlayingAudio.pause(); } catch(e) {}
    currentPlayingAudio = null;
  }
  if ('speechSynthesis' in window) {
    try { window.speechSynthesis.cancel(); } catch(e) {}
  }

  const halo = $('voiceAvatarHalo');
  const onSpeechDone = () => {
    if (voiceWatchdogTimer) clearTimeout(voiceWatchdogTimer);
    if (halo) halo.classList.remove('speaking');
    $('voiceCallStatus').innerText = 'Connected • Listening';
    isProcessingVoiceTurn = false;
    activeUtterance = null;
    currentPlayingAudio = null;
    if (voiceCallActive && !voiceMicMuted && voiceRecognition) {
      try { voiceRecognition.start(); } catch(e) {}
    }
  };

  // Strip Markdown characters, actions *...*, and emojis for clean spoken speech
  const cleanSpoken = text
    .replace(/\*[^*]*\*/g, '')
    .replace(/[*_#`~>\[\]()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim() || text.replace(/[*_#`~>\[\]()]/g, ' ').trim();

  if (!cleanSpoken) {
    onSpeechDone();
    return;
  }

  // 1. Try Custom TTS API from bot settings (Fish Audio / ElevenLabs / Cartesia / OpenAI)
  try {
    const customAudioUrl = await synthesizeCustomTTSAudio(cleanSpoken, activePersona);
    if (customAudioUrl) {
      if (halo) halo.classList.add('speaking');
      $('voiceCallStatus').innerText = 'Speaking (Custom Voice)...';

      const audio = new Audio(customAudioUrl);
      currentPlayingAudio = audio;
      audio.onended = () => {
        URL.revokeObjectURL(customAudioUrl);
        onSpeechDone();
      };
      audio.onerror = () => {
        URL.revokeObjectURL(customAudioUrl);
        onSpeechDone();
      };

      if (voiceWatchdogTimer) clearTimeout(voiceWatchdogTimer);
      voiceWatchdogTimer = setTimeout(onSpeechDone, 30000);

      await audio.play();
      return;
    }
  } catch(err) {
    console.warn('Custom TTS playback error, falling back to Web Speech:', err);
  }

  // 2. Fallback to Web Speech API
  if (!('speechSynthesis' in window)) {
    onSpeechDone();
    return;
  }

  try {
    window.speechSynthesis.resume();
  } catch(e) {}

  activeUtterance = new SpeechSynthesisUtterance(cleanSpoken);
  activeUtterance.rate = 1.05;
  activeUtterance.pitch = 1.0;

  // Pick suitable voice from cached list
  const voices = cachedBrowserVoices.length > 0 ? cachedBrowserVoices : (window.speechSynthesis.getVoices() || []);
  if (voices.length > 0) {
    const pName = (activePersona.name || '').toLowerCase();
    const isFemale = pName.includes('yuna') || pName.includes('maiko') || pName.includes('nene') || pName.includes('lucy') || pName.includes('teto');
    const match = voices.find(v => isFemale ? (v.name.includes('Female') || v.name.includes('Samantha') || v.name.includes('Google US English') || v.name.includes('Zira') || v.lang.startsWith('en')) : (v.name.includes('Male') || v.name.includes('David') || v.lang.startsWith('en')));
    if (match) activeUtterance.voice = match;
  }

  if (halo) halo.classList.add('speaking');
  $('voiceCallStatus').innerText = 'Speaking...';

  activeUtterance.onend = onSpeechDone;
  activeUtterance.onerror = onSpeechDone;

  // Watchdog timer guarantees that listening state resumes even if browser drops onend
  if (voiceWatchdogTimer) clearTimeout(voiceWatchdogTimer);
  const maxSpeechTime = Math.max(3500, Math.min(30000, cleanSpoken.length * 90));
  voiceWatchdogTimer = setTimeout(onSpeechDone, maxSpeechTime);

  try {
    window.speechSynthesis.speak(activeUtterance);
    window.speechSynthesis.resume();
  } catch(err) {
    console.warn('Speech synthesis speak error:', err);
    onSpeechDone();
  }
}

function startVoiceWaveform() {
  const canvas = $('voiceWaveCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = 300;
  canvas.height = 50;

  let phase = 0;
  function draw() {
    if (!voiceCallActive) return;
    voiceWaveAnimId = requestAnimationFrame(draw);
    phase += 0.08;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const halo = $('voiceAvatarHalo');
    const isSpeaking = halo && halo.classList.contains('speaking');

    // Sample real microphone decibels if available
    let micAmp = 4;
    let micLevel = 0;
    if (voiceAnalyser && voiceAudioDataArray && !voiceMicMuted && !isSpeaking) {
      voiceAnalyser.getByteFrequencyData(voiceAudioDataArray);
      let sum = 0;
      for (let i = 0; i < voiceAudioDataArray.length; i++) {
        sum += voiceAudioDataArray[i];
      }
      const avg = sum / voiceAudioDataArray.length;
      micLevel = Math.min(100, Math.round(avg * 1.8));
      micAmp = Math.max(4, Math.min(26, avg * 0.35));
    } else if (isSpeaking) {
      micAmp = 18;
      micLevel = 75;
    }

    const levelBar = $('voiceMicLevelBar');
    if (levelBar) {
      levelBar.style.width = (voiceMicMuted ? 0 : micLevel) + '%';
    }

    ctx.beginPath();
    ctx.lineWidth = 2.4;
    ctx.strokeStyle = isSpeaking ? 'var(--accent)' : (micLevel > 15 ? '#4caf50' : 'rgba(255,255,255,0.4)');

    for (let x = 0; x < canvas.width; x++) {
      const y = canvas.height / 2 + Math.sin(x * 0.05 + phase) * micAmp * Math.sin(x / canvas.width * Math.PI);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  draw();
}

/* --------------------------------------------------------------------------
   SCREEN SHARING & DRAGGABLE LIVE CAMERA / GAME VISION CO-PILOT
   -------------------------------------------------------------------------- */
let screenVisionStream = null;
let autoVisionInterval = null;
let screenVisionDragging = false;
let screenVisionDragOffsetX = 0;
let screenVisionDragOffsetY = 0;

function initDraggableScreenVision() {
  const panel = $('screenVisionFloating');
  if (!panel) return;
  const header = panel.querySelector('.screen-vision-header');
  if (!header) return;

  header.style.cursor = 'move';
  header.style.userSelect = 'none';

  function onDragStart(clientX, clientY) {
    screenVisionDragging = true;
    const rect = panel.getBoundingClientRect();
    screenVisionDragOffsetX = clientX - rect.left;
    screenVisionDragOffsetY = clientY - rect.top;
  }

  function onDragMove(clientX, clientY) {
    if (!screenVisionDragging) return;
    let newX = clientX - screenVisionDragOffsetX;
    let newY = clientY - screenVisionDragOffsetY;
    
    // Clamp inside viewport
    const maxX = window.innerWidth - panel.offsetWidth - 10;
    const maxY = window.innerHeight - panel.offsetHeight - 10;
    newX = Math.max(10, Math.min(maxX, newX));
    newY = Math.max(10, Math.min(maxY, newY));

    panel.style.left = newX + 'px';
    panel.style.top = newY + 'px';
    panel.style.right = 'auto';
    panel.style.bottom = 'auto';
  }

  function onDragEnd() {
    screenVisionDragging = false;
  }

  header.addEventListener('mousedown', (e) => {
    if (e.target.closest('button')) return;
    onDragStart(e.clientX, e.clientY);
  });

  window.addEventListener('mousemove', (e) => {
    if (screenVisionDragging) onDragMove(e.clientX, e.clientY);
  });

  window.addEventListener('mouseup', onDragEnd);

  header.addEventListener('touchstart', (e) => {
    if (e.target.closest('button')) return;
    if (e.touches.length === 1) {
      onDragStart(e.touches[0].clientX, e.touches[0].clientY);
    }
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (screenVisionDragging && e.touches.length === 1) {
      onDragMove(e.touches[0].clientX, e.touches[0].clientY);
    }
  }, { passive: true });

  window.addEventListener('touchend', onDragEnd);
}

async function toggleScreenVision() {
  if (screenVisionStream) {
    stopScreenVision();
  } else {
    await startScreenSharing();
  }
}

async function startScreenSharing() {
  try {
    if (navigator.mediaDevices && typeof navigator.mediaDevices.getDisplayMedia === 'function') {
      try {
        screenVisionStream = await navigator.mediaDevices.getDisplayMedia({
          video: { cursor: "always" },
          audio: true
        });
        showToast('🖥️ Screen vision & audio active! Companion is watching & hearing');
      } catch (dispErr) {
        if (dispErr.name === 'NotAllowedError') {
          showToast('Screen share permission cancelled');
          return;
        }
        // Fallback without audio if audio permission failed
        try {
          screenVisionStream = await navigator.mediaDevices.getDisplayMedia({
            video: { cursor: "always" },
            audio: false
          });
          showToast('🖥️ Screen vision active! Companion is watching with you');
        } catch(e2) {
          throw dispErr;
        }
      }
    } else if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      showToast('📷 Opening camera vision stream...');
      screenVisionStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 360 } },
        audio: false
      });
      showToast('📷 Live camera vision active!');
    } else {
      showToast('Media stream not supported on this browser');
      return;
    }

    const video = $('screenVisionVideo');
    if (video) {
      video.srcObject = screenVisionStream;
      video.play();
    }
    const monitor = $('screenVisionFloating');
    if (monitor) {
      monitor.classList.add('active');
      initDraggableScreenVision();
    }

    screenVisionStream.getVideoTracks()[0].onended = () => {
      stopScreenVision();
    };

    // Auto vision commentary every 30s if enabled
    if (autoVisionInterval) clearInterval(autoVisionInterval);
    autoVisionInterval = setInterval(() => {
      const autoCheck = $('autoVisionCommentaryCheck');
      if (autoCheck && autoCheck.checked && screenVisionStream && !document.hidden && !isProcessingVoiceTurn) {
        captureAndAskScreenVision("Give a short, natural in-character reaction to what you see on my screen right now!");
      }
    }, 30000);

  } catch (err) {
    console.warn('Vision capture error:', err);
    if (err.name === 'NotAllowedError') {
      showToast('Screen/Camera permission was denied');
    } else {
      showToast('Unable to start screen stream on this device');
    }
  }
}

function stopScreenVision() {
  if (screenVisionStream) {
    screenVisionStream.getTracks().forEach(t => t.stop());
    screenVisionStream = null;
  }
  if (autoVisionInterval) {
    clearInterval(autoVisionInterval);
    autoVisionInterval = null;
  }
  const monitor = $('screenVisionFloating');
  if (monitor) monitor.classList.remove('active');
  const video = $('screenVisionVideo');
  if (video) video.srcObject = null;
  showToast('Vision stream stopped');
}

async function captureAndAskScreenVision(customPrompt) {
  const video = $('screenVisionVideo');
  if (!video || !screenVisionStream) {
    showToast('Screen sharing is not active');
    return;
  }
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 288;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const frameData = canvas.toDataURL('image/jpeg', 0.75);

    const question = customPrompt || "Looking at what is on my screen right now: what do you see, and what advice or thoughts do you have?";
    showToast('👁 Analyzing screen...');

    appendChatMsg('user', question, frameData);

    if (activeGeminiLiveSession && activeGeminiLiveSession.isConnected) {
      activeGeminiLiveSession.sendImageFrame(frameData);
      activeGeminiLiveSession.sendText(question);
      return;
    }

    const sysPrompt = buildSystemPromptWithUser(activePersona.prompt || activePersona.personality, activePersona.id);
    const history = (chatMessages[activePersona.id] || []).slice(0, -1);

    const res = await executeAiChatRequest(question, sysPrompt, activePersona, history, frameData);
    const replyText = (res && res.reply) ? res.reply : "*watches screen attentively*";

    appendChatMsg('assistant', replyText);
    speakPersonaVoiceReply(replyText);
  } catch(e) {
    console.warn('Screen capture vision error:', e);
  }
}

/* --------------------------------------------------------------------------
   DYNAMIC TYPEWRITER ANIMATION ENGINE
   -------------------------------------------------------------------------- */
let currentTypewriterTimer = null;

function typewriteText(elementId, text, speed = 16, onComplete = null) {
  const el = $(elementId);
  if (!el) return;

  if (currentTypewriterTimer) {
    clearInterval(currentTypewriterTimer);
    currentTypewriterTimer = null;
  }

  el.innerHTML = '';
  const textSpan = document.createElement('span');
  const cursorSpan = document.createElement('span');
  cursorSpan.className = 'typewriter-cursor';
  cursorSpan.innerText = '▊';

  el.appendChild(textSpan);
  el.appendChild(cursorSpan);

  let i = 0;
  const finishInstant = () => {
    if (currentTypewriterTimer) {
      clearInterval(currentTypewriterTimer);
      currentTypewriterTimer = null;
      textSpan.innerText = text;
      cursorSpan.remove();
      if (onComplete) onComplete();
    }
  };

  el.onclick = finishInstant;

  currentTypewriterTimer = setInterval(() => {
    if (i < text.length) {
      textSpan.innerText += text.charAt(i);
      i++;
    } else {
      clearInterval(currentTypewriterTimer);
      currentTypewriterTimer = null;
      cursorSpan.remove();
      if (onComplete) onComplete();
    }
  }, speed);
}

/* --------------------------------------------------------------------------
   WATCH TOGETHER THEATER: BULLETPROOF VIDEO LOADER & PLAYBACK SYNC
   -------------------------------------------------------------------------- */
let watchTogetherCurrentVideo = null;
let watchTogetherVideoInfo = null;
let watchTogetherChimeInterval = null;
let theaterFrameClipBuffer = [];
let theaterBufferInterval = null;
let theaterSpeechRec = null;
let isTheaterEarActive = true;
let isTheaterVideoPaused = false;
let currentTheaterTimestamp = 0;
let theaterPlayStartedAt = null;
let theaterAccumulatedPlayTime = 0;
let theaterClockTickerInterval = null;

// Universal YouTube PostMessage State Listener & Progressive Timer Engine
if (typeof window !== 'undefined') {
  window.addEventListener('message', (event) => {
    try {
      if (!event.data) return;
      let data = event.data;
      if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch(e) { return; }
      }
      if (data && (data.event === 'infoDelivery' || data.infoDelivery) && data.info) {
        if (data.info.currentTime !== undefined && !isNaN(data.info.currentTime)) {
          const exactT = Number(data.info.currentTime);
          currentTheaterTimestamp = exactT;
          theaterAccumulatedPlayTime = exactT;
          theaterPlayStartedAt = Date.now();
        }
        if (data.info.playerState !== undefined) {
          const stateCode = data.info.playerState;
          const statusEl = $('theaterVideoStatus');
          if (stateCode === 1) { // PLAYING
            isTheaterVideoPaused = false;
            theaterPlayStartedAt = Date.now();
            const min = Math.floor(currentTheaterTimestamp / 60);
            const sec = Math.floor(currentTheaterTimestamp % 60);
            if (statusEl) statusEl.innerHTML = `<span style="color:#4caf50;">● 🟢 Playing (${min}m ${sec.toString().padStart(2, '0')}s)</span>`;
          } else if (stateCode === 2) { // PAUSED
            isTheaterVideoPaused = true;
            if (theaterPlayStartedAt) {
              theaterAccumulatedPlayTime += (Date.now() - theaterPlayStartedAt) / 1000;
              theaterPlayStartedAt = null;
            }
            currentTheaterTimestamp = theaterAccumulatedPlayTime;
            const min = Math.floor(currentTheaterTimestamp / 60);
            const sec = Math.floor(currentTheaterTimestamp % 60);
            if (statusEl) statusEl.innerHTML = `<span style="color:#e5c07b;">● ⏸️ Paused at ${min}m ${sec}s</span>`;
          } else if (stateCode === 0) { // ENDED
            isTheaterVideoPaused = true;
            if (statusEl) statusEl.innerHTML = '<span style="color:var(--text-muted);">● ⏹️ Ended</span>';
          }
        }
      }
    } catch(e) {}
  });
}

function getExactVideoPlaybackState() {
  const html5Vid = $('theaterHtml5Video');
  if (html5Vid && html5Vid.style.display !== 'none') {
    return {
      isPaused: html5Vid.paused,
      currentTime: html5Vid.currentTime || 0,
      duration: html5Vid.duration || 0,
      isHtml5: true
    };
  }

  let calculatedTime = currentTheaterTimestamp;
  if (!isTheaterVideoPaused && theaterPlayStartedAt) {
    calculatedTime = theaterAccumulatedPlayTime + ((Date.now() - theaterPlayStartedAt) / 1000);
  } else if (theaterAccumulatedPlayTime > 0) {
    calculatedTime = theaterAccumulatedPlayTime;
  }
  currentTheaterTimestamp = Math.max(0, calculatedTime);

  return {
    isPaused: isTheaterVideoPaused,
    currentTime: currentTheaterTimestamp,
    duration: 0,
    isHtml5: false
  };
}

function startTheaterClockTicker() {
  if (theaterClockTickerInterval) clearInterval(theaterClockTickerInterval);
  theaterClockTickerInterval = setInterval(() => {
    const modal = $('watchTogetherTheaterModal');
    if (!modal || !modal.classList.contains('open')) return;
    if (!watchTogetherCurrentVideo) return;

    // Send active polling heartbeat to YouTube embed iframe
    const iframe = $('theaterIframe');
    if (iframe && iframe.contentWindow && iframe.style.display !== 'none') {
      try {
        iframe.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: 1 }), '*');
        iframe.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'getCurrentTime', args: [] }), '*');
      } catch(e) {}
    }

    const state = getExactVideoPlaybackState();
    const statusEl = $('theaterVideoStatus');
    const min = Math.floor(state.currentTime / 60);
    const sec = Math.floor(state.currentTime % 60);
    const timeStr = `${min}m ${sec.toString().padStart(2, '0')}s`;

    if (!state.isPaused) {
      if (statusEl) {
        if (screenVisionStream) {
          statusEl.innerHTML = `<span style="color:#4caf50;">● 🟢 Live Screen Vision (${timeStr})</span>`;
        } else if (state.isHtml5) {
          statusEl.innerHTML = `<span style="color:#4caf50;">● 🟢 Direct HTML5 Video (${timeStr})</span>`;
        } else {
          statusEl.innerHTML = `<span style="color:#4caf50;">● 🟢 Playing YouTube (${timeStr})</span>`;
        }
      }
    }
  }, 1000);
}

function openWatchTogetherTheater() {
  const modal = $('watchTogetherTheaterModal');
  if (modal) {
    modal.classList.add('open');
    try {
      if ('speechSynthesis' in window) window.speechSynthesis.resume();
    } catch(e) {}
    if (activePersona) {
      $('theaterBotBadge').innerText = `Co-Watching with ${activePersona.name}`;
      if (!watchTogetherCurrentVideo) {
        typewriteText('theaterReactionText', `Ready to watch together! Paste a YouTube link, file, or share your screen above.`);
      }
    }
    updateTheaterFeedStatus();
    startTheaterClipBuffering();
    startTheaterClockTicker();
    showToast('🍿 Fullscreen Cinema Theater opened');
  }
}

function resetAndStopAllTheaterMedia() {
  const iframe = $('theaterIframe');
  if (iframe) {
    iframe.src = 'about:blank';
    iframe.style.display = 'none';
  }
  const html5Vid = $('theaterHtml5Video');
  if (html5Vid) {
    try {
      html5Vid.pause();
      html5Vid.removeAttribute('src');
      html5Vid.load();
    } catch(e) {}
    html5Vid.style.display = 'none';
  }
  stopTheaterVideoAudioIngestion();
  theaterLatestRawAudioBase64 = null;
  theaterRecentVideoDialogue = [];
  theaterFrameClipBuffer = [];
  isTheaterVideoPaused = true;
  theaterPlayStartedAt = null;
  currentTheaterTimestamp = 0;
  theaterAccumulatedPlayTime = 0;
}

function closeWatchTogetherTheater() {
  const modal = $('watchTogetherTheaterModal');
  if (modal) modal.classList.remove('open');
  if (watchTogetherChimeInterval) {
    clearInterval(watchTogetherChimeInterval);
    watchTogetherChimeInterval = null;
  }
  if (theaterBufferInterval) {
    clearInterval(theaterBufferInterval);
    theaterBufferInterval = null;
  }
  if (theaterClockTickerInterval) {
    clearInterval(theaterClockTickerInterval);
    theaterClockTickerInterval = null;
  }
  if (theaterSpeechRec) {
    try { theaterSpeechRec.stop(); } catch(e) {}
  }
  resetAndStopAllTheaterMedia();
}

function extractYouTubeId(url) {
  if (!url) return null;
  const str = url.trim();
  if (/^[a-zA-Z0-9_-]{11}$/.test(str)) {
    return str;
  }
  let m = str.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/i);
  if (m) return m[1];
  m = str.match(/[?&]v=([a-zA-Z0-9_-]{11})/i);
  if (m) return m[1];
  m = str.match(/youtube\.com\/(?:embed|shorts|v|live)\/([a-zA-Z0-9_-]{11})/i);
  if (m) return m[1];
  m = str.match(/(?:v=|\/embed\/|\/shorts\/|youtu\.be\/|\/v\/|\/e\/|watch\?v=|\&v=)([a-zA-Z0-9_-]{11})/i);
  if (m) return m[1];
  return null;
}

async function fetchImageAsBase64(url) {
  try {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'Anonymous';
      img.onload = () => {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = Math.min(img.naturalWidth || 480, 640);
          canvas.height = Math.min(img.naturalHeight || 360, 480);
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL('image/jpeg', 0.8));
        } catch(e) { resolve(null); }
      };
      img.onerror = () => resolve(null);
      img.src = url;
    });
  } catch(e) {
    return null;
  }
}

function captureSingleFrameFromSource() {
  if (screenVisionStream) {
    const v = $('screenVisionVideo');
    if (v && v.videoWidth > 0 && v.videoHeight > 0) {
      try {
        const c = document.createElement('canvas');
        c.width = 480;
        c.height = 270;
        c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
        return { data: c.toDataURL('image/jpeg', 0.75), time: Date.now() };
      } catch(e) {}
    }
  }
  const html5Vid = $('theaterHtml5Video');
  if (html5Vid && !html5Vid.paused && html5Vid.style.display !== 'none' && html5Vid.videoWidth > 0) {
    try {
      const c = document.createElement('canvas');
      c.width = 480;
      c.height = 270;
      c.getContext('2d').drawImage(html5Vid, 0, 0, c.width, c.height);
      return { data: c.toDataURL('image/jpeg', 0.75), time: Date.now() };
    } catch(e) {}
  }
  return null;
}

function startTheaterClipBuffering() {
  theaterFrameClipBuffer = [];
  if (theaterBufferInterval) clearInterval(theaterBufferInterval);
  theaterBufferInterval = setInterval(() => {
    const f = captureSingleFrameFromSource();
    if (f) {
      theaterFrameClipBuffer.push(f);
      if (theaterFrameClipBuffer.length > 3) {
        theaterFrameClipBuffer.shift();
      }
    }
  }, 1600);
}

async function getTheaterTemporalClipStrip() {
  if (theaterFrameClipBuffer.length >= 2) {
    try {
      const canvas = document.createElement('canvas');
      const numFrames = theaterFrameClipBuffer.length;
      canvas.width = 360 * numFrames;
      canvas.height = 200;
      const ctx = canvas.getContext('2d');

      const promises = theaterFrameClipBuffer.map((frame, idx) => {
        return new Promise((resolve) => {
          const img = new Image();
          img.onload = () => {
            ctx.drawImage(img, idx * 360, 0, 360, 200);
            ctx.fillStyle = 'rgba(0,0,0,0.65)';
            ctx.fillRect(idx * 360 + 6, 6, 80, 20);
            ctx.fillStyle = '#e5c07b';
            ctx.font = 'bold 10.5px sans-serif';
            const label = (idx === numFrames - 1) ? '● LIVE' : `T -${(numFrames - 1 - idx) * 2}s`;
            ctx.fillText(label, idx * 360 + 12, 20);
            resolve();
          };
          img.onerror = () => resolve();
          img.src = frame.data;
        });
      });
      await Promise.all(promises);
      return { data: canvas.toDataURL('image/jpeg', 0.78), isLive: true, isClipStrip: true };
    } catch(e) {
      console.warn('Clip strip build error:', e);
    }
  }

  const single = captureSingleFrameFromSource();
  if (single) return { data: single.data, isLive: true, isClipStrip: false };
  return { data: null, isLive: false, isClipStrip: false };
}

function updateTheaterFeedStatus() {
  const statusEl = $('theaterVideoStatus');
  const feedBtn = $('theaterScreenFeedBtn');
  const hasAudio = screenVisionStream && screenVisionStream.getAudioTracks && screenVisionStream.getAudioTracks().length > 0;

  if (screenVisionStream) {
    if (statusEl) {
      if (hasAudio) {
        statusEl.innerHTML = '<span style="color:#4caf50;">● 🟢 Live Screen & Tab Audio (Direct Hearing & Vision)</span>';
      } else {
        statusEl.innerHTML = '<span style="color:#4caf50;">● 🟢 Live Screen Vision (No Tab Audio)</span>';
      }
    }
    if (feedBtn) {
      feedBtn.style.background = 'rgba(76, 175, 80, 0.25)';
      feedBtn.style.color = '#4caf50';
      feedBtn.innerHTML = '🖥️ Stop Feed';
    }
  } else if ($('theaterHtml5Video') && $('theaterHtml5Video').style.display !== 'none') {
    if (statusEl) statusEl.innerHTML = '<span style="color:#4caf50;">● 🟢 Direct HTML5 Video Active</span>';
    if (feedBtn) {
      feedBtn.style.background = 'rgba(229,192,123,0.15)';
      feedBtn.style.color = '#e5c07b';
      feedBtn.innerHTML = '🖥️ Screen Feed';
    }
  } else if (watchTogetherCurrentVideo) {
    if (statusEl) statusEl.innerHTML = '<span style="color:var(--accent);">● YouTube Mode (Click "Screen Feed" & share tab to let AI hear & see)</span>';
    if (feedBtn) {
      feedBtn.style.background = 'rgba(229,192,123,0.15)';
      feedBtn.style.color = '#e5c07b';
      feedBtn.innerHTML = '🖥️ Screen Feed';
    }
  }
}

let theaterVideoAudioRecorder = null;
let theaterVideoAudioChunks = [];
let theaterRecentVideoDialogue = []; // [{ time: curSec, text: "transcribed speech" }]
let theaterLatestRawAudioBase64 = null; // Raw base64 audio clip for direct Gemini Multimodal Music/Audio listening
let theaterVideoAudioInterval = null;

let theaterVideoAudioCtx = null;

function startTheaterVideoAudioIngestion(mediaStreamOrElement) {
  stopTheaterVideoAudioIngestion();
  try {
    let audioStream = null;
    
    // 1. Try standard stream capture
    if (mediaStreamOrElement && mediaStreamOrElement.getAudioTracks && mediaStreamOrElement.getAudioTracks().length > 0) {
      audioStream = new MediaStream(mediaStreamOrElement.getAudioTracks());
    } else if (mediaStreamOrElement && (mediaStreamOrElement.tagName === 'VIDEO' || mediaStreamOrElement.captureStream)) {
      try {
        const stream = mediaStreamOrElement.captureStream ? mediaStreamOrElement.captureStream() : (mediaStreamOrElement.mozCaptureStream ? mediaStreamOrElement.mozCaptureStream() : null);
        if (stream && stream.getAudioTracks && stream.getAudioTracks().length > 0) {
          audioStream = new MediaStream(stream.getAudioTracks());
        }
      } catch(e) {}
      
      // 2. Android Chrome Fallback: Web Audio API
      if ((!audioStream || audioStream.getAudioTracks().length === 0) && mediaStreamOrElement.tagName === 'VIDEO') {
        try {
          theaterVideoAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
          const source = theaterVideoAudioCtx.createMediaElementSource(mediaStreamOrElement);
          const dest = theaterVideoAudioCtx.createMediaStreamDestination();
          source.connect(dest);
          source.connect(theaterVideoAudioCtx.destination);
          audioStream = dest.stream;
        } catch(fallbackErr) {
          console.warn("Web Audio fallback failed:", fallbackErr);
        }
      }
    }

    if (!audioStream || audioStream.getAudioTracks().length === 0) {
      console.warn("No audio tracks found from video stream!");
      showToast('⚠️ Note: Browser blocked internal video audio capture. AI will use subtitles instead.', 4000);
      return;
    }

    theaterVideoAudioRecorder = new MediaRecorder(audioStream);

    theaterVideoAudioRecorder.ondataavailable = async (e) => {
      if (!e.data || e.data.size < 500 || isTheaterVideoPaused) return;
      try {
        const reader = new FileReader();
        reader.onloadend = async () => {
          try {
            const base64Audio = reader.result;
            theaterLatestRawAudioBase64 = base64Audio; // RAW AUDIO CLIP CAPTURED!

            const statusEl = $('theaterVideoStatus');
            if (statusEl && !isTheaterVideoPaused) {
              statusEl.innerHTML = '<span style="color:#61afef;">🎵 Hearing Live Audio Stream</span>';
            }

            const groqKey = userGroqKey || localStorage.getItem('groq_key') || '';
            const res = await fetch('/api/stt', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ audio: base64Audio, groq_key: groqKey, filename: 'video_audio.webm' })
            });
            const data = await res.json();
            if (data && data.ok && data.text && data.text.trim()) {
              const text = data.text.trim();
              const curState = getExactVideoPlaybackState();
              const curSec = Math.floor(curState.currentTime);
              theaterRecentVideoDialogue.push({ time: curSec, text: text });
              if (theaterRecentVideoDialogue.length > 10) theaterRecentVideoDialogue.shift();

              if (statusEl && !isTheaterVideoPaused) {
                statusEl.innerHTML = `<span style="color:#61afef;">🎵 Audio: "${escapeHtml(text.slice(0, 40))}${text.length > 40 ? '...' : ''}"</span>`;
              }
            }
          } catch(e) {}
        };
        reader.readAsDataURL(e.data);
      } catch(e) {}
    };

    theaterVideoAudioRecorder.start(4000);
    const statusEl = $('theaterVideoStatus');
    if (statusEl) statusEl.innerHTML = '<span style="color:#61afef;">🎵 Audio Stream Connected</span>';
  } catch(err) {
    console.warn('Video audio ingestion setup notice:', err);
  }
}

function stopTheaterVideoAudioIngestion() {
  if (theaterVideoAudioInterval) {
    clearInterval(theaterVideoAudioInterval);
    theaterVideoAudioInterval = null;
  }
  if (theaterVideoAudioRecorder) {
    try { theaterVideoAudioRecorder.stop(); } catch(e) {}
    theaterVideoAudioRecorder = null;
  }
  if (theaterVideoAudioCtx) {
    try { theaterVideoAudioCtx.close(); } catch(e) {}
    theaterVideoAudioCtx = null;
  }
  theaterVideoAudioChunks = [];
  theaterLatestRawAudioBase64 = null;
}

function getRecentVideoDialogueSummary(curSec, windowSeconds = 30) {
  if (!theaterRecentVideoDialogue || theaterRecentVideoDialogue.length === 0) return '';
  const relevant = theaterRecentVideoDialogue.filter(d => Math.abs(curSec - d.time) <= windowSeconds);
  if (relevant.length === 0) {
    return theaterRecentVideoDialogue.slice(-2).map(d => d.text).join(' ');
  }
  return relevant.map(d => d.text).join(' ');
}

async function toggleTheaterScreenFeed() {
  if (screenVisionStream) {
    stopScreenVision();
    stopTheaterVideoAudioIngestion();
    updateTheaterFeedStatus();
  } else {
    await startScreenSharing();
    updateTheaterFeedStatus();
    startTheaterClipBuffering();
    if (screenVisionStream && screenVisionStream.getAudioTracks().length > 0) {
      startTheaterVideoAudioIngestion(screenVisionStream);
    }
  }
}

async function handleTheaterUserTypedMessage(event) {
  if (event) {
    try { event.preventDefault(); } catch(e) {}
  }
  const inp = $('theaterChatInput');
  if (!inp) return;
  const text = inp.value.trim();
  if (!text) return;
  inp.value = '';
  await handleTheaterUserSpokenOrTypedMessage(text);
}

async function loadTheaterYouTubeVideo() {
  const inp = $('theaterYoutubeUrlInput');
  if (!inp) return;
  const raw = inp.value.trim();
  if (!raw) {
    showToast('Please enter a video link or YouTube URL');
    return;
  }

  // 1. Direct video files (.mp4, .webm, .ogg, .mov, .m4v, .mkv)
  const isDirectFile = /\.(mp4|webm|ogg|mov|m4v|mkv)(\?.*)?$/i.test(raw);
  if (isDirectFile) {
    loadTheaterDirectVideo(raw, 'Direct Video File');
    return;
  }

  // 2. YouTube URLs / IDs
  const videoId = extractYouTubeId(raw);
  if (videoId) {
    resetAndStopAllTheaterMedia();
    watchTogetherCurrentVideo = videoId;
    watchTogetherVideoInfo = { id: videoId, title: "YouTube Video", author: "", thumb: null, loadedAt: Date.now(), isHtml5: false };
    isTheaterVideoPaused = false;
    currentTheaterTimestamp = 0;
    theaterAccumulatedPlayTime = 0;
    theaterPlayStartedAt = Date.now();

    const iframe = $('theaterIframe');
    if (iframe) {
      iframe.style.display = 'block';
      iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1&enablejsapi=1&playsinline=1&rel=0`;
    }

    showToast('▶ Playing in Cinema Theater');
    updateTheaterFeedStatus();
    startTheaterClockTicker();

    // Fetch rich YouTube video metadata & subtitles from backend
    try {
      fetch('/api/youtube_context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: raw, timestamp: 0 })
      }).then(r => r.json()).then(ytData => {
        if (ytData && ytData.ok) {
          if (ytData.title) watchTogetherVideoInfo.title = ytData.title;
          if (ytData.artist) watchTogetherVideoInfo.author = ytData.artist;
          if (ytData.description_snippet) watchTogetherVideoInfo.description = ytData.description_snippet;
          if (ytData.audio_data) theaterLatestRawAudioBase64 = ytData.audio_data;
          if (ytData.full_transcript) watchTogetherVideoInfo.full_transcript = ytData.full_transcript;
          if ($('theaterBotBadge')) $('theaterBotBadge').innerText = `Watching: ${watchTogetherVideoInfo.title}`;
          const statusEl = $('theaterVideoStatus');
          if (statusEl) statusEl.innerHTML = `<span style="color:#4caf50;">● 🟢 Playing: ${escapeHtml(watchTogetherVideoInfo.title.slice(0, 35))}</span>`;
        }
      }).catch(e => {});
    } catch(e) {}

    try {
      const thumbUrl = `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
      watchTogetherVideoInfo.thumb = await fetchImageAsBase64(thumbUrl);
    } catch(e) {}

    if ($('theaterBotBadge')) $('theaterBotBadge').innerText = `Watching: ${watchTogetherVideoInfo.title}`;

    triggerTheaterOpeningReaction();
    startTheaterCommentaryLoop();
    return;
  }

  // 3. Generic web embed fallback (Vimeo, Streamable, etc.)
  if (/^https?:\/\//i.test(raw)) {
    resetAndStopAllTheaterMedia();
    watchTogetherCurrentVideo = raw;
    watchTogetherVideoInfo = { id: raw, title: "Web Video", author: "Web", thumb: null, loadedAt: Date.now(), isHtml5: false };
    isTheaterVideoPaused = false;
    currentTheaterTimestamp = 0;
    theaterAccumulatedPlayTime = 0;
    theaterPlayStartedAt = Date.now();
    const iframe = $('theaterIframe');
    if (iframe) {
      iframe.style.display = 'block';
      iframe.src = raw;
    }
    showToast('▶ Loading web video in Cinema Theater');
    updateTheaterFeedStatus();
    startTheaterClockTicker();
    triggerTheaterOpeningReaction();
    startTheaterCommentaryLoop();
    return;
  }

  showToast('Please enter a valid YouTube URL or video link');
}

function loadTheaterDirectVideo(url, title) {
  resetAndStopAllTheaterMedia();
  watchTogetherCurrentVideo = url;
  watchTogetherVideoInfo = { id: url, title: title || "Direct Video Stream", author: "Direct Media", thumb: null, loadedAt: Date.now(), isHtml5: true };
  isTheaterVideoPaused = false;
  currentTheaterTimestamp = 0;
  theaterAccumulatedPlayTime = 0;
  theaterPlayStartedAt = Date.now();

  const html5Vid = $('theaterHtml5Video');
  if (html5Vid) {
    html5Vid.style.display = 'block';
    html5Vid.src = url;
    html5Vid.onplay = () => {
      isTheaterVideoPaused = false;
      theaterPlayStartedAt = Date.now();
      startTheaterVideoAudioIngestion(html5Vid);
      const statusEl = $('theaterVideoStatus');
      if (statusEl) statusEl.innerHTML = '<span style="color:#4caf50;">● 🟢 Playing (HTML5 Video & Audio)</span>';
    };
    html5Vid.onpause = () => {
      isTheaterVideoPaused = true;
      stopTheaterVideoAudioIngestion();
      if (theaterPlayStartedAt) {
        theaterAccumulatedPlayTime += (Date.now() - theaterPlayStartedAt) / 1000;
        theaterPlayStartedAt = null;
      }
      currentTheaterTimestamp = html5Vid.currentTime || theaterAccumulatedPlayTime;
      const min = Math.floor(currentTheaterTimestamp / 60);
      const sec = Math.floor(currentTheaterTimestamp % 60);
      const statusEl = $('theaterVideoStatus');
      if (statusEl) statusEl.innerHTML = `<span style="color:#e5c07b;">● ⏸️ Paused at ${min}m ${sec}s</span>`;
    };
    html5Vid.play().catch(e => console.warn('HTML5 play notice:', e));
  }
  showToast('▶ Playing Direct Video in Cinema Theater');
  if ($('theaterBotBadge')) $('theaterBotBadge').innerText = `Watching: ${watchTogetherVideoInfo.title}`;
  updateTheaterFeedStatus();
  startTheaterClipBuffering();
  startTheaterClockTicker();

  triggerTheaterOpeningReaction();
  startTheaterCommentaryLoop();
}

function loadTheaterLocalFile(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const objectUrl = URL.createObjectURL(file);
  loadTheaterDirectVideo(objectUrl, file.name);
}

async function triggerTheaterOpeningReaction() {
  if (!activePersona || !watchTogetherVideoInfo) return;

  const initialPrompt = `[LIVE THEATER CO-WATCHING - OPENING SCENE]
- Video Title: "${watchTogetherVideoInfo.title}"
- Creator: "${watchTogetherVideoInfo.author || 'Creator'}"
- Playback Status: Playback just started!

We just pressed play on this video on our theater screen. As my companion sitting right next to me with snacks, give an excited, short, natural in-character opening reaction about starting to watch "${watchTogetherVideoInfo.title}"! Keep it under 2 sentences.`;

  try {
    const sysPrompt = buildSystemPromptWithUser(activePersona.prompt || activePersona.personality, activePersona.id);
    const history = (chatMessages[activePersona.id] || []).slice(-3);
    const initialThumb = watchTogetherVideoInfo.thumb;
    const res = await executeAiChatRequest(initialPrompt, sysPrompt, activePersona, history, initialThumb);
    const startMsg = (res && res.reply) ? res.reply : `*grabs popcorn and snuggles in* Let's watch "${watchTogetherVideoInfo.title}"!`;
    typewriteText('theaterReactionText', startMsg);
    appendChatMsg('assistant', startMsg);
    speakPersonaVoiceReply(startMsg);
  } catch(e) {
    const fallbackMsg = `*grabs popcorn* Let's watch "${watchTogetherVideoInfo.title}"!`;
    typewriteText('theaterReactionText', fallbackMsg);
    appendChatMsg('assistant', fallbackMsg);
    speakPersonaVoiceReply(fallbackMsg);
  }
}

let lastAutoCommentaryDialogue = '';

function startTheaterCommentaryLoop() {
  if (watchTogetherChimeInterval) clearInterval(watchTogetherChimeInterval);
  watchTogetherChimeInterval = setInterval(async () => {
    const autoChime = $('theaterAutoChimeIn');
    const modal = $('watchTogetherTheaterModal');
    if (!autoChime || !autoChime.checked || !modal || !modal.classList.contains('open') || isProcessingVoiceTurn) return;
    if (!watchTogetherCurrentVideo || !watchTogetherVideoInfo) return;

    // EXACT REAL PLAYBACK STATE CHECK
    const playbackState = getExactVideoPlaybackState();
    if (playbackState.isPaused) {
      // STOP AUTO COMMENTING WHILE PAUSED!
      return;
    }

    const curSec = Math.floor(playbackState.currentTime);
    const clipResult = await getTheaterTemporalClipStrip();
    let videoAudioDialogue = getRecentVideoDialogueSummary(curSec);

    // If watching YouTube / URL, fetch live dialogue slice at this timestamp from backend
    if (watchTogetherCurrentVideo && !screenVisionStream) {
      try {
        const ytRes = await fetch('/api/youtube_context', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: watchTogetherCurrentVideo, timestamp: curSec })
        });
        if (ytRes.ok) {
          const ytData = await ytRes.json();
          if (ytData && ytData.ok) {
            if (ytData.audio_data) theaterLatestRawAudioBase64 = ytData.audio_data;
            if (ytData.dialogue) videoAudioDialogue = ytData.dialogue;
            if (ytData.full_transcript) watchTogetherVideoInfo.full_transcript = ytData.full_transcript;
            if (ytData.title && (!watchTogetherVideoInfo.title || watchTogetherVideoInfo.title === 'YouTube Video')) {
              watchTogetherVideoInfo.title = ytData.title;
              watchTogetherVideoInfo.author = ytData.artist;
            }
          }
        }
      } catch(e) {}
    }

    const rawAudioPayload = theaterLatestRawAudioBase64;
    const hasLiveSensory = !!((clipResult.isLive && clipResult.data) || rawAudioPayload || (videoAudioDialogue && videoAudioDialogue !== lastAutoCommentaryDialogue));

    // If there is NO live visual feed and NO new dialogue/audio, DO NOT spam fake commentary!
    if (!hasLiveSensory) {
      return;
    }

    if (videoAudioDialogue) {
      lastAutoCommentaryDialogue = videoAudioDialogue;
    }

    const fullTranscriptSnippet = (watchTogetherVideoInfo && watchTogetherVideoInfo.full_transcript) ? watchTogetherVideoInfo.full_transcript.slice(0, 600) : '';
    let prompt = '';
    let imagePayload = (clipResult.isLive && clipResult.data) ? clipResult.data : null;

    if (imagePayload) {
      prompt = `[LIVE THEATER CO-WATCHING VIDEO FEED - SEQUENTIAL MOTION CLIP + AUDIO STREAM]
- Video / Track Title: "${watchTogetherVideoInfo.title}"
- Channel / Artist: "${watchTogetherVideoInfo.author || 'Creator'}"
- Exact Playback Timestamp: ${Math.floor(curSec/60)}m ${curSec%60}s in.
- Attached Visuals: ${clipResult.isClipStrip ? 'A 3-panel chronological motion storyboard strip [T-4s, T-2s, Live Now] showing the recent video clip sequence!' : 'A real-time live frame snapshot from the active video screen.'}`;
      if (videoAudioDialogue) {
        prompt += `\n- Exact Spoken Dialogue / Subtitles At This Second: "${videoAudioDialogue}"`;
      }
      if (fullTranscriptSnippet) {
        prompt += `\n- Full Video Dialogue / Lyrics Sequence:\n${fullTranscriptSnippet}`;
      }
      if (rawAudioPayload) {
        prompt += `\n- Attached Audio: Raw audio waveform clip of the playing soundtrack / music / instruments is attached directly for you to hear.`;
      }
      prompt += `\n\nAs my companion watching this video clip sequence and listening to the music/audio right alongside me, make a spontaneous, short, natural in-character reaction directly about what is unfolding on screen, the music/audio vibe, and what is being said in "${watchTogetherVideoInfo.title}". Keep it under 2 sentences.`;
    } else {
      prompt = `[LIVE THEATER CO-WATCHING - SUBTITLES & AUDIO AT TIMESTAMP ${Math.floor(curSec/60)}m ${curSec%60}s]
- Video / Track Title: "${watchTogetherVideoInfo.title}"
- Channel / Artist: "${watchTogetherVideoInfo.author || 'Creator'}"
- Exact Playback Timestamp: ${Math.floor(curSec/60)}m ${curSec%60}s in.`;
      if (videoAudioDialogue) {
        prompt += `\n- Exact Spoken Dialogue / Subtitles At This Second: "${videoAudioDialogue}"`;
      }
      if (rawAudioPayload) {
        prompt += `\n- Attached Audio: Raw audio waveform clip of the soundtrack is attached.`;
      }
      prompt += `\n\nAs my companion co-watching "${watchTogetherVideoInfo.title}", make a brief, natural 1-2 sentence reaction to what was just spoken/heard!`;
    }

    try {
      const sysPrompt = buildSystemPromptWithUser(activePersona.prompt || activePersona.personality, activePersona.id);
      const history = (chatMessages[activePersona.id] || []).slice(-4);
      const res = await executeAiChatRequest(prompt, sysPrompt, activePersona, history, imagePayload, rawAudioPayload);
      if (res && res.reply) {
        typewriteText('theaterReactionText', res.reply);
        appendChatMsg('assistant', res.reply);
        speakPersonaVoiceReply(res.reply);
      }
    } catch(e) {
      console.warn('Auto chime notice:', e);
    }
  }, 30000);
}

async function handleTheaterUserSpokenOrTypedMessage(userText) {
  if (!userText || !activePersona) return;
  const input = $('theaterChatInput');
  if (input) input.value = '';

  const playbackState = getExactVideoPlaybackState();
  const curSec = Math.floor(playbackState.currentTime);
  const min = Math.floor(curSec / 60);
  const sec = curSec % 60;
  const vTitle = watchTogetherVideoInfo ? watchTogetherVideoInfo.title : 'the video';

  typewriteText('theaterReactionText', `${activePersona.name} is watching and thinking...`, 20);
  appendChatMsg('user', userText);

  const clipResult = await getTheaterTemporalClipStrip();
  let videoAudioDialogue = getRecentVideoDialogueSummary(curSec);

  // If watching YouTube / URL, fetch live subtitles at this timestamp
  if (watchTogetherCurrentVideo && !screenVisionStream) {
    try {
      const ytRes = await fetch('/api/youtube_context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: watchTogetherCurrentVideo, timestamp: curSec })
      });
      if (ytRes.ok) {
        const ytData = await ytRes.json();
        if (ytData && ytData.ok) {
          if (ytData.audio_data) theaterLatestRawAudioBase64 = ytData.audio_data;
          if (ytData.dialogue) videoAudioDialogue = ytData.dialogue;
          if (ytData.full_transcript) watchTogetherVideoInfo.full_transcript = ytData.full_transcript;
          if (ytData.title && (!watchTogetherVideoInfo.title || watchTogetherVideoInfo.title === 'YouTube Video')) {
            watchTogetherVideoInfo.title = ytData.title;
            watchTogetherVideoInfo.author = ytData.artist;
          }
        }
      }
    } catch(e) {}
  }

  const rawAudioPayload = theaterLatestRawAudioBase64;
  const fullTranscriptSnippet = (watchTogetherVideoInfo && watchTogetherVideoInfo.full_transcript) ? watchTogetherVideoInfo.full_transcript.slice(0, 600) : '';
  const imagePayload = (clipResult.isLive && clipResult.data) ? clipResult.data : null;
  const hasRealSensory = !!(imagePayload || rawAudioPayload || videoAudioDialogue);

  let prompt = '';

  if (playbackState.isPaused) {
    prompt = `[CO-WATCHING VIDEO - PAUSED AT TIMESTAMP ${min}m ${sec}s]
- Video / Track: "${vTitle}"
- Status: The video is currently PAUSED at ${min}m ${sec}s.`;
    if (imagePayload) {
      prompt += `\n- Visual Feed: Attached freeze-frame of the paused screen.`;
    }
    if (videoAudioDialogue) {
      prompt += `\n- Spoken Dialogue / Subtitles around this scene: "${videoAudioDialogue}"`;
    }
    if (rawAudioPayload) {
      prompt += `\n- Attached Audio: Raw audio clip around this scene is attached.`;
    }
    if (!hasRealSensory) {
      prompt += `\n- Sensory Note: Direct screen feed / tab audio is not currently active. You have video metadata. Do not fake specific visual or audio details.`;
    }
    prompt += `\n- User said: "${userText}"\n\nReply in character as their companion knowing the video is paused right now at this specific scene (${min}m ${sec}s) and addressing what they asked/said!`;
  } else {
    prompt = `[CO-WATCHING VIDEO - CURRENTLY PLAYING AT ${min}m ${sec}s]
- Video / Track: "${vTitle}"
- Channel / Artist: "${watchTogetherVideoInfo ? watchTogetherVideoInfo.author : 'Creator'}"
- Exact Live Timestamp: ${min}m ${sec}s in.`;
    if (imagePayload) {
      prompt += `\n- Attached Visuals: ${clipResult.isClipStrip ? 'A 3-panel chronological motion storyboard strip showing recent seconds of the video!' : 'A live snapshot frame.'}`;
    }
    if (videoAudioDialogue) {
      prompt += `\n- Exact Spoken Dialogue / Subtitles At This Second: "${videoAudioDialogue}"`;
    }
    if (fullTranscriptSnippet) {
      prompt += `\n- Full Video Dialogue / Lyrics Sequence:\n${fullTranscriptSnippet}`;
    }
    if (rawAudioPayload) {
      prompt += `\n- Attached Audio: Raw audio waveform clip of the playing soundtrack / music / instruments is attached directly for you to hear.`;
    }
    if (!hasRealSensory) {
      prompt += `\n- Sensory Note: Direct screen feed / tab audio stream is not currently shared into the browser. You only have video title and timestamp metadata. Do NOT pretend to see visual actions or hear specific instruments you don't have.`;
    }
    prompt += `\n- User said: "${userText}"\n\nReply in full character as their co-watching companion reacting naturally to the conversation and video!`;
  }

  try {
    const sysPrompt = buildSystemPromptWithUser(activePersona.prompt || activePersona.personality, activePersona.id);
    const history = (chatMessages[activePersona.id] || []).slice(0, -1);

    const res = await executeAiChatRequest(prompt, sysPrompt, activePersona, history, imagePayload, rawAudioPayload);
    const replyText = (res && res.reply) ? res.reply : "*reacts warmly and snuggles closer*";

    typewriteText('theaterReactionText', replyText);
    appendChatMsg('assistant', replyText);
    speakPersonaVoiceReply(replyText);
  } catch(e) {
    typewriteText('theaterReactionText', "*smiles and watches along with you*");
  }
}

function sendTheaterUserMessage(event) {
  if (event) event.preventDefault();
  const input = $('theaterChatInput');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  handleTheaterUserSpokenOrTypedMessage(text);
}

async function askCompanionAboutVideo() {
  const vTitle = (watchTogetherVideoInfo && watchTogetherVideoInfo.title) ? watchTogetherVideoInfo.title : 'this video';
  const state = getExactVideoPlaybackState();
  const min = Math.floor(state.currentTime / 60);
  const sec = Math.floor(state.currentTime % 60);
  const q = state.isPaused ? `What do you think of this scene we're paused on (${min}m ${sec}s)?` : `What do you think of ${vTitle} right now?`;
  await handleTheaterUserSpokenOrTypedMessage(q);
}

loadServerBots();
initBotPolling();
