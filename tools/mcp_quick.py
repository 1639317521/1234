import os, sys, json, uuid, time, re, urllib.request, urllib.error

_PORT = os.environ.get("WUCANVAS_PORT", "3000")
BASE = os.environ.get("WUCANVAS_MCP_BASE_URL", f'http://127.0.0.1:{_PORT}').rstrip("/")

BOX_W, BOX_H_PROMPT, BOX_H_GEN = 320, 170, 280
STEP_Y, STEP_X = 240, 380

# smart 画布 smart-image 节点默认 runSettings（对齐「小胖1」结构，16:9 = ratio wide + resolution 4k）
SMART_RUNSETTINGS = {
    'engine': 'api',
    'apiKind': 'image',
    'provider_id': 'custom-api-4',
    'model': 'gpt-image-2',
    'ratio': 'wide',
    'resolution': '4k',
    'customRatio': '',
    'customRatioWidth': '',
    'customRatioHeight': '',
    'customSize': '',
    'customWidth': '',
    'customHeight': '',
    'quality': 'high',
    'count': 1,
    'videoProvider': '',
    'videoModel': '',
    'videoDuration': 5,
    'videoAspect': '16:9',
    'videoResolution': '',
    'videoEnhancePrompt': False,
    'videoEnableUpsample': False,
    'videoWatermark': False,
    'videoCameraFixed': False,
    'videoGenerateAudio': False,
    'videoMultimodal': True,
    '_videoMultimodalUserSet': False,
    'videoUseFrameRoles': False,
    'videoTrustedAsset': False,
    'videoTrustedSource': 'library',
    'videoTempShLinks': [],
    'msgenModel': 'zimage',
    'msCustomModel': '',
    'msRatio': 'square',
    'msResolution': '1k',
    'msCustomRatio': '',
    'msCustomRatioWidth': '',
    'msCustomRatioHeight': '',
    'msCustomSize': '',
    'msCustomWidth': '',
    'msCustomHeight': '',
    'comfyMode': 'text',
    'comfyWorkflow': '',
    'comfyParams': {},
    'width': 1024,
    'height': 1024,
    'enhanceStrength': 0.5,
    'enhanceUpscale': False,
    'enhanceUpscaleRes': 2048,
    'editUpscale': False,
    'editUpscaleRes': 2048,
    'jimengUpscaleRes': '2k',
    'promptH': 124,
}


def http_json(req):
    return json.load(urllib.request.urlopen(req, timeout=10))


def get(url):
    return http_json(urllib.request.Request(url))


def pick_canvas():
    """选当前激活画布：优先取前端心跳上报（selection.at）最新的；无上报数据时回退到最近更新的画布。"""
    cvs = get(f'{BASE}/api/canvases').get('canvases') or []
    live = [c for c in cvs if not c.get('deleted_at')]
    if not live:
        return None
    live.sort(key=lambda c: c.get('updated_at') or 0, reverse=True)
    best_fallback = live[0]['id']
    best_at, active = 0, None
    for c in live:
        try:
            sel = get(f"{BASE}/api/canvases/{c['id']}/mcp-selection")
            at = float(sel.get('at') or 0)
            if at > best_at:
                best_at, active = at, c['id']
        except Exception:
            continue
    return active or best_fallback


def short_title(text):
    seg = re.split(r'[，,。;；!！?？\n]', text.strip())[0]
    seg = re.sub(r'\s+', '', seg)
    return seg[:12] or '提示词'


def smart_title(text):
    """smart-image 节点标题：优先取「角色为 X / 角色是 X」里的角色名，否则取首段前 12 字。"""
    m = re.search(r'角色(?:为|是)\s*([^，,。;；!！?？\n]+)', text)
    if m:
        return m.group(1).strip()[:12] or 'Image'
    return short_title(text)


