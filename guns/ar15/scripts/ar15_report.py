"""ar15_report.py - system-Python summary of a build: anchor deltas against M4Tactical (INTEGRATION.md), the socket list,
per-part / per-config triangle counts and LODs, texel density.  Writes out/anchor_deltas.json and out/summary.md.
    python ar15_report.py"""
import os, json, math, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
sys.path.insert(0, HERE)
import ar15_spec as SP

def load(p): return json.load(open(os.path.join(OUT, p)))

def anchors():
    rows = []
    for gun in ('SM_AR15_MLOK', 'SM_AR15_M4Quad'):
        S = {s['name']: s for s in load('sockets_%s.json' % gun)['sockets']}
        def d(name, ref, ours):
            dv = [None if r is None else round(o - r, 2) for o, r in zip(ours, ref)]
            mag = math.sqrt(sum(x * x for x in dv if x is not None))
            rows.append(dict(gun=gun, anchor=name, m4tactical=ref, ours=[round(c, 2) for c in ours], delta=dv, dist_cm=round(mag, 2),
                             within_1cm=mag <= 1.0))
        d('Trigger blade (M4T measured pad)', SP.M4T['Trigger blade (measured)'], S['Trigger']['loc'])
        d('Trigger socket (M4T: on its grip front)', SP.M4T['Trigger (socket, on its grip front)'], S['Trigger']['loc'])
        d('GripCyl_R', SP.M4T['GripCyl_R'], S['GripCyl_R']['loc'])
        d('bore line (x, -, z)', (-0.80, None, 12.14), (0.0, 0.0, S['Muzzle']['loc'][2]))
        d('MagazineSocket', SP.M4T['MagazineSocket'], S['MagazineSocket']['loc'])
        d('Optic_Socket', SP.M4T['Optic_Socket'], S['Optic_Socket']['loc'])
        d('Grip_Socket', SP.M4T['Grip_Socket'], S['Grip_Socket']['loc'])
        d('mag release', SP.M4T['mag release'], S['MagRelease']['loc'])
        d('bolt catch', SP.M4T['bolt catch'], S['BoltCatch']['loc'])
        d('Muzzle', SP.M4T['Muzzle'], S['Muzzle']['loc'])
        d('Stock', SP.M4T['Stock'], S['Stock']['loc'])
        lop = S['Trigger']['loc'][1] - S['Stock']['loc'][1]
        rows.append(dict(gun=gun, anchor='length of pull (trigger blade -> Stock socket, cm)', m4tactical=30.4, ours=round(lop, 2),
                         delta=round(lop - 30.4, 2), note='M4Tactical 30.4 is measured from its Trigger socket on the grip front'))
    json.dump(rows, open(os.path.join(OUT, 'anchor_deltas.json'), 'w'), indent=1)
    return rows

def main():
    rows = anchors()
    rep = load('assembly_report.json'); ver = load('verify_report.json')
    lines = ['# AR-15 build summary', '']
    lines.append('## Anchor deltas vs M4Tactical (F frame, cm; delta = ours - M4Tactical)')
    lines.append('| gun | anchor | M4Tactical | ours | delta | |delta| |')
    lines.append('|---|---|---|---|---|---|')
    for r in rows:
        lines.append('| %s | %s | %s | %s | %s | %s |' % (r['gun'], r['anchor'], r['m4tactical'], r['ours'], r['delta'], r.get('dist_cm', '')))
    lines += ['', '## Triangles', '| part | tris | slots | configs | bone | in static mesh |', '|---|---|---|---|---|---|']
    for n, p in rep['parts'].items():
        lines.append('| %s | %d | %s | %s | %s | %s |' % (n, p['tris'], ','.join(p['slots']), ','.join(p['configs']) or 'accessory', p['bone'], 'yes' if p['static'] and p['configs'] else 'no'))
    lines += ['', '| assembled | LOD0 | LOD1 | LOD2 |', '|---|---|---|---|']
    for g, v in rep['guns'].items():
        lines.append('| %s | %d | %d (%.2f) | %d (%.2f) |' % (g, v['tris'], v['lod1']['tris'], v['lod1']['ratio'], v['lod2']['tris'], v['lod2']['ratio']))
    lines += ['', '## Texel density: %.2f px/cm' % rep['texel_px_per_cm'], '| atlas | slot | texture | px/cm | coverage % | overlap % |', '|---|---|---|---|---|---|']
    for a, v in rep['atlases'].items():
        lines.append('| %s | %s | %d | %.2f | %.1f | %.3f |' % (a, v['slot'], v['texture'], v['texel_px_per_cm'], v['uv_coverage_pct'], v['overlap_pct']))
    lines[-len(rep['atlases']) - 3] = '## Texel density: %.2f px/cm (hero slots Receiver / Handguard: %.2f px/cm)' % (rep['texel_px_per_cm'], rep.get('texel_px_per_cm_hero', 0))
    gp = os.path.join(OUT, 'game_parts.json')
    if os.path.exists(gp):
        G = json.load(open(gp))
        lines += ['', '## Game parts (out/game_parts.json)', '| mesh | frame | tris | LOD1 | LOD2 | slots | sockets | attach |', '|---|---|---|---|---|---|---|---|']
        for m in G['meshes']:
            at = m['attach']; lines.append('| %s | %s | %d | %d | %d | %s | %d | %s |' % (m['name'], m['frame'], m['tris'], m['lod_tris'][0], m['lod_tris'][1],
                                                                                  ','.join(m['slots']), len(m['socket_names']),
                                                                                  '%s.%s' % (at['parent'], at['socket']) if at else 'core'))
        lines.append('')
        lines.append('Assembled: default %s tris, M4Quad %s tris (magazine + round included).  FSB over the low-profile block: %s.' %
                     (format(G['assembled_tris']['default'], ','), format(G['assembled_tris']['m4quad'], ','),
                      'OK' if G['checks']['fsb_covers_lpgb']['ok'] else 'FAIL'))
    lines += ['', '## Verify: %s' % ('ALL OK' if ver.get('ALL_OK') else 'FAILURES')]
    open(os.path.join(OUT, 'summary.md'), 'w').write('\n'.join(lines) + '\n')
    for r in rows:
        print('%-15s %-44s M4T %-22s ours %-26s delta %s' % (r['gun'], r['anchor'], r['m4tactical'], r['ours'], r['delta']))

if __name__ == '__main__':
    main()
