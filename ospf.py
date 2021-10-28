import sys
sys.path.append(r'/home/osu-sim/share/osu-sim')
import dijkstra


TIME_SCALE = 20 # 1 minute (60 seconds) is to 3 seconds (60 / 3 = 20)


def _scale_time(minutes):
    return (60.0 * minutes / TIME_SCALE)


BANDWIDTH_BASE = 100000000 # 100 Mbps
HELLO_INTERVAL = 10 # 10 seconds
DEAD_INTERVAL = 4 * HELLO_INTERVAL # typical value is 4 times the HELLO_INTERVAL
AGE_INTERVAL = _scale_time(1) # 1 minute
LS_REFRESH_TIME = _scale_time(30) # 30 minutes
MAX_AGE = _scale_time(60) # 1 hour


class LinkStatePacket(object):

    def __init__(self, osu_id, age, seq_no, networks, tlv: dict):
    # 报文首部
        self.adv_osu = osu_id
        self.age = age
        self.seq_no = seq_no

        # RTR_LSA 净荷
        self.networks = networks

        # TE_LSA 净荷，一个字典
        self.tlv = tlv

    def __repr__(self):
        stat = '\nADV Osu: %s\nAge: %d\nSeq No.: %d\nNetworks: %s\nTLV: %s\n' % (self.adv_osu, self.age, self.seq_no, self.networks, self.tlv)
        return stat

    def init_tlv(self, iface_name, lcl_id, rmt_id, max_bw, max_rsv_bw, max_unrsv_bw, av_delay=None):
        # 初始化链路tlv
        link_tlv = Link_TLV()
        link_tlv.init_lrrid_tlv(lcl_id, rmt_id)
        link_tlv.init_max_bw_tlv(max_bw)
        link_tlv.init_max_rsv_bw_tlv(max_rsv_bw)
        link_tlv.init_max_unrsv_bw_tlv(max_unrsv_bw)
        link_tlv.init_av_delay(av_delay)

        # 将链路tlv赋值到净荷区
        self.tlv[iface_name] = link_tlv.__dict__


class HelloPacket(object):

    def __init__(self, osu_id, address, netmask, seen):
        self.osu_id = osu_id
        self.address = address
        self.netmask = netmask
        self.seen = seen

	# Type-Length-Value结构
class TLV:

    def __init__(self, tpe, val):
        self.type = tpe
        self.val = val


class Link_TLV(TLV):

    def __init__(self, tpe=2, val=None):
        super().__init__(tpe, val)
        self.type = tpe
        self.val = {}

    # 初始化链路标识TLV
    def init_lrrid_tlv(self, lcl_id: str, rmt_id: str):
        self.val['10'] = (lcl_id, rmt_id)

    # 初始化最大带宽子TLV - TE隧道可以使用的带宽上限值（通常接口带宽）
    def init_max_bw_tlv(self, max_bw: float):
        # 带宽单位 Byte/s
        self.val['6'] = max_bw

    # 初始化最大可预留带宽子TLV
    # 隧道可分配带宽，初值默认为最大带宽
    def init_max_rsv_bw_tlv(self, max_rsv_bw: float):
        self.val['7'] = max_rsv_bw

    # 初始化最大未保留带宽子TLV
    # 提供给隧道后剩余的带宽，初值默认为最大可预留带宽
    def init_max_unrsv_bw_tlv(self, max_unrsv_bw: float):
        self.val['8'] = max_unrsv_bw

    # 初始化平均时延子TLV
    def init_av_delay(self, av_delay: float):
        # 时延单位 微妙
        self.val['27'] = av_delay


class Database(dict):

    def insert(self, lsa):
        """Returns True if LSA was added/updated"""
        if lsa.adv_osu not in self or \
           lsa.seq_no > self[lsa.adv_osu].seq_no:
            self[lsa.adv_osu] = lsa
            return True
        else:
            return False

    def remove(self, osu_id):
        """Remove LSA from osu_id"""
        if osu_id in self:
            del self[osu_id]

    def flush(self):
        """Flush old entries"""
        flushed = []
        for osu_id in self:
            if self[osu_id].age > MAX_AGE:
                flushed.append(osu_id)
        map(self.pop, flushed)
        return flushed

    def update(self):
        """Update LSDB by aging the LSAs and flushing expired LSAs"""
        for adv_osu in self:
            self[adv_osu].age += 1
        return self.flush()

    def get_shortest_paths(self, osu_id):
        """Return a list of shortest paths from osu_id to all other nodes"""
        g = dijkstra.Graph()
        nodes = []
        paths = {}
        for lsa in self.values():
            nodes.append(lsa.adv_osu)
            for data in lsa.networks.values():
                neighbor_id, cost = data[:2]
                g.add_e(lsa.adv_osu, neighbor_id, cost)
        if osu_id in nodes:
            nodes.remove(osu_id)
        # Find a shortest path from osu_id to dest
        dist, prev = g.s_path(osu_id)
        for dest in nodes:
            # Trace the path back using the prev array.
            path = []
            current = dest
            while current in prev:
                path.insert(0, prev[current])
                current = prev[current]
            try:
                cost = dist[dest]
            except KeyError:
                continue
            else:
                next_hop = (path[1] if len(path) > 1 else dest)
                paths[dest] = (next_hop, cost)
        return paths
