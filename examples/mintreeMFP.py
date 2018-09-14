# _*_ coding: utf-8 _*_
from pyscipopt import Model, Conshdlr, quicksum , SCIP_RESULT, SCIP_PRESOLTIMING, SCIP_PROPTIMING, SCIP_PARAMSETTING, SCIP_PARAMEMPHASIS
from pyscipopt.scip import Expr, ExprCons, Term
import networkx as nx             #导入networkx包
from networkx.algorithms.flow import shortest_augmenting_path
import re
import numpy as np
import sys
from collections import OrderedDict

"""
2018-3-20
因为ndnSIM中实现的多条路径没有实现流浪的split，只简单复制和Flooding一样的转发，而现在编写的SCIP采用的是randomized
Rounding将traffic split到多条路径中，所以比较是不公平的。为了公平比较，都采用多条路径传输不一样的内容。
目前认为简单的做法是在Python中重写多路径
2017-7-26
reference to mfc from PySCIPOpt/examples/finished/atsp.py
The most complex problem based on node flow conservation is Maximum Concurrent Multicommodity Flow Problem (MCFP). I extended the model of MCFP for solving Steiner Tree
the detail see my latex document. 
the if there are only the "C" type Vars, Conshdlr consenfolp don't be called
"""

EPS = 1.e-6
manualAssign=False

def mintreeMFP(n,e,d):
    """
    mintreeMFP: min Cost Tree based on Flow Conservation 
    Parameters:
        - n: number of nodes
        - e[i,j]['cap','cost']: edges of graph, 'cap': capacity of edge, 'cost': cost for traversing edge (i,j)
        - d[i,j]: demande(data) from node i to j
    Returns a model, ready to be solved.
    """
    print("\n========min Cost Tree based on Flow Conservation======")
    
    model=Model("mintreeMFP")
    x,f,z={},{},{}   # flow variable 
    """
    In our model, f[i,j] is the sum of flow on edge, if f[i,j]>0 then z[i,j]=1 else z[i,j]=0, such that get minTree
    In order to express the logical constraint, define a Big M, and z is Binary, 
    z[i,j]>=f[i,j]/M (gurantee f/M <1) and z[i,j]<=f[i,j]*M (gurantee f[i,j]*M >1)
    """
    M=100000000
    for (i,j) in e.keys():
        f[i,j]=model.addVar(ub=1000000,lb=0,vtype="C",name="f[%s,%s]"%(i,j))
        z[i,j]=model.addVar(ub=1,lb=0,vtype="B",name="z[%s,%s]"%(i,j))
        for (s,t) in d.keys():
            x[i,j,s,t]=model.addVar(ub=1000000,lb=0,vtype="C",name="x[%s,%s,%s,%s]"%(i,j,s,t))
    # node flow conservation
    for (s,t) in d.keys():
        for j in n.keys() :
            # for destination node
            if j==t:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == d[s,t], "DesNode(%s)"%j)
            # for source node
            elif j==s:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == -d[s,t], "SourceNode(%s)"%j)
            else:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == 0, "SourceNode(%s)"%j)
    # constrains for edge capacity, take into consideration of tree optimization, using variable f
    for (i,j) in e.keys():
        f[i,j]=quicksum(x[i,j,s,t] for (s,t) in d.keys())
        model.addCons(f[i,j]<=e[i,j]['cap'],'edge(%s,%s)'%(i,j))
        # logical constraint
        model.addCons(M*z[i,j]>=f[i,j])
        model.addCons(z[i,j]<=f[i,j]*M)

    model.data = x,f
    
    #model.setObjective(quicksum(f[i,j]*e[i,j]['cost'] for (i,j) in e.keys()), "minimize")
    model.setObjective(quicksum(z[i,j] for (i,j) in e.keys()), "minimize")
    return model
            
