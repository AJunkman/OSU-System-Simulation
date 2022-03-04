import random
import time
import threading
import rsvp

MAX_FLOW_NUMBER = 7
BANDWIDTH_UP_LIMIT = 10000

# test = rsvp.Connection(1, 1, 100, 1)
# test2 = rsvp.Connection(1, 1, 100, 1)
flowTable = {}
myLock = threading.Lock()


def printFlow(table):
    printTable = []
    for key in table:
        printTable.append([table[key].bandwidth, table[key].connection_bandwidth, table[key].bandwidth / table[key].connection_bandwidth])
    print(printTable)

# class Flow:
#
#     def __init__(self, uuid, timeStamp, src_ip, dst_ip, bandwidth):
#         self.uuid = uuid.uuid1()
#         self.timeStamp = timeStamp
#         self.src_ip = src_ip
#         self.dst_ip = dst_ip
#         self.bandwidth = bandwidth
#         self.connection_bandwidth = BANDWIDTH_UP_LIMIT/10
#
def update(self):
    self.timeStamp = time.time()
    self.bandwidth = random.uniform(BANDWIDTH_UP_LIMIT/10 * 3, BANDWIDTH_UP_LIMIT/10 * 7)


# def generator():
#     OSU_ip = ['OSU1', 'OSU2', 'OSU3', 'OSU4', 'OSU5']
#     while True:
#         if len(flowTable) <= MAX_FLOW_NUMBER:
#             myLock.acquire()
#             src_ip = OSU_ip[random.randint(0, 4)]
#             OSU_ip.remove(src_ip)
#             dst_ip = OSU_ip[random.randint(0, 3)]
#             new_flow = Flow(time.time(), src_ip, dst_ip, random.uniform(BANDWIDTH_UP_LIMIT/10 * 3, BANDWIDTH_UP_LIMIT/10 * 7))
#             flowTable.append(new_flow)
#             printFlow(flowTable)
#             OSU_ip.append(src_ip)
#             myLock.release()
#             time.sleep(3)
#         else:
#             break

# def updater():
#     while True:
#         for key in flowTable:
#             update(flowTable[key])
#             printFlow(flowTable)
#             time.sleep(1)

def adjustment():
    while True:
        for key in flowTable:
            update(flowTable[key])
            # printFlow(flowTable)
            # time.sleep(1)
        for key in flowTable:
            if flowTable[key].connection_bandwidth <= flowTable[key].bandwidth:  # 增大带宽
                if flowTable[key].connection_bandwidth * 2 <= flowTable[key].bandwidth:
                    flowTable[key].connection_bandwidth *= 2
                else:
                    flowTable[key].connection_bandwidth += BANDWIDTH_UP_LIMIT / 10
            else:  # 减小带宽
                if flowTable[key].connection_bandwidth - BANDWIDTH_UP_LIMIT / 10 > 0:
                    flowTable[key].connection_bandwidth -= BANDWIDTH_UP_LIMIT / 15
                else:
                    flowTable[key].connection_bandwidth = 1
            printFlow(flowTable[key])    # 此处改成调用socket接口
        # print("test")
        time.sleep(2)


# def main():
#     threads = [threading.Thread(target=adjustment())]
#     for t in threads:
#         t.start()
#     for t in threads:
#         t.join()
#
#
# if __name__ == '__main__':
#     main()

