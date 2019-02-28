#! /usr/local/bin/python3
#  -*- coding: utf-8 -*-

import argparse
from functools import reduce
import math
import os
import re
import sys

from tkinter import *
from tkinter.ttk import *
from tkinter.scrolledtext import *


class Diff:
    def __init__(self, data):
        self.data = data

    def get_time(self):
        t1, t2 = reduce((lambda x, y: (x[0] + y[0].time, x[1] + y[1].time)), self.data, (0, 0))
        return t2 - t1

    def get(self):
        return (self.data[0], self.data[-1])

    def __str__(self):
        t1, t2 = reduce((lambda x, y: ('{} {}'.format(x[0], y[0].time), '{} {}'.format(x[1], y[1].time))), self.data, ('[', '['))
        return '{}:{} {} {}] <-> {}]'.format(self.data[0][0].index, self.data[-1][0].index, self.get_time(), t1, t2)


class Node:
    def __init__(self, parent = None, addr='', name='', time=0):
        self.parent = parent
        self.addr = addr
        self.name = name
        self.time = time
        self.call = 0
        self.children = []
        self.tags = None
        self.index = 0
        self.opened = False
        self.row = 0

    def count_rows(self):
        result = 1
        if self.opened:
            for c in self.children:
                result += c.count_rows() if c.opened else 1
        return result

    def __str__(self):
        c = reduce((lambda x, y: '{0}\n{1}'.format(x, y)), self.children, '').replace('\n', '\n  ')
        return '{:7d} {} {} calls {}{}'.format(self.time, self.addr, self.name, self.call, c) if self.call > 0 else '{:7d} {} {}'.format(self.time, self.addr, self.name)


class Tree:
    def __init__(self, trace):
        self.roots = []
        nodes = []
        pattern = r'([0-9]+) (>>|<<) 0x([0-9a-f]+) (.*)'
        end_of_time = 0
        with open(trace, mode='r') as f:
            for line in f:
                m = re.match(pattern, line)
                if m:
                    (time, action, address, name) = (int(m.group(1)), m.group(2), m.group(3), m.group(4))
                    end_of_time = time
                    if action == '>>':
                        nodes.append(Node(nodes[-1] if len(nodes) > 0 else None, address, name, time))
                    else:
                        n = nodes.pop()
                        if n.addr != address:
                            print('Invalid stack {0} != {1}'.format(n.addr, address))
                        n.time = time - n.time
                        n.call = len(n.children)
                        if len(nodes) == 0:
                            self.roots.append(n)
                        else:
                            n.index = len(nodes[-1].children)
                            nodes[-1].children.append(n)
        while len(nodes) > 1:
            n = nodes.pop()
            n.time = end_of_time - n.time
            n.call = len(n.children)
            n.index = len(nodes[-1].children)
            nodes[-1].children.append(n)
        if len(nodes) > 0:
            n = nodes.pop()
            n.time = end_of_time - n.time
            n.call = len(n.children)
            n.index = len(self.roots)
            self.roots.append(n)

    def __str__(self):
        return reduce((lambda x, y: '{0}\n{1}'.format(x, y)), self.roots, '{0} roots:'.format(len(self.roots)))

    def count_rows(self):
        result = 0
        for n in self.roots:
            result += n.count_rows()
        return result

    def compute_rows(self):
        stack = []
        current = 0
        index = len(self.roots)
        while index > 0:
            index -= 1
            stack.append(self.roots[index])
        while len(stack) > 0:
            current += 1
            n = stack.pop()
            n.row = current
            if n.opened:
                index = len(n.children)
                while index > 0:
                    index -= 1
                    stack.append(n.children[index])


