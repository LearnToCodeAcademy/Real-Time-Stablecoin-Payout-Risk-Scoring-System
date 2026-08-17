"""
Graph Neural Network Models - Network-based Fraud Detection
Detects coordinated attacks and fraud rings through wallet network analysis

Uses PyTorch Geometric for GNN implementation:
- GraphConv: Basic graph convolution
- GATConv: Graph Attention Networks  
- GraphSAGE: Sampling and aggregating neighborhoods
"""

from __future__ import annotations

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional PyTorch libraries
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    F = None

    class _MissingTorchModule:
        pass

    class _MissingNN:
        Module = _MissingTorchModule

    nn = _MissingNN()
    logger.warning("PyTorch not installed. Install with: pip install torch")

try:
    import torch_geometric
    from torch_geometric.data import Data, DataLoader
    from torch_geometric.nn import GCNConv, GATConv, GraphSAGE
    HAS_TORCH_GEOMETRIC = True
except ImportError:
    HAS_TORCH_GEOMETRIC = False
    logger.warning("PyTorch Geometric not installed. Install with: pip install torch-geometric")


def _empty_node_scores(x):
    size = x.shape[0] if hasattr(x, "shape") else 0
    if HAS_TORCH:
        return torch.zeros(size)
    return np.zeros(size)


class GCNFraudDetector(nn.Module):
    """
    Graph Convolutional Network for fraud detection
    Detects fraudsters by analyzing wallet network patterns
    """
    
    def __init__(self, input_features: int = 10, hidden_size: int = 64, num_classes: int = 2):
        """
        Initialize GCN model
        
        Args:
            input_features: Node feature dimensionality (wallet features)
            hidden_size: Hidden layer size
            num_classes: Number of classification classes (2: fraud/safe)
        """
        super().__init__()
        self.input_features = input_features
        self.hidden_size = hidden_size
        
        if HAS_TORCH_GEOMETRIC:
            self.conv1 = GCNConv(input_features, hidden_size)
            self.conv2 = GCNConv(hidden_size, hidden_size)
            self.conv3 = GCNConv(hidden_size, num_classes)
            
            self.dropout = nn.Dropout(p=0.5)
            logger.info(f"✅ GCN initialized ({input_features} -> {hidden_size} -> {num_classes})")
        else:
            logger.warning("GCN requires PyTorch Geometric")
    
    def forward(self, x, edge_index):
        """
        Forward pass
        
        Args:
            x: Node features (n_nodes, n_features)
            edge_index: Edge connections (2, n_edges)
            
        Returns:
            Node fraud scores
        """
        if not HAS_TORCH_GEOMETRIC:
            return _empty_node_scores(x)
        
        # Graph convolution layers with ReLU activation
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)
        
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)
        
        # Output layer
        x = self.conv3(x, edge_index)
        
        return x


class GATFraudDetector(nn.Module):
    """
    Graph Attention Network for fraud detection
    Uses attention mechanisms to weight neighboring wallets
    """
    
    def __init__(self, input_features: int = 10, hidden_size: int = 64,
                 num_heads: int = 8, num_classes: int = 2):
        """
        Initialize GAT model
        
        Args:
            input_features: Node feature dimensionality
            hidden_size: Hidden feature size
            num_heads: Number of attention heads  
            num_classes: Output classes
        """
        super().__init__()
        self.input_features = input_features
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        
        if HAS_TORCH_GEOMETRIC:
            self.att1 = GATConv(input_features, hidden_size, heads=num_heads, dropout=0.6)
            self.att2 = GATConv(hidden_size * num_heads, num_classes, heads=1, dropout=0.6, concat=False)
            
            self.dropout = nn.Dropout(p=0.6)
            logger.info(f"✅ GAT initialized ({input_features} -> {hidden_size}x{num_heads} -> {num_classes})")
        else:
            logger.warning("GAT requires PyTorch Geometric")
    
    def forward(self, x, edge_index):
        """Forward pass with attention mechanism"""
        if not HAS_TORCH_GEOMETRIC:
            return _empty_node_scores(x)
        
        # First attention layer
        x = self.att1(x, edge_index)
        x = F.elu(x)
        x = self.dropout(x)
        
        # Second attention layer
        x = self.att2(x, edge_index)
        
        return x


