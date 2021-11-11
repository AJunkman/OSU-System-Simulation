import random
import time

from osuSim import OSU

BANDWIDTH_UP_LIMIT = 100000

class flow():

    def __init__(self, timeStamp, src_ip, dst_ip, bandwidth, bw_up_limit):
        self.timeStamp = timeStamp
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.bandwidth = bandwidth
        self.bw_up_limit = bw_up_limit

    def print(self):
        print("timeStamp:%s \tsrc_ip:%s \tdst_ip:%s \tbandwidth:%s \tbw_up_limit:%s"\
            %(self.timeStamp, self.src_ip, self.dst_ip, self.bandwidth, self.bw_up_limit))

class flowGenerator():

    def generator(current_ip):
        flows = []
        timeStamp = time.time()
        src_ip = current_ip
        OSU_ip = ['OSU1', 'OSU2', 'OSU3', 'OSU4', 'OSU5']
        OSU_ip.remove(src_ip)
        for i in range(random.randint(0, len(OSU_ip))):
            dst_ip = OSU_ip[random.randint(0, len(OSU_ip)-1)]
            bandwidth = random.randint(2, 1250)
            conn_num = random.randint(80, 200)
            bw_up_limit = int(BANDWIDTH_UP_LIMIT / conn_num)
            # f = flow(timeStamp, src_ip, dst_ip, bandwidth, bw_up_limit)
            f = [timeStamp, src_ip, dst_ip, bandwidth, bw_up_limit]
            flows.append(f)
        return flows

# if __name__ == '__main__':
#    current_ip = 'OSU1'
#    flows = flowGenerator.generator(current_ip)
#    for i in range(len(flows)):
#        flows[i].print()