class CallTreeview(Frame):
    def __init__(self, frame, tree, st):
        Frame.__init__(self, frame)
        self.tree = tree
        sb = Scrollbar(self)
        tv = Treeview(self, height=50, columns=('time', 'numb', 'call'))
        sb.config(command=tv.yview)
        tv.config(yscrollcommand=self.on_scroll)
        tv.column('time', anchor=E, stretch=FALSE, width=150)
        tv.column('numb', anchor=E, stretch=FALSE, width=50)
        tv.column('call', anchor=E, stretch=FALSE, width=50)
        tv.heading('time', text='microseconds')
        tv.heading('numb', text='#')
        tv.heading('call', text='# calls')
        tv.tag_configure('diff', background='yellow')
        tv.tag_configure('only', background='pink')
        sb.pack(side=RIGHT, fill=Y)
        tv.pack(side=LEFT, expand=YES, fill=BOTH)
        tv.bind('<<TreeviewSelect>>', self.on_select)
        tv.bind('<<TreeviewOpen>>', self.on_open)
        tv.bind('<<TreeviewClose>>', self.on_close)
        self.tv = tv
        self.st = st
        self.sb = sb
        index = 0
        for n in tree.roots:
            index += 1
            calls = '{}'.format(n.call) if n.call > 0 else ''
            ctime = '({})'.format(n.time - reduce((lambda x, y: x + y.time), n.children, 0)) if len(n.children) > 0 else ''
            m = re.match(r'.*::([A-Za-z_][A-Za-z0-9_]*)(?=\().*', n.name)
            name = m.group(1) if m else n.name
            p = tv.insert('', END, text=name, values=('{} {:>7}'.format(ctime, n.time), '{}'.format(index), calls))
            if len(n.children) > 0:
                self.insert_children(p, n)
        self.rows = index
        self.partner = None

    def redisplay(self, *args):
        self.tv.yview(*args)
        print('new view {}'.format(args))

    def on_scroll(self, a, b):
        self.sb.set(a, b)
        row_height = 1 / self.rows
        first_row = float(a) / row_height
        last_row = float(b) / row_height

    def on_select(self, event):
        item = self.tv.selection()
        chain = []
        while item != '':
            chain.append(self.tv.index(item))
            item = self.tv.parent(item)
        self.st.delete('1.0', 'end')
        depth = len(chain) - 1
        node = self.tree.roots[chain.pop()]
        self.st.insert('1.0', '{:>3d}: {}'.format(depth, node.name))
        while chain != []:
            depth -= 1
            node = node.children[chain.pop()]
            self.st.insert('1.0', '{:>3d}: {}\n'.format(depth, node.name))

    def on_open(self, event):
        item = self.tv.focus()
        chain = []
        while item != '':
            chain.append(self.tv.index(item))
            item = self.tv.parent(item)
        node = self.tree.roots[chain.pop()]
        node.opened = True
        while chain != []:
            node = node.children[chain.pop()]
            node.opened = True
        self.rows = self.tree.count_rows()

    def on_close(self, event):
        item = self.tv.focus()
        chain = []
        while item != '':
            chain.append(self.tv.index(item))
            item = self.tv.parent(item)
        node = self.tree.roots[chain.pop()]
        node.opened = True
        while chain != []:
            node = node.children[chain.pop()]
        node.opened = False
        self.rows = self.tree.count_rows()

    def set_partner(self, partner):
        self.partner = partner

    def insert_children(self, parent, node):
        index = 0
        for n in node.children:
            if n.tags != ('skip'):
                index += 1
                calls = '{}'.format(n.call) if n.call > 0 else ''
                ctime = '({})'.format(n.time - reduce((lambda x, y: x + y.time), n.children, 0)) if len(n.children) > 0 else ''
                m = re.match(r'.*::([A-Za-z_][A-Za-z0-9_]*)(?=\().*', n.name)
                name = m.group(1) if m else n.name
                tags = n.tags if n.tags else ()
                p = self.tv.insert(parent, 'end', text=name, values=('{} {:>7}'.format(ctime, n.time), '{}'.format(index), calls), tags=tags)
                if len(n.children) > 0:
                    self.insert_children(p, n)
            else:
                self.tv.insert(parent, 'end', text='', values=('', '', ''), tags=n.tags)


class DiffListbox(Frame):
    def __init__(self, frame, diffs, t1, t2):
        Frame.__init__(self, frame, width=40)
        sb = Scrollbar(self)
        lb = Listbox(self, font=('Menlo'))
        sb.config(command=lb.yview)
        lb.config(yscrollcommand=sb.set, selectmode=SINGLE)
        sb.pack(side=RIGHT, fill=Y)
        lb.pack(side=LEFT, expand=YES, fill=BOTH)
        lb.bind('<<ListboxSelect>>', self.on_left_click)
        for (i, d) in enumerate(diffs):
            lb.insert(END, '{:>5d}: {}'.format(i + 1, d.get_time()))
        self.diffs = diffs
        self.t1 = t1
        self.t2 = t2
        self.lb = lb

    def on_left_click(self, event):
        (index,) = self.lb.curselection()
        (first, last) = self.diffs[index].get()
        (n1, n2) = first
        chain = []
        while n1 != None or n2 != None:
            chain.append((n1, n2))
            n1 = n1.parent
            n2 = n2.parent
        i1, i2 = chain.pop()
        item1 = self.t1.tv.get_children()[i1.index]
        item2 = self.t2.tv.get_children()[i2.index]
        n1 = self.t1.tree.roots[i1.index]
        is_opened1 = n1.opened
        n1.opened = True
        n2 = self.t2.tree.roots[i2.index]
        is_opened2 = n2.opened
        n2.opened = True
        while chain != []:
            i1, i2 = chain.pop()
            item1 = self.t1.tv.get_children(item1)[i1.index]
            item2 = self.t2.tv.get_children(item2)[i2.index]
            n1 = n1.children[i1.index]
            is_opened1 = n1.opened
            n1.opened = True
            n2 = n2.children[i2.index]
            is_opened2 = n2.opened
            n2.opened = True
        n1.opened = is_opened1
        n2.opened = is_opened2
        self.t1.tv.see(item1)
        self.t2.tv.see(item2)
        self.t1.tv.selection_set([item1])
        self.t2.tv.selection_set([item2])
        self.t1.tree.compute_rows()
        self.t2.tree.compute_rows()
        rows1 = self.t1.tree.count_rows()
        rows2 = self.t2.tree.count_rows()
        loc1 = float(n1.row - 25) / float(rows1)
        loc2 = float(n2.row - 25) / float(rows2)
        yv1 = self.t1.tv.yview()
        yv2 = self.t2.tv.yview()
        #print(' left panel focus row {} of total rows {} computed location {}, actual {}\nright panel focus row {} of total rows {} computed location {}, actual {}'.format(n1.row, rows1, loc1, yv1, n2.row, rows2, loc2, yv2))
        self.t1.tv.yview('moveto', loc1)
        self.t2.tv.yview('moveto', loc2)