class GraphSAGEFraudDetector(nn.Module):
    """
    GraphSAGE model - Sampling-based neighborhood aggregation
    Scalable to large wallet networks
    """
    
    def __init__(self, input_features: int = 10, hidden_size: int = 64, num_classes: int = 2):
        """Initialize GraphSAGE model"""
        super().__init__()
        
        if HAS_TORCH_GEOMETRIC:
            from torch_geometric.nn import SAGEConv
            
            self.sage1 = SAGEConv(input_features, hidden_size)
            self.sage2 = SAGEConv(hidden_size, hidden_size)
            self.out = nn.Linear(hidden_size, num_classes)
            
            self.dropout = nn.Dropout(p=0.5)
            logger.info(f"✅ GraphSAGE initialized ({input_features} -> {hidden_size} -> {num_classes})")
        else:
            logger.warning("GraphSAGE requires PyTorch Geometric")
    
    def forward(self, x, edge_index):
        """Forward pass"""
        if not HAS_TORCH_GEOMETRIC:
            return _empty_node_scores(x)
        
        x = self.sage1(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)
        
        x = self.sage2(x, edge_index)
        x = F.relu(x)
        
        x = self.out(x)
        return x


class WalletNetworkGNN:
    """High-level interface for wallet network GNN analysis"""
    
    def __init__(self, model_type: str = 'gcn', input_features: int = 10):
        """
        Initialize wallet network GNN
        
        Args:
            model_type: 'gcn', 'gat', or 'graphsage'
            input_features: Number of wallet features
        """
        self.model_type = model_type
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu') if HAS_TORCH else None
        
        if HAS_TORCH_GEOMETRIC:
            if model_type == 'gcn':
                self.model = GCNFraudDetector(input_features)
            elif model_type == 'gat':
                self.model = GATFraudDetector(input_features)
            elif model_type == 'graphsage':
                self.model = GraphSAGEFraudDetector(input_features)
            else:
                raise ValueError(f"Unknown model type: {model_type}")
            
            if self.device:
                self.model = self.model.to(self.device)
        else:
            logger.warning("GNN models require PyTorch Geometric")
    
    def build_wallet_graph(self, wallet_graph_data: Dict) -> Optional[Data]:
        """
        Convert wallet transaction graph to PyTorch Geometric format
        
        Args:
            wallet_graph_data: Dict with 'nodes' and 'edges'
                - nodes: Dict of wallet_addr -> features
                - edges: List of (from, to, value) tuples
                
        Returns:
            PyTorch Geometric Data object
        """
        if not HAS_TORCH or not HAS_TORCH_GEOMETRIC:
            return None
        
        try:
            nodes = wallet_graph_data.get('nodes', {})
            edges = wallet_graph_data.get('edges', [])
            
            # Create node features tensor
            node_ids = sorted(nodes.keys())
            node_features = torch.tensor(
                [nodes[addr] for addr in node_ids],
                dtype=torch.float
            )
            
            # Create edge index tensor
            addr_to_idx = {addr: idx for idx, addr in enumerate(node_ids)}
            edge_index_list = []
            
            for sender, receiver, value in edges:
                if sender in addr_to_idx and receiver in addr_to_idx:
                    edge_index_list.append([addr_to_idx[sender], addr_to_idx[receiver]])
            
            edge_index = torch.tensor(
                edge_index_list,
                dtype=torch.long
            ).t().contiguous()
            
            # Create Data object
            data = Data(x=node_features, edge_index=edge_index)
            
            return data
        except Exception as e:
            logger.error(f"Graph construction error: {e}")
            return None
    
    def predict_wallet_risk(self, wallet_graph: Data, target_wallet_idx: int) -> Dict[str, Any]:
        """
        Predict fraud risk for wallet based on network context
        
        Args:
            wallet_graph: PyTorch Geometric Data object
            target_wallet_idx: Index of wallet to score
            
        Returns:
            Risk assessment with attention weights
        """
        if not self.model or not HAS_TORCH:
            return {
                'fraud_probability': 0.0,
                'network_influence': 0.0,
                'connected_fraudsters': 0
            }
        
        try:
            self.model.eval()
            
            with torch.no_grad():
                # Forward pass
                x = wallet_graph.x.to(self.device) if self.device else wallet_graph.x
                edge_index = wallet_graph.edge_index.to(self.device) if self.device else wallet_graph.edge_index
                
                logits = self.model(x, edge_index)
                probs = torch.softmax(logits, dim=1)
                
                # Get fraud probability for target wallet
                target_fraud_prob = float(probs[target_wallet_idx, 1])  # Class 1 = fraud
                
                # Find connected fraudsters
                connected_edges = edge_index[:, edge_index[0] == target_wallet_idx]
                connected_nodes = connected_edges[1].tolist()
                
                connected_fraud_count = sum(
                    1 for node_idx in connected_nodes
                    if float(probs[node_idx, 1]) > 0.5
                )
                
                return {
                    'fraud_probability': target_fraud_prob,
                    'network_influence': float(probs[target_wallet_idx, 1]),
                    'connected_fraudsters': connected_fraud_count,
                    'total_connections': len(connected_nodes),
                    'risk_level': 'HIGH' if target_fraud_prob > 0.7 else 'MEDIUM' if target_fraud_prob > 0.4 else 'LOW'
                }
        
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                'fraud_probability': 0.0,
                'network_influence': 0.0,
                'connected_fraudsters': 0
            }
    
    def train(self, wallet_graph: Data, labels: np.ndarray,
              epochs: int = 10, lr: float = 0.001):
        """Train GNN model"""
        if not self.model or not HAS_TORCH:
            logger.error("Model not initialized")
            return
        
        try:
            optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
            criterion = nn.CrossEntropyLoss()
            
            x = wallet_graph.x.to(self.device) if self.device else wallet_graph.x
            edge_index = wallet_graph.edge_index.to(self.device) if self.device else wallet_graph.edge_index
            y = torch.tensor(labels, dtype=torch.long)
            if self.device:
                y = y.to(self.device)
            
            for epoch in range(epochs):
                self.model.train()
                optimizer.zero_grad()
                
                logits = self.model(x, edge_index)
                loss = criterion(logits, y)
                
                loss.backward()
                optimizer.step()
                
                if (epoch + 1) % 2 == 0:
                    logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {loss.item():.4f}")
            
            logger.info("✅ GNN training complete")
        except Exception as e:
            logger.error(f"Training error: {e}")


