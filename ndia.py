from bisect import insort, bisect_left, bisect_right
from dataclasses import dataclass, field
from functools import reduce
from ipaddress import _BaseAddress, _BaseNetwork, ip_address, ip_network
from operator import attrgetter

class GraphViz:
    indent = 0

    def __init__(self, out):
        self.out = out

    def write(self, s):
        self.out.write(s)

    @staticmethod
    def string(s):
        return '"' + s.replace('"', '\\"') + '"'

    @classmethod
    def alist(cls, kv):
        if isinstance(kv, dict):
            kv = list(kv.items())
        for key, val in kv:
            yield f'{key}={val}'

    @classmethod
    def styled(cls, expr, kv):
        if not kv:
            return expr
        return f'{expr} [{" ".join(cls.alist(kv))}]'

    def indented(self, s):
        return '\t' * self.indent + s + '\n'

    @staticmethod
    def stmt(s):
        return s + ';'

    def write_stmt(self, s):
        self.write(self.indented(self.stmt(s)))

    @dataclass
    class _GroupCtx:
        gv: 'GraphViz'
        prefix: str

        def __enter__(self):
            self.gv.write(self.gv.indented(self.prefix + ' {'))
            self.gv.indent += 1

        def __exit__(self, *exc_info):
            self.gv.indent -= 1
            self.gv.write(self.gv.indented('} // ' + self.prefix))

    def group(self, pfx):
        return self._GroupCtx(self, pfx)

@dataclass
class NIC:
    name: str | None
    address: _BaseAddress
    host: 'Host | None' = None
    net: 'Net | None' = None
    info: dict = field(default_factory=dict)

    @property
    def port(self):
        if self.name is not None:
            if self.host is not None:
                return f'{self.host.port}_{self.name}'
            return self.name
        return str(id(self))

@dataclass
class Host:
    name: str
    nics: list[NIC] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def is_solitary(self):
        if not self.nics:
            return True
        fnet = self.nics[0].net
        return all(fnet is n.net for n in self.nics[1:])

    @property
    def net(self):
        if not self.nics:
            return None
        return reduce(Net.common_ancestor, map(attrgetter('net'), self.nics))

    @property
    def port(self):
        return self.name

@dataclass
class Net:
    name: str | None
    net: _BaseNetwork
    sup: 'Net | None' = None
    sub: 'list[Net]' = field(default_factory=list)
    nics: list[NIC] = field(default_factory=list)
    hosts: list[Host] = field(default_factory=list)
    nodename: str | None = None
    info: dict = field(default_factory=dict)

    @property
    def is_child(self):
        return not self.sub

    @property
    def ancestors(self):
        cur = self.sup
        while cur is not None:
            yield cur
            cur = cur.sup

    def common_ancestor(self, other):
        ours = frozenset(map(attrgetter('net'), self.ancestors)) | frozenset((self.net,))
        cur = other
        while cur is not None:
            if cur.net in ours:
                return cur
            cur = cur.sup

    @property
    def all(self):
        yield self
        for sub in self.sub:
            yield from sub.all

class Styler:
    def nothing(self, *args):
        return {}

    nics = nothing
    net = nothing

    def hosts(self, *args):
        return {'color': '"#0a0"'}

    conn = hosts

    def graph(self):
        return {'newrank': 'true', 'compound': 'true'}

class RenderInfo:
    hosts_nowhere = 0
    empty_nets = 0

