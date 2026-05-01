import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import joblib

# ================= LOAD DATA =================
df = pd.read_csv("dataset.csv")
print("Dataset loaded:", df.shape)

# ================= DATA PREPROCESSING =================

# Remove missing values
df = df.dropna()

# Keep only attack actions
df = df[df["action_type"] == "attack"]

# Remove unrealistic values (outliers)
df = df[
    (df["my_speed"] < 200) &
    (df["opp_speed"] < 200) &
    (df["max_my_damage"] < 500) &
    (df["max_opp_damage"] < 500)
]

# Shuffle dataset
df = df.sample(frac=1, random_state=42)

print("After preprocessing:", df.shape)

# ================= FEATURES =================

features = [
    "my_hp",
    "opp_hp",
    "my_speed",
    "opp_speed",
    "faster",
    "max_my_damage",
    "max_opp_damage",
]

X = df[features]
y = df["move_id"]

# ================= ENCODING =================

encoder = LabelEncoder()
y_encoded = encoder.fit_transform(y)

# ================= TRAIN TEST SPLIT =================

X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.4, random_state=42
)

# ================= MODEL =================

model = RandomForestClassifier(
    n_estimators=40,
    max_depth=3,
    min_samples_split=20,
    min_samples_leaf=10,
    class_weight="balanced",
    random_state=42
)

# ================= TRAIN =================

model.fit(X_train, y_train)

# ================= EVALUATE =================

train_acc = model.score(X_train, y_train)
test_acc = model.score(X_test, y_test)

print("Training Accuracy:", round(train_acc, 3))
print("Testing Accuracy:", round(test_acc, 3))
# ================= FEATURE IMPORTANCE =================

print("\nFeature Importance:")
for name, val in zip(X.columns, model.feature_importances_):
    print(f"{name}: {round(val,4)}")

# ================= SAVE MODEL =================

joblib.dump(model, "model.pkl")
joblib.dump(encoder, "encoder.pkl")

print("Model saved!")

# ================= GRAPHS =================

# Accuracy Graph
plt.figure()
plt.bar(["Train", "Test"], [train_acc, test_acc])
plt.title("Training vs Testing Accuracy")
plt.ylim(0, 1)
plt.savefig("accuracy_comparison.png")
plt.close()

# Feature Importance
plt.figure()
plt.barh(features, model.feature_importances_)
plt.title("Feature Importance")
plt.savefig("feature_importance.png")
plt.close()

# Move Distribution
plt.figure()
df["move_id"].value_counts().head(10).plot(kind="bar")
plt.title("Top Moves Distribution")
plt.savefig("move_distribution.png")
plt.close()

# ================= WINRATE =================

y_pred = model.predict(X_test)
winrate = (y_pred == y_test).mean()

print("Winrate:", round(winrate, 3))