class App(Tk):
    def __init__(self, trace_filename1, trace_filename2):
        Tk.__init__(self)
        self.title('Call tree differences {} and {}'.format(trace_filename1, trace_filename2))
        Style().configure('Treeview', font=('Menlo'))

        t1 = Tree(trace_filename1)
        t2 = Tree(trace_filename2)
        list_of_diffs = []
        compare_nodes(t1.roots[-1], t2.roots[-1], list_of_diffs)
        list_of_diffs.sort(key=(lambda x: x.get_time()), reverse=True)

        dw = Panedwindow(self, orient=VERTICAL)
        dw.pack(side=LEFT, expand=YES, fill=BOTH)
        tf = Frame(dw)
        bf = Frame(dw)
        dw.add(tf)
        dw.add(bf)

        st1 = ScrolledText(bf)
        st2 = ScrolledText(bf)
        st1.pack(side=LEFT, expand=YES, fill=BOTH)
        st2.pack(side=RIGHT, expand=YES, fill=BOTH)

        tv1 = CallTreeview(tf, t1, st1)
        tv2 = CallTreeview(tf, t2, st2)
        tv1.set_partner(tv2)
        tv2.set_partner(tv1)
        tv1.pack(side=LEFT, expand=YES, fill=BOTH, pady=2, padx=2)
        tv2.pack(side=RIGHT, expand=YES, fill=BOTH, pady=2, padx=2)

        dl = DiffListbox(self, list_of_diffs, tv1, tv2)
        dl.pack(side=RIGHT, fill=Y)

    def run(self):
        self.mainloop()


