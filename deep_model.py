"""
Deep Learning Models - LSTM & Transformer for Sequence Fraud Detection
Detects sophisticated sequential fraud patterns in transaction history

Models:
- LSTMFraudDetector: LSTM-based sequence pattern recognition
- TransformerFraudDetector: Self-attention based (Transformer) detection
"""

import numpy as np
import logging
from typing import Tuple, Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional deep learning libraries
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    HAS_TF = True
except ImportError:
    HAS_TF = False
    logger.warning("TensorFlow not installed. Install with: pip install tensorflow")

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not installed. Install with: pip install torch")


class LSTMFraudDetector:
    """
    Long Short-Term Memory network for transaction sequence analysis
    Detects temporal fraud patterns: rapid bursts, unusual timing, cyclic patterns
    """
    
    def __init__(self, sequence_length: int = 50, feature_dim: int = 8):
        """
        Initialize LSTM detector
        
        Args:
            sequence_length: Maximum transaction sequence length
            feature_dim: Number of features per transaction
        """
        self.sequence_length = sequence_length
        self.feature_dim = feature_dim
        self.model = None
        
        if HAS_TF:
            self._build_model()
        else:
            logger.warning("LSTM model requires TensorFlow")
    
    def _build_model(self):
        """Build TensorFlow LSTM model"""
        model = keras.Sequential([
            # LSTM encoder
            layers.LSTM(64, input_shape=(self.sequence_length, self.feature_dim),
                       return_sequences=True, dropout=0.2),
            layers.LSTM(32, return_sequences=False, dropout=0.2),
            
            # Dense layers
            layers.Dense(16, activation='relu'),
            layers.Dropout(0.3),
            layers.Dense(8, activation='relu'),
            
            # Output: fraud probability
            layers.Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', keras.metrics.Precision(), keras.metrics.Recall()]
        )
        
        self.model = model
        logger.info("✅ LSTM model built (64 -> 32 -> 16 -> 8 -> 1)")
    
    def prepare_sequence(self, transactions: list, features: np.ndarray) -> np.ndarray:
        """
        Prepare transaction sequence for model input
        
        Args:
            transactions: List of transaction dicts
            features: Feature matrix (n_tx, n_features)
            
        Returns:
            Padded/truncated sequence (sequence_length, feature_dim)
        """
        if len(features) == 0:
            return np.zeros((self.sequence_length, self.feature_dim))
        
        # Normalize features
        features = (features - features.mean(axis=0)) / (features.std(axis=0) + 1e-8)
        
        # Pad or truncate to sequence_length
        if len(features) < self.sequence_length:
            padding = np.zeros((self.sequence_length - len(features), self.feature_dim))
            sequence = np.vstack([features, padding])
        else:
            sequence = features[-self.sequence_length:]
        
        return sequence
    
    def predict(self, transactions: list, features: np.ndarray) -> Dict[str, Any]:
        """
        Predict fraud probability for transaction sequence
        
        Args:
            transactions: List of transactions
            features: Feature matrix
            
        Returns:
            Dict with fraud score and patterns detected
        """
        if not self.model or not HAS_TF:
            return {'fraud_probability': 0.0, 'patterns': []}
        
        try:
            sequence = self.prepare_sequence(transactions, features)
            sequence = np.expand_dims(sequence, axis=0)  # Add batch dimension
            
            fraud_prob = float(self.model.predict(sequence, verbose=0)[0, 0])
            
            # Detect patterns
            patterns = self._detect_patterns(transactions)
            
            return {
                'fraud_probability': fraud_prob,
                'patterns': patterns,
                'risk_level': 'HIGH' if fraud_prob > 0.7 else 'MEDIUM' if fraud_prob > 0.4 else 'LOW'
            }
        except Exception as e:
            logger.error(f"LSTM prediction error: {e}")
            return {'fraud_probability': 0.0, 'patterns': []}
    
    def _detect_patterns(self, transactions: list) -> list:
        """Detect specific fraud patterns in transaction sequence"""
        patterns = []
        
        if len(transactions) < 2:
            return patterns
        
        # Detect rapid-fire transactions
        timestamps = [int(tx.get('timeStamp', 0)) for tx in transactions]
        time_gaps = np.diff(timestamps)
        
        if np.any(time_gaps < 60):  # Less than 1 minute between txs
            patterns.append('rapid_fire_sequence')
        
        # Detect cyclic patterns
        if len(set([tx.get('to') for tx in transactions])) < len(transactions) / 2:
            patterns.append('cyclic_recipients')
        
        # Detect value spike
        amounts = [int(tx.get('value', 0)) for tx in transactions]
        if len(amounts) > 1 and max(amounts) > np.mean(amounts) * 10:
            patterns.append('value_spike')
        
        return patterns
    
    def train(self, X_train: np.ndarray, y_train: np.ndarray,
              epochs: int = 10, batch_size: int = 32):
        """Train LSTM model"""
        if not self.model:
            logger.error("Model not initialized")
            return
        
        try:
            self.model.fit(
                X_train, y_train,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=0.2,
                verbose=1
            )
            logger.info("✅ LSTM training complete")
        except Exception as e:
            logger.error(f"LSTM training error: {e}")


class TransformerFraudDetector:
    """
    Transformer model (self-attention) for fraud detection
    Better captures long-range dependencies in transaction patterns
    """
    
    def __init__(self, sequence_length: int = 50, feature_dim: int = 8,
                 num_heads: int = 4, num_layers: int = 2):
        """
        Initialize Transformer detector
        
        Args:
            sequence_length: Max transaction sequence length
            feature_dim: Features per transaction
            num_heads: Number of attention heads
            num_layers: Number of transformer layers
        """
        self.sequence_length = sequence_length
        self.feature_dim = feature_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.model = None
        
        if HAS_TF:
            self._build_model()
        else:
            logger.warning("Transformer model requires TensorFlow")
    
    def _build_model(self):
        """Build Transformer model using TensorFlow"""
        inputs = layers.Input(shape=(self.sequence_length, self.feature_dim))
        
        x = inputs
        
        # Positional encoding
        x = x + self._positional_encoding(self.sequence_length, self.feature_dim)
        
        # Multi-head attention blocks
        for _ in range(self.num_layers):
            # Multi-head attention
            attn_output = layers.MultiHeadAttention(
                num_heads=self.num_heads,
                key_dim=self.feature_dim // self.num_heads,
                dropout=0.1
            )(x, x)
            x = layers.Add()([x, attn_output])
            x = layers.LayerNormalization(epsilon=1e-6)(x)
            
            # Feed-forward
            ffn = keras.Sequential([
                layers.Dense(self.feature_dim * 4, activation='relu'),
                layers.Dense(self.feature_dim)
            ])
            ffn_output = ffn(x)
            x = layers.Add()([x, ffn_output])
            x = layers.LayerNormalization(epsilon=1e-6)(x)
        
        # Global average pooling
        x = layers.GlobalAveragePooling1D()(x)
        
        # Classification layers
        x = layers.Dense(16, activation='relu')(x)
        x = layers.Dropout(0.3)(x)
        outputs = layers.Dense(1, activation='sigmoid')(x)
        
        model = keras.Model(inputs=inputs, outputs=outputs)
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        self.model = model
        logger.info(f"✅ Transformer model built ({self.num_heads} heads, {self.num_layers} layers)")
    
    def _positional_encoding(self, seq_len: int, d_model: int) -> np.ndarray:
        """Generate positional encoding matrix"""
        position = np.arange(seq_len)[:, np.newaxis]
        div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
        
        pe = np.zeros((seq_len, d_model))
        pe[:, 0::2] = np.sin(position * div_term)
        pe[:, 1::2] = np.cos(position * div_term)
        
        return tf.constant(pe, dtype=tf.float32)
    
    def prepare_sequence(self, features: np.ndarray) -> np.ndarray:
        """Prepare sequence for Transformer"""
        if len(features) == 0:
            return np.zeros((self.sequence_length, self.feature_dim))
        
        # Normalize
        features = (features - features.mean(axis=0)) / (features.std(axis=0) + 1e-8)
        
        # Pad or truncate
        if len(features) < self.sequence_length:
            padding = np.zeros((self.sequence_length - len(features), self.feature_dim))
            sequence = np.vstack([features, padding])
        else:
            sequence = features[-self.sequence_length:]
        
        return sequence
    
    def predict(self, transactions: list, features: np.ndarray) -> Dict[str, Any]:
        """Predict fraud probability using Transformer"""
        if not self.model or not HAS_TF:
            return {'fraud_probability': 0.0, 'attention_patterns': []}
        
        try:
            sequence = self.prepare_sequence(features)
            sequence = np.expand_dims(sequence, axis=0)
            
            fraud_prob = float(self.model.predict(sequence, verbose=0)[0, 0])
            
            return {
                'fraud_probability': fraud_prob,
                'attention_patterns': self._extract_attention_patterns(),
                'risk_level': 'HIGH' if fraud_prob > 0.7 else 'MEDIUM' if fraud_prob > 0.4 else 'LOW'
            }
        except Exception as e:
            logger.error(f"Transformer prediction error: {e}")
            return {'fraud_probability': 0.0, 'attention_patterns': []}
    
    def _extract_attention_patterns(self) -> list:
        """Extract patterns from attention weights"""
        # Placeholder: in full implementation, extract from attention heads
        return []
    
    def train(self, X_train: np.ndarray, y_train: np.ndarray,
              epochs: int = 10, batch_size: int = 32):
        """Train Transformer model"""
        if not self.model:
            logger.error("Model not initialized")
            return
        
        try:
            self.model.fit(
                X_train, y_train,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=0.2,
                verbose=1
            )
            logger.info("✅ Transformer training complete")
        except Exception as e:
            logger.error(f"Transformer training error: {e}")


class EnsembleDeepModels:
    """Combine LSTM + Transformer for robust fraud detection"""
    
    def __init__(self, sequence_length: int = 50):
        """Initialize ensemble"""
        self.lstm = LSTMFraudDetector(sequence_length=sequence_length)
        self.transformer = TransformerFraudDetector(sequence_length=sequence_length)
    
    def predict(self, transactions: list, features: np.ndarray) -> Dict[str, Any]:
        """
        Combine predictions from both models
        Average probabilities for robust score
        """
        lstm_result = self.lstm.predict(transactions, features)
        transformer_result = self.transformer.predict(transactions, features)
        
        avg_fraud_prob = (lstm_result.get('fraud_probability', 0) +
                         transformer_result.get('fraud_probability', 0)) / 2
        
        all_patterns = list(set(
            lstm_result.get('patterns', []) +
            transformer_result.get('attention_patterns', [])
        ))
        
        return {
            'ensemble_fraud_probability': avg_fraud_prob,
            'lstm_probability': lstm_result.get('fraud_probability', 0),
            'transformer_probability': transformer_result.get('fraud_probability', 0),
            'detected_patterns': all_patterns,
            'risk_level': 'HIGH' if avg_fraud_prob > 0.7 else 'MEDIUM' if avg_fraud_prob > 0.4 else 'LOW'
        }


# ============ UTILITY FUNCTIONS ============

def create_feature_sequences(transactions: list, window_size: int = 50) -> np.ndarray:
    """
    Convert transaction sequence into feature matrix
    
    Args:
        transactions: List of transaction dicts
        window_size: Sequence length
        
    Returns:
        Feature array (n_sequences, window_size, n_features)
    """
    features = []
    
    for tx in transactions:
        amount = int(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18)))
        timestamp = int(tx.get('timeStamp', 0))
        
        features.append([
            np.log1p(amount),  # Log-normalized value
            int(tx.get('isError', 0)),  # Error flag
            len(tx.get('from', '')),  # Sender addr length
            len(tx.get('to', '')),  # Receiver addr length
            # Add more features as needed (20+ total)
        ])
    
    if not features:
        return np.zeros((1, window_size, 4))
    
    features = np.array(features)
    
    # Pad to window size
    if len(features) < window_size:
        padding = np.zeros((window_size - len(features), features.shape[1]))
        features = np.vstack([features, padding])
    else:
        features = features[-window_size:]
    
    return np.expand_dims(features, axis=0)


if __name__ == "__main__":
    print("""
    Deep Learning Models for Fraud Detection
    
    📊 Available Models:
    - LSTMFraudDetector: LSTM sequence processing
    - TransformerFraudDetector: Self-attention architecture
    - EnsembleDeepModels: Combined predictions
    
    📌 Usage:
    from deep_model import LSTMFraudDetector
    detector = LSTMFraudDetector(sequence_length=50)
    result = detector.predict(transactions, features)
    """)
