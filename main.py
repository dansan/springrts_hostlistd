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
from time import sleep

from lobbyclient.lobbyclient import Lobbyclient
from hostlistd.hostlistd import Hostlistd
from settings import LOG_INTERVAL, LOBBY_CONNECT_TRIES, LOBBY_CONNECT_RETRY_WAIT

LOG_PATH = realpath(dirname(__file__)) + '/log'
DEBUG_FORMAT = '%(asctime)s %(levelname)-8s %(module)s.%(funcName)s:%(lineno)d  %(message)s'
LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

logging.basicConfig(level=logging.DEBUG,
                    format=DEBUG_FORMAT,
                    datefmt=LOG_DATETIME_FORMAT,
                    filename=LOG_PATH + '/root_debug.log',
                    filemode='a')
logger = logging.getLogger()
logger.info("========= main starting =========")

lc = None  # lobby client
hl = None  # hosts list
ev = threading.Event()  # signaling object
stats_thread = None  # statistics thread
watchdog_thread = None  # lobbyclient watchdog thread


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
    logger.info("'%s' thread terminated, '%s'.isAlive(): %s", lc.listen_thread.name, lc.listen_thread.name,
                lc.listen_thread.isAlive())
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
    global lc, ev

    retries = 1
    while retries < LOBBY_CONNECT_TRIES:
        try:
            logger.info("Connecting to lobby server...")
            lc = Lobbyclient()
            login_info = lc.connect()
            logger.info("... connected.")
            break
        except Exception:
            logger.exception("Cannot connect to lobby server:")
            logger.info("Will retry in %d seconds (this is the %d. try)...", LOBBY_CONNECT_RETRY_WAIT, retries)
            sleep(LOBBY_CONNECT_RETRY_WAIT)
            retries += 1
    else:
        logger.critical("Could not connect to lobby server, exiting.")
        ev.set()  # signal other threads
        signal.alarm(1)  # signal main thread
        exit(1)

    lc.ping()
    try:
        for li in login_info.split("\n"):
            lc.consume(li)
        lc.login_info_consumed = True
        logger.info("login_info consumed")
        lc.log_stats()
        if len(lc.users) == 0:
            logger.critical("No users found -> error -> exiting.")
            ev.set()  # signal other threads
            signal.alarm(1)  # signal main thread
            exit(1)
        lc.listen()
    except SystemExit:
        raise
    except Exception:
        logger.exception("Exception:")


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
