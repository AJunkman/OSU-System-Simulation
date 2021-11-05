# 系统模块
import sys
import socket
import time
import configparser
import asyncio
import random
import threading
import logging
from threading import *

# 项目模块
import ospf
import rsvp
import log


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
        logging.info('%s-Received data: %s '%(self.osu._hostname, packet))
        self.transport.close()
        # Hello包处理
        if 'seen' in packet.keys():
            neighbor_id = packet['osu_id']
            # log('Seen %s' % (neighbor_id, ))
            logging.info('%s-Seen %s' % (self.osu._hostname, neighbor_id, ))
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
            # Insert to Link State database
            packets = ospf.LinkStatePacket(packet['adv_osu'], packet['age'], packet['seq_no'], packet['networks'], packet['tlv'])
            if self.osu._lsdb.insert(packets):
                if packets.adv_osu == self.osu._hostname:
                    self.osu._advertise()
                else:
                    logging.info('%s-Received LSA of %s via %s and merged to the LSDB' % (self.osu._hostname, packets.adv_osu, self.iface_name))
                    self.osu._flood(packets, self.iface_name)
                    self.osu._update_routing_table()
            elif packets.adv_osu == self.osu._hostname and packets.seq_no == 1:
                self.osu._advertise()
        elif 'msg_type' in packet.keys():
            # 判断是PathMsg
            if packet['msg_type'] == '0x01':
                pathMsg = rsvp.PathMsg(packet['src_ip'], packet['dst_ip'], packet['dataSize'])
                pathMsg.route = packet['route']
                self.osu._path(pathMsg)
            # 判断是PathResvMsg
            elif packet['msg_type'] == '0x02':
                pathResvMsg = rsvp.PathResvMsg(packet['src_ip'], packet['dst_ip'], packet['dataSize'])
                pathResvMsg.route = packet['route']
                self.osu._pathResv(pathResvMsg)
            else:
                pass
        else:
            pass


