import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib

# ================= LOAD DATA =================

print("\n===================================")
print("      POKEMON AI MODEL TRAINING")
print("===================================\n")

df = pd.read_csv("dataset.csv")

print(f"[INFO] Dataset loaded successfully")
print(f"[INFO] Shape: {df.shape}\n")

# ================= DATA PREPROCESSING =================

print("===================================")
print("        DATA PREPROCESSING")
print("===================================\n")

# Remove missing values
before_rows = len(df)
df = df.dropna()
print(f"[CLEANING] Removed missing values: {before_rows - len(df)} rows")

# Keep only attack actions
before_rows = len(df)
df = df[df["action_type"] == "attack"]
print(f"[FILTER] Kept attack actions only: {len(df)} rows")

# Remove unrealistic values (outliers)
before_rows = len(df)

df = df[
    (df["my_speed"] < 200) &
    (df["opp_speed"] < 200) &
    (df["max_my_damage"] < 500) &
    (df["max_opp_damage"] < 500)
]

print(f"[OUTLIERS] Removed unrealistic rows: {before_rows - len(df)}")
print(f"[INFO] Final dataset shape: {df.shape}\n")

# Shuffle dataset
df = df.sample(frac=1, random_state=42)

print("[SUCCESS] Dataset preprocessing completed!\n")

# ================= FEATURES =================

print("===================================")
print("        FEATURE ENGINEERING")
print("===================================\n")

features = [
    "my_hp",
    "opp_hp",
    "my_speed",
    "opp_speed",
    "faster",
    "max_my_damage",
    "max_opp_damage",
]

print("[FEATURES USED]")
for f in features:
    print(f" - {f}")

X = df[features]
y = df["move_id"]

print(f"\n[INFO] Total features selected: {len(features)}\n")

# ================= ENCODING =================

print("===================================")
print("         LABEL ENCODING")
print("===================================\n")

print("[ENCODING] Encoding move labels...\n")

encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)

print(f"[INFO] Total unique moves encoded: {len(encoder.classes_)}\n")

# ================= TRAIN TEST SPLIT =================

print("===================================")
print("         TRAIN TEST SPLIT")
print("===================================\n")

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y_encoded,
    test_size=0.4,
    random_state=42
)

print(f"[TRAINING DATA] {len(X_train)} samples")
print(f"[TESTING DATA]  {len(X_test)} samples")
print(f"[TRAIN RATIO]   60%")
print(f"[TEST RATIO]    40%\n")

# ================= MODEL =================

print("===================================")
print("       RANDOM FOREST MODEL")
print("===================================\n")

model = RandomForestClassifier(
    n_estimators=40,
    max_depth=3,
    min_samples_split=20,
    min_samples_leaf=10,
    class_weight="balanced",
    random_state=42
)

print("[MODEL CONFIGURATION]")
print(" - Algorithm           : Random Forest")
print(" - Trees               : 40")
print(" - Max Depth           : 3")
print(" - Min Samples Split   : 20")
print(" - Min Samples Leaf    : 10")
print(" - Balanced Classes    : Enabled")
print(" - Random State        : 42\n")

# ================= TRAIN =================

print("===================================")
print("          MODEL TRAINING")
print("===================================\n")

print("[TRAINING] Training model...\n")

model.fit(X_train, y_train)

print("[SUCCESS] Model training completed successfully!\n")

# ================= EVALUATE =================

print("===================================")
print("         MODEL EVALUATION")
print("===================================\n")

train_acc = model.score(X_train, y_train)
test_acc = model.score(X_test, y_test)

print(f"Training Accuracy : {round(train_acc * 100, 2)}%")
print(f"Testing Accuracy  : {round(test_acc * 100, 2)}%")

gap = abs(train_acc - test_acc)

print(f"Accuracy Gap      : {round(gap * 100, 2)}%")

if gap < 0.05:
    print("[STATUS] Model generalization looks stable\n")
else:
    print("[STATUS] Possible overfitting detected\n")

# ================= FEATURE IMPORTANCE =================

print("===================================")
print("       FEATURE IMPORTANCE")
print("===================================\n")

sorted_features = sorted(
    zip(X.columns, model.feature_importances_),
    key=lambda x: x[1],
    reverse=True
)

for name, val in sorted_features:
    print(f"{name:<20} : {round(val,4)}")

# ================= SAVE MODEL =================

print("\n===================================")
print("          SAVING FILES")
print("===================================\n")

joblib.dump(model, "model.pkl")
joblib.dump(encoder, "encoder.pkl")

print("[SAVED] model.pkl")
print("[SAVED] encoder.pkl")

# ================= GRAPHS =================

print("\n===================================")
print("         GENERATING GRAPHS")
print("===================================\n")

# Accuracy Graph
plt.figure(figsize=(5, 4))
plt.bar(["Train", "Test"], [train_acc, test_acc])
plt.title("Training vs Testing Accuracy")
plt.ylim(0, 1)
plt.savefig("accuracy_comparison.png")
plt.close()

print("[GRAPH SAVED] accuracy_comparison.png")

# Feature Importance Graph
plt.figure(figsize=(7, 5))
plt.barh(features, model.feature_importances_)
plt.title("Feature Importance")
plt.savefig("feature_importance.png")
plt.close()

print("[GRAPH SAVED] feature_importance.png")

# Move Distribution Graph
plt.figure(figsize=(8, 5))
df["move_id"].value_counts().head(10).plot(kind="bar")
plt.title("Top Moves Distribution")
plt.savefig("move_distribution.png")
plt.close()

print("[GRAPH SAVED] move_distribution.png")

# ================= WINRATE =================

y_pred = model.predict(X_test)
winrate = (y_pred == y_test).mean()

print("\n===================================")
print("          FINAL RESULTS")
print("===================================\n")

print(f"Approx Winrate    : {round(winrate * 100, 2)}%")
print(f"Training Accuracy : {round(train_acc * 100, 2)}%")
print(f"Testing Accuracy  : {round(test_acc * 100, 2)}%")

print("\n===================================")
print("        TRAINING COMPLETED")
print("===================================\n")

print("[SUCCESS] Pokemon AI training pipeline completed successfully!\n")