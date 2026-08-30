import re

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Header Button
btn_target = """<button class="chat-top-btn" id="watchTogetherHeaderBtn" onclick="openWatchTogetherTheater()" title="Watch Together Cinema" style="color:#e5c07b; border-color:#e5c07b; background:rgba(229,192,123,0.12);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <span>Theater</span>
        </button>"""
btn_inject = """<button class="chat-top-btn" id="watchTogetherHeaderBtn" onclick="openWatchTogetherTheater()" title="Watch Together Cinema" style="color:#e5c07b; border-color:#e5c07b; background:rgba(229,192,123,0.12);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <span>Theater</span>
        </button>

        <!-- MUSIC LOUNGE BUTTON -->
        <button class="chat-top-btn" id="musicLoungeHeaderBtn" onclick="openMusicLounge()" title="Music Lounge" style="color:#c678dd; border-color:#c678dd; background:rgba(198,120,221,0.12);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
          <span>Music</span>
        </button>"""
if "musicLoungeHeaderBtn" not in content:
    content = content.replace(btn_target, btn_inject)

# 2. Add Modal HTML
modal_html = """
  <!-- FULLSCREEN MUSIC LOUNGE OVERLAY -->
  <div class="theater-cinema-overlay" id="musicLoungeModal" style="background:rgba(20,15,30,0.95); backdrop-filter:blur(25px);">
    <div class="theater-top-bar" style="background:rgba(0,0,0,0.4); border-bottom:1px solid rgba(198,120,221,0.2);">
      <div class="theater-top-row1">
        <div style="display:flex; align-items:center; gap:6px; min-width:0; overflow:hidden;">
          <span style="font-size:14px; flex-shrink:0;">🎧</span>
          <span style="font-size:12px; font-weight:700; color:#c678dd; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" id="musicBotBadge">Listening with Yuna</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
          <button type="button" class="chat-top-btn" onclick="closeMusicLounge()" style="padding:4px 10px; font-size:11px; border-radius:14px; color:#c678dd; border:1px solid rgba(198,120,221,0.3);">✕ Close</button>
        </div>
      </div>
      <div class="theater-top-row2">
        <input type="text" class="composer-input" id="musicUrlInput" placeholder="Paste Spotify, YT Music, or link..." onkeydown="if(event.key==='Enter') loadMusicUrl()" style="background:rgba(0,0,0,0.5); border:1px solid rgba(198,120,221,0.2); border-radius:16px; padding:5px 12px; font-size:11.5px; flex:1; min-width:0; color:#fff;">
        <button type="button" class="btn-primary" onclick="loadMusicUrl()" style="padding:5px 12px; font-size:11px; border-radius:16px; background:#c678dd; white-space:nowrap; flex-shrink:0;">▶ Play</button>
        <input type="file" id="musicFileInput" accept="audio/*" style="display:none;" onchange="loadMusicFile(event)">
        <button type="button" class="chat-top-btn" onclick="document.getElementById('musicFileInput').click()" style="padding:5px 9px; font-size:11px; border-radius:16px; white-space:nowrap; flex-shrink:0;" title="Open local audio file">📁 File</button>
      </div>
    </div>

    <div class="theater-screen-wrapper" style="display:flex; align-items:center; justify-content:center; flex-direction:column; gap:20px;">
      <div id="musicArtContainer" style="width:200px; height:200px; border-radius:12px; background:linear-gradient(135deg, #2d2a3d, #1a1725); box-shadow:0 10px 30px rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; overflow:hidden;">
         <svg id="musicPlaceholderIcon" viewBox="0 0 24 24" fill="none" stroke="rgba(198,120,221,0.4)" stroke-width="1.5" style="width:80px; height:80px;"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
      </div>
      <iframe class="theater-iframe" id="musicIframe" src="" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="display:none; width:300px; height:80px; border-radius:12px; box-shadow:0 5px 15px rgba(0,0,0,0.3);"></iframe>
      <audio class="theater-iframe" id="musicHtml5Audio" style="display:none; width:300px;" controls autoplay playsinline></audio>
    </div>

    <div class="theater-companion-hud" style="border-top:1px solid rgba(198,120,221,0.2); background:rgba(0,0,0,0.6);">
      <div class="theater-reaction-bubble" id="musicReactionBubble">
        <span style="font-size:16px; flex-shrink:0;">🎧</span>
        <div id="musicReactionText" class="theater-reaction-text" style="color:#e0e0e0;">Ready to vibe together! Paste a music link or file above.</div>
      </div>
      <form class="theater-type-form" onsubmit="sendMusicUserMessage(event)">
        <input type="text" class="theater-chat-input" id="musicChatInput" placeholder="Talk about the song..." autocomplete="off">
        <button type="submit" class="theater-send-btn" style="background:rgba(198,120,221,0.2); color:#c678dd;">Send ➔</button>
      </form>
      <div style="display:flex; align-items:center; justify-content:space-between; width:100%; border-top:1px solid rgba(255,255,255,0.06); padding-top:4px; font-size:10.5px; gap:4px;">
        <span style="color:#c678dd; font-weight:600;" id="musicStatus">● Music Lounge Connected</span>
        <div style="display:flex; gap:6px;">
          <label style="display:flex; align-items:center; gap:4px; color:var(--text-muted); cursor:pointer;">
            <input type="checkbox" id="musicAutoChimeIn" checked>
            <span>Vibe Check</span>
          </label>
        </div>
      </div>
    </div>
  </div>
"""
if "musicLoungeModal" not in content:
    content = content.replace("  <!-- FULLSCREEN VOICE CALL OVERLAY -->", modal_html + "\n  <!-- FULLSCREEN VOICE CALL OVERLAY -->")