def smart_runsettings(cv, nodes):
    """取画布最近的 smart-image 节点的 runSettings 作为模板（沿用 provider/model），缺省用默认 16:9。"""
    rs = dict(SMART_RUNSETTINGS)
    cands = [n for n in nodes if n.get('type') == 'smart-image' and isinstance(n.get('runSettings'), dict)]
    if cands:
        tmpl = cands[-1]['runSettings']
        for key in ('engine', 'apiKind', 'provider_id', 'model', 'quality'):
            if key in tmpl:
                rs[key] = tmpl[key]
    # 固定 16:9
    rs['ratio'] = 'wide'
    rs['resolution'] = '4k'
    rs['count'] = 1
    return rs


def viewport_center(cv, cid):
    """返回当前视口中心的世界坐标；视口缩放异常或拿不到有效中心时返回 None。"""
    vp = cv.get('viewport') or {}
    try:
        scale = float(vp.get('scale') or 1)
    except Exception:
        scale = 1
    # 缩放正常范围约 0.001~20；出现天文数字说明视口被滚爆，视为不可用
    if not 0.001 <= scale <= 20:
        return None
    sel = {}
    try:
        sel = get(f'{BASE}/api/canvases/{cid}/mcp-selection') or {}
    except Exception:
        pass
    x, y = float(sel.get('x') or 0), float(sel.get('y') or 0)
    if x or y:
        return x, y
    # 无前端上报时，用视口偏移反推屏幕中心（默认 1920x1080）
    if vp.get('x') is not None and scale > 0:
        return (960.0 - float(vp.get('x') or 0)) / scale, (540.0 - float(vp.get('y') or 0)) / scale
    return None


def latest_node_anchor(nodes):
    """无有效视口时的回退锚点：现有节点包围盒右侧，向下找空位（避免重叠）。"""
    if not nodes:
        return 200.0, 300.0
    xs = [float(n.get('x') or 0) for n in nodes]
    ys = [float(n.get('y') or 0) for n in nodes]
    return max(xs) + BOX_W + 40.0, (min(ys) + max(ys)) / 2.0


def existing_boxes(nodes):
    out = []
    for n in nodes:
        try:
            out.append((float(n.get('x') or 0), float(n.get('y') or 0), BOX_W,
                        BOX_H_GEN if n.get('type') == 'generator' else BOX_H_PROMPT))
        except Exception:
            pass
    return out


def overlaps(b, boxes):
    bx, by, bw, bh = b
    for x, y, w, h in boxes:
        if bx < x + w and x < bx + bw and by < y + h and y < by + bh:
            return True
    return False


def find_free_spot(boxes, cx, cy, with_gen):
    total_h = BOX_H_GEN if with_gen else BOX_H_PROMPT
    col = 0
    for _ in range(40):
        px, py = cx - 150 + col * STEP_X, cy
        while overlaps((px, py, BOX_W, total_h), boxes):
            py += STEP_Y
            if py > cy + 12 * STEP_Y:
                break
        if not overlaps((px, py, BOX_W, total_h), boxes):
            return px, py
        col += 1
    return cx - 150, cy


def save(cid, cv, nodes, conns):
    body = {'title': cv.get('title', ''), 'icon': cv.get('icon', ''),
            'nodes': nodes, 'connections': conns,
            'viewport': cv.get('viewport') or {}, 'logs': cv.get('logs') or [],
            'settings': cv.get('settings') or {}, 'comfyQueue': cv.get('comfyQueue') or [],
            'client_id': 'mcp-quick', 'base_updated_at': int(cv.get('updated_at') or 0)}
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(f'{BASE}/api/canvases/{cid}', data=data, method='PUT',
                                 headers={'Content-Type': 'application/json; charset=utf-8'})
    return http_json(req)