def maxConcurrentMFP(n,e,d):
    """
    maxConcurrentMFP: max concurrent multi-commodity flow Problem
    Parameters:
        - n: number of nodes
        - e[i,j]['cap','cost']: edges of graph, 'cap': capacity of edge, 'cost': cost for traversing edge (i,j)
        - d[i,j]: demande from node i to j
    Returns a model, ready to be solved.
    """
    print("\n========concurrent multi-commodity flow Problem======")
    model=Model("maxConcurrentMFP")
    x={}  # flow variable 
    lamb=model.addVar(ub=1000000,lb=1.0,vtype="C",name="lamb")
    for (i,j) in e.keys():        
        for (s,t) in d.keys():
            x[i,j,s,t]=model.addVar(ub=1000000,lb=0.0,vtype="I",name="x[%s,%s,%s,%s]"%(i,j,s,t))
    # node flow conservation
    for (s,t) in d.keys():
        for j in n.keys():
            # for destination node
            if j==t:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == d[s,t]*lamb, "DesNode(%s)"%j)
            # for source node
            elif j==s:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == -d[s,t]*lamb, "SourceNode(%s)"%j)
            else:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == 0, "SourceNode(%s)"%j)
    # constrains for edge capacity, take into consideration of tree optimization, using variable f
    for (i,j) in e.keys():
        model.addCons(quicksum(x[i,j,s,t] for (s,t) in d.keys())<=e[i,j]['cap'],'edge(%s,%s)'%(i,j))    
    model.data = x
    
    model.setObjective(lamb, "maximize")
    return model
def maxConcurrentFlowMinCostMFP(n,e,d):
    """
    maxConcurrentMFP: max concurrent multi-commodity flow and min Cost Problem
    2018-3-27 如果目标函数中没有加入最小代价，在Mac和Ubuntu下的计算结果都不一样，显然同样的lamb下有多中路由方式。而且也可以去除环路
    Parameters:
        - n: number of nodes
        - e[i,j]['cap','cost']: edges of graph, 'cap': capacity of edge, 'cost': cost for traversing edge (i,j)
        - d[i,j]: demande from node i to j
    Returns a model, ready to be solved.
    """
    print("\n========concurrent multi-commodity flow Problem======")
    model=Model("maxConcurrentMFP")
    x={}  # flow variable 
    lamb=model.addVar(ub=1000000,lb=1.0,vtype="C",name="lamb")
    for (i,j) in e.keys():        
        for (s,t) in d.keys():
            x[i,j,s,t]=model.addVar(ub=1000000,lb=0.0,vtype="I",name="x[%s,%s,%s,%s]"%(i,j,s,t))
    # node flow conservation
    for (s,t) in d.keys():
        for j in n.keys():
            # for destination node
            if j==t:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == d[s,t]*lamb, "DesNode(%s)"%j)
            # for source node
            elif j==s:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == -d[s,t]*lamb, "SourceNode(%s)"%j)
            else:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == 0, "SourceNode(%s)"%j)
    # constrains for edge capacity, take into consideration of tree optimization, using variable f
    for (i,j) in e.keys():
        model.addCons(quicksum(x[i,j,s,t] for (s,t) in d.keys())<=e[i,j]['cap'],'edge(%s,%s)'%(i,j))    
    model.data =lamb, x
    model.setObjective(lamb-0.0001*quicksum(quicksum(x[i,j,s,t] for (s,t) in d.keys()) for (i,j) in e.keys()), "maximize")
    #model.setObjective(lamb-(quicksum(0.00000001*quicksum(x[i,j,s,t] for (s,t) in d.keys()) for (i,j) in e.keys())), "maximize")
    return model
def MaxMFP(n,e,d):
    """
    MaxMFP: Max sum multi-commodity flow Problem
    Parameters:
        - n: number of nodes
        - e[i,j]['cap','cost']: edges of graph, 'cap': capacity of edge, 'cost': cost for traversing edge (i,j)
        - d[i,j]: demande from node i to j
    Returns a model, ready to be solved.
    """
    print("\n========Max multi-commodity flow Problem======")
    model=Model("MaxMFP")
    x,vard={},{}  # flow variable
    for (s,t) in d.keys():
        vard[s,t]=model.addVar(ub=1000000,lb=0.0,vtype="C",name="vard[%s,%s]"%(s,t)) 
    for (i,j) in e.keys():        
        for (s,t) in d.keys():
            x[i,j,s,t]=model.addVar(ub=1000000,lb=0.0,vtype="C",name="x[%s,%s,%s,%s]"%(i,j,s,t))
    # node flow conservation
    for (s,t) in d.keys():
        for j in n.keys():
            # for destination node
            if j==t:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == vard[s,t], "DesNode(%s)"%j)
            # for source node
            elif j==s:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == -vard[s,t], "SourceNode(%s)"%j)
            else:
                model.addCons(quicksum(x[i,j,s,t] for i in n.keys() if (i,j) in e.keys()) - 
                              quicksum(x[j,i,s,t] for i in n.keys() if (j,i) in e.keys()) == 0, "SourceNode(%s)"%j)
    # constrains for edge capacity, take into consideration of tree optimization, using variable f
    for (i,j) in e.keys():
        model.addCons(quicksum(x[i,j,s,t] for (s,t) in d.keys())<=e[i,j]['cap'],'edge(%s,%s)'%(i,j))    
    model.data = x,vard
    
    model.setObjective(quicksum(vard[s,t] for (s,t) in d.keys()), "maximize")
    return model

