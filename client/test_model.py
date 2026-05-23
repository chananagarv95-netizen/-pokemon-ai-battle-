import joblib
import pandas as pd

print("\n===================================")
print("      REAL-TIME MOVE PREDICTION")
print("===================================\n")

# Load model
print("[LOADING] Loading trained model...")

model = joblib.load("model.pkl")
encoder = joblib.load("encoder.pkl")

print("[SUCCESS] Model loaded successfully!\n")

# Battle state input
sample = pd.DataFrame([{
    "my_hp": 80,
    "opp_hp": 60,
    "my_speed": 100,
    "opp_speed": 90,
    "faster": 1,
    "max_my_damage": 120,
    "max_opp_damage": 80
}])

print("===================================")
print("        CURRENT BATTLE STATE")
print("===================================\n")

for col in sample.columns:
    print(f"{col:<20}: {sample.iloc[0][col]}")

print("\n[PREDICTION] Evaluating best move...\n")

# Predict move
prediction = model.predict(sample)

# Decode prediction
move = encoder.inverse_transform(prediction)

print("===================================")
print("         PREDICTION RESULT")
print("===================================\n")

print(f"Recommended Move : {move[0]}")

print("\n[SUCCESS] Prediction completed!\n")