# 客户端消息发送协议
class TxProtocol(asyncio.Protocol):
    def __init__(self, message, on_con_lost):
        self.message = str(message.__dict__)
        self.on_con_lost = on_con_lost
    def connection_made(self, transport):
        transport.write(self.message.encode())
        # logging.info('Data sent: %s '%(self.message))
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
        self.shortestPath = {}
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
        self._timers['createConnTest'] = mktimer(rsvp.CREATE_CONN_INTERVAL, self._createConnTest)

    def _update_lsdb(self):
        flushed = self._lsdb.update()
        if flushed:
            logging.info('%s-LSA(s) of %s reached MaxAge and was/were flushed from the LSDB' % (self._hostname, ', '.join(flushed), ))

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
        logging.info('%s-Recalculating shortest paths and updating routing table'%(self._hostname,))
        # 清除当前路由表内容
        # 计算当前主机最短路径
        self._table.clear()
        paths, self.shortestPath = self._lsdb.get_shortest_paths(self._hostname)
        logging.info('%s-The next_hop in the shortest path: %s'%(self._hostname, paths))
        logging.info('%s-Full paths: %s'%(self._hostname, self.shortestPath))
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
        logging.info('%s-%s is down'%(self._hostname, neighbor_id))
        self._advertise()

    def _flood(self, packet, source_iface=None):
        # 向其他接口泛洪接收到的数据包
        if packet.adv_osu == self._hostname:
            logging.info('%s-Flooding own LSA'%(self._hostname,))
        else:
            logging.info('%s-Flooding LSA of %s' % (self._hostname, packet.adv_osu, ))
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
                                 ava_bw=iface.ava_bw,
                                 use_bw=iface.use_bw,
                                 av_delay=iface.av_delay)
                # lth: 更新链路信息
                else:
                    iface = self._interfaces[iface_name]
                    lsa.tlv[iface_name]['val']['32'] = iface.ava_bw
                    lsa.tlv[iface_name]['val']['33'] = iface.use_bw
        else:
            lsa = ospf.LinkStatePacket(self._hostname, 1, 1, networks, {})
            for iface_name in link_enable_ports:
                iface = self._interfaces[iface_name]
                lsa.init_tlv(iface_name=iface_name,
                             lcl_id=self._hostname,
                             rmt_id=iface.link,
                             max_bw=iface.bandwidth,
                             ava_bw=iface.ava_bw,
                             use_bw=iface.use_bw,
                             av_delay=iface.av_delay)
        self._lsdb.insert(lsa)
        # 向邻居泛洪 LSA
        self._flood(lsa)
        self._update_routing_table()

    def _sync_lsdb(self, neighbor_id):
        topology_changed = (neighbor_id not in self._neighbors)
        if topology_changed:
            logging.info('%s-Adjacency established with %s' % (self._hostname, neighbor_id, ))
        self._neighbors[neighbor_id] = self._seen[neighbor_id]
        if self._hostname not in self._lsdb:
            logging.info('%s-Creating initial LSA'%(self._hostname,))
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

    def _createConnTest(self):
        for dst in self.shortestPath.keys():
            dataSize = random.randint(2, 10000)
            pathMsg = rsvp.PathMsg(self._hostname, dst, dataSize)
            pathMsg.route = self.shortestPath[dst]
            self._path(pathMsg)

    
    # 处理pathMsg，向下游沿途保存路径状态
    def _path(self, pathMsg):
        # 判断是不是第一跳，不是第一跳
        routeObject = rsvp.RouteObject(pathMsg.src_ip, pathMsg.dst_ip, pathMsg.route)
        if pathMsg.src_ip != self._hostname:
            # 循环遍历当前设备所有接口，找出与上一条连接的接口
            prv_hop = routeObject.get_prev_hop(self._hostname)
            for pre_iface in self._interfaces.values():
                if prv_hop == pre_iface.link:
                    # 检查输入端口的资源是否够用
                    if pathMsg.dataSize > pre_iface.ava_bw:
                        # 此处应当返回资源不足，连接创建失败的消息，后续根据PathErrorMsg补充
                        pass
        # 判断是不是最后一跳，不是最后一跳
        if pathMsg.dst_ip != self._hostname:
            next_hop = routeObject.get_next_hop(self._hostname)
            seen = list(self._seen.keys())
            if next_hop in seen:
                for next_iface in self._interfaces.values():
                    if next_hop == next_iface.link:
                        # 检查输出端口的资源是否够用
                        if pathMsg.dataSize < next_iface.ava_bw:
                            # 向下一跳发送pathMsg
                            next_iface.transmit(pathMsg)
                        else:
                            # 此处应当返回资源不足，连接创建失败的消息，后续根据PathErrorMsg补充
                            pass
        # 是最后一跳，触发_pathResv方法，开始向上游逐一回复pathResvMsg
        else:
            # 封装pathResvMsg，逆着回发消息，源地址和目的地址调换位置赋值
            pathResvMsg = rsvp.PathResvMsg(pathMsg.dst_ip, pathMsg.src_ip, pathMsg.dataSize)
            # 原来的路径应当逆序赋值给pathResvMsg中的路由
            pathResvMsg.route = pathMsg.route
            pathResvMsg.route.reverse()
            self._pathResv(pathResvMsg)

    # 处理pathResvMsg，向上游沿途预留资源
    def _pathResv(self, pathResvMsg):
        routeObject = rsvp.RouteObject(pathResvMsg.src_ip, pathResvMsg.dst_ip, pathResvMsg.route)
        # routeObject.set_shortest_path(pathResvMsg.route)
        if pathResvMsg.src_ip != self._hostname:
            prv_hop = routeObject.get_prev_hop(self._hostname)
            # 循环遍历当前设备所有接口，找出与上一条连接的接口
            for pre_iface in self._interfaces.values():
                if prv_hop == pre_iface.link:
                    if pathResvMsg.dataSize < pre_iface.ava_bw:
                    # 资源可用，将即将创建的连接保存在interface中
                        rsvp.Resource.reservation(pre_iface, pathResvMsg)
                    else:
                    # 抢占资源，连接创建失败，后续根据pathResvMsgErr补充
                        pass
        # 判断是不是最后一跳，不是最后一跳
        if pathResvMsg.dst_ip != self._hostname:
            #pdb.set_trace()
            next_hop = routeObject.get_next_hop(self._hostname)
            seen = list(self._seen.keys())
            if next_hop in seen:
                for next_iface in self._interfaces.values():
                    if next_hop == next_iface.link:
                        if pathResvMsg.dataSize < next_iface.ava_bw:
                            rsvp.Resource.reservation(next_iface, pathResvMsg)
                            # 向下一跳发送pathMsg
                            next_iface.transmit(pathResvMsg)
                        else:
                            # 抢占资源，连接创建失败，后续根据pathResvMsgErr补充
                            pass
        else:
            # 最后一跳，说明连接创建成功
            logging.info("%s-The %s connection between %s and %s is successfully created"%(self._hostname, pathResvMsg.dataSize, pathResvMsg.src_ip, pathResvMsg.dst_ip,))
        # 资源变化，通告LSA消息
        # self._advertise()

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
        self.ava_bw = bandwidth
        self.use_bw = 0
        self.bd_change_rng = 20
        self.av_delay = av_delay
        self.connNum = 0
        self.connection = {}
        self.psb = {}
        self.rsb = {}
        # self.monitor_port_thread()

    def transmit(self, packet):
        # 通过接口发送数据包
        thread_loop = asyncio.new_event_loop()
        t = threading.Thread(target=IfaceTx, args=(thread_loop,self.remote_end_host, self.remote_end_port, packet,))
        t.daemon = True
        t.start()

    # 在没有RSVP的条件下，随机修改端口带宽
    def change_port_bd(self):
        time.sleep(60)
        while True:
            time_sleep = random.randint(1, 10)
            time.sleep(time_sleep)
            rsv_bd = int(self.bandwidth)
            change_bd = random.randint(0, 10)
            self.bandwidth = str(rsv_bd - change_bd) if rsv_bd - change_bd >= 0 else '10000'

    def monitor_port_bd(self):
        current_bd = int(self.bandwidth)
        while True:
            if abs(current_bd - int(self.bandwidth)) > self.bd_change_rng:
                current_bd = int(self.bandwidth)
                logging.info('%s-%s has triggered the flooding, and the bandwidth remained %s'%(self.osu._hostname, self.name, self.bandwidth))
                self.osu._advertise()

    def monitor_port_thread(self):
        change_thread = threading.Thread(target=self.change_port_bd)
        monitor_thread = threading.Thread(target=self.monitor_port_bd)
        change_thread.start()
        monitor_thread.start()


def sim_run(conf_file_path):
    log.start_thread_logging()
    AdjList = {}
    cp = configparser.ConfigParser()
    cp.read(conf_file_path)
    hostname = cp.get('Local','hostname')
    osu = OSU(hostname)

    ifaces = [i for i in cp.sections() if i.startswith('Local:')]
    for iface in ifaces:
        # 创建接口
        name = iface.split(':')[1]
        bandwidth = int(cp.get(iface, 'bandwidth'))
        port = int(cp.get(iface, 'port'))
        try:
            osu.iface_create(name, bandwidth, port)
            logging.info('%s-%s up' % (osu._hostname, name, ))
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
    osu.start()
