# _*_ coding: utf-8 _*_
from pyscipopt import Model, Conshdlr, quicksum , SCIP_RESULT, SCIP_PRESOLTIMING, SCIP_PROPTIMING, SCIP_PARAMSETTING, SCIP_PARAMEMPHASIS
from pyscipopt.scip import Expr, ExprCons, Term
import networkx as nx             #导入networkx包
from networkx.algorithms.flow import shortest_augmenting_path
import re
import numpy as np
import mpmath as mp
from mpmath import mpf
import sys, time 
from collections import OrderedDict

"""
2018-6-10 编写高精度的Fleischer算法
因为Matlab eps精度不够，导致delta运算
"""
EPS = 1.e-6
manualAssign=False

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
        plt.savefig("topology_graph.eps", format='eps')  # save as eps
        #plt.ion()
        #plt.pause(5)
        plt.close()
    
    return edge,node

def customedSort(nodeName):
    return int(re.findall("\d+", nodeName)[0])

if __name__ == "__main__":
        
    #filename="topo-for-CompareMultiPath.txt"
    filename="18Nodes-2.txt"
    e,n=readTopology("/topologies30/"+filename)

    consumerList=[]
    producerList=[]
    if(manualAssign):
        consumerList=['Node0','Node1']
        producerList=['Node2','Node3']
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
    # 数据预处理，缩放
    for i in range(len(consumerList)):
        d[consumerList[i],producerList[i]]=1 
    '''
    开始计算，输入有 nodes, edges, dem
    '''
    #构造图G，边的属性只设置 u(e)和 le
    G=nx.DiGraph()
    G.add_nodes_from(n)
    #G.add_edges_from(e,weight=2)
    mp.dbs=50   #浮点数的精度（小数点位数）
    epsilon=0.002
    delta=(mpf(len(e))/(mpf(1)-mpf(epsilon)))**(mpf(-1)/mpf(epsilon))

    for (i,j) in e.keys():
        G.add_edge(i,j,ue=e[i,j]['cap'])
        G.add_edge(i,j,le=delta/mpf(e[i,j]['cap']))
    
    startTime=time.time()
    #根据我的论文进行的缩放
    mincap=float(e.values()[0]['cap'])
    for i in range(len(e.values())-1):
        if float(e.values()[i]['cap'])<mincap:
            mincap=float(e.values()[i]['cap'])
    rho=mincap/max(d.values())
    for (i,j) in d.keys():
        d[i,j]=d[i,j]*rho
    edgeFlows={}
    # 开始计算
    Dl=mpf(0.0)
    for (i,j) in e.keys():
        Dl=Dl+G.edges[i,j]['le']
        edgeFlows[i,j]=0.0
    t=0
    while(Dl<1):
        t=t+1
        for (source,target) in d.keys():
            dj=d[source,target]
            while (Dl<1 and dj>0):
                p=nx.shortest_path(G, source, target, 'le')
                minu=int(G[p[0]][p[1]]['ue'])
                # 在链路均匀的情况下，下面的循环是可以省略的,包括后面的le计算中直接使用了minu
                #for q in range(len(p)-1):
                #    minu=min(G[p[q]][p[q+1]]['ue'],minu)
                
                u=min(dj,minu)
                dj=dj-u

                for q in range(len(p)-1):
                    edgeFlows[p[q],p[q+1]]=edgeFlows[p[q],p[q+1]]+u
                    G[p[q]][p[q+1]]['le']=G[p[q]][p[q+1]]['le']*(mpf(1)+mpf(epsilon)*mpf(u)/mpf(minu))
                    #print 'G.edges[{0},{1}][le]={2}'.format(p[q],p[q+1],G[p[q]][p[q+1]]['le'])
                for (i,j) in e.keys():
                    Dl=Dl+G.edges[i,j]['le']
        if t%10000==0:
            print ('Now t={0}, Dl={1}'.format(t,Dl))
            if t>10000000:
                print ('Timeout without a solution')
                break            
    lamb=rho*(t-1)/mp.log(mpf(1)/delta,(1+epsilon))
    #lamb=rho*(t)/mp.log(mpf(1+epsilon)/delta,(1+epsilon))
    print ('lambda is : {0}'.format(lamb))
    print ('耗时：{0} s'.format(time.time()-startTime))

    scale=mp.log((mpf(1)+mpf(epsilon))/mpf(delta))/mp.log(mpf(1)+mpf(epsilon))
    #print edgeFlows
    
    