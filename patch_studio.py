files_to_fix = [
    "/storage/emulated/0/discord-bot2/studio.html",
    "/storage/emulated/0/discord-bot/studio.html"
]

for filepath in files_to_fix:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

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
