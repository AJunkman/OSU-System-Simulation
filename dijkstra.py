import heapq
import pdb
from collections import defaultdict


class Edge(object):

    def __init__(self, start, end, weight):
        self.start = start
        self.end = end
        self.weight = weight

    # For heapq.
    def __cmp__(self, other):
        return cmp(self.weight, other.weight)


class Graph(object):

    def __init__(self):
        # The adjacency list.
        self.adj = defaultdict(list)

    def add_e(self, start, end, weight=0):
        self.adj[start].append(Edge(start, end, weight))

    def s_path(self, src):
        """
        返回从源和数组到每个顶点的距离，数组表示在索引 i 处，在访问节点 i 之前访问过的节点。
        形式 (dist, previous)。
        """
        dist = {src: 0}     # 去往各个目的地所需代价
        visited = {}        # 已遍历路由器
        previous = {}       # 去往各个目的地的下一跳路由器
        complete_route = {} # 记录去往各个节点的全路径，{'end': [path]}格式
        queue = []
        heapq.heappush(queue, (dist[src], src))     # 将(累计代价，目的地)加入到queue中，形成堆队列
        while queue:
            distance, current = heapq.heappop(queue)
            if current in visited:
                continue
            visited[current] = True

            for edge in self.adj[current]:
                relaxed = dist[current] + edge.weight
                end = edge.end
                if end not in complete_route or relaxed < dist[end]:
                    if end != src:
                        complete_route[end] = [current, end]
                        if current in complete_route:
                            complete_route[end] = complete_route[current] + complete_route[end][1:]
                if end not in dist or relaxed < dist[end]:
                    previous[end] = current
                    dist[end] = relaxed
                    heapq.heappush(queue, (dist[end], end))
        return dist, previous, complete_route


if __name__ == '__main__':
    g = Graph()
    nodes = ['r1', 'r2', 'r3', 'r4', 'r5', 'r6']
    path = {'r1': [('r2', 4), ('r4', 1), ('r5', 1)],
            'r2': [('r1', 1), ('r3', 1)],
            'r3': [('r2', 1), ('r4', 1), ('r6', 1)],
            'r4': [('r1', 1), ('r3', 1)],
            'r5': [('r1', 1)]}

    for rtr in path:
        for adj in path[rtr]:
            g.add_e(rtr, adj[0], adj[1])
    dist, prev, cr = g.s_path(nodes[0])
    print(cr)
    # print(dist, prev)

