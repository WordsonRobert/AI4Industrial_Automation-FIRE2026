"""Per-task figure: verifier verdict vs behavioural probes, sorted by required I/O."""
import json, os, sys
R = os.path.dirname(os.path.abspath(__file__)) + '/'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'fig_tasks.tex'
rows = [l.split() for l in open(R + 'task_matrix.dat').read().strip().split('\n')[1:]]
out = json.load(open(R + 'output_numbers.json'))
C = out['configs']
data = []
for r in rows:
    t = int(r[0])
    d = dict(task=t, io=int(r[6]), v={'oneshot7': int(r[1]), 'repair7': int(r[2]), 'repair15': int(r[3])})
    d['act'] = {c: C[c]['active_per_task'][str(t)] for c in C}
    d['all'] = {c: t in C[c]['probe_tasks_all'] for c in C}
    data.append(d)
data.sort(key=lambda d: (d['io'], d['task']))
W = 4.6; H = 4.6
L = []; A = L.append
A(r"""\documentclass[border=3pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage{libertinus}
\usepackage{tikz}
\definecolor{good}{HTML}{0CA30C}\definecolor{warn}{HTML}{FAB219}\definecolor{crit}{HTML}{D03B3B}
\definecolor{ink}{HTML}{1F2933}\definecolor{muted}{HTML}{6B7280}\definecolor{bar}{HTML}{86B6EF}
\definecolor{beh}{HTML}{1F4E8C}\definecolor{zero}{HTML}{EEF0F3}
\begin{document}
\begin{tikzpicture}[x=1mm,y=1mm,font=\footnotesize\color{ink}]""")
n = len(data); maxio = max(d['io'] for d in data); bh = 10.0 / maxio
cfgs = [('oneshot7', '7B, single pass'), ('repair7', '7B + repair'), ('repair15', '1.5B + repair')]
rowgap = 1.6
top = 3 * (2 * H + rowgap) + H + 3.0
for i, d in enumerate(data):
    x = i * W; h = d['io'] * bh
    A(r"\fill[bar] (%.2f,%.2f) rectangle (%.2f,%.2f);" % (x + 0.7, top, x + W - 0.7, top + h))
    A(r"\node[font=\scriptsize, anchor=south, inner sep=0.5pt] at (%.2f,%.2f) {%d};" % (x + W / 2, top + h, d['io']))
A(r"\node[anchor=east] at (-1.2,%.2f) {required I/O};" % (top + 3.5))
yA = top - H - 1.0
for i, d in enumerate(data):
    A(r"\node[font=\scriptsize, text=muted] at (%.2f,%.2f) {%d};" % (i * W + W / 2, yA + H / 2, d['act']['repair7'][1]))
A(r"\node[anchor=east, text=muted] at (-1.2,%.2f) {active checks};" % (yA + H / 2))
for j, (c, label) in enumerate(cfgs):
    base = (2 - j) * (2 * H + rowgap)
    yv, yb = base + H, base
    A(r"\node[anchor=east] at (-1.2,%.2f) {%s};" % (base + H, label))
    for i, d in enumerate(data):
        x = i * W
        col, txt, tc = {2: ('good', 'C', 'white'), 1: ('warn', 'I', 'ink'), 0: ('crit', 'F', 'white')}[d['v'][c]]
        A(r"\fill[%s, rounded corners=0.5pt] (%.2f,%.2f) rectangle (%.2f,%.2f);" % (col, x + 0.3, yv + 0.3, x + W - 0.3, yv + H - 0.3))
        A(r"\node[text=%s, font=\scriptsize\bfseries, inner sep=0] at (%.2f,%.2f) {%s};" % (tc, x + W / 2, yv + H / 2, txt))
        k, tot = d['act'][c]
        f = k / tot if tot else 0
        fill = 'zero' if k == 0 else 'beh!%d!white' % round(25 + 75 * f)
        tcol = 'white' if f > 0.5 else ('muted' if k == 0 else 'ink')
        A(r"\fill[%s, rounded corners=0.5pt] (%.2f,%.2f) rectangle (%.2f,%.2f);" % (fill, x + 0.3, yb + 0.3, x + W - 0.3, yb + H - 0.3))
        if d['all'][c]:
            A(r"\draw[ink, line width=0.7pt, rounded corners=0.5pt] (%.2f,%.2f) rectangle (%.2f,%.2f);" % (x + 0.35, yb + 0.35, x + W - 0.35, yb + H - 0.35))
        A(r"\node[text=%s, font=\scriptsize, inner sep=0] at (%.2f,%.2f) {%d};" % (tcol, x + W / 2, yb + H / 2, k))
for i, d in enumerate(data):
    A(r"\node[font=\scriptsize, text=muted, anchor=north] at (%.2f,-0.6) {%d};" % (i * W + W / 2, d['task']))
A(r"\node[anchor=east, text=muted] at (-1.2,-2.3) {task};")


def sw(col, txt, tc, extra=''):
    return (r"\tikz[baseline=-0.6ex]{\fill[%s,rounded corners=0.5pt] (0,-1.7mm) rectangle (3.4mm,1.7mm);%s"
            r"\node[anchor=center,text=%s,font=\scriptsize\bfseries,inner sep=0] at (1.7mm,0) {%s};}" % (col, extra, tc, txt))


box = r"\draw[ink,line width=0.7pt,rounded corners=0.5pt] (0.05mm,-1.65mm) rectangle (3.35mm,1.65mm);"
A(r"\node[anchor=north, align=center] at (%.2f,-5.0) {" % (n * W / 2)
  + r"verifier: " + sw('good', 'C', 'white') + r"\ clean\quad " + sw('warn', 'I', 'ink') + r"\ issues flagged\quad "
  + sw('crit', 'F', 'white') + r"\ no parseable AST\qquad behaviour: " + sw('zero', '0', 'muted')
  + r"\," + sw('beh!50!white', '2', 'ink') + r"\," + sw('beh', '3', 'white')
  + r"\ active checks passed (shade = fraction)\quad " + sw('beh', '3', 'white', box) + r"\ all checks pass};")
A(r"\end{tikzpicture}"); A(r"\end{document}")
open(OUT, 'w').write('\n'.join(L).replace('active checks passed (shade = fraction)', 'active checks earned (shade = fraction)'))
print('wrote', OUT)