def readTopology(filename,cap=None): 
    # ZhangYu 2018-1-28使用SCIP计算时，发现这里没有设置是否无向图， 而Matlab有这个选项
    isUndirectedGraph=True   
    mark=["router\n","link\n"]
    try:
        filehandle = open(sys.path[0]+filename,'r')
    except:
        print("Could not open file " + sys.path[0]+filename)
        quit()
    filelines=filehandle.readlines()
    markPos=[]
    for i in range(len(mark)):
        markPos.append(filelines.index(mark[i]))
    # read edges
    edge,node={},{}
    for aline in filelines[markPos[1]+1:]:
        if str(aline).startswith('#') | str(aline).startswith(' ') | str(aline).startswith('\n'):
            continue
        else:
            alineArray=str(aline).split()
            if cap is None:
                # 这里允许节点是诸如 UCLA-A这样的名字
                edge[str(alineArray[0]),
                     str(alineArray[1])]={'cap':re.findall(
                         "\d+",str(alineArray[2]))[0],'cost':re.findall("\d+",str(alineArray[3]))[0]}
            else:
                edge[str(alineArray[0]),
                     str(alineArray[1])]={'cap':cap,'cost':re.findall("\d+",str(alineArray[3]))[0]}
            if isUndirectedGraph:
                edge[str(alineArray[1]),str(alineArray[0])]=edge[str(alineArray[0]),str(alineArray[1])]
                
    # read nodes. G can be get only by edges, we read nodes here because we need the nodes coordinate for drawing graph
    for aline in filelines[markPos[0]+1:markPos[1]]:
        if str(aline).startswith('#') | str(aline).startswith(' ') | str(aline).startswith('\n') | str(aline).startswith('\r'):
            continue
        else:
            alineArray=str(aline).split()
            node[str(alineArray[0])]=np.array(
                [int(re.findall("\d+", str(alineArray[3]))[0]),int(re.findall("\d+", str(alineArray[2]))[0])])
            #pos['1']=np.array([4,5])
            
    if __name__=="__main__":
        import matplotlib.pyplot as plt
        G=nx.DiGraph()
        G.add_nodes_from(node)
        G.add_edges_from(edge.keys())    
        
        # Draw nodes
        nx.draw_networkx_nodes(G, node,node_size=290, node_color='orange')
        nx.draw_networkx_labels(G, node,font_size=13, font_family='sans-serif')
        
        # Draw edges
        nx.draw_networkx_edges(G,node, arrows=True,width=0.5, edge_color='g')
        
        # Draw edge labels
        #edge_labels = dict([((u, v), d['label'])
        #                    for u, v, d in G.edges(data=True)])
        #nx.draw_networkx_edge_labels(G, pos,edge_labels=edge_labels)
        
        plt.axis('off')  # 是否打开坐标系on/off
        #plt.savefig("lyy_graph.eps", format='eps')  # save as eps
        #plt.ion()
        plt.pause(5)
        #plt.close()
    
    return edge,node

