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
logger.info("========= main starting =========")

lc = None
hl = None
ev = threading.Event()
stats_thread = None
watchdog_thread = None


def log_stats(interval, ev):
    global hl, lc

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

def _lobbyclient_watchdog():
    global lc, hl

    lc.listen_thread.join()
    logger.info("'%s' thread terminated, '%s'.isAlive(): %s", lc.listen_thread.name, lc.listen_thread.name, lc.listen_thread.isAlive())
    if ev.is_set():
        # shutting down, don't start new threads 
        return
    lc.shutdown()
    hl.log_stats()
    logger.info("Creating new Lobbyclient object and threads.")
    launch_lobbyclient()
    logger.info("Creating new lobbyclient_watchdog thread.")
    launch_lobbyclient_watchdog()
    hl.log_stats()
    logger.info("Current lobbyclient_watchdog exiting.")

def launch_lobbyclient_watchdog():
    global lc, watchdog_thread

    watchdog_thread = threading.Thread(target=_lobbyclient_watchdog, name="lobbyclient_watchdog")
    watchdog_thread.start()
    logger.info("Started watchdog (in '%s' thread) observing '%s' thread.", watchdog_thread.name, lc.listen_thread.name)

def launch_lobbyclient():
    global lc

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
        lc.log_stats()
        lc.listen()
    except SystemExit:
        raise
    except Exception, e:
        logger.exception("Exception: %s", e)

def launch_hostlistd():
    global hl, lc

    try:
        hl = Hostlistd()
    except Exception, e:
        logger.exception("Cannot create Hostlistd server: %s", e)
        lc.shutdown()
        exit(1)
    hl.set_host_lists(lc.hosts, lc.hosts_open, lc.hosts_ingame)
    hl.start()
    logger.info("hostlistd listening on %s:%d", hl.ip, hl.port)

def launch_log_stats():
    global ev, stats_thread

    stats_thread = threading.Thread(target=log_stats, name="stats", kwargs={"interval": LOG_INTERVAL, "ev": ev})
    stats_thread.start()

launch_lobbyclient()
launch_lobbyclient_watchdog()
launch_hostlistd()
launch_log_stats()

hl.log_stats()

# sleep until ctrl-c
try:
    signal.pause()
except:
    pass
logger.info("Shutting down")

# shutdown all threads
ev.set()

lc.shutdown()
lc.listen_thread.join(2)
if lc.listen_thread.isAlive():
    logger.error("ERROR: lc.listen_thread is still alive")
else:
    logger.info("lc.listen_thread quitted")

watchdog_thread.join(2)
if watchdog_thread.isAlive():
    logger.error("ERROR: watchdog_thread is still alive")
else:
    logger.info("watchdog_thread quitted")

hl.shutdown()
hl.server_thread.join(2)
if hl.server_thread.isAlive():
    logger.error("ERROR: hl.server_thread is still alive")
else:
    logger.info("hl.server_thread quitted")

stats_thread.join(2)
if stats_thread.isAlive():
    logger.error("ERROR: stats_thread is still alive")
else:
    logger.info("stats_thread quitted")

exit(0)