def diff(e, f, i=0, j=0):
    N, M, L, Z = len(e), len(f), len(e) + len(f), 2 * min(len(e), len(f)) + 2
    if N > 0 and M > 0:
        w, g, p = N - M, [0] * Z, [0] * Z
        for h in range(0, (L // 2 + (L % 2 != 0)) + 1):
            for r in range(0, 2):
                c, d, o, m = (g, p, 1, 1) if r == 0 else (p, g, 0, -1)
                for k in range(-(h - 2 * max(0, h - M)), h - 2 * max(0, h - N) + 1, 2):
                    a = c[(k + 1) % Z] if (k == -h or k != h and c[(k - 1) % Z] < c[(k + 1) % Z]) else c[(k - 1) % Z] + 1
                    b = a - k
                    s, t = a, b
                    i1 = (1 - o) * N + m * a + (o - 1)
                    i2 = (1 - o) * M + m * b + (o - 1)
                    while a < N and  b < M and e[i1].name == f[i2].name and len(e[i1].children) == len(f[i2].children):
                        a, b = a + 1, b + 1
                        i1 = (1 - o) * N + m * a + (o - 1)
                        i2 = (1 - o) * M + m * b + (o - 1)
                    c[k % Z], z = a, -(k - w)
                    if L % 2 == o and z >= -(h - o) and z <= h - o and c[k % Z] + d[z % Z] >= N:
                        D, x, y, u, v = (2 * h - 1, s, t, a, b) if o == 1 else (2 * h, N - a, M - b, N - s, M - t)
                        if D > 1 or (x != u and y != v):
                            return diff(e[0:x], f[0:y], i, j) + diff(e[u:N], f[v:M], i + u, j + v)
                        elif M > N:
                            return diff([], f[N:M], i + N, j + N)
                        elif M < N:
                            return diff(e[M:N], [], i + M, j + M)
                        else:
                            return []
    else:
        return [{'op': 'del', 'old': i + n} for n in range(0, N)] if N > 0 else [{'op': 'ins', 'old': i, 'new': j + n} for n in range(0, M)]


def synchronize_children(n1, n2):
    diffs = diff(n1.children, n2.children)
    c1, i1, c2, i2, e, skip = [], 0, [], 0, len(diffs), False
    for (i, d) in enumerate(diffs):
        if skip:
            skip = False
            continue
        while i1 < d['old']:
            n1.children[i1].index = len(c1)
            c1.append(n1.children[i1])
            n2.children[i2].index = len(c2)
            c2.append(n2.children[i2])
            i1 += 1
            i2 += 1
        if d['op'] == 'del':
            if i + 1 < e and diffs[i + 1]['op'] == 'ins' and diffs[i + 1]['old'] == i1 + 1 and n1.children[i1].name == n2.children[i2].name:
                skip = True
                n1.children[i1].index = len(c1)
                c1.append(n1.children[i1])
                n2.children[i2].index = len(c2)
                c2.append(n2.children[i2])
                i1 += 1
                i2 += 1
            else:
                n1.children[i1].index = len(c1)
                c1.append(n1.children[i1])
                c2.append(Node(n2))
                c2[-1].index = len(c2) - 1
                i1 += 1
        else:
            if i + 1 < e and diffs[i + 1]['op'] == 'del' and diffs[i + 1]['old'] == i1 and n1.children[i1].name == n2.children[i2].name:
                skip = True
                n1.children[i1].index = len(c1)
                c1.append(n1.children[i1])
                n2.children[i2].index = len(c2)
                c2.append(n2.children[i2])
                i1 += 1
                i2 += 1
            else:
                c1.append(Node(n1))
                c1[-1].index = len(c1) - 1
                n2.children[i2].index = len(c2)
                c2.append(n2.children[i2])
                i2 += 1
    while i1 < len(n1.children) and i2 < len(n2.children):
        n1.children[i1].index = len(c1)
        c1.append(n1.children[i1])
        n2.children[i2].index = len(c2)
        c2.append(n2.children[i2])
        i1 += 1
        i2 += 1
    if len(c1) == len(c2):
        n1.children = c1
        n2.children = c2
    else:
        print('after synchronization children list lengths {} and {}'.format(len(c1), len(c2)))


def compare_nodes(n1, n2, list_of_differences):
    ns = []
    if n1.name != n2.name or len(n1.children) != len(n2.children):
        n1.tags = n2.tags = ('diff')
        list_of_differences.append(Diff([(n1, n2)]))
        if n1.name == n2.name and len(n1.children) > 0 and len(n2.children) > 0:
            synchronize_children(n1, n2)
            for i in range(0, min(len(n1.children), len(n2.children))):
                if n1.children[i].name == n2.children[i].name:
                    if len(ns) > 0:
                        list_of_differences.append(Diff(ns))
                        ns = []
                    compare_nodes(n1.children[i], n2.children[i], list_of_differences)
                elif n1.children[i].name == '':
                    if i > 0 and n1.children[i - 1].tags != ('skip') or i == 0:
                        if len(ns) > 0:
                            list_of_differences.append(Diff(ns))
                            ns = []
                    ns.append((n1.children[i], n2.children[i]))
                    n1.children[i].tags = ('skip')
                    n2.children[i].tags = ('only')
                elif n2.children[i].name == '':
                    if i > 0 and n1.children[i - 1].tags != ('only') or i == 0:
                        if len(ns) > 0:
                            list_of_differences.append(Diff(ns))
                            ns = []
                    ns.append((n1.children[i], n2.children[i]))
                    n1.children[i].tags = ('only')
                    n2.children[i].tags = ('skip')
                else:
                    if len(ns) > 0:
                        list_of_differences.append(Diff(ns))
                        ns = []
                    n1.children[i].tags = ('diff')
                    n2.children[i].tags = ('diff')
                    list_of_differences.append(Diff([(n1.children[i], n2.children[i])]))
            if len(ns) > 0:
                list_of_differences.append(Diff(ns))
    else:
        for c in range(len(n1.children)):
            compare_nodes(n1.children[c], n2.children[c], list_of_differences)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        usage='%(prog)s <file name> <file name>',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Compares two traces produced by running applications instrumented with -finstrument-functions compiler option.\n',
        epilog='For example:\npython compare_traces.py thread0x1.trace thread0x2.trace')
    parser.add_argument('files', nargs=2, help='Trace file names.')
    args = parser.parse_args()
    print('Comparing {0} with {1} ...'.format(args.files[0], args.files[1]))
    app = App(args.files[0], args.files[1])
    app.run()
    print('Finished.')
