# Keeps the launcher's translations in step with its code.
#   python tools\i18n_check.py          checks every locales\<code>.json against locales\source.json
#   python tools\i18n_check.py --sync   also adds strings that are new in the code to the end of
#                                       source.json (and empty slots to each language)
#   python tools\i18n_check.py --prune  also drops strings the code no longer uses, from every file
# A translation must keep the same %-placeholders (%s, %d, %02d, %.1f, %%...) in the same order.
import ast, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'src')
LOC = os.path.join(SRC, 'locales')
# strings shown through a variable instead of a literal _('...') call
EXTRA = ['antes de restaurar', 'antes de importar', 'antes de apagar slot', 'manual']
PLACEHOLDER = re.compile(r'%[-+ 0#]*\d*(?:\.\d+)?[sdifxXr%]|%[dmYHMS]')


def code_strings():
    found = []
    for f in sorted(glob.glob(os.path.join(SRC, '*.py'))):
        for n in ast.walk(ast.parse(open(f, encoding='utf-8').read())):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_' and n.args \
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                found.append(n.args[0].value)
    return list(dict.fromkeys(found + EXTRA))


def main():
    source = json.load(open(os.path.join(LOC, 'source.json'), encoding='utf-8'))
    if '--prune' in sys.argv:
        used = set(code_strings())
        keep = [i for i, t in enumerate(source) if t in used]
        if len(keep) < len(source):
            print('%d unused string(s) removed' % (len(source) - len(keep)))
            for path in glob.glob(os.path.join(LOC, '*.json')):
                data = json.load(open(path, encoding='utf-8'))
                data = [data[i] if i < len(data) else '' for i in keep]
                json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
            source = [source[i] for i in keep]
    new = [s for s in code_strings() if s not in source]
    ok = True
    if new:
        print('%d string(s) in the code but not in source.json' % len(new))
        if '--sync' in sys.argv:
            source += new
            json.dump(source, open(os.path.join(LOC, 'source.json'), 'w', encoding='utf-8'), ensure_ascii=False,
                      indent=0)
        else:
            ok = False
    for path in sorted(glob.glob(os.path.join(LOC, '*.json'))):
        code = os.path.basename(path)[:-5]
        if code == 'source':
            continue
        tr = json.load(open(path, encoding='utf-8'))
        if '--sync' in sys.argv and len(tr) < len(source):
            tr += [''] * (len(source) - len(tr))
            json.dump(tr, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        if len(tr) != len(source):
            print('%s: %d entries, source has %d' % (code, len(tr), len(source)))
            ok = False
            continue
        missing = 0
        for i, (a, b) in enumerate(zip(source, tr)):
            if not b:
                missing += 1
                continue
            if PLACEHOLDER.findall(a) != PLACEHOLDER.findall(b):
                print('%s #%d placeholders differ:\n  %r\n  %r' % (code, i, a, b))
                ok = False
        print('%-6s %d/%d translated' % (code, len(source) - missing, len(source)))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
