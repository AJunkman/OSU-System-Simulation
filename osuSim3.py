import sys
sys.path.append(r'/home/osu-sim/share/osu-sim')
import socket
import time
import configparser
import asyncio
import random
import threading
from threading import *
import logging
import ospf

def log(msg):
    print('%s    %s' % (time.ctime().split()[3], msg))

# 自定义日志输出格式
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y/%m/%d %H:%M:%S %p"
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.basicConfig(filename='log/r3.log', level=logging.DEBUG, format=LOG_FORMAT, datefmt=DATE_FORMAT)

# 重写Thread中的方法，实现多定时任务不间断执行
class RepeatingTimer(Thread):
    def __init__(self, interval, callback, args = ()):
        super().__init__()
        self.stop_event = Event()
        self.interval = interval
        self.callback = callback
        self.args = args
    def run(self):
        while not self.stop_event.wait(self.interval):
            if self.args:
                self.callback(self.args)
            else:
                self.callback()
    def stop(self):
        self.stop_event.set()
def mktimer(interval, callback, args = ()):
    timer = RepeatingTimer(interval, callback, args)
    return timer

# 服务端消息接收协议
class RxProtocol(asyncio.Protocol):
    def __init__(self, osu, name):
        self.osu = osu
        self.iface_name = name
    def connection_made(self, transport):
        self.transport = transport
    def data_received(self, data):
        packet = eval(data.decode())
        # log('Data received: %s '%(packet))
        logging.info('Data received: %s '%(packet))
        self.transport.close()
        # todo
        # 测试用代码，正式服应删除以下代码
        # 模拟链路建立过程，测试TE LSA是否可以正确泛洪链路信息
        iface = self.osu._interfaces[self.iface_name]
        if int(iface.rsv_bw) >= 20:
            conn_bw = random.randint(1, 20)
            iface.rsv_bw = str(int(iface.rsv_bw) - conn_bw)
            iface.unrsv_bw = str(int(iface.unrsv_bw) + conn_bw)
        # Hello包处理
        if 'seen' in packet.keys():
            neighbor_id = packet['osu_id']
            # log('Seen %s' % (neighbor_id, ))
            logging.info('Seen %s' % (neighbor_id, ))
            # Reset Dead timer
            if neighbor_id in self.osu._timers.keys():
                self.osu._timers[neighbor_id].stop()
            self.osu._timers[neighbor_id] = mktimer(ospf.DEAD_INTERVAL, self.osu._break_adjacency, (neighbor_id, ))
            self.osu._timers[neighbor_id].start()
            self.osu._seen[neighbor_id] = (self.iface_name, packet['address'], packet['netmask'])
            if self.osu._hostname in packet['seen']:
                self.osu._sync_lsdb(neighbor_id)
        # LSP包处理
        elif 'adv_osu' in packet.keys():
        # else:
            # Insert to Link State database  
            packets = ospf.LinkStatePacket(packet['adv_osu'], packet['age'], packet['seq_no'], packet['networks'], packet['tlv'])
            if self.osu._lsdb.insert(packets):
                if packets.adv_osu == self.osu._hostname:
                    self.osu._advertise()
                else:
                    logging.info('Received LSA of %s via %s and merged to the LSDB' % (packets.adv_osu, self.iface_name))
                    self.osu._flood(packets, self.iface_name)
                    self.osu._update_routing_table()
            elif packets.adv_osu == self.osu._hostname and packets.seq_no == 1:
                self.osu._advertise()
        else:
            pass

# 客户端消息发送协议
class TxProtocol(asyncio.Protocol):
    def __init__(self, message, on_con_lost):
        self.message = str(message.__dict__)
        self.on_con_lost = on_con_lost
    def connection_made(self, transport):
        transport.write(self.message.encode())
        logging.info('Data sent: %s '%(self.message))
    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)

