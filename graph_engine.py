"""
Graph Engine - Network Intelligence for Transaction Analysis
Detects coordinated attacks, laundering chains, and poisoning clusters
"""

import networkx as nx
from collections import defaultdict, deque
import numpy as np
from typing import Dict, List, Tuple, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransactionGraph:
    """
    Builds and analyzes transaction network graphs
    - Nodes: wallets
    - Edges: transactions (source -> recipient)
    """
    
    def __init__(self, directed=True):
        """
        Initialize graph
        
        Args:
            directed: True for directed graph (source -> recipient), False for undirected
        """
        self.graph = nx.DiGraph() if directed else nx.Graph()
        self.directed = directed
        self.edge_weights = defaultdict(float)  # Store cumulative transaction amounts
        self.edge_frequencies = defaultdict(int)  # Store transaction count per edge
        self.known_malicious = set()  # Known malicious wallet addresses
        
    def add_transaction(self, sender: str, recipient: str, amount: float = 1.0, tx_hash: str = None):
        """
        Add transaction to graph
        
        Args:
            sender: Source wallet address
            recipient: Destination wallet address
            amount: Transaction amount (default 1.0)
            tx_hash: Transaction hash for reference
        """
        if not sender or not recipient or sender == recipient:
            return
            
        # Add nodes
        self.graph.add_node(sender, type='sender')
        self.graph.add_node(recipient, type='recipient')
        
        # Add/update edge
        edge_key = (sender, recipient)
        self.edge_weights[edge_key] += amount
        self.edge_frequencies[edge_key] += 1
        
        # Add edge with accumulated weight
        self.graph.add_edge(
            sender, recipient,
            weight=self.edge_weights[edge_key],
            frequency=self.edge_frequencies[edge_key]
        )
            
    def build_from_transactions(self, transactions: List[Dict]):
        """
        Build graph from transaction list
        
        Args:
            transactions: List of transaction dicts with keys:
                - 'from' or 'sender': source wallet
                - 'to' or 'recipient': destination wallet
                - 'value': transaction amount (optional)
        """
        for tx in transactions:
            sender = tx.get('from') or tx.get('sender')
            recipient = tx.get('to') or tx.get('recipient')
            amount = float(tx.get('value', 1.0))
            
            self.add_transaction(sender, recipient, amount)
            
        logger.info(f"Built graph with {self.graph.number_of_nodes()} nodes, "
                   f"{self.graph.number_of_edges()} edges")
    
    def add_known_malicious(self, wallets: List[str]):
        """
        Register known malicious wallets for cluster detection
        
        Args:
            wallets: List of malicious wallet addresses
        """
        self.known_malicious.update(wallets)
        logger.info(f"Registered {len(wallets)} known malicious wallets")
    
    # ============ GRAPH METRICS ============
    
    def get_node_degree(self, wallet: str = None) -> Dict[str, int] | int:
        """
        Get in/out degree for wallet(s)
        
        Args:
            wallet: Specific wallet to check, or None for all
            
        Returns:
            Dict of degrees for all wallets, or int for specific wallet
        """
        if wallet:
            if self.directed:
                return self.graph.in_degree(wallet) + self.graph.out_degree(wallet)
            return self.graph.degree(wallet)
        
        if self.directed:
            return {node: self.graph.in_degree(node) + self.graph.out_degree(node)
                    for node in self.graph.nodes()}
        
        return dict(self.graph.degree())
    
    def get_pagerank(self) -> Dict[str, float]:
        """
        Compute PageRank for all nodes
        High PageRank = central in network, likely hub or connector
        
        Returns:
            Dict of wallet -> pagerank score
        """
        try:
            return nx.pagerank(self.graph, weight='weight', max_iter=100)
        except Exception as e:
            logger.warning(f"PageRank computation failed: {e}")
            return {}
    
    def get_clustering_coefficient(self, wallet: str = None) -> Dict[str, float] | float:
        """
        Compute clustering coefficient (triangle density around node)
        
        Args:
            wallet: Specific wallet or None for all
            
        Returns:
            Dict of clustering coefficients or single float
        """
        if not self.directed:
            try:
                if wallet:
                    return nx.clustering(self.graph, wallet)
                return nx.clustering(self.graph)
            except Exception as e:
                logger.warning(f"Clustering coefficient failed: {e}")
                return {} if not wallet else 0.0
        
        # For directed graphs, use undirected projection
        undirected = self.graph.to_undirected()
        if wallet:
            return nx.clustering(undirected, wallet)
        return nx.clustering(undirected)
    
    def get_betweenness_centrality(self) -> Dict[str, float]:
        """
        Compute betweenness centrality (how many shortest paths pass through node)
        High values = critical connector/bridge in network
        
        Returns:
            Dict of wallet -> betweenness score
        """
        try:
            return nx.betweenness_centrality(self.graph, weight='weight')
        except Exception as e:
            logger.warning(f"Betweenness centrality failed: {e}")
            return {}
    
    def get_closeness_centrality(self) -> Dict[str, float]:
        """
        Compute closeness centrality (average distance to other nodes)
        
        Returns:
            Dict of wallet -> closeness score
        """
        try:
            if self.directed:
                # Use weakly connected components for directed graphs
                return nx.closeness_centrality(self.graph.to_undirected())
            return nx.closeness_centrality(self.graph)
        except Exception as e:
            logger.warning(f"Closeness centrality failed: {e}")
            return {}
    
    def get_unique_counterparties(self, wallet: str) -> Dict[str, int]:
        """
        Count unique counterparties for wallet
        
        Args:
            wallet: Wallet address
            
        Returns:
            Dict with 'inbound' and 'outbound' unique counterparty counts
        """
        if wallet not in self.graph:
            return {'inbound': 0, 'outbound': 0}
        
        if self.directed:
            inbound = set(self.graph.predecessors(wallet))
            outbound = set(self.graph.successors(wallet))
        else:
            neighbors = set(self.graph.neighbors(wallet))
            inbound = outbound = neighbors
        
        return {
            'inbound': len(inbound),
            'outbound': len(outbound),
            'total': len(inbound | outbound)
        }
    
    # ============ CLUSTER DETECTION ============
    
    def get_connected_components(self, minimum_size: int = 2) -> List[Set[str]]:
        """
        Find connected components (groups of wallets connected to each other)
        
        Args:
            minimum_size: Only return components with >= this many nodes
            
        Returns:
            List of sets, each set is a cluster of wallets
        """
        if self.directed:
            components = list(nx.weakly_connected_components(self.graph))
        else:
            components = list(nx.connected_components(self.graph))
        
        return [comp for comp in components if len(comp) >= minimum_size]
    
    def get_strongly_connected_components(self) -> List[Set[str]]:
        """
        Find strongly connected components (directed cycles)
        Only meaningful for directed graphs (transaction cycles)
        
        Returns:
            List of sets of wallets forming cycles
        """
        if not self.directed:
            logger.warning("Strongly connected components only for directed graphs")
            return []
        
        components = list(nx.strongly_connected_components(self.graph))
        return [comp for comp in components if len(comp) > 1]  # Cycles only
    
    def detect_suspicious_clusters(self) -> List[Dict]:
        """
        Detect suspicious clusters: connected to malicious wallets
        
        Returns:
            List of dicts with cluster info:
            - 'cluster': set of wallet addresses
            - 'malicious_count': number of known malicious wallets in cluster
            - 'size': cluster size
            - 'threat_level': 'HIGH', 'MEDIUM', 'LOW'
        """
        components = self.get_connected_components()
        suspicious = []
        
        for cluster in components:
            malicious_in_cluster = len(cluster & self.known_malicious)
            
            if malicious_in_cluster > 0:
                size = len(cluster)
                
                # Threat level based on malicious ratio
                if malicious_in_cluster / size >= 0.3:
                    threat = 'HIGH'
                elif malicious_in_cluster / size >= 0.1:
                    threat = 'MEDIUM'
                else:
                    threat = 'LOW'
                
                suspicious.append({
                    'cluster': cluster,
                    'malicious_count': malicious_in_cluster,
                    'size': size,
                    'threat_level': threat,
                    'malicious_wallets': list(cluster & self.known_malicious)
                })
        
        return sorted(suspicious, key=lambda x: x['malicious_count'], reverse=True)
    
    def find_paths_to_malicious(self, wallet: str, max_hops: int = 3) -> List[List[str]]:
        """
        Find all paths from wallet to known malicious wallets
        
        Args:
            wallet: Source wallet
            max_hops: Maximum path length
            
        Returns:
            List of paths (each path is list of wallets)
        """
        if wallet not in self.graph or not self.known_malicious:
            return []
        
        paths = []
        for malicious in self.known_malicious:
            if malicious not in self.graph:
                continue
            
            try:
                # Find all simple paths up to max_hops
                found_paths = list(nx.all_simple_paths(
                    self.graph, wallet, malicious, cutoff=max_hops
                ))
                paths.extend(found_paths)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
        
        return paths[:10]  # Limit to top 10 paths
    
    # ============ MONEY FLOW ANALYSIS ============
    
    def get_total_inflow(self, wallet: str) -> float:
        """Get total transaction value flowing into wallet"""
        if wallet not in self.graph:
            return 0.0
        
        total = 0.0
        if self.directed:
            for predecessor in self.graph.predecessors(wallet):
                edge_data = self.graph[predecessor][wallet]
                total += edge_data.get('weight', 1.0)
        return total
    
    def get_total_outflow(self, wallet: str) -> float:
        """Get total transaction value flowing out of wallet"""
        if wallet not in self.graph:
            return 0.0
        
        total = 0.0
        if self.directed:
            for successor in self.graph.successors(wallet):
                edge_data = self.graph[wallet][successor]
                total += edge_data.get('weight', 1.0)
        return total
    
    def get_transaction_flow_ratio(self, wallet: str) -> float:
        """
        Get inflow / outflow ratio
        - Ratio > 1: more money coming in
        - Ratio < 1: more money going out
        """
        inflow = self.get_total_inflow(wallet)
        outflow = self.get_total_outflow(wallet)
        
        if outflow == 0:
            return float('inf') if inflow > 0 else 1.0
        return inflow / outflow
    
    # ============ FEATURE EXTRACTION ============
    
    def extract_features(self, wallet: str) -> Dict[str, float]:
        """
        Extract all graph features for a wallet
        
        Args:
            wallet: Wallet address
            
        Returns:
            Dict of feature_name -> value
        """
        if wallet not in self.graph:
            return {
                'graph_degree': 0,
                'graph_in_degree': 0,
                'graph_out_degree': 0,
                'graph_pagerank': 0.0,
                'graph_clustering': 0.0,
                'graph_betweenness': 0.0,
                'graph_closeness': 0.0,
                'graph_unique_counterparties': 0,
                'graph_inflow': 0.0,
                'graph_outflow': 0.0,
                'graph_flow_ratio': 1.0,
                'connected_to_malicious': 0,
                'malicious_distance': float('inf')
            }
        
        features = {}
        
        # Degree metrics
        if self.directed:
            features['graph_in_degree'] = self.graph.in_degree(wallet)
            features['graph_out_degree'] = self.graph.out_degree(wallet)
            features['graph_degree'] = features['graph_in_degree'] + features['graph_out_degree']
        else:
            features['graph_degree'] = self.graph.degree(wallet)
            features['graph_in_degree'] = self.graph.degree(wallet)
            features['graph_out_degree'] = self.graph.degree(wallet)
        
        # Centrality metrics
        pagerank = self.get_pagerank()
        features['graph_pagerank'] = pagerank.get(wallet, 0.0)
        
        clustering = self.get_clustering_coefficient(wallet)
        features['graph_clustering'] = clustering if isinstance(clustering, float) else 0.0
        
        betweenness = self.get_betweenness_centrality()
        features['graph_betweenness'] = betweenness.get(wallet, 0.0)
        
        closeness = self.get_closeness_centrality()
        features['graph_closeness'] = closeness.get(wallet, 0.0)
        
        # Counterparties
        counterparties = self.get_unique_counterparties(wallet)
        features['graph_unique_counterparties'] = counterparties.get('total', 0)
        
        # Money flow
        features['graph_inflow'] = self.get_total_inflow(wallet)
        features['graph_outflow'] = self.get_total_outflow(wallet)
        features['graph_flow_ratio'] = self.get_transaction_flow_ratio(wallet)
        
        # Malicious connection
        paths_to_malicious = self.find_paths_to_malicious(wallet, max_hops=2)
        features['connected_to_malicious'] = 1 if paths_to_malicious else 0
        
        if paths_to_malicious:
            features['malicious_distance'] = min(len(p) for p in paths_to_malicious)
        else:
            features['malicious_distance'] = float('inf')
        
        return features
    
    def get_statistics(self) -> Dict:
        """Get overall graph statistics"""
        return {
            'node_count': self.graph.number_of_nodes(),
            'edge_count': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'is_directed': self.directed,
            'num_components': nx.number_connected_components(
                self.graph if not self.directed else self.graph.to_undirected()
            ),
            'num_strongly_connected': len(self.get_strongly_connected_components()) if self.directed else 0,
            'avg_degree': sum(dict(self.graph.degree()).values()) / max(self.graph.number_of_nodes(), 1)
        }


def create_graph_from_wallet_transactions(wallet: str, transactions: List[Dict],
                                          known_malicious: List[str] = None) -> TransactionGraph:
    """
    Convenience function to create graph from wallet transaction history
    
    Args:
        wallet: Primary wallet address
        transactions: List of transaction dicts
        known_malicious: List of known malicious addresses
        
    Returns:
        TransactionGraph object populated with transactions
    """
    graph = TransactionGraph(directed=True)
    graph.build_from_transactions(transactions)
    
    if known_malicious:
        graph.add_known_malicious(known_malicious)
    
    return graph
