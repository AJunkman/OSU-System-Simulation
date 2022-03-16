import os
import threading
import logging
import time
import random

import log
import osuSim
import flow


log.config_root_logger()
# nums = [1, 2, 3, 4, 5]
# nums = [1, 2, 3, 4, 5, 6, 7, 8, 9]
nums = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
try:
    for i in nums:
        os.remove('log/OSU{}.log'.format(i))
    os.remove('log/MainThread.log')
except:
    pass

log.config_root_logger()
thd = []
# for str in nums:
#     thd.append(threading.Thread(target=osuSim.sim_run,
#                                 args=("topologies14/osu{}.cfg".format(str),),
#                                 name='OSU{}'.format(str)))
#     thd[str-1].start()
for str in nums:
    thd.append(threading.Thread(target=osuSim.sim_run,
                                args=("topologies/osu{}.cfg".format(str),),
                                name='OSU{}'.format(str)))
    thd[str-1].start()
    time.sleep(random.randint(1,10))

# 带宽调整线程
threading.Thread(target=flow.adjustment()).start()