def caculatemaxConcurrentMFPRoute(filename,consumerList,producerList):
    # Traffic Matrix d[1,5] represent interest from node 1 to node 5
    e,n=readTopology(filename)
    d=OrderedDict()
    for i in range(len(consumerList)):
        d[consumerList[i],producerList[i]]=1
    #model=maxConcurrentMFP(n, e, d)
    model=maxConcurrentFlowMinCostMFP(n,e,d)
    model.hideOutput()
    model.optimize()
    vlamb,x = model.data
    lamb=model.getVal(vlamb)
    print "  --------variant lambda is:",lamb
    print "  --------obj is: ",model.getObjVal()
    '''
    for v in model.getVars():
        if model.getVal(v)>EPS:
            print('{0}={1}'.format(v.name,model.getVal(v)))
    for (s,t) in d.keys():
        if(d[s,t]>EPS):
            for (i,j) in e.keys():
                if(model.getVal(x[i,j,s,t])>EPS):
                    print('--------x[{0},{1},{2},{3}]={4}'.format(i,j,s,t,model.getVal(x[i,j,s,t])))
    '''
        
    routeList=[]
    probability=1.0
    rG=nx.DiGraph()
    for (s,t) in d.keys():
        # 2018-3-26，为了去掉解中的路由环路
        rG.clear()
        for (i,j) in e.keys():
            if(model.getVal(x[i,j,s,t])>EPS):
                rG.add_edge(i,j,capacity=model.getVal(x[i,j,s,t]))
        R = shortest_augmenting_path(rG, s, t)
        if R.graph['flow_value']+EPS<lamb:
            print "2018-3-26 全局解的最大流没有达到lambda"
            print "最大流：{0}".format(R.graph['flow_value'])
            continue
        ''' ******traffic split 实现方法*********
        因为即使没有环路，也不能保证一种商品流的多条路径没有公共节点，当有公共节点时，例如节点 Node5流入有两条边共200
        流出有2条（边的容量是100）。在转发时，默认的转发策略ncc和Flooding一样，向所有端口复制，导致每条边都有200，
        由于超出带宽，会被迫丢包，但是丢包不能保证公平，所以仿真结果和预期差别较大
        为避免上述情况，这里是针对源节点，分流概率为 流量/lamb，对于中继节点，概率=流量/流入该节点的总和
        当使用概率转发时，可以split流量，和cpp中的多路径不一样
        '''
        # 计算节点的流入流量总和
        inFlow={}
        for aNode in R.nodes:
            inFlow[aNode]=0
            for (eStart,aNode) in rG.in_edges(aNode):
                inFlow[aNode]=inFlow[aNode]+R[eStart][aNode]['flow']
        for (i,j) in rG.edges :
            if(R[i][j]['flow']>EPS):
                if (i==s):
                    totalInFlow=lamb
                else:
                    totalInFlow=inFlow[i]
                    if (totalInFlow==0):
                        print ("i={0},j={1},s={2},t={3},flow={4},inFlow={5}".format(i,j,s,t,R[i][j]['flow'],inFlow[i]))
                r={'edgeStart':i,'edgeEnd':j,'prefix':"/"+t,'cost':1, 'probability':
                   (R[i][j]['flow']/totalInFlow)}
                routeList.append(r)
                print r
    return lamb,routeList

