import cmd
from dataclasses import asdict
from ipaddress import ip_address, ip_network
from pprint import pprint
import shlex
import sys

class Interpreter(cmd.Cmd):
    use_rawinput = False
    prompt = 'ndia > '

    @staticmethod
    def to_info(args):
        rv = {}
        for arg in args:
            k, _, v = arg.partition('=')
            if not v:
                v = True
            rv[k] = v
        return rv

    def __init__(self, dia, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dia = dia
        self.hostctx = None

    def emptyline(self):
        pass

    def precmd(self, line):
        return line.partition('#')[0]

    def do_opt(self, rest):
        self.dia.opts.update(self.to_info(shlex.split(rest)))

    def do_net(self, rest):
        args = shlex.split(rest)
        name, net = args[:2]
        self.dia.net_sub(ip_network(net), name).info.update(self.to_info(args[2:]))

    def do_host(self, rest):
        args = shlex.split(rest)
        name = args[0]
        self.do_nohost('')
        self.hostctx = self.dia.host(name)
        self.hostctx.__enter__().info.update(self.to_info(args[1:]))

    def do_nohost(self, rest):
        if self.hostctx is not None:
            self.hostctx.__exit__(None, None, None)
            self.hostctx = None

    def do_nic(self, rest):
        args = shlex.split(rest)
        name, addr = args[:2]
        self.dia.nic(ip_address(addr), name).info.update(self.to_info(args[2:]))

    def do_show(self, rest):
        args = shlex.split(rest)
        if args[0] == 'host':
            pprint(self.dia.hosts.get(args[1]))
        elif args[0] == 'net':
            self.print_net(self.dia.root)
        elif args[0] == 'root':
            pprint(self.dia.root)

    def print_net(self, net, indent=0):
        i = '\t' * indent
        print(f'{i}{net.net}: {net.name}', file=self.stdout)
        for nic in net.nics:
            hname = nic.host.name if nic.host is not None else 'None'
            print(f'{i}\t{nic.address}: {nic.name}@{hname}', file=self.stdout)
        for sub in net.sub:
            self.print_net(sub, indent + 1)

    def do_load(self, rest):
        args = shlex.split(rest)
        with open(args[0]) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                self.cmdqueue.append(line)

    def do_EOF(self, rest):
        return True

def from_flatfile(dia, f):
    intr = Interpreter(dia, stdin=f, stdout=sys.stderr)
    intr.cmdloop()

if __name__ == '__main__':
    from ndia import Diagram, GraphViz, Styler

    dia = Diagram()
    from_flatfile(dia, sys.stdin)
    #print(dia, dia.hosts, dia.root)
    dia.render(GraphViz(sys.stdout), Styler())
