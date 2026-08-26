import sys

with open('static/js/pump_curves.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "if (trimmedCleanText && (trimmedCleanText === trimmedCleanRaw || cleanRaw.includes(trimmedCleanText) || cleanText.includes(cleanRaw))) return true;" in line:
        indent = line.split("if")[0]
        new_lines.append(indent + "if (trimmedCleanText && trimmedCleanText === trimmedCleanRaw) return true;\n")
        new_lines.append(indent + "if (trimmedCleanText && (cleanRaw.includes(trimmedCleanText) || cleanText.includes(cleanRaw))) {\n")
        new_lines.append(indent + "  const rawNumbersOnly = cleanRaw.replace(/[^0-9]/g, '');\n")
        new_lines.append(indent + "  const textNumbersOnly = cleanText.replace(/[^0-9]/g, '');\n")
        new_lines.append(indent + "  if (rawNumbersOnly && textNumbersOnly && rawNumbersOnly !== textNumbersOnly && rawNumbersOnly.includes(textNumbersOnly)) {\n")
        new_lines.append(indent + "    return false;\n")
        new_lines.append(indent + "  }\n")
        new_lines.append(indent + "  return true;\n")
        new_lines.append(indent + "}\n")
    else:
        new_lines.append(line)

with open('static/js/pump_curves.js', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Patched via line matching!")