def caculatenoCommLinkPairFirst(filename,consumerList,producerList):
    """
    GNOMP: caculate no comm link pair first multipath routing
    Parameters:
        - filename: topology file name
        - consumerList: consumer list, need the ascend order
        - producerList: 
    Returns maxThroughput, lambda, routeList
    """
    if __name__=="__main__":
       print("\n========caculate no common link multipath pair first======")
    e,n=readTopology(filename)
    edgecapacity=0;
    d=OrderedDict()
    for i in range(len(consumerList)):
        d[consumerList[i],producerList[i]]=1
    G=nx.DiGraph()
    G.add_nodes_from(n)
    #G.add_edges_from(e,weight=2)
    for (i,j) in e.keys():
        G.add_edge(i,j,weight=e[i,j]['cost'])
        edgecapacity=int(e[i,j]['cap']) #这里认为网络容量是均匀的，所以用了偷懒的做法
        #print(G[i][j]['weight'])
        #print(G.edges[i,j]['cap'])
    pathsList=OrderedDict()
    hasPath=True
    while(hasPath):
        hasPath=False
        for (s,t) in d: 
            # 很奇怪，下面写'weight'竟然不识别报错
            try:
                p=nx.shortest_path(G, s, t, 'cost')
            except:
                continue
            if(len(p)>1):
                hasPath=True
                if(not(pathsList.has_key((s,t)))):
                    pathsList[s,t]=[]
                pathsList[s,t].append(p)
                print ('  ----source:{0}, sink:{1}, path:{2}'.format(s,t,p))
                for i in range(0,len(p)-1):
                    G.remove_edge(p[i], p[i+1])
            else:
                continue
    routeList=[]
    MaxThroughput=0
    lamb=np.inf
    rG=nx.DiGraph()
    for (s,t) in pathsList.keys():
        #print("source:{0}  sink:{1}   total paths:{2}  ".format(s,t,len(pathsList[s,t])))
        MaxThroughput=MaxThroughput+(edgecapacity*len(pathsList[s,t]))
        if (edgecapacity*len(pathsList[s,t])<lamb):
            lamb=edgecapacity*len(pathsList[s,t])
        #得到每对节点对的流量图
        rG.clear()
        #probability=1.0/len(pathsList[s,t])
        for i in range(len(pathsList[s,t])):
            p=pathsList[s,t][i]
            for j in range(len(p)-1):
                rG.add_edge(p[j], p[j+1],capacity=e[p[j],p[j+1]]['cap'])
        #计算节点的流量总和
        inFlow={}
        for aNode in rG.nodes:
            inFlow[aNode]=0
            for (eStart,aNode) in rG.in_edges(aNode):
                inFlow[aNode]=inFlow[aNode]+float(rG[eStart][aNode]['capacity'])
        #生成路由表
        for (i,j) in rG.edges :
            if (i==s):
                totalInFlow=edgecapacity*len(pathsList[s,t])
            else:
                totalInFlow=inFlow[i]
            r={'edgeStart':i,'edgeEnd':j,'prefix':"/"+t,'cost':1, 'probability':
               (float(rG[i][j]['capacity'])/totalInFlow)}
            routeList.append(r)        
                #print r

    
    # 如果某对s-t没有路径，上面的求lamb只是找到了存在的路径中的最小lamb，对s-t流量为0的没处理，因此补上下面的语句
    if(len(pathsList.keys())<len(d)):
        lamb=0

    return MaxThroughput,lamb,routeList

def caculateKshortest(filename,consumerList,producerList,K):
    """
    K-shortest: caculate K-shortest multipath routing, find all K-shortest path for a pair then another pair
    Parameters:
        - filename: topology file name
        - consumerList: consumer list, need the ascend order
        - producerList: 
        - K: K=1 is BestRoute, K=np.inf is Flooding
    Returns maxThroughput, lambda, routeList
    """
    if __name__=="__main__":
       print("\n========caculate K-shortest Path======")
    e,n=readTopology(filename)
    edgecapacity=0;
    d=OrderedDict()
    for i in range(len(consumerList)):
        d[consumerList[i],producerList[i]]=1
    G=nx.DiGraph()
    G.add_nodes_from(n)
    #G.add_edges_from(e,weight=2)
    for (i,j) in e.keys():
        G.add_edge(i,j,weight=e[i,j]['cost'])
        edgecapacity=int(e[i,j]['cap']) #这里认为网络容量是均匀的，所以用了偷懒的做法
        #print(G[i][j]['weight'])
        #print(G.edges[i,j]['cap'])
    pathsList=OrderedDict()
    for (s,t) in d: 
        for k in range(K):
            # 很奇怪，下面写'weight'竟然不识别报错
            try:
                p=nx.shortest_path(G, s, t, 'cost')
            except:
                break
            if(len(p)>1):
                if(not(pathsList.has_key((s,t)))):
                    pathsList[s,t]=[]
                pathsList[s,t].append(p)
                print ('  ----source:{0}, sink:{1}, path:{2}'.format(s,t,p))
                for i in range(0,len(p)-1):
                    G.remove_edge(p[i], p[i+1])
            else:
                break
    routeList=[]
    MaxThroughput=0
    lamb=np.inf
    rG=nx.DiGraph()
    for (s,t) in pathsList.keys():
        #print("source:{0}  sink:{1}   total paths:{2}  ".format(s,t,len(pathsList[s,t])))
        MaxThroughput=MaxThroughput+(edgecapacity*len(pathsList[s,t]))
        if (edgecapacity*len(pathsList[s,t])<lamb):
            lamb=edgecapacity*len(pathsList[s,t])
        #得到每对节点对的流量图
        rG.clear()
        #probability=1.0/len(pathsList[s,t])
        for i in range(len(pathsList[s,t])):
            p=pathsList[s,t][i]
            for j in range(len(p)-1):
                rG.add_edge(p[j], p[j+1],capacity=e[p[j],p[j+1]]['cap'])
        #计算节点的流量总和
        inFlow={}
        for aNode in rG.nodes:
            inFlow[aNode]=0
            for (eStart,aNode) in rG.in_edges(aNode):
                inFlow[aNode]=inFlow[aNode]+float(rG[eStart][aNode]['capacity'])
        #生成路由表
        for (i,j) in rG.edges :
            if (i==s):
                totalInFlow=edgecapacity*len(pathsList[s,t])
            else:
                totalInFlow=inFlow[i]
            r={'edgeStart':i,'edgeEnd':j,'prefix':"/"+t,'cost':1, 'probability':
               (float(rG[i][j]['capacity'])/totalInFlow)}
            routeList.append(r)        
                #print r
    # 如果某对s-t没有路径，上面的求lamb只是找到了存在的路径中的最小lamb，对s-t流量为0的没处理，因此补上下面的语句
    if(len(pathsList.keys())<len(d)):
        lamb=0

    return MaxThroughput,lamb,routeList