# 3. Add JS Logic correctly wrapped in script tag BEFORE </body>
js_logic = """
<script>
// --- MUSIC LOUNGE LOGIC ---
let musicLoungeCurrentUrl = null;
let musicLoungeInfo = null;
let musicChimeInterval = null;

function openMusicLounge() {
  const modal = document.getElementById('musicLoungeModal');
  if (modal) modal.classList.add('open');
  if (window.speechSynthesis) window.speechSynthesis.resume();
}

function closeMusicLounge() {
  const modal = document.getElementById('musicLoungeModal');
  if (modal) modal.classList.remove('open');
  if (musicChimeInterval) clearInterval(musicChimeInterval);
  const iframe = document.getElementById('musicIframe');
  const audio = document.getElementById('musicHtml5Audio');
  if (iframe) iframe.src = '';
  if (audio) { audio.pause(); audio.src = ''; }
  stopTheaterVideoAudioIngestion();
}

async function loadMusicUrl() {
  const raw = document.getElementById('musicUrlInput').value.trim();
  if (!raw) return showToast('Please enter a music link');
  
  const iframe = document.getElementById('musicIframe');
  const audio = document.getElementById('musicHtml5Audio');
  iframe.style.display = 'none';
  audio.style.display = 'none';
  
  musicLoungeCurrentUrl = raw;
  musicLoungeInfo = { title: "Streaming Audio", author: "Artist", url: raw };
  
  if (raw.includes('spotify.com')) {
    iframe.style.display = 'block';
    iframe.style.height = '152px';
    let embedUrl = raw;
    if (raw.includes('/track/')) embedUrl = raw.replace('/track/', '/embed/track/').split('?')[0];
    else if (raw.includes('/album/')) embedUrl = raw.replace('/album/', '/embed/album/').split('?')[0];
    else if (raw.includes('/playlist/')) embedUrl = raw.replace('/playlist/', '/embed/playlist/').split('?')[0];
    iframe.src = embedUrl;
  } else if (raw.includes('youtube.com') || raw.includes('youtu.be')) {
    const videoId = extractYouTubeId(raw);
    if (videoId) {
      iframe.style.display = 'block';
      iframe.style.height = '80px';
      iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1&enablejsapi=1`;
      fetch('/api/youtube_context', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ url: raw, timestamp: 0 })
      }).then(r => r.json()).then(data => {
        if (data.ok && data.title) {
          musicLoungeInfo.title = data.title;
          musicLoungeInfo.author = data.artist;
          document.getElementById('musicBotBadge').innerText = `Listening: ${data.title}`;
        }
      }).catch(e => console.error(e));
    }
  } else {
    audio.style.display = 'block';
    audio.src = raw;
    audio.play();
    startTheaterVideoAudioIngestion(audio);
  }
  
  typewriteText('musicReactionText', `*puts on headphones* I love this one!`);
  startMusicCommentaryLoop();
}

function loadMusicFile(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  const audio = document.getElementById('musicHtml5Audio');
  document.getElementById('musicIframe').style.display = 'none';
  audio.style.display = 'block';
  audio.src = url;
  audio.play();
  
  musicLoungeCurrentUrl = url;
  musicLoungeInfo = { title: file.name, author: "Local File", url: url };
  document.getElementById('musicBotBadge').innerText = `Listening: ${file.name}`;
  
  audio.onplay = () => startTheaterVideoAudioIngestion(audio);
  typewriteText('musicReactionText', `*nods head to the beat* Great choice!`);
  startMusicCommentaryLoop();
}

function startMusicCommentaryLoop() {
  if (musicChimeInterval) clearInterval(musicChimeInterval);
  musicChimeInterval = setInterval(async () => {
    const autoChime = document.getElementById('musicAutoChimeIn');
    const modal = document.getElementById('musicLoungeModal');
    if (!autoChime || !autoChime.checked || !modal || !modal.classList.contains('open')) return;
    if (!musicLoungeInfo) return;
    
    let prompt = `[MUSIC LOUNGE CO-LISTENING]
- Currently Playing: "${musicLoungeInfo.title}" by "${musicLoungeInfo.author}"
- Note: We are vibing to this music together in the Music Lounge.`;
    
    if (theaterLatestRawAudioBase64) {
      prompt += `\n- Audio Clip Attached: You are hearing the raw music stream directly right now!`;
    }
    prompt += `\n\nMake a very short, natural 1-sentence reaction to the current music vibe!`;
    
    try {
      const sysPrompt = buildSystemPromptWithUser(activePersona.prompt, activePersona.id);
      const res = await executeAiChatRequest(prompt, sysPrompt, activePersona, [], null, theaterLatestRawAudioBase64);
      if (res && res.reply) {
        typewriteText('musicReactionText', res.reply);
        appendChatMsg('assistant', res.reply);
        speakPersonaVoiceReply(res.reply);
      }
    } catch(e) {}
  }, 45000);
}

async function sendMusicUserMessage(event) {
  event.preventDefault();
  const input = document.getElementById('musicChatInput');
  const userText = input.value.trim();
  if (!userText || !activePersona) return;
  input.value = '';
  
  typewriteText('musicReactionText', `${activePersona.name} is listening...`, 20);
  appendChatMsg('user', userText);
  
  let prompt = `[MUSIC LOUNGE CHAT]
- Currently Playing: "${musicLoungeInfo ? musicLoungeInfo.title : 'Some music'}"
- User said: "${userText}"`;

  if (theaterLatestRawAudioBase64) {
    prompt += `\n- Audio Clip Attached: You are hearing the music directly.`;
  }
  prompt += `\n\nReply naturally as their companion sharing this listening session.`;
  
  try {
    const sysPrompt = buildSystemPromptWithUser(activePersona.prompt, activePersona.id);
    const history = (chatMessages[activePersona.id] || []).slice(-4);
    const res = await executeAiChatRequest(prompt, sysPrompt, activePersona, history, null, theaterLatestRawAudioBase64);
    if (res && res.reply) {
      typewriteText('musicReactionText', res.reply);
      appendChatMsg('assistant', res.reply);
      speakPersonaVoiceReply(res.reply);
    }
  } catch(e) {}
}
</script>
"""

if "function openMusicLounge" not in content:
    content = content.replace("</body>", js_logic + "\n</body>")

with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)
print("Injected Music Lounge correctly!")
