# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import threading
import SocketServer
import logging
import csv, cStringIO
import datetime

from settings import HOST, PORT
from unicodewriter import UnicodeWriter

logger = logging.getLogger()

class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler, object):
    """
    Request handler, each connection gets an new object of this class.
    """
    hosts        = None # dict of lobbyclient.model.Host
    hosts_open   = None # dict of lobbyclient.model.Host
    hosts_ingame = None # dict of lobbyclient.model.Host
    name         = ""   # name of thread

    def setup(self):
        self.hosts = self.server.hosts
        self.hosts_open = self.server.hosts_open
        self.hosts_ingame = self.server.hosts_ingame
        name = threading.current_thread().name
        self.name = "hostlistd-request-" + " ".join(name.split("-")[1:])
        threading.current_thread().name = self.name
        super(ThreadedTCPRequestHandler, self).setup()

    def handle(self):
        """
        Reply to incoming requests.

        Request:
            <COMMAND> <FILTER-TYPE> [SUBSTRING ...]
            COMMAND:     ALL|OPEN|INGAME
            FILTER-TYPE: NONE|MOD|HOST|DESC
            SUBSTRING:   The text to look for in the column FILTER-TYPE. If
                         spaces are encountered, each word must be in the
                         field.
        Reply:
            1st line: 'START <ISO 8601 timestamp, UTC>'
            2nd: List of hosts as an UTF-8 encoded CSV using ; as separator and
               quoting every field. The list will be filtered if
               FILTER-TYPE != NONE.
            3rd: 'END <length of list>'
        """
        for line in self.rfile:
            # loop until disconnect
            line = line.split()
            if len(line) < 2 or (len(line) == 2 and line[1] != "NONE"):
                logger.error("Format error: '%s'", line)
                continue
            # COMMAND
            if line[0] == "ALL":
                host_list = self.hosts.values()
            elif line[0] == "OPEN":
                host_list = self.hosts_open.values()
            elif line[0] == "INGAME":
                host_list = self.hosts_ingame.values()
            else:
                logger.error("Unknown COMMAND '%s'.", line[0])
                continue
            # FILTER-TYPE
            def substr_search(words, text):
                """
                Case-insensitive search for words in text.
                Returns True if all words exist in text.
                """
                text = text.upper()
                words_exist_in_text = map(lambda x: x.upper() in text, words)
                return reduce(lambda x, y: x and y, words_exist_in_text, True)

            if line[1] == "NONE":
                host_list_filtered = host_list
            elif line[1] == "MOD":
                host_list_filtered = [host for host in host_list if substr_search(line[2:], host.gameName)]
            elif line[1] == "HOST":
                host_list_filtered = [host for host in host_list if substr_search(line[2:], host.founder)]
            else:
                logger.error("Unknown FILTER-TYPE '%s'.", line[0])
                continue

            response = u"START %s\n" % datetime.datetime.utcnow().isoformat()
            if len(host_list_filtered) > 0:
                csvfile = cStringIO.StringIO()
                csvwriter = UnicodeWriter(csvfile, quoting=csv.QUOTE_ALL)
                csvwriter.writerow(host_list_filtered[0].as_list_header())
                csvwriter.writerows([host.as_list() for host in host_list_filtered])
                response += csvfile.getvalue()
                csvfile.close()
            response += u"END %d\n" % len(host_list_filtered)
            self.wfile.write(response)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

class Hostlistd(object):
    """
    Serves the lists of available hosts on a socket, multi-threaded.
    """
    server        = None # server object
    server_thread = None # thread in which the servers main loop runs
    ip            = ""
    port          = 0

    def __init__(self):
        self.server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
        self.ip, self.port = self.server.server_address

    def set_host_lists(self, hosts, hosts_open, hosts_ingame):
        self.server.hosts = hosts
        self.server.hosts_open = hosts_open
        self.server.hosts_ingame = hosts_ingame

    def start(self):
        self.server_thread = threading.Thread(target=self.server.serve_forever, name="hostlistd_main")
        self.server_thread.daemon = True
        self.server_thread.start()
        return self.server_thread.name

    def shutdown(self):
        logger.info("Shutting hostlistd server down.")
        self.server.shutdown()

    def log_stats(self):
        logger.info("Threads: %s", [t.name for t in threading.enumerate()])