def caculateKshortestwithRestore(filename,consumerList,producerList,K):
    """
    restroe original graph after each K-shortest: caculate K-shortest multipath routing, 
    find all K-shortest path for a pair then restore graph to orighinal for another pair
    Parameters:
        - filename: topology file name
        - consumerList: consumer list, need the ascend order
        - producerList: 
        - K: K=1 is BestRoute, K=np.inf is Flooding
    Returns maxThroughput, lambda, routeList
    """
    if __name__=="__main__":
       print("\n========caculate K-shortest Path with Restore======")
    e,n=readTopology(filename)
    edgecapacity=0;
    d=OrderedDict()
    for i in range(len(consumerList)):
        d[consumerList[i],producerList[i]]=1
    G=nx.DiGraph()
    G.add_nodes_from(n)
    #G.add_edges_from(e,weight=2)
    for (i,j) in e.keys():
        G.add_edge(i,j,weight=e[i,j]['cost'])
        edgecapacity=int(e[i,j]['cap']) #这里认为网络容量是均匀的，所以用了偷懒的做法
        #print(G[i][j]['weight'])
        #print(G.edges[i,j]['cap'])
    if nx.__version__=="2.1":
        originalG=G.copy(as_view=False)
    else:
        originalG=G.copy(with_data=True)
    pathsList=OrderedDict()
    for (s,t) in d: 
        for k in range(K):
            # 很奇怪，下面写'weight'竟然不识别报错
            try:
                p=nx.shortest_path(G, s, t, 'cost')
            except:
                break
            if(len(p)>1):
                if(not(pathsList.has_key((s,t)))):
                    pathsList[s,t]=[]
                pathsList[s,t].append(p)
                print ('  ----source:{0}, sink:{1}, path:{2}'.format(s,t,p))
                for i in range(0,len(p)-1):
                    G.remove_edge(p[i], p[i+1])
            else:
                break
        if nx.__version__=="2.1":
            G=originalG.copy(as_view=False)
        else:
            G=originalG.copy(with_data=True)
    routeList=[]
    MaxThroughput=0
    lamb=np.inf
    rG=nx.DiGraph()
    for (s,t) in pathsList.keys():
        #print("source:{0}  sink:{1}   total paths:{2}  ".format(s,t,len(pathsList[s,t])))
        MaxThroughput=MaxThroughput+(edgecapacity*len(pathsList[s,t]))
        if (edgecapacity*len(pathsList[s,t])<lamb):
            lamb=edgecapacity*len(pathsList[s,t])
        #得到每对节点对的流量图
        rG.clear()
        #probability=1.0/len(pathsList[s,t])
        for i in range(len(pathsList[s,t])):
            p=pathsList[s,t][i]
            for j in range(len(p)-1):
                rG.add_edge(p[j], p[j+1],capacity=e[p[j],p[j+1]]['cap'])
        #计算节点的流量总和
        inFlow={}
        for aNode in rG.nodes:
            inFlow[aNode]=0
            for (eStart,aNode) in rG.in_edges(aNode):
                inFlow[aNode]=inFlow[aNode]+float(rG[eStart][aNode]['capacity'])
        #生成路由表
        for (i,j) in rG.edges :
            if (i==s):
                totalInFlow=edgecapacity*len(pathsList[s,t])
            else:
                totalInFlow=inFlow[i]
            r={'edgeStart':i,'edgeEnd':j,'prefix':"/"+t,'cost':1, 'probability':
               (float(rG[i][j]['capacity'])/totalInFlow)}
            routeList.append(r)        
            #print r
    # 如果某对s-t没有路径，上面的求lamb只是找到了存在的路径中的最小lamb，对s-t流量为0的没处理，因此补上下面的语句
    if(len(pathsList.keys())<len(d)):
        lamb=0
    return MaxThroughput,lamb,routeList

