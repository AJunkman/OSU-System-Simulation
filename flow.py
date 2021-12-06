import random
import time
import threading

MAX_FLOW_NUMBER = 50
BANDWIDTH_UP_LIMIT = 10000

flowTable = []
myLock = threading.Lock()


class Flow:

    def __init__(self, timeStamp, src_ip, dst_ip, bandwidth):
        self.timeStamp = timeStamp
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.bandwidth = bandwidth
        self.connection_bandwidth = 0

    def update(self):
        self.timeStamp = time.time()
        self.bandwidth = random.uniform(0, BANDWIDTH_UP_LIMIT)


def generator():
    OSU_ip = ['OSU1', 'OSU2', 'OSU3', 'OSU4', 'OSU5']

    while True:
        if len(flowTable) <= MAX_FLOW_NUMBER:
            myLock.acquire()
            time.sleep(3)
            src_ip = OSU_ip[random.randint(0, 4)]
            OSU_ip.remove(src_ip)
            dst_ip = OSU_ip[random.randint(0, 3)]
            new_flow = Flow(time.time(), src_ip, dst_ip, random.uniform(0, BANDWIDTH_UP_LIMIT))
            flowTable.append(new_flow)
            # print(flowTable)
            OSU_ip.append(src_ip)
            myLock.release()
        else:
            break


def updater():
    while True:
        # time.sleep(2)
        myLock.acquire()
        for flow in flowTable:
            flow.update()
        # print(flowTable)
        myLock.release()


def bandwidth_request():
    while True:
        myLock.acquire()
        for flow in flowTable:
            if flow.connection_bandwidth <= flow.bandwidth: # 增大带宽
                if flow.connection_bandwidth * 2 <= flow.bandwidth:
                    flow.connection_bandwidth *= 2
                else:
                    flow.connection_bandwidth += BANDWIDTH_UP_LIMIT/10
            else:   # 减小带宽
                if flow.connection_bandwidth - BANDWIDTH_UP_LIMIT/10 > 0:
                    flow.connection_bandwidth -= BANDWIDTH_UP_LIMIT/10
                else:
                    flow.connection_bandwidth = 0
        myLock.release()
# def main():
#
#     flow_generate = threading.Thread(target=generator)
#     flow_update = threading.Thread(target=updater)
#
#     flow_generate.start()
#     flow_update.start()
#
#
#
# if __name__ == '__main__':
#     main()
#
# # flow_generate.join()
# # flow_update.join()
