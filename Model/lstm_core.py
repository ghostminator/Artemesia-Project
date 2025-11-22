import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Bidirectional, Input
from tensorflow.keras.callbacks import EarlyStopping
import logging

# Suppress TF warnings
tf.get_logger().setLevel('ERROR')

class DeepModel:
    def __init__(self, input_shape, units=64):
        """
        Enhanced Bidirectional LSTM Model.
        """
        self.model = Sequential()
        
        # Input Layer
        self.model.add(Input(shape=input_shape))
        
        # Layer 1: Bidirectional LSTM (Looks at past and future context in the sequence)
        self.model.add(Bidirectional(LSTM(units=units, return_sequences=True)))
        self.model.add(Dropout(0.3)) # Increased dropout for better generalization
        
        # Layer 2: Bidirectional LSTM
        self.model.add(Bidirectional(LSTM(units=units, return_sequences=False)))
        self.model.add(Dropout(0.3))
        
        # Dense Layers for output refinement
        self.model.add(Dense(25, activation='relu'))
        
        # Output Layer
        self.model.add(Dense(1)) 
        
        # Optimizer & Loss
        # Huber loss is robust to outliers (better for stock volatility)
        self.model.compile(optimizer='adam', loss=tf.keras.losses.Huber())

    def train(self, x_train, y_train, epochs=10, batch_size=32):
        # Early stopping to stop training if loss stops improving (saves time)
        es = EarlyStopping(monitor='loss', patience=3, restore_best_weights=True)
        self.model.fit(x_train, y_train, batch_size=batch_size, epochs=epochs, verbose=0, callbacks=[es])

    def predict(self, x_input):
        return self.model.predict(x_input, verbose=0)
