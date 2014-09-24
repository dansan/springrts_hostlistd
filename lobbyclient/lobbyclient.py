# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import telnetlib
import threading
import logging

from settings import LOBBY_SERVER_FQDN, LOBBY_SERVER_PORT, LOGIN, PING_INTERVAL
from models import Host, User

logger = logging.getLogger()

class LobbyTCPConnectException(Exception):
    pass

class Lobbyclient():

    def __init__(self):
        self.users = dict()              # all users
        self.hosts = dict()              # all hosts
        self.hosts_open = dict()         # hosts that are not ingame
        self.hosts_ingame = dict()       # hosts that are ingame
        self.login_info_consumed = False # prevent error msg during initial data collection

    def connect(self):
        try:
            self.tn = telnetlib.Telnet(LOBBY_SERVER_FQDN, LOBBY_SERVER_PORT)
        except:
            raise LobbyTCPConnectException
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

        login_info = self.tn.read_until("LOGININFOEND\n", 2)
        logger.info("LOGININFOEND reached")
        return login_info

    def _send_pings(self, interval, tn_socket, ev):
        """
        starts separate thread to send PING every interval seconds to the server 
        """
        # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#PING:client
        logger.info("Sending a PING to lobby server every %d seconds.", interval)
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
        self.ping_thread = threading.Thread(target=self._send_pings, name="lobbyclient_ping", kwargs={"interval": PING_INTERVAL, "tn_socket": self.tn.get_socket(), "ev": self.ev})
        self.ping_thread.start()

    def _listen(self):
        more = ""
        while True:
            try:
                some = self.tn.read_some()
            except Exception:
                logger.info("Connection closed")
                tnsocket = self.tn.get_socket()
                self.tn.close()
                tnsocket.close()
                logger.info("Quitting '%s' thread.", self.listen_thread.name)
                return
            if some == "":
                return
            else:
                if some.endswith("\n"):
                    for txt in (more+some[:-1]).split("\n"):
                        self.consume(txt)
                    more = ""
                else:
                    more += some

    def listen(self):
        self.listen_thread = threading.Thread(target=self._listen, name="lobbyclient_main")
        self.listen_thread.start()
        logger.info("Started lobbyclient (in '%s' thread).", self.listen_thread.name)

    def consume(self, commandstr):
        """
        Read and act upon a line of lobby protocol.

        Only the following commands are implemented:
          ADDUSER
          BATTLECLOSED
          BATTLEOPENED
          CLIENTSTATUS
          JOINEDBATTLE
          LEFTBATTLE
          REMOVEUSER
          UPDATEBATTLEINFO
        """
        if commandstr.startswith("ADDUSER"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#ADDUSER:server
            # ADDUSER userName country cpu [accountID]
            try:
                self.users[commandstr.split()[1]] = User(*commandstr.split()[1:])
            except ValueError:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            except Exception:
                logger.exception("Exception, commandstr: '%s'", repr(commandstr))
                return
        elif commandstr.startswith("BATTLECLOSED"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#BATTLECLOSED:server
            # BATTLECLOSED battleID
            try:
                battleID = commandstr.split()[1]
            except Exception:
                logger.exception("Commandstr: '%s'", repr(commandstr))
                return
            # founder is founder no more
            try:
                self.hosts[battleID].user.host = None
            except:
                logger.exception("error removing host-user-founder association")
            # remove battle from all host lists
            for hosts in [self.hosts, self.hosts_ingame, self.hosts_open]:
                try:
                    del hosts[battleID]
                except:
                    pass
        elif commandstr.startswith("BATTLEOPENED"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#BATTLEOPENED:server
            # BATTLEOPENED battleID type natType founder ip port maxPlayers passworded rank mapHash {engineName} {engineVersion} {map} {title} {gameName}
            try:
                cmd, engineVersion, _map, title, gameName = commandstr.split("\t")
                _, battleID, _type, natType, founder, ip, port, maxPlayers, passworded, rank, mapHash, engineName = cmd.split()
            except ValueError:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            except Exception:
                logger.exception("Commandstr: '%s'", repr(commandstr))
                return
            loc = locals()
            del loc["_"]
            del loc["cmd"]
            del loc["commandstr"]
            del loc["self"]
            loc["map"] = _map
            del loc["_map"]
            loc["type"] = _type
            del loc["_type"]
            host = Host(loc)
            self.hosts[battleID] = host
            self.hosts_open[battleID] = host
            host.user = self.users[founder]
            host.user.host = host
        elif commandstr.startswith("CLIENTSTATUS"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#CLIENTSTATUS:server
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#MYSTATUS:client
            # CLIENTSTATUS userName status
            # status bits: is_bot|has_access|3*rank|is_away|is_ingame
            try:
                _, userName, status = commandstr.split()
            except ValueError:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            except:
                logger.exception("Commandstr: '%s'", repr(commandstr))
                return
            try:
                user = self.users[userName]
            except:
                logger.exception("Exception in CLIENTSTATUS: userName '%s' in self.users?: %s, commandstr: '%s'", userName, userName in self.users, repr(commandstr))
                return
            try:
                status_bin = bin(int(status))[2:].zfill(7)
                user.is_ingame    = bool(int(status_bin[6]))
                user.is_away      = bool(int(status_bin[5]))
                user.rank         = int(status_bin[2:5], base=2)
                user.is_moderator = bool(int(status_bin[1]))
                user.is_bot       = bool(int(status_bin[0]))
            except:
                logger.exception("Exception in CLIENTSTATUS: status: '%s', status_bin: '%s', commandstr: '%s'", repr(commandstr), status, status_bin)
                return
            if user.host:
                user.host.is_ingame = user.is_ingame
                if user.is_ingame:
                    # add host to hosts_ingame
                    self.hosts_ingame[user.host.battleID] = user.host
                    # remove host from hosts_open
                    try:
                        del self.hosts_open[user.host.battleID]
                    except:
                        # CLIENTSTATUS is sent twice in case of self-hosted battles
                        #logger.exception("Exception in CLIENTSTATUS: trying to remove host from hosts_open, commandstr: '%s'", repr(commandstr))
                        pass
                else:
                    # add host to hosts_open
                    self.hosts_open[user.host.battleID] = user.host
                    # remove host from hosts_ingame
                    try:
                        del self.hosts_ingame[user.host.battleID]
                    except Exception:
                        if self.login_info_consumed:
                            logger.exception("Exception in CLIENTSTATUS: trying to remove host from hosts_ingame, commandstr: '%s'", repr(commandstr))
                        else:
                            # msg flood in in wrong order during initial setup
                            pass
        elif commandstr.startswith("JOINEDBATTLE"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#JOINEDBATTLE:server
            # JOINEDBATTLE battleID userName [scriptPassword]
            try:
                _, battleID, userName = commandstr.split()
            except ValueError:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            self.hosts[battleID].user_list.append(self.users[userName])
            self.hosts[battleID].set_player_count()
        elif commandstr.startswith("LEFTBATTLE"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#LEFTBATTLE:server
            # LEFTBATTLE battleID userName
            try:
                _, battleID, userName = commandstr.split()
            except ValueError:
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
            userName = commandstr.split()[1]
            user = self.users[userName]
            if user.host:
                try:
                    del self.hosts[user.host.battleID]
                    del self.hosts_open[user.host.battleID]
                except:
                    pass
            try:
                del self.users[userName]
            except ValueError:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            except KeyError:
                logger.exception("Exception in REMOVEUSER: userName '%s' not in self.users?", userName)
                return
        elif commandstr.startswith("UPDATEBATTLEINFO"):
            # http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#UPDATEBATTLEINFO:server
            # UPDATEBATTLEINFO battleID spectatorCount locked mapHash {mapName}
            try:
                battleID, spectatorCount, locked, mapHash = commandstr.split()[1:5]
                mapName = " ".join(commandstr.split()[5:])
            except ValueError:
                logger.exception("Bad format, commandstr: '%s'", repr(commandstr))
                return
            try:
                host = self.hosts[battleID]
            except KeyError:
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
        logger.info("Shutting lobbyclient down.")
        # stop ping thread
        self.ev.set()
        self.ping_thread.join(1)
        if self.ping_thread.isAlive():
            logger.error("ERROR: ping_thread is still alive")
        else:
            logger.info("ping_thread quitted")
        
        # say goodbye to lobby server
        logger.info("EXIT")
        try:
            self.tn.write("EXIT\n")
            remaining_data = self.tn.read_all()
            self.tn.close()
            logger.info("REMAINING DATA: tn.read_all():\n%s", remaining_data)
            logger.info("tn.close()")
        except:
            pass

    def log_stats(self):
        logger.info("users:        %03d", len(self.users))
        logger.info("hosts:         %02d", len(self.hosts))
        logger.info("hosts_open:    %02d", len(self.hosts_open))
        logger.info("hosts_ingame:  %02d", len(self.hosts_ingame))
