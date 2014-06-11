#!/usr/bin/env python

# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#
# Simple telnet client: makes a connection, sends a line, prints reply.
#
# Used to test hostlistd:
# $ ./cmdline_test.py OPEN MOD Evo
#

import sys
import telnetlib

from hostlistd.settings import HOST, PORT

data = " ".join(sys.argv[1:])

tn = telnetlib.Telnet(HOST, PORT)

tn.write(data + "\n")
print "Sent:     '{}'".format(data)

recv = tn.expect(["^END.*"], 2)
print "Received: '{}'".format(recv[2])

tn.close()