# 定义消息传输方法
def IfaceTx(loop, address, port, data):
    asyncio.set_event_loop(loop)
    async def init_tx_client():     
        try:
            # 当服务端未启动时，直接启动客户端发送消息会报错
            on_con_lost = loop.create_future() 
            transport, protocol = await loop.create_connection(
                lambda: TxProtocol(data, on_con_lost),
                address, port)
        except OSError:
            pass
        else:
            try:
                await on_con_lost
            finally:
                transport.close()
    future = asyncio.gather(init_tx_client())
    loop.run_until_complete(future)
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()

class Route(object):
    def __init__(self, dest, gateway, netmask, metric, iface):
        self.dest = dest
        self.gateway = gateway
        self.netmask = netmask
        self.metric = metric
        self.iface = iface
class RoutingTable(list): # RoutingTable[Route1, Route2...]
    def __repr__(self):
        routes = ['Dest\tGateway\tNetmask\tMetric\tInterface']
        for r in self:
            routes.append("%s\t%s\t%s\t%.2f\t%s" % (r.dest, r.gateway, r.netmask, r.metric, r.iface))
        return '\n'.join(routes)
    def clear(self):
        del self[:]

class OSU(object):

    def __init__(self, hostname):
        self._hostname = hostname
        self._table = RoutingTable()
        self._lsdb = ospf.Database()
        self._interfaces = {}
        self._neighbors = {}
        self._seen = {}
        self._init_timers()

    @staticmethod
    def _get_netadd(addr, netmask):
        addr = addr.split('.')
        netmask = netmask.split('.')
        netadd = []
        for i in range(4):
            netadd.append(str(int(addr[i]) & int(netmask[i])))
        return '.'.join(netadd)

    def _init_timers(self):
        self._dead_timer = None
        self._timers = {}
        self._timers['lsdb'] = mktimer(ospf.AGE_INTERVAL, self._update_lsdb)
        self._timers['refresh_lsa'] = mktimer(ospf.LS_REFRESH_TIME, self._refresh_lsa)
        self._timers['hello'] = mktimer(ospf.HELLO_INTERVAL, self._hello)

    def _update_lsdb(self):
        flushed = self._lsdb.update()
        if flushed:
            logging.info('LSA(s) of %s reached MaxAge and was/were flushed from the LSDB' % (', '.join(flushed), ))

    def _refresh_lsa(self):
        if self._hostname in self._lsdb:
            logging.info('Refreshing own LSA')
            self._advertise()

    def _hello(self):
        # 建立邻接
        seen = self._seen.keys()
        for iface in self._interfaces.values():
            packet = ospf.HelloPacket(self._hostname, iface.address, iface.netmask, list(seen))
            iface.transmit(packet)
        for neighbor_id in self._seen:
            if neighbor_id not in self._neighbors:
                self._sync_lsdb(neighbor_id)

    def _update_routing_table(self):
        logging.info('Recalculating shortest paths and updating routing table')
        # 清除当前路由表内容
        # 计算当前主机最短路径
        self._table.clear()
        paths = self._lsdb.get_shortest_paths(self._hostname)
        logging.info('shortest_paths: %s'%(paths))
        if not paths:
            return
        networks = {}
        for node, lsa in self._lsdb.items():
            for network, data in lsa.networks.items():    # networks(neighbor_id, cost, address, netmask)
                if network not in networks:
                    networks[network] = {}
                networks[network][node] = data[1]  # cost
        gateways = {}
        for network, nodes in networks.items():
            if len(nodes) != 2:
                continue
            n1, n2 = nodes.keys()
            if self._hostname in nodes:
                # 假设路由器通过自己的接口发送数据，即使成本更高
                dest = next_hop = (n2 if n1 == self._hostname else n1)
                cost = nodes[self._hostname]
            else:
                # 确定哪个节点是到目标网络的较短路径
                dest = (n1 if paths[n1][1] + nodes[n1] < paths[n2][1] + nodes[n2] else n2)
                next_hop, cost = paths[dest]
                # 获取实际成本
                cost += nodes[dest]
            # 获取其他信息
            iface, gateway = self._neighbors[next_hop][:2]
            netmask = self._lsdb[dest].networks[network][3]
            if self._hostname in nodes:
                gateways[cost] = (gateway, iface)
                gateway = '-'
            r = Route(network, gateway, netmask, cost, iface)
            self._table.append(r)
        if gateways:
            cost = min(gateways.keys())
            gateway, iface = gateways[cost]
            self._table.append(Route('0.0.0.0', gateway, '0.0.0.0', cost, iface))

    def _break_adjacency(self, neighbor_id):
        self._dead_timer = self._timers[neighbor_id]
        del self._timers[neighbor_id]
        del self._neighbors[neighbor_id]
        del self._seen[neighbor_id]
        logging.info(' '.join([neighbor_id, 'is down']))
        self._advertise()

    def _flood(self, packet, source_iface=None):
        # 向其他接口泛洪接收到的数据包
        if packet.adv_osu == self._hostname:
            logging.info('Flooding own LSA')
        else:
            logging.info('Flooding LSA of %s' % (packet.adv_osu, ))
        interfaces = []
        for data in self._neighbors.values():
            interfaces.append(data[0])
        if source_iface in interfaces:
            interfaces.remove(source_iface)
        for iface_name in interfaces:
            iface = self._interfaces[iface_name]
            iface.transmit(packet)

    def _advertise(self):
        networks = {}
        link_enable_ports = []
        for neighbor_id, data in self._neighbors.items():
            iface_name, address, netmask = data
            iface = self._interfaces[iface_name]
            # todo 需要修改CSOT
            cost = ospf.BANDWIDTH_BASE / float(iface.bandwidth)
            netadd = self._get_netadd(address, netmask)
            networks[netadd] = (neighbor_id, cost, address, netmask)
            link_enable_ports.append(iface.name)
        # 创建新的或更新现有的 LSA
        if self._hostname in self._lsdb:
            lsa = self._lsdb[self._hostname]
            lsa.seq_no += 1
            lsa.age = 1
            lsa.networks = networks
            for iface_name in link_enable_ports:
                # lth: 有新端口上线
                if iface_name not in lsa.tlv.keys():
                    iface = self._interfaces[iface_name]
                    lsa.init_tlv(iface_name=iface_name,
                                 lcl_id=self._hostname,
                                 rmt_id=iface.link,
                                 max_bw=iface.bandwidth,
                                 max_rsv_bw=iface.rsv_bw,
                                 max_unrsv_bw=iface.unrsv_bw,
                                 av_delay=iface.av_delay)
                # lth: 更新链路信息
                else:
                    iface = self._interfaces[iface_name]
                    lsa.tlv[iface_name]['val']['7'] = iface.rsv_bw
                    lsa.tlv[iface_name]['val']['8'] = iface.unrsv_bw
        else:
            lsa = ospf.LinkStatePacket(self._hostname, 1, 1, networks, {})
            for iface_name in link_enable_ports:
                iface = self._interfaces[iface_name]
                lsa.init_tlv(iface_name=iface_name,
                             lcl_id=self._hostname,
                             rmt_id=iface.link,
                             max_bw=iface.bandwidth,
                             max_rsv_bw=iface.rsv_bw,
                             max_unrsv_bw=iface.unrsv_bw,
                             av_delay=iface.av_delay)
        self._lsdb.insert(lsa)
        # 向邻居泛洪 LSA
        self._flood(lsa)
        self._update_routing_table()

    def _sync_lsdb(self, neighbor_id):
        topology_changed = (neighbor_id not in self._neighbors)
        if topology_changed:
            logging.info('Adjacency established with %s' % (neighbor_id, ))
        self._neighbors[neighbor_id] = self._seen[neighbor_id]
        if self._hostname not in self._lsdb:
            logging.info('Creating initial LSA')
            self._advertise()
        elif topology_changed:
            self._advertise()
            # 与邻居同步LSDB
            iface_name = self._neighbors[neighbor_id][0]
            iface = self._interfaces[iface_name]
            for lsa in list(self._lsdb.values()):
                iface.transmit(lsa)

    def iface_create(self, name, bandwidth, port):
        if name not in self._interfaces:
            self._interfaces[name] = Interface(name, bandwidth, port, self)

    def iface_config(self, name, address, netmask, link, host, port):
        iface = self._interfaces[name]
        iface.address = address
        iface.netmask = netmask
        iface.link = link
        iface.remote_end_host = host
        iface.remote_end_port = port              

    def IfaceRx(self, loop, name):
        #为子线程设置自己的事件循环 
        asyncio.set_event_loop(loop)
        async def init_rx_server():
            server = await loop.create_server(
                lambda: RxProtocol(self, name),
                '127.0.0.1', self._interfaces[name].port)
            async with server:
                await server.serve_forever()
        future = asyncio.gather(init_rx_server())
        loop.run_until_complete(future)

    def start(self):
        # 启动定时任务
        for t in self._timers.values():
            t.start()
        for name in self._interfaces.keys():
            # 为启动服务端创建一个事件循环thread_loop
            thread_loop = asyncio.new_event_loop() 
            t = threading.Thread(target=self.IfaceRx, args=(thread_loop,name,))
            t.daemon = True
            t.start()

