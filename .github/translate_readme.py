import requests
import json

def translate_text(text, target_lang):
    url = 'https://api-free.deepl.com/v2/translate'
    headers = {
        'Authorization': 'DeepL-Auth-Key YOUR_DEEPL_AUTH_KEY',
        'Content-Type': 'application/json',
    }
    data = {
        'text': [text],
        'target_lang': target_lang,
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        translations = response.json().get('translations', [])
        if translations:
            return translations[0].get('text', '')
    return None

def main():
    with open('README.md', 'r', encoding='utf-8') as file:
        content = file.read()

    translated_content = translate_text(content, 'DE')  # Translate to German

    if translated_content:
        with open('README_DE.md', 'w', encoding='utf-8') as file:
            file.write(translated_content)
    else:
        print('Translation failed.')

if __name__ == '__main__':
    main()
