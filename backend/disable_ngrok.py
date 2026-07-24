with open("D:\\GENAI\\backend\\.env", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("NGROK_ENABLED=true", "NGROK_ENABLED=false")

with open("D:\\GENAI\\backend\\.env", "w", encoding="utf-8") as f:
    f.write(content)
