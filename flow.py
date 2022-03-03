import random
import time
import threading

MAX_FLOW_NUMBER = 7
BANDWIDTH_UP_LIMIT = 10000

flowTable = []
myLock = threading.Lock()


def printFlow(table):
    printTable = []
    for flow in table:
        printTable.append([flow.bandwidth, flow.connection_bandwidth, flow.bandwidth / flow.connection_bandwidth])
    print(printTable)

class Flow:

    def __init__(self, timeStamp, src_ip, dst_ip, bandwidth):
        self.timeStamp = timeStamp
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.bandwidth = bandwidth
        self.connection_bandwidth = BANDWIDTH_UP_LIMIT/10

    def update(self):
        self.timeStamp = time.time()
        self.bandwidth = random.uniform(BANDWIDTH_UP_LIMIT/10 * 3, BANDWIDTH_UP_LIMIT/10 * 7)


def generator():
    OSU_ip = ['OSU1', 'OSU2', 'OSU3', 'OSU4', 'OSU5']
    while True:
        if len(flowTable) <= MAX_FLOW_NUMBER:
            myLock.acquire()
            src_ip = OSU_ip[random.randint(0, 4)]
            OSU_ip.remove(src_ip)
            dst_ip = OSU_ip[random.randint(0, 3)]
            new_flow = Flow(time.time(), src_ip, dst_ip, random.uniform(BANDWIDTH_UP_LIMIT/10 * 3, BANDWIDTH_UP_LIMIT/10 * 7))
            flowTable.append(new_flow)
            printFlow(flowTable)
            OSU_ip.append(src_ip)
            myLock.release()
            time.sleep(3)
        else:
            break


def updater():
    while True:
        myLock.acquire()
        for flow in flowTable:
            flow.update()
        for flow in flowTable:
            if flow.connection_bandwidth <= flow.bandwidth:  # 增大带宽
                if flow.connection_bandwidth * 2 <= flow.bandwidth:
                    flow.connection_bandwidth *= 2
                else:
                    flow.connection_bandwidth += BANDWIDTH_UP_LIMIT / 10
            else:  # 减小带宽
                if flow.connection_bandwidth - BANDWIDTH_UP_LIMIT / 10 > 0:
                    flow.connection_bandwidth -= BANDWIDTH_UP_LIMIT / 15
                else:
                    flow.connection_bandwidth = 0
        printFlow(flowTable)
        myLock.release()
        time.sleep(1)


def bandwidth_request():
    while True:
        myLock.acquire()
        for flow in flowTable:  
            if flow.connection_bandwidth <= flow.bandwidth:  # 增大带宽
                if flow.connection_bandwidth * 2 <= flow.bandwidth:
                    flow.connection_bandwidth *= 2
                else:
                    flow.connection_bandwidth += BANDWIDTH_UP_LIMIT / 10
            else:  # 减小带宽
                if flow.connection_bandwidth - BANDWIDTH_UP_LIMIT / 10 > 0:
                    flow.connection_bandwidth -= BANDWIDTH_UP_LIMIT / 10
                else:
                    flow.connection_bandwidth = 0
        myLock.release()


def main():
    flow_generate = threading.Thread(target=generator)
    flow_update = threading.Thread(target=updater)
    # flow_request = threading.Thread(target=bandwidth_request())
    #
    # flow_request.start()
    flow_generate.start()
    flow_update.start()


if __name__ == '__main__':
    main()

