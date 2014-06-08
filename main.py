#!/usr/bin/env python

# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from time import sleep
import logging
from os.path import realpath, dirname

from lobbyclient.lobbyclient import Lobbyclient

LOG_PATH        = realpath(dirname(__file__))+'/log'
DEBUG_FORMAT = '%(asctime)s %(levelname)-8s %(module)s.%(funcName)s:%(lineno)d  %(message)s'
LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(level=logging.DEBUG,
                    format=DEBUG_FORMAT,
                    datefmt=LOG_DATETIME_FORMAT,
                    filename=LOG_PATH+'/root_debug.log',
                    filemode='w')
logger = logging.getLogger()

lc = Lobbyclient()
login_info = lc.connect()
lc.ping()
try:
    for li in login_info.split("\n"):
        lc.consume(li)
    lc.listen()
except Exception, e:
    logger.exception("Exception: %s", e)
sleep(20)
lc.shutdown()

logger.debug("***** lc.users: *****")
for k,v in lc.users.items():
    logger.debug("   %s: %s", k, v)
logger.debug("*********************")
logger.debug("***** lc.hosts: *****")
for k,v in lc.hosts.items():
    logger.debug("   %s: %s", v.founder, v)
    if len(v.user_list) > 0:
        logger.debug("      Autohost(%s).player_list: %s", k, [u.name for u in v.user_list])
logger.debug("*********************")
logger.debug("***** lc.hosts 2: *****")
for k,v in lc.hosts.items():
    if v.is_ingame:
        logger.debug("%s: ingame players: %02d spec: %02d", v.founder.ljust(20), v.player_count, v.spec_count)
    else:
        logger.debug("%s:   open players: %02d spec: %02d", v.founder.ljust(20), v.player_count, v.spec_count)
logger.debug("*********************")

exit(0)
