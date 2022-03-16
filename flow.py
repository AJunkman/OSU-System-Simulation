import random
import time
import threading
import rsvp
import connectClient

MAX_FLOW_NUMBER = 7
BANDWIDTH_UP_LIMIT = 10000

test = rsvp.Connection(1, 1, 100, 1)
test2 = rsvp.Connection(1, 1, 100, 1)
flowTable = {}

myLock = threading.Lock()


def printFlow(table):
    printTable = []
    for key in table:
        printTable.append([table[key].bandwidth, table[key].connection_bandwidth, table[key].bandwidth / table[key].connection_bandwidth])
    print(printTable)



def update(self):
    self.timeStamp = time.time()
    self.bandwidth = random.randint(BANDWIDTH_UP_LIMIT/10 * 3, BANDWIDTH_UP_LIMIT/10 * 7)



def adjustment():
    while True:
        myLock.acquire()
        for key in flowTable.copy():
            update(flowTable[key])

        for key in flowTable.copy():
            if flowTable[key].connection_bandwidth <= flowTable[key].bandwidth:  # 增大带宽
                if flowTable[key].connection_bandwidth * 2 <= flowTable[key].bandwidth:
                    flowTable[key].connection_bandwidth *= 2
                else:
                    flowTable[key].connection_bandwidth += BANDWIDTH_UP_LIMIT / 8
            else:  # 减小带宽
                if flowTable[key].connection_bandwidth - BANDWIDTH_UP_LIMIT / 10 > 0:
                    flowTable[key].connection_bandwidth -= BANDWIDTH_UP_LIMIT / 20
                else:
                    flowTable[key].connection_bandwidth = 1
            flowTable[key].utilization_rate = flowTable[key].bandwidth / flowTable[key].connection_bandwidth
            if flowTable[key].bandwidth > flowTable[key].connection_bandwidth:
                flowTable[key].overflow = flowTable[key].bandwidth - flowTable[key].connection_bandwidth
            else:
                flowTable[key] = 0
            # 发给后端
            client_send_type = 2            
            packet = flowTable[key]    # packet = flowTable   flowTable[key] 
            connectClient.main(client_send_type,key,packet)
            client_send_type = 0
            printFlow(flowTable[key])
        myLock.release()
        time.sleep(10)

if __name__ == '__main__':
    flowTable
    adjustment()
