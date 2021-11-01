import os
from multiprocessing.dummy import Pool as ThreadPool

threadNum = 5
nums = [1, 2, 3, 4, 5]
def start(str):
    print('osuSim%s starting...'%(str))
    os.system('python3 osuSim%s.py'%(str))

pool = ThreadPool(threadNum)
pool.map(start, nums)
pool.close()
pool.join()

test()