class Diagram:
    def __init__(self, hosts=(), subnets={}):
        self.hosts = {h.name: h for h in hosts}
        self.cur_host = None
        self.root = Net('The Internet', ip_network('0.0.0.0/0'))
        for name, net in subnets.items():
            if isinstance(net, str):
                net = ip_network(net)
            self.net_sub(net, name)
        self.opts = {}

    def net_of(self, addr):
        cur = self.root
        while True:
            assert addr in cur.net, f'{addr} not in {cur.net} ({cur.name})'
            ix = bisect_right(cur.sub, addr, key=lambda ch: ch.net.network_address)
            if ix > 0:
                sub = cur.sub[ix - 1]
                if addr in sub.net:
                    cur = sub
                    continue
            return cur

    def net_sub(self, net, name=None):
        cur = self.root
        while True:
            assert net.subnet_of(cur.net)
            #rix = bisect_right(cur.sub, net, key=attrgetter('net'))
            #lix = bisect_left(cur.sub, net, key=attrgetter('net'))
            lix, rix = 0, len(cur.sub)
            #print('NET', net, 'IN', cur.net)
            for ix in range(lix, rix + 1):
                if ix >= len(cur.sub):
                    continue
                ch = cur.sub[ix]
                #print('NETSUB', net, '<-', ch.net)

                if ch.net == net:
                    #print('NETSUB EQ')
                    if name is not None:
                        if ch.name is None:
                            ch.name = name
                        else:
                            ch.name += ', ' + name
                    return ch
                elif net.subnet_of(ch.net):
                    #print('NETSUB IN')
                    cur = ch
                    break
            else:
                n = Net(name, net, cur)
                # Move NICs into subnet
                for nic in cur.nics:
                    if nic.address in net:
                        insort(n.nics, nic, key=attrgetter('address'))
                        nic.net = n
                for nic in n.nics:
                    cur.nics.remove(nic)
                # Move any sibling subnets into this one
                for sub in cur.sub:
                    if sub.net.subnet_of(net):
                        #print('NETSUB MOVEIN', sub.net, '->', net)
                        insort(n.sub, sub, key=attrgetter('net'))
                        sub.sup = n
                for sub in n.sub:
                    cur.sub.remove(sub)
                insort(cur.sub, n, key=attrgetter('net'))
                return n

    def nic(self, addr, name=None):
        net = self.net_of(addr)
        ix = bisect_left(net.nics, addr, key=attrgetter('address'))
        if ix != len(net.nics) and net.nics[ix].address == addr:
            nic = net.nics[ix]
            if name is not None:
                if nic.name is None:
                    nic.name = name
                else:
                    nic.name += ', ' + name
        else:
            nic = NIC(name, addr)
            insort(net.nics, nic, key=attrgetter('address'))
            nic.net = net
        if self.cur_host is not None:
            ix = bisect_left(self.cur_host.nics, addr, key=attrgetter('address'))
            if ix == len(self.cur_host.nics) or self.cur_host.nics[ix].address != addr:
                insort(self.cur_host.nics, nic, key=attrgetter('address'))
                nic.host = self.cur_host
        return nic

    @dataclass
    class _HostCtx:
        dia: 'Diagram'
        host: Host

        def __enter__(self):
            self.old_host = self.dia.cur_host
            self.dia.cur_host = self.host
            return self.host

        def __exit__(self, *exc_info):
            self.dia.cur_host = self.old_host

    def host(self, name):
        if name not in self.hosts:
            self.hosts[name] = Host(name)
        return self._HostCtx(self, self.hosts[name])

    def render(self, gv, styler):
        ri = RenderInfo()

        for net in self.root.all:
            net.hosts = []

        for host in self.hosts.values():
            net = host.net
            if net is not None:
                insort(net.hosts, host, key=attrgetter('name'))
            else:
                ri.hosts_nowhere += 1

        with gv.group('graph ndia'):
            style = styler.graph()
            gv.write_stmt(' '.join(gv.alist(style)))
            self._render_net(self.root, gv, styler, ri)

        return ri

    def _render_net(self, net, gv, styler, ri):
        name = net.name if net.name is not None else str(net.net)
        net.nodename = name

        with gv.group('subgraph ' + gv.string(f'cluster_{name}')):
            label = str(net.net)
            if net.name is not None:
                label = net.name + '\\n' + label
            gv.write_stmt(' '.join(gv.alist({'label': gv.string(label)})))

            hosts = net.hosts

            if self.opts.get('all_hosts'):
                rtr_hosts = hosts
            else:
                rtr_hosts = [h for h in hosts if not h.is_solitary]

            if not hosts:
                ri.empty_nets += 1

            for sub in net.sub:
                self._render_net(sub, gv, styler, ri)

            self._render_nics(net, name, gv, styler, ri)
            self._render_hosts(rtr_hosts, net, f'rtr_{name}', True, gv, styler, ri)

    def _render_nics(self, net, name, gv, styler, ri):
        hosts = [nic.host for nic in net.nics if nic.host]
        self._render_hosts(hosts, net, name, False, gv, styler, ri)

    def _render_hosts(self, hosts, net, node, connect, gv, styler, ri):
        if not hosts:
            return

        host_info_headers = sorted(reduce(set.union, (set(h.info.keys()) for h in hosts), set()))
        nic_info_headers = sorted(
                reduce(set.union, (
                    reduce(set.union, (set(n.info.keys()) for n in h.nics), set())
                    for h in hosts
                ), set())
        )
        headers = ['Host'] + host_info_headers + ['NIC', 'Address'] + nic_info_headers

        parts = ['<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">\n<TR>']
        for hdr in headers:
            parts.append(f'<TD><B>{hdr}</B></TD>')
        parts.append('</TR>\n')

        for host in hosts:
            if connect:
                nics = [nic for nic in host.nics if nic.address in net.net]  # should be all of them
            else:
                nics = [nic for nic in host.nics if nic.net is net]

            if not nics:
                continue

            first = True
            for nic in nics:
                parts.append(f'<TR>')
                if first:
                    rowspan = ''
                    if len(nics) > 1:
                        rowspan = f' ROWSPAN="{len(nics)}"'
                    parts.append(f'<TD{rowspan} PORT="{host.port}">{host.name}</TD>')
                    for hihdr in host_info_headers:
                        parts.append(f'<TD{rowspan}>{host.info.get(hihdr, "")}</TD>')
                    first = False

                port = f' PORT="{nic.port}"'
                parts.append(f'<TD>{nic.name or ""}</TD><TD{port if not nic_info_headers else ""}>{nic.address}</TD>')
                for nihdr in nic_info_headers:
                    parts.append(f'<TD{port if nihdr == nic_info_headers[-1] else ""}>{nic.info.get(nihdr, "")}</TD>')

                parts.append('</TR>\n')

        parts.append('</TABLE>')
        if connect:
            style = styler.hosts(hosts)
        else:
            style = styler.nics(hosts)
        style['label'] = f'<{"".join(parts)}>'
        style['shape'] = 'none'
        gv.write_stmt(gv.styled(gv.string(node), style))
        if not connect:
            return

        for host in hosts:
            for nic in host.nics:
                nicnode = getattr(nic.net, 'nodename', None)
                if nicnode is None:
                    continue
                gv.write_stmt(
                        gv.styled(
                            f'{gv.string(node)}:{gv.string(host.port)} -- {gv.string(nicnode)}:{gv.string(nic.port)}',
                            styler.conn(host, nic),
                        ),
                )