class EnsembleGNNs:
    """Ensemble of multiple GNN architectures for robust network analysis"""
    
    def __init__(self, input_features: int = 10):
        """Initialize ensemble with GCN, GAT, and GraphSAGE"""
        self.gcn = WalletNetworkGNN(model_type='gcn', input_features=input_features)
        self.gat = WalletNetworkGNN(model_type='gat', input_features=input_features)
        self.graphsage = WalletNetworkGNN(model_type='graphsage', input_features=input_features)
    
    def predict_network_risk(self, wallet_graph: Data, target_idx: int) -> Dict[str, Any]:
        """Combine predictions from all GNN models"""
        gcn_result = self.gcn.predict_wallet_risk(wallet_graph, target_idx)
        gat_result = self.gat.predict_wallet_risk(wallet_graph, target_idx)
        gs_result = self.graphsage.predict_wallet_risk(wallet_graph, target_idx)
        
        avg_fraud_prob = (
            gcn_result.get('fraud_probability', 0) +
            gat_result.get('fraud_probability', 0) +
            gs_result.get('fraud_probability', 0)
        ) / 3
        
        return {
            'ensemble_fraud_probability': avg_fraud_prob,
            'gcn_probability': gcn_result.get('fraud_probability', 0),
            'gat_probability': gat_result.get('fraud_probability', 0),
            'graphsage_probability': gs_result.get('fraud_probability', 0),
            'connected_fraudsters': max(
                gcn_result.get('connected_fraudsters', 0),
                gat_result.get('connected_fraudsters', 0),
                gs_result.get('connected_fraudsters', 0)
            ),
            'risk_level': 'HIGH' if avg_fraud_prob > 0.7 else 'MEDIUM' if avg_fraud_prob > 0.4 else 'LOW'
        }


if __name__ == "__main__":
    print("""
    Graph Neural Networks for Wallet Network Fraud Detection
    
    🕸️  Available GNN Architectures:
    - GCN (Graph Convolutional Network): Basic spectral convolution
    - GAT (Graph Attention Network): Attention-weighted aggregation
    - GraphSAGE: Scalable sampling and aggregating
    
    📌 Usage:
    from gnn_model import WalletNetworkGNN
    gnn = WalletNetworkGNN(model_type='gat')
    result = gnn.predict_wallet_risk(wallet_graph_data, target_wallet_idx)
    """)
