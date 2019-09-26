## -*- Mode: python; py-indent-offset: 4; indent-tabs-mode: nil; coding: utf-8; -*-
#
# 2017-9-2 ZhangYu-SCIP-Routing.py
#
from ns.core import *
from ns.network import *
from ns.point_to_point import *
from ns.point_to_point_layout import *
from ns.ndnSIM import *
import mintreeMFP
from ns.topology_read import TopologyReader
import visualizer
import math


# ZhangYu 2019-7-14 为了Iot的更改，添加不同缓存策略的仿真结果，在仿真结果文件中添加缓存策略
# ZhangYu 2018-1-26 添加了traffic split, randomized rounding。因为randomized rounding是需要路由计算的结果来分配的带宽的，一种方法是按照
# NDF Developer Guide的建议保存在PIT中，这里采用了较简单的做法，直接保存在该主程序中，然后传递给自定义的NDF Strategy中
# ZhangYu 2017-9-6 改用Python脚本运行ndnSIM仿真
""" 
    PyBindGen在Ubuntu1204虚拟机中的是可以用的，但是ndnSIM2.0以后无论是1404的GCC4.8还是1604的GCC5.1都不能正常执行--apiscan
    所以放弃了自动生成，而是手工修改modulegen__gcc_ILP32来添加AnnotatedTopologyReader，运行命令如下：
    NS_LOG=ndn.GlobalRoutingHelper:ndn.Producer ./waf --pyrun="src/ndnSIM/examples/ndn-zhangyu-scip-routing.py --routingName='Flooding'"
"""
# ----------------命令行参数----------------
from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
# Setup argument parser
parser = ArgumentParser(description="./waf --pyrun=ndn-zhangyu-scip-routing.py", formatter_class=RawDescriptionHelpFormatter)
parser.add_argument("--InterestsPerSec", type=str,
                    default="300", help="Interests emit by consumer per second")
parser.add_argument("--simulationSpan", type=int, 
                    default=200, help="Simulation span time by seconds")
parser.add_argument("--routingName", type=str, choices=["Flooding","BestRoute","k-shortest-2","k-shortest-3","MultiPathPairFirst",
                                                        "SCIP","pyMultiPathPairFirst","pyFlooding","pyBestRoute","pyk-shortest-2",
                                                        "pyk-shortest-3","pyFloodingwithRestore","pyBestRoutewithRestore",
                                                        "pyk-shortestwithRestore-2","pyk-shortestwithRestore-3","debug"], 
                    default="MultiPathPairFirst", 
                    help="could be Flooding, BestRoute, MultiPath, MultiPathPairFirst")
parser.add_argument("--recordsNumber",type=int,default=100,help="total number of records in trace file")
parser.add_argument("--vis",action="store_true",default=False)

args=parser.parse_args()

manualAssign=False

# ----------------仿真拓扑----------------
#topoFileName="topo-for-CompareMultiPath.txt"
#topoFileName="5Nodes-Debug.txt"
topoFileName="12Nodes-3-1000.txt"
#topoFileName="100Nodes-5-1000.txt"
topologyReader=AnnotatedTopologyReader("",0.2)
topologyReader.SetFileName("src/ndnSIM/examples/topologies/"+topoFileName)
nodes=topologyReader.Read()

# ----------------协议加载----------------
ndnHelper = ndn.StackHelper()
cachepolicy="Random"
# cs::Lru Least recently used (LRU) (default)
# cs::Fifo First-in-first-Out (FIFO)
# cs::Lfu Least frequently used (LFU)
# cs::Random Random
# cs::Nocache Policy that completely disables caching
if cachepolicy=="Nocache":
    ndnHelper.SetOldContentStore("ns3::ndn::cs::Nocache","","","","","","","","")
else:
    ndnHelper.SetOldContentStore("ns3::ndn::cs::" + cachepolicy,"MaxSize","500","","","","","","")
ndnHelper.InstallAll();
topologyReader.ApplyOspfMetric()
ndnGlobalRoutingHelper = ndn.GlobalRoutingHelper()
ndnGlobalRoutingHelper.InstallAll()

# ----------------业务加载----------------
consumerList=[]
producerList=[]
if(manualAssign):
    consumerList=['Node0','Node1']
    producerList=['Node3','Node4']
