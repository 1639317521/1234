import sys, os, json, shutil, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUPS = os.path.join(ROOT, '_backups')


def points():
    if not os.path.isdir(BACKUPS):
        return []
    out = []
    for name in sorted(os.listdir(BACKUPS), reverse=True):
        p = os.path.join(BACKUPS, name)
        if os.path.isdir(p) and not name.startswith('.'):
            files = []
            for dirpath, _, names in os.walk(p):
                for n in names:
                    full = os.path.join(dirpath, n)
                    rel = os.path.relpath(full, p).replace('\\', '/')
                    files.append(rel)
            out.append({'dir': name, 'path': p, 'files': sorted(files)})
    return out


def cmd_save(args):
    note = 'change'
    files = []
    i = 0
    while i < len(args):
        if args[i] == '--note':
            i += 1
            note = args[i] if i < len(args) else note
        else:
            files.append(args[i])
        i += 1
    files = [f for f in files if f]
    if not files:
        print(json.dumps({'error': 'usage: rollback.py save <file...> --note "desc"'}, ensure_ascii=False))
        return
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    safe = ''.join(c if c.isalnum() or c in '-_' else '-' for c in note)[:40]
    dest = os.path.join(BACKUPS, f'{ts}-{safe}')
    saved = []
    for f in files:
        src = os.path.normpath(os.path.join(ROOT, f))
        if not os.path.isfile(src):
            print(json.dumps({'skip_not_found': f}, ensure_ascii=False))
            continue
        target = os.path.join(dest, os.path.relpath(src, ROOT))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(src, target)
        saved.append(f.replace('\\', '/'))
    with open(os.path.join(dest, '_manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump({'time': ts, 'note': note, 'files': saved}, fh, ensure_ascii=False, indent=2)
    print(json.dumps({'saved_to': os.path.relpath(dest, ROOT).replace('\\', '/'), 'files': saved}, ensure_ascii=False))


def cmd_list(_args):
    pts = points()
    if not pts:
        print('no backups')
        return
    for idx, p in enumerate(pts, 1):
        print(f'[{idx}] {p["dir"]}  ({len(p["files"])} files)')
        for f in p['files']:
            print(f'      {f}')


def cmd_back(args):
    pts = points()
    if not pts:
        print('no backups to restore')
        return
    sel = args[0] if args else '1'
    if sel == 'all':
        chosen = pts
    elif sel.isdigit() and 1 <= int(sel) <= len(pts):
        chosen = [pts[int(sel) - 1]]
    else:
        print(json.dumps({'error': 'bad index', 'hint': 'use list first'}, ensure_ascii=False))
        return
    for p in chosen:
        pre = os.path.join(BACKUPS, '.pre-restore', p['dir'])
        for rel in p['files']:
            if rel == '_manifest.json':
                continue
            cur = os.path.join(ROOT, rel.replace('/', os.sep))
            bak_src = os.path.join(p['path'], rel.replace('/', os.sep))
            if os.path.isfile(cur):
                t = os.path.join(pre, rel.replace('/', os.sep))
                os.makedirs(os.path.dirname(t), exist_ok=True)
                if not os.path.exists(t):
                    shutil.copy2(cur, t)
            os.makedirs(os.path.dirname(cur) or '.', exist_ok=True)
            shutil.copy2(bak_src, cur)
            print(f'restored: {rel}  <- {p["dir"]}')
    print('done. (current versions kept under _backups/.pre-restore/)')


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else 'list'
    rest = args[1:]
    if cmd == 'save':
        cmd_save(rest)
    elif cmd == 'back':
        cmd_back(rest)
    else:
        cmd_list(rest)


if __name__ == '__main__':
    main()
