import random
import time
import uuid


CREATE_CONN_INTERVAL = 15 # 15 seconds

class PathMsg:
    
    def __init__(self, src_ip, dst_ip, dataSize):
        self.msg_type = '0x01'
        self.lsp_id = None
        
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.tos = None
        self.dataSize = dataSize
        self.route = None

    def set_lsp_id(self):
        # random.seed(time.time())
        # self.lsp_id = random.random()       
        self.lsp_id = str(uuid.uuid1())

class ResvMsg:

    def __init__(self, lsp_id, src_ip, dst_ip, dataSize):
        self.msg_type = '0x02'
        self.lsp_id = lsp_id
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.dataSize = dataSize
        self.route = None
        self.style = None

class PathErrMsg():

    def __init__(self, lsp_id, src_ip, dst_ip, err_msg, route):
        self.msg_type = '0x03'
        self.lsp_id = lsp_id
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.err_msg = err_msg
        self.route = route


class ResvErrMsg():

    def __init__(self, lsp_id, src_ip, dst_ip, err_msg, route):
        self.msg_type = '0x04'
        self.lsp_id = lsp_id
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.err_msg = err_msg
        self.route = route


class PathTearMsg():

    def __init__(self, lsp_id, src_ip, dst_ip, route):
        self.msg_type = '0x05'
        self.lsp_id = lsp_id
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.route = route

class ResvTearMsg():

    def __init__(self, lsp_id, src_ip, dst_ip, route):
        self.msg_type = '0x06'
        self.lsp_id = lsp_id
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.route = route


class RouteObject():

    def __init__(self, src_ip, dst_ip, path):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.path = path

    # 获取当前设备在路径表中的索引值, 加1后是下一跳地址索引值
    def get_next_hop(self, current_hop):
        current_hop_id = self.path.index(current_hop)
        next_hop = self.path[current_hop_id + 1]
        return next_hop

    # 减1是上一跳地址索引值
    def get_prev_hop(self, current_hop):
        current_hop_id = self.path.index(current_hop)
        prev_hop = self.path[current_hop_id - 1]
        return prev_hop

class PSB():

    def __init__(self, lsp_id, prv_hop, interface):
        self.lsp_id = lsp_id
        self.prv_hop = prv_hop
        self.interface = interface


class RSB():

    def __init__(self, lsp_id, next_hop, bandWidth, interface):
        self.lsp_id = lsp_id
        self.next_hop = next_hop
        self.bandWidth = bandWidth
        self.interface = interface

class Connection():

    def __init__(self, src_ip, dst_ip, bandWidth, route):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.bandWidth = bandWidth
        self.path = route
        self.real_bw = []

class State_Block():

    def creatPSB(pathMsg, hop, pre_iface, iface):
        # 检查端口的资源是否够用
        if pathMsg.dataSize < iface.ava_bw:
            # 资源充足，将路径状态信息保存在psb中
            psb = PSB(pathMsg.lsp_id, hop, pre_iface)
            iface.psb[pathMsg.lsp_id] = psb
            return psb

    def creatRSB(resvMsg, hop, pre_iface, iface):
        # if resvMsg.dataSize < iface.ava_bw and iface.psb[resvMsg.lsp_id].prv_hop==hop:
        if resvMsg.dataSize < iface.ava_bw:
            # # 资源可用，将资源状态保存在rsb中，并为连接预留资源
            rsb = RSB(resvMsg.lsp_id, hop, resvMsg.dataSize, pre_iface)
            iface.rsb[resvMsg.lsp_id] = rsb
            Resource.reservation(iface, resvMsg)
            return rsb

# 资源管理
class Resource():

    def reservation(interface, resvMsg):
        # conn = Connection(resvMsg.src_ip, resvMsg.dst_ip, resvMsg.dataSize, resvMsg.route)
        # if interface.conn_insert(resvMsg.lsp_id, conn):         
        # 预留资源，可用带宽减少
        interface.ava_bw = interface.ava_bw - resvMsg.dataSize
        interface.use_bw = interface.use_bw + resvMsg.dataSize

    def release(interface, Msg):
        # if interface.conn_del(Msg.lsp_id):
        # 释放占用资源，可用带宽增加
        interface.ava_bw = interface.ava_bw + interface.connection[Msg.lsp_id].bandWidth
        interface.use_bw = interface.use_bw - interface.connection[Msg.lsp_id].bandWidth






