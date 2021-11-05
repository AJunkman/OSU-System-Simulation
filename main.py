import threading
import logging
from logging import config

import osuSim

logging.config.fileConfig('logconfig.ini')
# logging.getLogger('asyncio').setLevel(logging.ERROR)

nums = [1, 2, 3, 4, 5]
thd = []
for str in nums:
    logging.info('osuSim%s starting...'%(str))
    thd.append(threading.Thread(target=osuSim.sim_run, args=("topologies/osu{}.cfg".format(str),)))

for t in thd:
    t.start()