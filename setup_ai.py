from getpass import getpass
from pathlib import Path

root = Path(__file__).resolve().parent
key = getpass('OpenAI API key (input hidden): ').strip()
if not key:
    print('No key entered. Nothing changed.')
    raise SystemExit(1)
(root / '.env').write_text(
    f'OPENAI_API_KEY={key}\nOPENAI_MODEL=gpt-5.6-luna\n',
    encoding='utf-8',
)
print('Cloud AI configured in .env. Restart the app and open AI Copilot.')
