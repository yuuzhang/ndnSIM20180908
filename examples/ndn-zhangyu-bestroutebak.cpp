/* -*-  Mode: C++; c-file-style: "gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2011-2012 University of California, Los Angeles
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author: Alexander Afanasyev <alexander.afanasyev@ucla.edu>
 */


#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/point-to-point-layout-module.h"
#include "ns3/ndnSIM-module.h"

//2016-12-7
#include <boost/lexical_cast.hpp>
#include <boost/lambda/lambda.hpp>
#include <boost/lambda/bind.hpp>
#include "ns3/ndnSIM/helper/ndn-link-control-helper.hpp"

//ZhangYu 2014-2-7 for DynamicRouting，否则不认识Name，试了很多.h才知道要包含ndn-interest.h
#include "ns3/names.h"
#include "ns3/string.h"
#include "ns3/ptr.h"
#include <boost/ref.hpp>
#include <boost/lexical_cast.hpp>
#include <boost/lambda/lambda.hpp>
#include <boost/lambda/bind.hpp>

using namespace std;
//2017-8-19 try python caculate routes and add to FIB manually

//---ZhangYu

namespace ns3	{
/**
 * ZhangYu 2014-3-10，使用BRITE产生的随机网络拓扑，业务量均匀分布在随机的节点对之间
 * 我们这里可以偷懒，因为节点的位置和链路是随机的，所以可以让节点对编号是连续的，效果上应该和均匀分布的随机是一样的。
 * 而且这样拓扑和业务分布可以是固定的，分析数据结果时，可比性强。
 */

int
main (int argc, char *argv[])
{
	bool manualAssign=true;
	int InterestsPerSec=200;
	int simulationSpan=200;
	int TraceSpan=1;
	int recordsNumber=100;
	string routingName="MultiPathPairFirst";

	//----------------命令行参数----------------
	CommandLine cmd;
	cmd.AddValue("InterestsPerSec","Interests emit by consumer per second",InterestsPerSec);
	cmd.AddValue("simulationSpan","Simulation span time by seconds",simulationSpan);
	cmd.AddValue ("routingName", "could be Flooding, BestRoute, k-shortest, MultiPathPairFirst, debug", routingName);
	cmd.AddValue ("recordsNumber", "total number of records in tracer file", recordsNumber);
	cmd.Parse(argc,argv);
	//std::cout << "routingName: " << routingName << "   " << InterestsPerSec << " " << simulationSpan << std::endl;

	//----------------仿真拓扑----------------
	AnnotatedTopologyReader topologyReader ("", 20);
	//topologyReader.SetFileName ("src/ndnSIM/examples/topologies/26node-result.txt");
	//topologyReader.SetFileName ("src/ndnSIM/examples/topologies/topo-for-CompareMultiPath80k.txt");
	topologyReader.SetFileName ("src/ndnSIM/examples/topologies/5Nodes-Debug.txt");
	//topologyReader.SetFileName ("src/ndnSIM/examples/topologies/topo-for-xujun.txt");
	topologyReader.Read ();
	int nodesNumber=topologyReader.GetNodes().size();

	//----------------安装Install CCNx stack ----------------
	ndn::StackHelper ndnHelper;
	// 下面这一句是Install NDN stack on all nodes
	ndnHelper.SetOldContentStore("ns3::ndn::cs::Lru", "MaxSize","100"); // default ContentStore parameters
	ndnHelper.SetOldContentStore("ns3::ndn::cs::Nocache"); // default ContentStore parameters
	ndnHelper.InstallAll();

	topologyReader.ApplyOspfMetric();  //使得链路metric生效

	//----------------Installing global routing interface on all nodes ----------------
	ndn::GlobalRoutingHelper ndnGlobalRoutingHelper;
	ndnGlobalRoutingHelper.InstallAll ();

	//----------------设置节点的业务 ----------------
	//根据不同的拓扑手工指定或者自动生成业务节点对
	std::vector<int> consumerNodes,producerNodes;
	//生成consumer和producer的节点号动态数组
	if(manualAssign)	{
		int tmpConsumer[]={0,1};
		int tmpProducer[]={3,4};
		consumerNodes.assign(tmpConsumer,tmpConsumer+sizeof(tmpConsumer)/sizeof(int));
		producerNodes.assign(tmpProducer,tmpProducer+sizeof(tmpConsumer)/sizeof(int));
	}
	else	{
		for(int i=0;i<nodesNumber/2;i++)	{
		  consumerNodes.push_back(i);
		  producerNodes.push_back(i+nodesNumber/2);
		}
	}

	//根据上面生成的节点对编号装载应用
	for(uint32_t i=0;i<consumerNodes.size();i++)	{
		ndn::AppHelper consumerHelper ("ns3::ndn::ConsumerCbr");
		consumerHelper.SetAttribute("Frequency", StringValue (boost::lexical_cast<std::string>(InterestsPerSec)));        // 100 interests a second
		//ndn::AppHelper consumerHelper("ns3::ndn::ConsumerZipfMandelbrot");
		//consumerHelper.SetAttribute("NumberOfContents", StringValue("100")); // 10 different contents
		//可以选择的有：
		//"none": no randomization
		//"uniform": uniform distribution in range (0, 1/Frequency)
		//"exponential": exponential distribution with mean 1/Frequency
		consumerHelper.SetAttribute("Randomize", StringValue("uniform"));

		Ptr<Node> consumer1 = Names::Find<Node> ("Node"+boost::lexical_cast<std::string> (consumerNodes[i]));
		consumerHelper.SetPrefix ("/Node"+boost::lexical_cast<std::string>(consumerNodes[i]));
		ApplicationContainer app=consumerHelper.Install(consumer1);
		app.Start(Seconds(0.01*i));
		// Choosing forwarding strategy
		//ndn::StrategyChoiceHelper::InstallAll("/Node"+boost::lexical_cast<std::string> (consumerNodes[i]), "/localhost/nfd/strategy/randomized-rounding");
		ndn::StrategyChoiceHelper::InstallAll("/Node"+boost::lexical_cast<std::string> (consumerNodes[i]), "/localhost/nfd/strategy/best-route");
		//ndn::StrategyChoiceHelper::InstallAll("/Node"+boost::lexical_cast<std::string> (consumerNodes[i]), "/localhost/nfd/strategy/ncc");

		std::cout <<"ZhangYu  consumer1->GetId(): " <<consumer1->GetId() << "  prefix: /Node"+boost::lexical_cast<std::string>(consumerNodes[i]) << std::endl;
	}

	for(uint32_t i=0;i<producerNodes.size();i++)	{
		ndn::AppHelper producerHelper ("ns3::ndn::Producer");
		producerHelper.SetAttribute ("PayloadSize", StringValue("8192"));
		//认为producer节点的Prefix和对应位置的consumer节点一致
		producerHelper.SetPrefix ("/Node"+boost::lexical_cast<std::string>(consumerNodes[i]));

		Ptr<Node> producer1 = Names::Find<Node> ("Node"+boost::lexical_cast<std::string> (producerNodes[i]));
		ndnGlobalRoutingHelper.AddOrigins ("/Node"+boost::lexical_cast<std::string>(consumerNodes[i]), producer1);
		producerHelper.Install(producer1);
		std::cout <<"ZhangYu producer1->GetId(): " <<producer1->GetId() << std::endl;
	}

	// Calculate and install FIBs
	if(routingName.compare("BestRoute")==0){
	  ndn::GlobalRoutingHelper::CalculateRoutes ();
	}
	/*
	else if(routingName.compare("k-shortest")==0){
		ndn::GlobalRoutingHelper::CalculateNoCommLinkMultiPathRoutes(2);
	}
	else if(routingName.compare("MultiPathPairFirst")==0){
		ndn::GlobalRoutingHelper::CalculateNoCommLinkMultiPathRoutesPairFirst();
		//ndn::GlobalRoutingHelper::CalculateRoutes();
	}
	else if(routingName.compare("debug")==0){
		//当Consumer是0时，prefix=/Node0时，需要添加 0-->1-->4 的路由才可以，添加反向4->1->0没有Traffic
		ndn::GlobalRoutingHelper::addRouteHop("Node0","/Node0","Node1",1);
		ndn::GlobalRoutingHelper::addRouteHop("Node1","/Node0","Node4",1);
	}
	*/
	else if(routingName.compare("Flooding")==0){
		ndn::GlobalRoutingHelper::CalculateAllPossibleRoutes();
	}
	else{
		std::cout << "!!!!  ~~~~~~Unkown routingName: " << routingName << ", try again..." <<std::endl;
	}

	// The failure of the link connecting consumer and router will start from seconds 10.0 to 15.0
	//Simulator::Schedule (Seconds (10.0), ndn::LinkControlHelper::FailLink, Names::Find<Node> ("Node0"),Names::Find<Node> ("Node4"));
	//Simulator::Schedule (Seconds (15.0), ndn::LinkControlHelper::UpLink,   Names::Find<Node> ("Node0"),Names::Find<Node> ("Node4"));

	Simulator::Stop (Seconds(simulationSpan));

	//ZhangYu Add the trace，不愿意文件名称还有大小写的区别，所以把 routingName 全部转为小写
	std::transform(routingName.begin(), routingName.end(), routingName.begin(), ::tolower);
	string filename="-"+routingName+"-"+boost::lexical_cast<std::string>(InterestsPerSec)+".txt";

	TraceSpan=simulationSpan/recordsNumber;
	if(TraceSpan<1)
		TraceSpan=1;
	ndn::CsTracer::InstallAll ("cs-trace"+filename, Seconds (TraceSpan));
	ndn::L3RateTracer::InstallAll ("rate-trace"+filename, Seconds (TraceSpan));
	// L3AggregateTracer disappeared in new version
	//ndn::L3AggregateTracer::InstallAll ("aggregate-trace-"+filename, Seconds (1));
	ndn::AppDelayTracer::InstallAll ("app-delays-trace"+filename);
	L2RateTracer::InstallAll ("drop-trace"+filename, Seconds (TraceSpan));

	Simulator::Run ();
	Simulator::Destroy ();

  return 0;
}
} // namespace ns3

int
main(int argc, char* argv[])
{
  return ns3::main(argc, argv);
}

