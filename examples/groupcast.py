# _*_ coding: utf-8 _*_
from pyscipopt import Model, Conshdlr, quicksum , SCIP_RESULT, SCIP_PRESOLTIMING, SCIP_PROPTIMING, SCIP_PARAMSETTING, SCIP_PARAMEMPHASIS
from pyscipopt.scip import Expr, ExprCons, Term
import networkx as nx             #导入networkx包
import re
import numpy as np
import sys
import copy

EPS = 1.e-6


def readTopology(filename, cap=None):
    # ZhangYu 2018-1-28使用SCIP计算时，发现这里没有设置是否无向图， 而Matlab有这个选项
    isUndirectedGraph = False
    mark = ["router\n", "link\n"]
    try:
        filehandle = open(sys.path[0]+"/"+filename, 'r')
    except:
        print("Could not open file " + sys.path[0]+"/"+filename)
        quit()
    filelines = filehandle.readlines()
    markPos = []
    for i in range(len(mark)):
        markPos.append(filelines.index(mark[i]))
    # read edges
    edge, node = {}, {}
    for aline in filelines[markPos[1] + 1:]:
        if str(aline).startswith('#') | str(aline).startswith(' ') | str(aline).startswith('\n'):
            continue
        else:
            alineArray = str(aline).split()
            if cap is None:
                # 这里允许节点是诸如 UCLA-A这样的名字
                edge[str(alineArray[0]),
                     str(alineArray[1])] = {'cap': re.findall(
                    "\d+", str(alineArray[2]))[0], 'cost': re.findall("\d+", str(alineArray[3]))[0]}
            else:
                edge[str(alineArray[0]),
                     str(alineArray[1])] = {'cap': cap, 'cost': re.findall("\d+", str(alineArray[3]))[0]}
            if isUndirectedGraph:
                edge[str(alineArray[1]), str(alineArray[0])] = edge[str(alineArray[0]), str(alineArray[1])]

    # read nodes. G can be get only by edges, we read nodes here because we need the nodes coordinate for drawing graph
    for aline in filelines[markPos[0] + 1:markPos[1]]:
        if str(aline).startswith('#') | str(aline).startswith(' ') | str(aline).startswith('\n') | str(
                aline).startswith('\r'):
            continue
        else:
            alineArray = str(aline).split()
            node[str(alineArray[0])] = np.array(
                [int(re.findall("\d+", str(alineArray[3]))[0]), int(re.findall("\d+", str(alineArray[2]))[0])])
            # pos['1']=np.array([4,5])


    return edge, node


def maxConcurrentMFP(n, e, d, st):
    """
    maxConcurrentMFP: max concurrent multi-commodity flow Problem
    Parameters:
        - n: number of nodes
        - e[i,j]['cap','cost']: edges of graph, 'cap': capacity of edge, 'cost': cost for traversing edge (i,j)
        - d[i,j]: demande from node i to j
    Returns a model, ready to be solved.
    """
    print("\n========concurrent multi-commodity flow Problem======")

    model = Model("maxConcurrentMFP")
    x, m = {}, {}  # flow variable
    lamba = model.addVar(ub=1000000, lb=1.0, vtype="C", name="lamba")
    for (i, j) in e.keys():
        # f[i, j] = model.addVar(ub=100000000000, lb=0, vtype="I", name="f[%s,%s]" % (i, j))
        # z[i, j] = model.addVar(ub=1, lb=0, vtype="B", name="z[%s,%s]" % (i, j))
        for s in d.keys():
            # ture flow
            m[i, j, s] = model.addVar(ub=100000000000, lb=0, vtype='C', name="m[%s,%s,%s]" % (i, j, s))
            for t in st[s]:
                # presudo flow
                x[i, j, s, t] = model.addVar(ub=100000000, lb=0, vtype="C", name="x[%s,%s,%s,%s]" % (i, j, s, t))
                # model.addCons(x[i, j, s, t] <= e[i, j]['cap'], 'edges(%s, %s)' % (i, j))
        # f[i, j] = quicksum(x[i, j, s, t] for (s, t) in d.keys())
    # commodity flow conservation
    for (i, j) in e.keys():
        for s in st.keys():
            for t in st[s]:
                model.addCons(x[i, j, s, t] <= m[i, j, s], 'edges(%s, %s, %s)' % (i, j, s))
                # node flow conservation
                # for destination node
                if j == t:
                    model.addCons(quicksum(m[i, j, s] for i in n.keys() if (i, j) in e.keys()) -
                                  quicksum(m[j, i, s] for i in n.keys() if (j, i) in e.keys()) == lamba * d[s],
                                  "DesNode(%s)" % j)
                # for source node
                elif j == s:
                    model.addCons(quicksum(m[i, j, s] for i in n.keys() if (i, j) in e.keys()) -
                                  quicksum(m[j, i, s] for i in n.keys() if (j, i) in e.keys()) == -lamba * d[s],
                                  "SourceNode(%s)" % j)
                # for relay node
                else:
                    model.addCons(quicksum(x[i, j, s, t] for i in n.keys() if (i, j) in e.keys()) -
                                  quicksum(x[j, i, s, t] for i in n.keys() if (j, i) in e.keys()) == 0,
                                  "InterNode(%s)" % j)
    # constrains for edge capacity, take into consideration of tree optimization, using variable f
    for (i, j) in e.keys():
        # f[i, j] = quicksum(x[i, j, s, t] for (s, t) in d.keys())
        model.addCons(quicksum(m[i, j, s] for s in st.keys()) <= e[i, j]['cap'], 'edge(%s,%s)' % (i, j))
        # logical constraint
        # model.addCons(M * z[i, j] >= f[i, j])
        # model.addCons(z[i, j] <= f[i, j] * M)

    model.data = m

    # model.setObjective(quicksum(f[i,j]*e[i,j]['cost'] for (i,j) in e.keys()), "minimize")
    model.setObjective(lamba, "maximize")
    return model


def pmph(filename, src_set, tar_set):
    # Traffic Matrix d[1,5] represent interest from node 1 to node 5
    e, n = readTopology(filename)
    d = {}
    st = {}

    for s in range(len(src_set)):
        # d[src_set[s]] = 10
        for t in range(len(tar_set[s])):
            st[src_set[s]] = tar_set[s]
    d['Node29'] = 10
    d['Node28'] = 30
    model = maxConcurrentMFP(n, e, d, st)
    model.hideOutput()
    model.optimize()
    lamba = model.getObjVal()
    print "  ------------variant lambda is:", lamba

    for v in model.getVars():
        if model.getVal(v)>EPS:
            print('{0}={1}'.format(v.name, model.getVal(v)))

    m = model.data
    '''
    edgesUsed = {}
    for (i, j) in e.keys():
        totalTraffic = 0
        for (s, t) in d.keys():
            totalTraffic = totalTraffic + model.getVal(x[i, j, s, t])
        edgesUsed[i, j] = {'totalTraffic':totalTraffic}
    '''
    routeList = []
    for s in d.keys():
        for (i, j) in e.keys():
            if (model.getVal(m[i, j, s]) > EPS):
                r = {'edgeStart': j, 'edgeEnd': i, 'prefix': "/" + s, 'cost': 30}
                if r not in routeList:
                    routeList.append(r)

    return routeList


filename = "300Nodes-8.txt"
tar_set = [['Node7', 'Node3'], ['Node5', 'Node4']]
src_set = ['Node29', 'Node28']
r = pmph(filename, src_set, tar_set)
# print(r)
for i in r:
    print i