def caculateMaxMFPRoute(filename,consumerList,producerList):
    # Traffic Matrix d[1,5] represent interest from node 1 to node 5
    e,n=readTopology(filename)
    d={}
    for i in range(len(consumerList)):
        d[consumerList[i],producerList[i]]=1
    model=maxConcurrentMFP(n, e, d)
    model.hideOutput()
    model.optimize()
    lamb=model.getObjVal()
    print "  --------variant lambda is:",lamb 
    for v in model.getVars():
        if model.getVal(v)>EPS:
            print('{0}={1}'.format(v.name,model.getVal(v)))
            
    x = model.data
    routeList=[]
    for (s,t) in d.keys():
        for (i,j) in e.keys() :
            if(model.getVal(x[i,j,s,t])>EPS):
                d={'edgeStart':i,'prefix':"/"+t,'edgeEnd':j}
                routeList.append(d)
                #print('edgeUsed({0},{1})={2}',format(i,j,z[i,j]))
    return routeList
def TenNodesTopology():
    isUndirectedGraph=True
    n=dict()
    for i in range(1,10):
        n[i]=1
    e,d={},{}
    e[1,2]={'cap':10,'cost':2}
    e[1,3]={'cap':10,'cost':2}
    e[1,4]={'cap':10,'cost':2}
    e[1,5]={'cap':10,'cost':2}
    e[1,6]={'cap':10,'cost':2}
    e[2,3]={'cap':10,'cost':2}
    e[2,6]={'cap':10,'cost':2}
    e[3,4]={'cap':10,'cost':2}
    e[3,6]={'cap':10,'cost':2}
    e[4,5]={'cap':10,'cost':2}
    e[4,6]={'cap':10,'cost':2}
    e[5,6]={'cap':10,'cost':2}
    e[7,1]={'cap':10,'cost':2}
    e[7,3]={'cap':10,'cost':2}
    e[8,1]={'cap':10,'cost':2}
    e[8,5]={'cap':10,'cost':2}
    e[9,2]={'cap':10,'cost':2}
    e[9,3]={'cap':10,'cost':2}
    e[9,4]={'cap':10,'cost':2}
    e[9,5]={'cap':10,'cost':2}
    e[10,9]={'cap':10,'cost':2}
    e[10,6]={'cap':10,'cost':2}
    e[10,1]={'cap':10,'cost':2}    
    d[1,3]=1
    d[1,5]=1
    d[9,6]=1
    d[7,1]=1
    #d[2,6]=1
    #d[4,6]=1
    if isUndirectedGraph:
        for (i,j) in e.keys():
            e[j,i]=e[i,j]
    return n,e,d
def SixNodesTopology():
    n=6
    e,d={},{}
    e[0,1]={'cap':10,'cost':2}
    e[0,2]={'cap':10,'cost':2}
    e[0,5]={'cap':10,'cost':2}
    e[5,3]={'cap':10,'cost':2}
    e[1,4]={'cap':10,'cost':2}
    e[2,4]={'cap':10,'cost':2}
    e[2,3]={'cap':10,'cost':2}
    # Traffic Matrix d[1,5] represent data from node 1 to node 5
    d['Node0','Node4']=1
    #d['Node0','Node3']=1

'''
为了能支持更一般化的节点名字，所以在 readTopology中没有提取节点的数值部分。但是为了和Matlab中节点的顺序一致
以便于能自动产生一样的Traffic，所以这里必须按照数值部分排序，Node11不能自动排在Node2之前，所以需要提取数字
'''
def customedSort(nodeName):
    return int(re.findall("\d+", nodeName)[0])

