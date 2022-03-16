import asyncio
import threading
import websockets


class ConnectionMsg:
    def __init__(self, client_send_type,uuid, src_ip, dst_ip,
                 bandwidth, path, real_bw):
        self.client_send_type = client_send_type      # 两种触发场景：（1）新增业务、（2）流量模拟
        self.uuid = uuid 
        self.src_ip = src_ip             # 源地址
        self.dst_ip = dst_ip             # 目的地址
        self.bandwidth = bandwidth       # 业务占用带宽大小
        self.path = path
        self.real_bw = real_bw


    
# 1、发送数据包
async def send_msg(websocket, client_send_type, key, packet):
    # 1-1  重新封装包
    client_send_type = client_send_type
    uuid = key
    src_ip = packet.src_ip
    dst_ip = packet.dst_ip
    bandwidth = packet.connection_bandwidth
    path = packet.path
    real_bw = packet.bandwidth

    # 1-2  转字符串-编码
    packet = ConnectionMsg(client_send_type,uuid, src_ip, dst_ip,
                           bandwidth, path, real_bw)
    packet = str(packet.__dict__)               #对象转字符串

    # 1-3  发送数据 
    if client_send_type == 1:
        print(f"Type{client_send_type}  【仿真系统---创建业务】: 创建业务成功！！！！！ ") 
        await websocket.send(packet.encode())   #字符串编码再发送       
    if client_send_type == 2:
        print(f"\nType{client_send_type}  【仿真系统---业务】: 实时流量/带宽调整！！！！！ ")
        print(f"       uuid：{uuid}， 带宽：{bandwidth}， 真实流量：{real_bw}") 
        await websocket.send(packet.encode())   #字符串编码再发送
        # await asyncio.sleep(0.5)
    else:
        pass
    




# 2、发送数据包主逻辑
async def ConServer_recv_logic(client_send_type, key, packet):
    async with websockets.connect('ws://localhost:10000') as websocket:
        await send_msg(websocket, client_send_type, key, packet)


def main(client_send_type, key, packet):
    threading.Thread(
          target = asyncio.run,
          args = (ConServer_recv_logic(client_send_type, key, packet),)
          ).start()

