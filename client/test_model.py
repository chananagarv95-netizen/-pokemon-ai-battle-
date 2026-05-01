import joblib
import pandas as pd

# Load model
model = joblib.load("model.pkl")
encoder = joblib.load("encoder.pkl")

print("Model loaded successfully!")

# Create input with feature names (IMPORTANT)
sample = pd.DataFrame([{
    "my_hp": 80,
    "opp_hp": 60,
    "my_speed": 100,
    "opp_speed": 90,
    "faster": 1,
    "max_my_damage": 120,
    "max_opp_damage": 80
}])

# Predict
prediction = model.predict(sample)
move = encoder.inverse_transform(prediction)

print("Predicted Move:", move[0])