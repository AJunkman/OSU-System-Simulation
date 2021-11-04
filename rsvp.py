


CREATE_CONN_INTERVAL = 30 # 30 seconds

class PathMsg:
    
    def __init__(self, src_ip, dst_ip, dataSize):
        self.msg_type = '0x01'
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.tos = None
        self.dataSize = dataSize
        self.route = None

class PathResvMsg:

    def __init__(self, src_ip, dst_ip, dataSize):
        self.msg_type = '0x02'
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.dataSize = dataSize
        self.route = None

class RouteObject():

    def __init__(self, src_ip, dst_ip, path):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.path = path

    def set_shortest_path(self, path):
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

class Connection():

    def __init__(self, src_ip, dst_ip, bandWidth, route):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.bandWidth = bandWidth
        self.path = route

# 资源管理
class Resource():

    def reservation(interface, pathResvMsg):
        conn = Connection(pathResvMsg.src_ip, pathResvMsg.dst_ip, pathResvMsg.dataSize, pathResvMsg.route)
        # 生成一个可表示该连接的唯一Key值，目前用各属性拼接起来方法标识，后续可考虑更好的方法
        connKey = pathResvMsg.src_ip + pathResvMsg.dst_ip + str(pathResvMsg.dataSize)
        interface.connection[connKey] = conn
        # 预留资源，可用带宽减少
        interface.rsv_bw = interface.rsv_bw - pathResvMsg.dataSize
        # 不可用带宽增加
        interface.unrsv_bw = interface.unrsv_bw + pathResvMsg.dataSize
        # 端口创建的连接数增加
        interface.connNum += 1

    def release(interface, Msg):
        connKey = Msg.src_ip + Msg.dst_ip + str(Msg.dataSize)
        interface.connection.pop(connKey)
        # 释放占用资源，可用带宽增加
        interface.rsv_bw = interface.rsv_bw + Msg.dataSize
        # 不可用带宽减少
        interface.unrsv_bw = interface.unrsv_bw - Msg.dataSize




