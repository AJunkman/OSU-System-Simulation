import heapq
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
        dist = {src: 0}
        visited = {}
        previous = {}
        queue = []
        heapq.heappush(queue, (dist[src], src))     # 将参数二加入到queue中，形成堆队列
        while queue:
            distance, current = heapq.heappop(queue)
            if current in visited:
                continue
            visited[current] = True

            for edge in self.adj[current]:
                relaxed = dist[current] + edge.weight
                end = edge.end
                if end not in dist or relaxed < dist[end]:
                    previous[end] = current
                    dist[end] = relaxed
                    heapq.heappush(queue, (dist[end],end))
        return dist, previous
