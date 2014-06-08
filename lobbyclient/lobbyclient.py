# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import telnetlib
#from time import sleep
import threading
import signal
import logging

from settings import LOBBY_SERVER_FQDN, LOBBY_SERVER_PORT, LOGIN, PING_INTERVAL
from models import Host, User

logger = logging.getLogger()

class Lobbyclient():
    
    def __init__(self):
        self.users = dict()
        self.hosts = dict()

    def _sig_handler(self, signum, frame):
        self.shutdown()

    def connect(self):
        self.tn = telnetlib.Telnet(LOBBY_SERVER_FQDN, LOBBY_SERVER_PORT)
        logger.info("Connected to %s:%d", LOBBY_SERVER_FQDN, LOBBY_SERVER_PORT)

        # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#TASSERVER:server
        # TASSERVER protocolVersion springVersion udpPort serverMode
        self.tn.read_until("TASServer", 2)
        self.tasserver_info = self.tn.read_very_eager().split()
        logger.info("TASServer: %s", self.tasserver_info)

        self.tn.write(LOGIN + "\n")
        login_result = self.tn.expect(["^ACCEPTED .*", "^DENIED .*"], 2)

        if login_result[2].startswith("DENIED"):
            logger.error("LOGIN DENIED, exiting.")
            self.tn.close()
            exit(1)
        else:
            logger.info("LOGIN ACCEPTED")

        # abort on ctrl-c and kill
        signal.signal(signal.SIGTERM, self._sig_handler)
        signal.signal(signal.SIGINT, self._sig_handler)

        login_info = self.tn.read_until("LOGININFOEND\n", 2)
        logger.info("LOGININFOEND reached")
        return login_info

    def _send_pings(self, interval, tn_socket, ev):
        """
        starts separate thread to send PING every interval seconds to the server 
        """
        # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#PING:client
        logger.info("_send_pings() START")
        while True:
            if ev.wait(interval):
                # got signal
                return
            try:
                tn_socket.sendall("PING\n")
            except:
                # socket was probably closed
                return

    def ping(self):    
        self.ev = threading.Event()
        self.ping_thread = threading.Thread(target=self._send_pings, name="send_pings", kwargs={"interval": PING_INTERVAL, "tn_socket": self.tn.get_socket(), "ev": self.ev})
        self.ping_thread.start()

    def _listen(self):
        logger.info("_listen() START")
        more = ""
        while True:
            some = self.tn.read_some()
            if some == "":
                return
            else:
                if some.endswith("\n"):
                    for txt in (more+some[:-1]).split("\n"):
                        self.consume(txt)
#                     self.consume(more+some[:-1])
                    more = ""
                else:
                    more += some

    def listen(self):
        self.listen_thread = threading.Thread(target=self._listen, name="listen")
        self.listen_thread.start()

    def consume(self, commandstr):
        """
        Read and act upon a line of lobby protocol.
        """
