


class PathMsg:
    def __init__(self, src_ip, dst_ip, dataSize):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.tos = None
        self.dataSize = dataSize
        self.route = None

class PathResvMsg:
    def __init__(self, src_ip, dst_ip, dataSize):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.dataSize = dataSize
        self.route = None

#  rsvp协议里面应该有一个数据库来保存路径状态信息的
# class Database(dict):
#     def insert(self, lsa):
        
