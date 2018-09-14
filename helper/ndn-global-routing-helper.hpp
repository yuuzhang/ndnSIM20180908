/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/**
 * Copyright (c) 2011-2015  Regents of the University of California.
 *
 * This file is part of ndnSIM. See AUTHORS for complete list of ndnSIM authors and
 * contributors.
 *
 * ndnSIM is free software: you can redistribute it and/or modify it under the terms
 * of the GNU General Public License as published by the Free Software Foundation,
 * either version 3 of the License, or (at your option) any later version.
 *
 * ndnSIM is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
 * without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.  See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * ndnSIM, e.g., in COPYING.md file.  If not, see <http://www.gnu.org/licenses/>.
 **/

#ifndef NDN_GLOBAL_ROUTING_HELPER_H
#define NDN_GLOBAL_ROUTING_HELPER_H

#include "ns3/ndnSIM/model/ndn-common.hpp"

#include "ns3/ptr.h"

namespace ns3 {

class Node;
class NodeContainer;
class Channel;

namespace ndn {

/**
 * @ingroup ndn-helpers
 * @brief Helper for GlobalRouter interface
 */
class GlobalRoutingHelper {
public:
  /**
   * @brief Install GlobalRouter interface on a node
   *
   * Note that GlobalRouter will also be installed on all connected nodes and channels
   *
   * @param node Node to install GlobalRouter interface
   */
  void
  Install(Ptr<Node> node);

  /**
   * @brief Install GlobalRouter interface on nodes
   *
   * Note that GlobalRouter will also be installed on all connected nodes and channels
   *
   * @param nodes NodeContainer to install GlobalRouter interface
   */
  void
  Install(const NodeContainer& nodes);

  /**
   * @brief Install GlobalRouter interface on all nodes
   */
  void
  InstallAll();

  /**
   * @brief Add `prefix' as origin on `node'
   * @param prefix Prefix that is originated by node, e.g., node is a producer for this prefix
   * @param node   Pointer to a node
   */
  void
  AddOrigin(const std::string& prefix, Ptr<Node> node);

  /**
   * @brief Add `prefix' as origin on all `nodes'
   * @param prefix Prefix that is originated by nodes
   * @param nodes NodeContainer
   */
  void
  AddOrigins(const std::string& prefix, const NodeContainer& nodes);

  /**
   * @brief Add `prefix' as origin on node `nodeName'
   * @param prefix     Prefix that is originated by node, e.g., node is a producer for this prefix
   * @param nodeName   Name of the node that is associated with Ptr<Node> using ns3::Names
   */
  void
  AddOrigin(const std::string& prefix, const std::string& nodeName);

  /**
   * @brief Add origin to each node based on the node's name (using Names class)
   */
  void
  AddOriginsForAll();

  /**
   * @brief Calculate for every node shortest path trees and install routes to all prefix origins
   */
  static void
  CalculateRoutes();

  /**
   * @brief Calculate all possible next-hop independent alternative routes
   *
   * Refer to the implementation for more details.
   *
   * Note that this method is highly experimental and should be used with caution (very time
   *consuming).
   */
  static void
  CalculateAllPossibleRoutes();
  /* ZhangYu 2018-2-28 从2014年的版本中找出来的代码加上
   * 为了对比，修改为 k-shortest path
   */
  static void
  CalculateNoCommLinkMultiPathRoutes(std::int32_t k);

  /*
  * @ZY, back up originalMetric for all edges, using in CalculateNoCommLinkMultiPathRoutes
  */
  static void
  BackupRestoreOriginalMetrics(const std::string action);
  /*
   * @ZY, 2015-1-7 no common link multi-path algorithms PairFirst
   */
  static void
  CalculateNoCommLinkMultiPathRoutesPairFirst();
  /*
   * @ZY, 2016-12-6 no common link multi-path algorithms PairFirst, but add reverse routes
   *
   */
  static void
  CalculateNoCommLinkMultiPathRoutesPairFirst(bool addReverseRoute);

/*
 * @ZY, 2017-8-19 try to caculate routes by python, and use the python results in ns3 c++
 * add next hop for a route
 * 原本打算用scenarioHelper来实现，结果发现它自成体系，拓扑和节点都用自己的，所以放弃
 */
static void
addRouteHop(const std::string edgeStart,const std::string prefix, const std::string edgeEnd, std::int32_t metri);

/*
 * @ZY, 2018-1-30 add probability for the consumer node, in case of randomized rounding
 */
static void
addRouteHop(const std::string edgeStart,const std::string prefix, const std::string edgeEnd, std::int32_t metri, std::double_t probability);

private:
  void
  Install(Ptr<Channel> channel);
};

} // namespace ndn
} // namespace ns3

#endif // NDN_GLOBAL_ROUTING_HELPER_H
