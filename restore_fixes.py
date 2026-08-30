import re
import os

files_to_fix = [
    "/storage/emulated/0/discord-bot2/index.html",
    "/storage/emulated/0/discord-bot2/designs/index.html",
    "/storage/emulated/0/discord-bot/index.html"
]

for filepath in files_to_fix:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Vision Bug Fix (getTheaterTemporalClipStrip)
    target_vision = """      img.src = src;
    });
  });

  return { data: canvas.toDataURL('image/jpeg', 0.78), isLive: true, isClipStrip: true };"""
    
    replace_vision = """      img.src = src;
    });
  });

  await Promise.all(promises);
  return { data: canvas.toDataURL('image/jpeg', 0.78), isLive: true, isClipStrip: true };"""
    
    if "await Promise.all(promises);" not in content:
        content = content.replace(target_vision, replace_vision)

    # 2. Audio Bug Fix (startTheaterVideoAudioIngestion)
    target_audio = """function startTheaterVideoAudioIngestion(html5Video) {
  if (!html5Video || typeof html5Video.captureStream !== 'function') return;
  
  try {
    const stream = html5Video.captureStream();"""
    
    replace_audio = """function startTheaterVideoAudioIngestion(html5Video) {
  if (!html5Video) return;
  
  try {
    let stream;
    if (typeof html5Video.captureStream === 'function') {
      stream = html5Video.captureStream();
    } else {
      stream = new MediaStream();
    }

    if (!window.theaterAudioContext) {
      window.theaterAudioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    const audioCtx = window.theaterAudioContext;
    if (!html5Video.audioSourceNode) {
      try {
         html5Video.audioSourceNode = audioCtx.createMediaElementSource(html5Video);
      } catch(e) {}
    }
    if (html5Video.audioSourceNode) {
      const dest = audioCtx.createMediaStreamDestination();
      html5Video.audioSourceNode.disconnect();
      html5Video.audioSourceNode.connect(dest);
      html5Video.audioSourceNode.connect(audioCtx.destination);
      const destStream = dest.stream;
      if (destStream.getAudioTracks().length > 0) {
        if (!stream) stream = new MediaStream();
        stream.addTrack(destStream.getAudioTracks()[0]);
      }
    }"""
    if "window.theaterAudioContext" not in content:
        content = content.replace(target_audio, replace_audio)

    # 3. Security Block Fix (startVoiceCall and toggleVoiceCallMic)
    target_sec = "if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {"
    replace_sec = """if (!window.isSecureContext) {
    alert("❌ BROWSER SECURITY BLOCK ❌\\nYour browser blocked microphone access because this is not a Secure Context.\\n\\nPlease use http://localhost:5000 (NOT file:// or 192.168.x.x) or use HTTPS.");
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {"""
    if "❌ BROWSER SECURITY BLOCK ❌" not in content:
        content = content.replace(target_sec, replace_sec)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched {filepath}")