if __name__ == "__main__":
    filename="5nodes-Debug.txt"    
    #filename="topo-for-CompareMultiPath.txt"
    #filename="100Nodes-5.txt"
    e,n=readTopology("/topologies/"+filename)
    manualAssign=False
    consumerList=[]
    producerList=[]
    if(manualAssign):
        consumerList=['Node0']
        producerList=['Node3']
        #consumerList=['Node0','Node1','Node2','Node3','Node4','Node5','Node6','Node7','Node8','Node9','Node10','Node11','Node12','Node13']
        #producerList=['Node14','Node15','Node16','Node17','Node18','Node19','Node20','Node21','Node22','Node23','Node24','Node25','Node26','Node27']
        
        '''
        d['Node4','Node0']=1
        d['Node3','Node0']=1
        '''
    else:
        K=int(np.floor(len(n)/2))
        nodesName=n.keys()
        nodesName.sort(key=customedSort)
        for k in range(K):
            consumerList.append(nodesName[k])
            producerList.append(nodesName[k+K])
    d=OrderedDict()
    for i in range(len(consumerList)):
        d[consumerList[i],producerList[i]]=1
    '''
    model=mintreeMFP(n,e,d)
    model.hideOutput()
    model.optimize()
    maxFlow = model.getObjVal()
    print "  ------minTreeMFP Optimal value: ",maxFlow

    for v in model.getVars():
        if model.getVal(v)>EPS:
            print('{0}={1}'.format(v.name,model.getVal(v)))
    
    x,f = model.data
    edgeflow={}
    for (i,j) in e.keys() :
        edgeflow[i,j]=0

        for (s,t) in d.keys():
            edgeflow[i,j]=edgeflow[i,j]+ model.getVal(x[i,j,s,t])
        if (edgeflow[i,j]>EPS):
            print('edgeflow({0},{1})={2}'.format(i,j,edgeflow[i,j]))
            #print('edgeUsed({0},{1})={2}',format(i,j,z[i,j]))
    '''
        
    fileName="/topologies/"+filename
    lamb,routeList=caculatemaxConcurrentMFPRoute(fileName,consumerList,producerList)
    print "  --------maxConcurrentMFP variant lambda is:",lamb             
    '''
    model=MaxMFP(n, e, d)
    model.hideOutput()
    model.optimize()
    maxFlow=model.getObjVal()
    print "  --------MaxMFP Optimal value: ",maxFlow
    
    # show the flow detail if nodes is not too many
    if len(n)<50:
        x,vard=model.data
        for (s,t) in d.keys():
            if(d[s,t]>EPS):
                print('Flow({0},{1})={2}'.format(s,t,model.getVal(vard[s,t])))
                for (i,j) in e.keys():
                    if(model.getVal(x[i,j,s,t])>EPS):
                        print('--------x[{0},{1},{2},{3}]={4}'.format(i,j,s,t,model.getVal(x[i,j,s,t])))
    '''
    
    maxThroughput,lamb,routeList=caculatenoCommLinkPairFirst(fileName, consumerList, producerList)
    print "  --------NoCommLinkMultipathPairFirst lambda value: ",lamb
    print "  --------NoCommLinkMultipathPairFirst maxThroughput value: ",maxThroughput
    maxThroughput,lamb,routeList=caculateKshortest(fileName, consumerList, producerList,10000)
    print "  --------Flooding lambda value: ",lamb
    print "  --------Flooding maxThroughput value: ",maxThroughput
    maxThroughput,lamb,routeList=caculateKshortest(fileName, consumerList, producerList,1)
    print "  --------BestRoute lambda value: ",lamb
    print "  --------BestRoute maxThroughput value: ",maxThroughput
    maxThroughput,lamb,routeList=caculateKshortest(fileName, consumerList, producerList,2)
    print "  --------K-shortest -2 lambda value: ",lamb
    print "  --------K-shortest -2 maxThroughput value: ",maxThroughput
    maxThroughput,lamb,routeList=caculateKshortest(fileName, consumerList, producerList,3)
    print "  --------K-shortest -3 lambda value: ",lamb
    print "  --------K-shortest -3 maxThroughput value: ",maxThroughput
    maxThroughput,lamb,routeList=caculateKshortestwithRestore(fileName, consumerList, producerList,3)
    print "  --------K-shortest with Restore -3 lambda value: ",lamb
    print "  --------K-shortest with Restore -3 maxThroughput value: ",maxThroughput
