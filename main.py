#!/usr/bin/env python

# This file is part of the "springrts-hostlist" program. It is published
# under the GPLv3.
#
# Copyright (C) 2014 Daniel Troeder (daniel #at# admin-box #dot# com)
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from os.path import realpath, dirname
import signal
from threading import Timer
import threading

from lobbyclient.lobbyclient import Lobbyclient
from hostlistd.hostlistd import Hostlistd
from settings import LOG_INTERVAL

LOG_PATH        = realpath(dirname(__file__))+'/log'
DEBUG_FORMAT = '%(asctime)s %(levelname)-8s %(module)s.%(funcName)s:%(lineno)d  %(message)s'
LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(level=logging.DEBUG,
                    format=DEBUG_FORMAT,
                    datefmt=LOG_DATETIME_FORMAT,
                    filename=LOG_PATH+'/root_debug.log',
                    filemode='a')
logger = logging.getLogger()


def log_stats(interval, ev):
    logger.info("Logging stats every %d seconds.", interval)
        
    while True:
        if ev.wait(interval):
            # got signal
            return
        try:
            hl.log_stats()
            lc.log_stats()
        except:
            # this shouldn't happen
            return

# launch lobby client
lc = Lobbyclient()
try:
    login_info = lc.connect()
except Exception, e:
    logger.exception("Cannot connect to lobby server: %s", e)
    exit(1)
lc.ping()
try:
    for li in login_info.split("\n"):
        lc.consume(li)
    lc.login_info_consumed = True
    logger.info("login_info consumed")
    lc.listen()
except SystemExit:
    raise
except Exception, e:
    logger.exception("Exception: %s", e)

# launch hostlist server
try:
    hl = Hostlistd()
except Exception, e:
    logger.exception("Cannot create Hostlistd server: %s", e)
    lc.shutdown()
    exit(1)
hl.set_host_lists(lc.hosts, lc.hosts_open, lc.hosts_ingame)
hl.start()
logger.info("hostlistd listening on %s:%d", hl.ip, hl.port)

# launch statistic logging thread
ev = threading.Event()
stats_thread = threading.Thread(target=log_stats, name="stats", kwargs={"interval": LOG_INTERVAL, "ev": ev})
stats_thread.start()

# sleep until ctrl-c
signal.pause()
logger.info("Shutting down")

# shutdown all threads
ev.set()
stats_thread.join(1)
if stats_thread.isAlive():
    logger.error("ERROR: stats_thread is still alive")
else:
    logger.info("stats_thread quitted")
lc.shutdown()
hl.shutdown()
exit(0)