def main():
    args = sys.argv[1:]
    texts, with_gen, canvas_id, title = [], False, '', ''
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--gen':
            with_gen = True
        elif a == '--canvas':
            i += 1
            canvas_id = args[i] if i < len(args) else ''
        elif a == '--title':
            i += 1
            title = args[i] if i < len(args) else ''
        elif a == '--file':
            i += 1
            texts.append(open(args[i], encoding='utf-8-sig').read().strip())
        elif a.strip():
            texts.append(a.strip())
        i += 1
    if not texts:
        print(json.dumps({'error': 'usage: mcp_quick.py "text" ["text2"...] [--gen] [--canvas id] [--title 名]'}, ensure_ascii=False))
        return
    cid = canvas_id or pick_canvas()
    if not cid:
        print(json.dumps({'error': 'no canvas found'}))
        return

    added = []
    for attempt in range(3):
        cv = get(f'{BASE}/api/canvases/{cid}')
        cv = cv.get('canvas') if isinstance(cv, dict) and 'canvas' in cv else cv
        nodes = [dict(n) for n in cv.get('nodes') or []]
        conns = [dict(c) for c in cv.get('connections') or []]
        boxes = existing_boxes(nodes)

        is_smart = cv.get('kind') == 'smart'
        tmpl = None
        if with_gen and not is_smart:
            gens = [n for n in nodes if n.get('type') == 'generator']
            if gens:
                tmpl = gens[-1]
        center = viewport_center(cv, cid)
        if center is None:
            # 视口不可用（缩放异常等）时，回退到现有节点右侧，find_free_spot 会继续找空位避免重叠
            center = latest_node_anchor(nodes)
        cx, cy = center
        now = int(time.time() * 1000)

        new_ids = []
        for k, text in enumerate(texts):
            spot_cx = cx + (k % 2) * (STEP_X // 2)
            spot_cy = cy + (k // 2) * (BOX_H_GEN + 80)
            px, py = find_free_spot(boxes, spot_cx, spot_cy, with_gen and not is_smart)
            if is_smart:
                # smart 画布：创建 smart-image 节点（对齐「小胖1」结构）
                nd_title = (title if k == 0 and title else '') or smart_title(text)
                nd = {'id': 'smart_' + uuid.uuid4().hex, 'type': 'smart-image',
                      'x': float(px), 'y': float(py), 'title': nd_title, 'displayTitle': nd_title,
                      'images': [], 'created_at': now, 'scale': 1,
                      'runSettings': smart_runsettings(cv, nodes),
                      'promptDraftText': text, 'promptDraftHtml': text}
                nodes.append(nd)
                boxes.append((nd['x'], nd['y'], BOX_W, BOX_H_GEN))
                added.append({'id': nd['id'], 'type': 'smart-image', 'title': nd_title,
                              'x': round(nd['x'], 1), 'y': round(nd['y'], 1)})
                continue
            np_ = {'id': 'prompt_' + uuid.uuid4().hex, 'type': 'prompt',
                   'x': float(px), 'y': float(py),
                   'text': text, 'title': short_title(text)}
            entry = {'prompt': np_['id'], 'title': np_['title'], 'x': round(np_['x'], 1), 'y': round(np_['y'], 1)}
            nodes.append(np_)
            boxes.append((np_['x'], np_['y'], BOX_W, BOX_H_PROMPT))
            if with_gen:
                ng = {k2: v for k2, v in (tmpl or {}).items() if k2 not in ('id', 'output', 'outputs', 'status', 'error')}
                ng.setdefault('type', 'generator')
                ng.setdefault('apiProvider', 'custom-api')
                ng.setdefault('model', 'gpt-image-2')
                ng.setdefault('ratio', 'wide')
                ng.setdefault('resolution', '4k')
                ng['id'] = 'gen_' + uuid.uuid4().hex[:12] + '_' + str(now + k)
                ng['x'] = px + BOX_W + 30
                ng['y'] = py
                ng['inputs'] = [np_['id']]
                conn = {'id': 'c_' + uuid.uuid4().hex[:8] + '_' + str(now + k),
                        'from': np_['id'], 'to': ng['id']}
                nodes.append(ng)
                conns.append(conn)
                boxes.append((ng['x'], ng['y'], BOX_W, BOX_H_GEN))
                entry['gen'] = ng['id']
                entry['conn'] = conn['id']
            added.append(entry)

        try:
            save(cid, cv, nodes, conns)
        except urllib.error.HTTPError as e:
            if e.code == 409 and attempt < 2:
                added = []
                time.sleep(0.6)
                continue
            print(json.dumps({'error': f'HTTP {e.code}'}, ensure_ascii=False))
            return
        break

    print(json.dumps({'ok': True, 'canvas': cid, 'total_nodes': len(nodes), 'added': added}, ensure_ascii=False))


if __name__ == '__main__':
    main()
