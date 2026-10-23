"""Parse dis7x instruction text into (pred, mnemonic, unit, skeleton, atoms)."""
import re

PRED = re.compile(r'^\[(!?)(A[0-5])\]\s*')
ATOM = re.compile(r'(\$[+-](?:0x[0-9a-f]+|\d+))|(\*?)([A-Z][A-Z0-9_]*)(\+\+|--)?|(0x[0-9a-f]+|\d+)')

def parse(text):
    t = text.strip()
    par = False
    if t.startswith('||'):
        par = True; t = t[2:].strip()
    pred = None
    m = PRED.match(t)
    if m:
        pred = m.group(1) + m.group(2); t = t[m.end():]
    parts = t.split(None, 1)
    if not parts:
        return None
    mn = parts[0]
    rest = parts[1] if len(parts) > 1 else ''
    unit = ''
    if rest.startswith('.'):
        u = rest.split(None, 1)
        unit = u[0]; rest = u[1] if len(u) > 1 else ''
    rest = rest.strip()
    skel = []; atoms = []
    pos = 0
    for m in ATOM.finditer(rest):
        skel.append(rest[pos:m.start()])
        if m.group(1):
            skel.append('L'); atoms.append(('L', m.group(1)))
        elif m.group(3):
            star, name, inc = m.group(2), m.group(3), m.group(4) or ''
            if star:
                skel.append('*R' + inc); atoms.append(('R', name))
            else:
                skel.append('R'); atoms.append(('R', name + inc))
        else:
            skel.append('N'); atoms.append(('N', m.group(5)))
        pos = m.end()
    skel.append(rest[pos:])
    return dict(par=par, pred=pred, mn=mn, unit=unit, skel=''.join(skel), atoms=atoms)

def unit_base(u):
    return u[:-1] if u.endswith('X') else u

def key(p):
    return '%s|%s|%s|%s' % (p['mn'], unit_base(p['unit']), p['skel'], 'P' if p['pred'] else '')

def numval(s):
    if s.startswith('$'):
        v = int(s[2:], 0)
        return -v if s[1] == '-' else v
    return int(s, 16) if s.startswith('0x') else int(s)
