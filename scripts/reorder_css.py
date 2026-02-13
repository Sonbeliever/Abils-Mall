path = 'static/css/style.css'
with open(path, encoding='utf-8') as f:
    data = f.read()

data = data.replace(
    'backdrop-filter: var(--glass-blur);\\n    -webkit-backdrop-filter: var(--glass-blur);',
    '-webkit-backdrop-filter: var(--glass-blur);\\n    backdrop-filter: var(--glass-blur);'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(data)

print('reordered backdrop-filter lines')