class Interface():
    # OSU接口
    def __init__(self, name, bandwidth, port, osu, av_delay=None):
        self.name = name
        self.bandwidth = bandwidth
        self.port = port
        self.osu = osu
        self.address = None
        self.netmask = None
        self.link = None
        self.remote_end_host = None
        self.remote_end_port = None
        self.rsv_bw = bandwidth
        self.unrsv_bw = '0'
        self.av_delay = av_delay
        logging.info('%s up' % (self.name, ))
    
    def transmit(self, packet):
        # 通过接口发送数据包
        thread_loop = asyncio.new_event_loop() 
        t = threading.Thread(target=IfaceTx, args=(thread_loop,self.remote_end_host, self.remote_end_port, packet,))
        t.daemon = True
        t.start()

if __name__ == '__main__':
    AdjList = {}
    routingT = {}
    routingTable = []
    linkState = {}
    linkStateDb = []
    cp = configparser.ConfigParser()
    cp.read('topologies/r3.cfg')
    hostname = cp.get('Local','hostname')
    osu = OSU(hostname)

    ifaces = [i for i in cp.sections() if i.startswith('Local:')]
    for iface in ifaces:
        # 创建接口
        name = iface.split(':')[1]
        bandwidth = cp.get(iface, 'bandwidth')
        port = int(cp.get(iface, 'port'))
        try:
            osu.iface_create(name, bandwidth, port)
        except socket.error:
            sys.exit(1)
        # 配置接口
        address = cp.get(iface, 'address')
        netmask = cp.get(iface, 'netmask')
        link = cp.get(iface, 'link')
        host = cp.get(link, 'host')
        port = int(cp.get(link, 'port'))
        osu.iface_config(name, address, netmask, link, host, port)
        bandwidth = int(bandwidth)
        if bandwidth < 1000:
            bandwidth = '%d bps' % (bandwidth, )
        elif bandwidth < 1000000:
            bandwidth = '%.1f kbps' % (bandwidth / 1000.0, )
        elif bandwidth < 1000000000:
            bandwidth = '%.1f Mbps' % (bandwidth / 1000000.0, )
        else:
            bandwidth = '%.1f Gbps' % (bandwidth / 1000000000.0, )
        cols = [name, address, netmask, bandwidth, link]
        for val in cols:
            AdjList.setdefault(cols[0],[]).append(val)
    # print(AdjList)

    osu.start()