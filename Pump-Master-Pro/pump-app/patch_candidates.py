import re

with open('static/js/pump_curves.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = '''          if (a.name.startsWith('eta_') || a.name.startsWith('pow_') || a.name.startsWith('npsh_') || a.name.startsWith('spd_') || a.name.startsWith('dia_')) {
            const numName = a.name.replace(/[^0-9.]/g, '');
            if (numRaw && numName && numRaw === numName) return true;
            const trimmedCleanText = cleanText.replace(/^(p|eta|npsh|h)/, '');
            const trimmedCleanRaw = cleanRaw.replace(/^(p|eta|npsh|h)/, '');
            if (trimmedCleanText && (trimmedCleanText === trimmedCleanRaw || cleanRaw.includes(trimmedCleanText) || cleanText.includes(cleanRaw))) return true;
          }'''

new_logic = '''          if (a.name.startsWith('eta_') || a.name.startsWith('pow_') || a.name.startsWith('npsh_') || a.name.startsWith('spd_') || a.name.startsWith('dia_')) {
            const numName = a.name.replace(/[^0-9.]/g, '');
            if (numRaw && numName && numRaw === numName) return true;
            const trimmedCleanText = cleanText.replace(/^(p|eta|npsh|h)/, '');
            const trimmedCleanRaw = cleanRaw.replace(/^(p|eta|npsh|h)/, '');
            if (trimmedCleanText && trimmedCleanText === trimmedCleanRaw) return true;
            if (trimmedCleanText && (cleanRaw.includes(trimmedCleanText) || cleanText.includes(cleanRaw))) {
              const rawNumbersOnly = cleanRaw.replace(/[^0-9]/g, '');
              const textNumbersOnly = cleanText.replace(/[^0-9]/g, '');
              if (rawNumbersOnly && textNumbersOnly && rawNumbersOnly !== textNumbersOnly && rawNumbersOnly.includes(textNumbersOnly)) {
                return false;
              }
              return true;
            }
          }'''

content = content.replace(old_logic, new_logic)

with open('static/js/pump_curves.js', 'w', encoding='utf-8') as f:
    f.write(content)

with open('templates/pump_form.html', 'r', encoding='utf-8') as f:
    html = f.read()
    
html = re.sub(r'pump_curves\.js\?v=\d+', 'pump_curves.js?v=194', html)

with open('templates/pump_form.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Patched!")
