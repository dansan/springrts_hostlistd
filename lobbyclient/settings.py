# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import base64
import hashlib

LOBBY_SERVER_FQDN = "lobby.springrts.com"
LOBBY_SERVER_PORT = 8200

CONNECT_DATA = {"username": "DanNew",
                "password": "9xpvhXsXIK8v",
                "cpu": "2400",
                "ip": "*",
                "software": "py-telnet",
                "version": "0.1",
                "id": "0",
                "compat_flags": "a cl"}
PING_INTERVAL = 30

# http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#LOGIN:client
# LOGIN userName password cpu localIP {lobby name and version} [userID] [{compFlags}]
# LOGIN Johnny Gnmk1g3mcY6OWzJuM4rlMw== 3200 * TASClient 0.30[TAB]0[TAB]a b
LOGIN = "LOGIN "+ CONNECT_DATA["username"] +" "+ base64.b64encode(hashlib.md5(CONNECT_DATA["password"]).digest()) +" "+ CONNECT_DATA["cpu"] +" "+ CONNECT_DATA["ip"] +" "+ CONNECT_DATA["software"] +" "+ CONNECT_DATA["version"] +"\t"+ CONNECT_DATA["id"] +"\t"+ CONNECT_DATA["compat_flags"]

