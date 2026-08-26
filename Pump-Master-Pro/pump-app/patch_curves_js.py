import sys

with open('static/js/pump_curves.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''            const trimmedCleanText = cleanText.replace(/^(p|eta|npsh|h)/, '');
            const trimmedCleanRaw = cleanRaw.replace(/^(p|eta|npsh|h)/, '');
            if (trimmedCleanText && (trimmedCleanText === trimmedCleanRaw || cleanRaw.includes(trimmedCleanText) || cleanText.includes(cleanRaw))) return true;'''

new_block = '''            const trimmedCleanText = cleanText.replace(/^(p|eta|npsh|h)/, '');
            const trimmedCleanRaw = cleanRaw.replace(/^(p|eta|npsh|h)/, '');
            if (trimmedCleanText && trimmedCleanText === trimmedCleanRaw) return true;
            if (trimmedCleanText && (cleanRaw.includes(trimmedCleanText) || cleanText.includes(cleanRaw))) {
              const rawNumbersOnly = cleanRaw.replace(/[^0-9]/g, '');
              const textNumbersOnly = cleanText.replace(/[^0-9]/g, '');
              if (rawNumbersOnly && textNumbersOnly && rawNumbersOnly !== textNumbersOnly && rawNumbersOnly.includes(textNumbersOnly)) {
                return false;
              }
              return true;
            }'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('static/js/pump_curves.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Failed to find block")
