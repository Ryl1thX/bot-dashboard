import re
with open("/storage/emulated/0/discord-bot2/index.html") as f:
    html = f.read()
scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
for i, s in enumerate(scripts):
    with open(f"script_new_{i}.js", "w") as sf:
        sf.write(s)