#         logger.debug("commandstr: %s", repr(commandstr))
        if commandstr.startswith("ADDUSER"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#ADDUSER:server
            # ADDUSER userName country cpu [accountID]
            try:
                self.users[commandstr.split()[1]] = User(*commandstr.split()[1:])
            except ValueError, e:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            except Exception, e:
                logger.exception("Exception, commandstr: '%s'", repr(commandstr))
                return
        elif commandstr.startswith("BATTLEOPENED"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#BATTLEOPENED:server
            # BATTLEOPENED battleID type natType founder ip port maxPlayers passworded rank mapHash {engineName} {engineVersion} {map} {title} {gameName}
            try:
                cmd, engineVersion, map, title, gameName = commandstr.split("\t")
                _, battleID, type, natType, founder, ip, port, maxPlayers, passworded, rank, mapHash, engineName = cmd.split()
            except ValueError, e:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            loc = locals()
            del loc["_"]
            del loc["cmd"]
            del loc["commandstr"]
            del loc["self"]
            self.hosts[battleID] = Host(loc)
            try:
                self.hosts[battleID].user = self.users[founder]
                self.users[founder].host = self.hosts[battleID]
            except KeyError, e:
                logger.exception("founder of self.hosts[%d] not self.users[%s]", battleID, founder)
                return
        elif commandstr.startswith("CLIENTSTATUS"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#CLIENTSTATUS:server
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#MYSTATUS:client
            # CLIENTSTATUS userName status
            # status bits: is_bot|has_access|3*rank|is_away|is_ingame
            # 88 = 1011000 = bot, not a moderator, rank=6, not away, not ingame
            # 93 = 1011101 = bot, not a moderator, rank=7, not away, ingame
            try:
                _, userName, status = commandstr.split()
            except ValueError, e:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            try:
                user = self.users[userName]
            except Exception, e:
                logger.exception("Exception in CLIENTSTATUS: userName '%s' not in self.users?", userName)
                return
            try:
                status_bin = bin(int(status))[2:].zfill(7)
                user.is_ingame    = bool(int(status_bin[6]))
                user.is_away      = bool(int(status_bin[5]))
                rank              = int(status_bin[2:5], base=2)
                user.is_moderator = bool(int(status_bin[1]))
                user.is_bot       = bool(int(status_bin[0]))
#                     logger.debug("status: '%s', status_bin: '%s'", status, status_bin)
#                     logger.debug("locales: %s", locals())
            except Exception, e:
                logger.exception("Exception in CLIENTSTATUS: commandstr: '%s', status: '%s', status_bin: '%s'", repr(commandstr), status, status_bin)
                return
            if user.host:
                user.host.is_ingame = user.is_ingame
        elif commandstr.startswith("JOINEDBATTLE"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#JOINEDBATTLE:server
            # JOINEDBATTLE battleID userName [scriptPassword]
            try:
                _, battleID, userName = commandstr.split()
            except ValueError, e:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            self.hosts[battleID].user_list.append(self.users[userName])
            self.hosts[battleID].set_player_count()
        elif commandstr.startswith("LEFTBATTLE"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#LEFTBATTLE:server
            # LEFTBATTLE battleID userName
            try:
                _, battleID, userName = commandstr.split()
            except ValueError, e:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            try:
                self.hosts[battleID].user_list.remove(self.users[userName])
                self.hosts[battleID].set_player_count()
            except:
                logger.exception("Exception in LEFTBATTLE: userName '%s' not in self.hosts[%s].user_list?", userName, battleID)
                return
        elif commandstr.startswith("REMOVEUSER"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#REMOVEUSER:server
            # REMOVEUSER userName
            try:
                del self.users[commandstr.split()[1]]
            except ValueError, e:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            except KeyError, e:
                logger.exception("Exception in REMOVEUSER: userName '%s' not in self.users?", userName)
                return
        elif commandstr.startswith("UPDATEBATTLEINFO"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#UPDATEBATTLEINFO:server
            # UPDATEBATTLEINFO battleID spectatorCount locked mapHash {mapName}
            try:
                battleID, spectatorCount, locked, mapHash = commandstr.split()[1:5]
                mapName = " ".join(commandstr.split()[5:])
            except ValueError, e:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            try:
                host = self.hosts[battleID]
            except KeyError, e:
                logger.exception("Exception in UPDATEBATTLEINFO: battleID '%s' not in self.hosts?", battleID)
                return
            host.spec_count = int(spectatorCount)
            self.hosts[battleID].set_player_count()
            host.locked     = bool(locked)
            host.mapHash    = mapHash
            self.map        = mapName
        else:
            # ignore all other commands
            pass


    def shutdown(self):
        # stop ping thread
        self.ev.set()
        self.ping_thread.join(1)
        if self.ping_thread.isAlive():
            logger.error("ERROR: ping_thread is still alive")
        else:
            logger.info("ping_thread quitted")
        
        # say goodbye to lobby server
        logger.info("EXIT")
        self.tn.write("EXIT\n")
        remaining_data = self.tn.read_all()
        self.tn.close()
        logger.info("REMAINING DATA: tn.read_all():\n%s", remaining_data)
        logger.info("tn.close()")
