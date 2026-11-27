import sys, re
base_p, add_p = sys.argv[1], sys.argv[2]
def parse(lines):
    secs, order, cur = {}, [], None
    for l in lines:
        s = l.rstrip('\r\n')
        m = re.match(r'^\[(.+)\]$', s.strip())
        if m:
            cur = m.group(1); 
            if cur not in secs: secs[cur] = []; order.append(cur)
            continue
        if cur is None: continue
        secs[cur].append(s)
    return secs, order
bs, bo = parse(open(base_p, encoding='utf-8-sig').readlines())
as_, ao = parse(open(add_p, encoding='utf-8').readlines())
for sec in ao:
    if sec not in bs: bs[sec] = []; bo.append(sec)
    tgt = bs[sec]
    for l in as_[sec]:
        t = l.strip()
        if not t or t.startswith(';'): 
            continue
        if t[0] in '+-':
            if t not in [x.strip() for x in tgt]: tgt.append(t)
            continue
        k = t.split('=',1)[0]
        idx = [i for i,x in enumerate(tgt) if x.strip().split('=',1)[0] == k and not x.strip().startswith(';')]
        if idx: tgt[idx[0]] = t
        else: tgt.append(t)
out = []
for sec in bo:
    body = bs[sec]
    while body and not body[-1].strip(): body.pop()
    out.append(f'[{sec}]'); out += body; out.append('')
open(base_p, 'w', encoding='utf-8', newline='\r\n').write('\n'.join(out) + '\n')
print('ok')
