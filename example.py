from ndia import Diagram, GraphViz, Styler
from ipaddress import ip_address, ip_network
import sys

dia = Diagram()

# Hosts are scoped with context managers; they take only a name
with dia.host('a') as h:

    # NICs take an address and a name
    dia.nic(ip_address('10.0.1.1'), 'a_priv')

    # The returned NIC object has an `info` dict that can be given arbitrary properties
    # These properties will show up in the tables generated
    nic = dia.nic(ip_address('127.0.0.1'), 'a_pub')
    nic.info['scope'] = 'public'

# Filling out a more typical large LAN:
hosts = {name: ip_address(f'10.0.1.{octet}') for name, octet in zip('bcdef', range(2, 100))}

for hname, addr in hosts.items():
    with dia.host(hname) as h:
        dia.nic(addr, hname)

        # Hosts also have an `info` property that works similarly
        h.info['role'] = 'host'

# You can declare your network structure simultaneously, before, or afterward
# Nets, too, have an `info` property, but it doesn't render by default
# Instead, Stylers can use it to change styles
net = dia.net_sub(ip_network('10.0.1.0/24'), 'Private')
net.info['scope'] = 'private'

# Actually draw the current state
# We're using the default Styler, but you can derive your own to set fairly
# arbitrary attributes on the GraphViz statements
dia.render(GraphViz(sys.stdout), Styler())
