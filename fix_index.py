import re

with open("/storage/emulated/0/discord-bot2/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# The JS was appended after </html>. We need to find </html> and split.
if "</html>" in content:
    parts = content.split("</html>")
    html_part = parts[0]
    js_part = parts[1] if len(parts) > 1 else ""
    
    if "// --- MUSIC LOUNGE LOGIC ---" in js_part:
        # We need to move the JS part into a <script> tag before </body>
        script_tag = f"\n<script>{js_part}</script>\n"
        
        # Remove the old JS part from the end
        # Find </body> in html_part
        if "</body>" in html_part:
            html_part = html_part.replace("</body>", script_tag + "</body>")
        
        content = html_part + "</html>\n"

        with open("/storage/emulated/0/discord-bot2/index.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Fixed index.html!")
    else:
        print("JS not found after </html>")
else:
    print("</html> not found")