else:
    K=int(math.floor(int(nodes.GetN())/2.0))
    for k in range(K):
        consumerList.append(topologyReader.GetNodeName(nodes.Get(k)))
        producerList.append(topologyReader.GetNodeName(nodes.Get(k+K)))
if cachepolicy=="Nocache":
        cHelper = ndn.AppHelper("ns3::ndn::ConsumerCbr")
else:
    cHelper= ndn.AppHelper("ns3::ndn::ConsumerZipfMandelbrot")
    cHelper.SetAttribute("NumberOfContents", StringValue("1000")) # 1000 different contents，看ContentStore缓存多少
cHelper.SetAttribute("Frequency", StringValue(args.InterestsPerSec))
#可以选择的有：
#"none": no randomization
#"uniform": uniform distribution in range (0, 1/Frequency)
#"exponential": exponential distribution with mean 1/Frequency
cHelper.SetAttribute("Randomize", StringValue("exponential"))

pHelper = ndn.AppHelper("ns3::ndn::Producer")
pHelper.SetAttribute("PayloadSize", StringValue("10240"));
'''
2017-10-17 ZhangYu 考虑到多播时的FIB，把prefix改为跟producerName相关，而不是consumerName
'''
for i in range(len(producerList)):
    #if i==7:
    cHelper.SetPrefix("/"+producerList[i])
    print consumerList[i]
    App=cHelper.Install(topologyReader.FindNodeFromName(consumerList[i]))
    #App.Start(Seconds(0.01*i));

    pHelper.SetPrefix("/"+producerList[i])
    ndnGlobalRoutingHelper.AddOrigin("/"+producerList[i], topologyReader.FindNodeFromName(producerList[i]))
    pHelper.Install(topologyReader.FindNodeFromName(producerList[i]))

# ----------------路由和转发----------------
# Calculate and install FIBs
if args.routingName=="Flooding":
    ndnGlobalRoutingHelper.CalculateAllPossibleRoutes()
    for i in range(len(producerList)):
        #ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/ncc")
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/multicast")
elif args.routingName=="BestRoute":
    ndnGlobalRoutingHelper.CalculateRoutes()
    for i in range(len(producerList)):
        #ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/best-route")
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/multicast")
elif args.routingName=="k-shortest-2":
    ndnGlobalRoutingHelper.CalculateNoCommLinkMultiPathRoutes(2)
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/ncc")

