


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
      prompt += `
- Audio Clip Attached: You are hearing the raw music stream directly right now!`;
    }
    prompt += `

Make a very short, natural 1-sentence reaction to the current music vibe!`;
    
    try {
      const sysPrompt = buildSystemPromptWithUser(activePersona.prompt, activePersona.id);
      const res = await executeAiChatRequest(prompt, sysPrompt, activePersona, [], null, theaterLatestRawAudioBase64);
      if (res && res.reply) {
        typewriteText('musicReactionText', res.reply);
        appendChatMsg('assistant', res.reply);
        speakPersonaVoiceReply(res.reply);
      }
    } catch(e) {}
  }, 45000); // Vibe check every 45s
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
    prompt += `
- Audio Clip Attached: You are hearing the music directly.`;
  }
  prompt += `

Reply naturally as their companion sharing this listening session.`;
  
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
