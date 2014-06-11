# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

class Host(object):
    """
    An autohost or self-hosting user.

    Attention: most values are stored as strings, because that's how we get it
    from the lobby server and that's what is sent to the LUA clients. 
    """
    battleID      = 0
    type          = 0
    natType       = 0
    founder       = u""
    ip            = u""
    port          = 0
    maxPlayers    = 0
    passworded    = 0
    rank          = 0
    mapHash       = 0
    engineName    = u""
    engineVersion = u""
    map           = u""
    title         = u""
    gameName      = u""
    locked        = False

    spec_count   = 0
    user_list    = None
    player_count = 0 # len(user_list)-spec_count+1 (w/o locking, because ints are updated atomically)
    is_ingame    = False
    user         = None # founder as reference to an User object

    def __init__(self, kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.user_list = list()

    def __str__(self):
        return str(self.__dict__)

    def set_player_count(self):
        self.player_count = len(self.user_list) - self.spec_count + 1 # +1 because host itself is in spec_count, but is not in user_list

    def as_list_header(self):
        return [u"battleID", u"founder", u"passworded", u"rank",
                u"engineVersion", u"map", u"title", u"gameName", u"locked",
                u"spec_count", u"player_count", u"is_ingame"]

    def as_list(self):
        return [unicode(self.battleID), unicode(self.founder),
                unicode(self.passworded), unicode(self.rank),
                unicode(self.engineVersion), unicode(self.map),
                unicode(self.title), unicode(self.gameName),
                unicode(self.locked), unicode(self.spec_count),
                unicode(self.player_count), unicode(self.is_ingame)]

class User(object):
    """
    A lobby account.
    """
    name      = ""
    country   = ""
    cpu       = ""
    accountid = 0

    # status bits from http://springrts.com/dl/LobbyProtocol/ProtocolDescription.html#MYSTATUS:client
    is_ingame    = False
    is_away      = False
    rank         = 0
    is_moderator = False
    is_bot       = False

    host         = None # references a Host if it's the hosts founder

    def __init__(self, name, country, cpu, accountid=0):
        self.name      = name
        self.country   = country
        self.cpu       = cpu
        self.accountid = accountid

    def __str__(self):
        return str(self.__dict__)