elif args.routingName=="k-shortest-3":
    ndnGlobalRoutingHelper.CalculateNoCommLinkMultiPathRoutes(3)
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/ncc")
elif args.routingName=="MultiPathPairFirst":
    ndnGlobalRoutingHelper.CalculateNoCommLinkMultiPathRoutesPairFirst();
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/multicast")
elif args.routingName=="SCIP":
    lamb,routeList=mintreeMFP.caculatemaxConcurrentMFPRoute("/topologies/"+topoFileName,consumerList,producerList)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
        print(routeList[i]['edgeStart']+','+routeList[i]['prefix']+','+routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    '''
    为了能让数据分流到多条路径，使用概率转发，以前的多路径只是让Interest多副本转发，在统计时丢弃了重复的数据，应该在除了BestRoute和Flooding之外的所有其他多路径策略中设置概率转发
    '''
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
        #ndn.StrategyChoiceHelper.Install(topologyReader.FindNodeFromName(consumerList[i]), "/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")

elif args.routingName=="pyMultiPathPairFirst":
    # 前面的各种算法是多路径重复发送数据，提高可靠性的，用来统计吞吐量是不合适的，因此使用了下面的使用概率转发实现业务分离的方式，为了简单全部使用Python实现
    maxThroughput,lamb,routeList=mintreeMFP.caculatenoCommLinkPairFirst("/topologies/"+topoFileName,consumerList,producerList)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
        print(routeList[i]['edgeStart']+','+routeList[i]['prefix']+','+routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
# 下面是全部调用了caculateKshortest来实现的，这个实现中，所有计算路径的过程中，都会删除占用的边，全过程中没有复原拓扑，适用于静态业务
elif args.routingName=="pyFlooding":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortest("/topologies/"+topoFileName,consumerList,producerList,10000)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
elif args.routingName=="pyBestRoute":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortest("/topologies/"+topoFileName,consumerList,producerList,1)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
elif args.routingName=="pyk-shortest-2":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortest("/topologies/"+topoFileName,consumerList,producerList,2)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
elif args.routingName=="pyk-shortest-3":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortest("/topologies/"+topoFileName,consumerList,producerList,3)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
# 下面是调用了caculateKshortestwithRestore，在计算完一轮K后，要复原拓扑，重新计算下一对源目的节点对，这更适合传统意义上的k-shortest path，
# 适合于动态业务，不能预先知道
elif args.routingName=="pyFloodingwithRestore":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortestwithRestore("/topologies/"+topoFileName,consumerList,producerList,10000)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
elif args.routingName=="pyBestRoutewithRestore":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortestwithRestore("/topologies/"+topoFileName,consumerList,producerList,1)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
elif args.routingName=="pyk-shortestwithRestore-2":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortestwithRestore("/topologies/"+topoFileName,consumerList,producerList,2)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
elif args.routingName=="pyk-shortestwithRestore-3":
    maxThroughput,lamb,routeList=mintreeMFP.caculateKshortestwithRestore("/topologies/"+topoFileName,consumerList,producerList,3)
    for i in range(len(routeList)):
        ndnGlobalRoutingHelper.addRouteHop(routeList[i]['edgeStart'],routeList[i]['prefix'],routeList[i]['edgeEnd'],
                                           routeList[i]['cost'],routeList[i]['probability'])
    for i in range(len(producerList)):
        ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
elif args.routingName=="debug":
    ndnGlobalRoutingHelper.addRouteHop("Node0","/Node4","Node2",1,0.1);
    ndnGlobalRoutingHelper.addRouteHop("Node2","/Node4","Node4",1,0.1);
    ndnGlobalRoutingHelper.addRouteHop("Node0","/Node4","Node1",1,0.9);
    ndnGlobalRoutingHelper.addRouteHop("Node1","/Node4","Node4",1,0.9);
    for i in range(len(producerList)):
        #ndn.StrategyChoiceHelper.InstallAll("/"+producerList[i], "/localhost/nfd/strategy/multicast")
        ndn.StrategyChoiceHelper.Install(topologyReader.FindNodeFromName(consumerList[i]), "/"+producerList[i], "/localhost/nfd/strategy/randomized-rounding")
else:
    print "Unkown routingName, try again..."


# # To access FIB, PIT, CS, uncomment the following lines

# l3Protocol = ndn.L3Protocol.getL3Protocol(grid.GetNode(0,0))
# forwarder = l3Protocol.getForwarder()

# fib = forwarder.getFib()
# print "Contents of FIB (%d):" % fib.size()
# for i in fib:
#     print " - %s:" % i.getPrefix()
#     for nh in i.getNextHops():
#         print "    - %s%d (cost: %d)" % (nh.getFace(), nh.getFace().getId(), nh.getCost())

# pit = forwarder.getPit()
# print "Contents of PIT (%d):" % pit.size()
# for i in pit:
#     print " - %s" % i.getName()

# cs = forwarder.getCs()
# print "Contents of CS (%d):" % cs.size()
# for i in cs:
#     print " - %s" % i.getName()
# ----------------------------------------

Simulator.Stop(Seconds(args.simulationSpan))
#print dir(L2RateTracer)

# ----------------结果记录----------------
filename="-"+args.routingName.lower()+"-"+cachepolicy+"-"+str(args.InterestsPerSec)+".txt"
#filename=".txt"
TraceSpan=args.simulationSpan/args.recordsNumber;
if (TraceSpan<1) :
    TraceSpan=1
#ndn.CsTracer.InstallAll("Results/cs-trace"+filename, Seconds(TraceSpan))
ndn.L3RateTracer.InstallAll("Results/rate-trace"+filename, Seconds(TraceSpan))
ndn.AppDelayTracer.InstallAll("Results/app-delays-trace"+filename)
L2RateTracer.InstallAll("Results/drop-trace"+filename,Seconds(TraceSpan))
if args.vis:
    visualizer.start()
Simulator.Run()

Simulator.Destroy()

# ----------------结果处理----------------
import subprocess



