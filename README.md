# Pokémon Battle AI (ML Project)

## 📌 Overview
This project builds an AI system that predicts optimal moves in Pokémon battles using Machine Learning.

The base battle simulation environment was provided by the Tryst IIT Delhi competition. On top of that, we built intelligent agents capable of learning and improving battle strategies.

---

## ❓ What Problem Does This Solve?
In a Pokémon battle, selecting the best move at each turn is difficult because it depends on multiple factors:
- Current HP of both Pokémon
- Speed comparison (who attacks first)
- Damage potential of moves
- Opponent’s possible actions

This project aims to:
- Learn patterns from battle simulations
- Predict the best move automatically

---

## ⚙️ System Overview

The system consists of two main components:

### 1. Rule-Based AI (AI1)
This AI uses manually defined logic:
- Calculates damage for all available moves
- Compares speed to determine turn order
- Predicts if a move can knock out the opponent

It selects the move with the highest expected effectiveness.

---

### 2. Machine Learning AI (AI5)
- Uses data generated from simulated battles
- Trains a model to learn decision patterns
- Predicts the best move based on current battle state

This enables smarter decisions beyond fixed rules.

---

## 📊 Dataset Generation

The dataset is generated automatically by running battle simulations between AI agents.

Each row represents a battle decision and includes:
- `my_hp` → your Pokémon’s health
- `opp_hp` → opponent’s health
- `my_speed`, `opp_speed`
- `max_my_damage`, `max_opp_damage`
- `move_id` → selected move

Stored in:
```
client/dataset.csv
```

---

## 🧠 Machine Learning Pipeline

1. Load dataset  
2. Remove missing/invalid values  
3. Filter only attack actions  
4. Remove outliers  
5. Select relevant features  
6. Encode move labels  
7. Train-test split (60-40)  
8. Train Random Forest model  
9. Evaluate performance  

---

## 🤖 Model Details

- **Algorithm:** Random Forest Classifier  
- **Why chosen:**
  - Handles complex patterns well  
  - Works effectively on structured data  
  - Fast and reliable  

---

## 🚀 How to Run

### 1. Train the model
```bash
cd client
python3 train_model.py
```

### 2. Test the model
```bash
python3 test_model.py
```

### 3. Run battle simulation
```bash
python3 driver.py battle ai1 ai2 -n 10
```

---

## 🔧 Customization

Modify AI strategies in:
```
client/ai.py
```

You can:
- Add new AI strategies (AI2, AI3, etc.)
- Improve decision logic
- Generate better training data

---

## 🌐 Optional Server Setup

Original framework:
https://github.com/Aries-IITD/Tryst-RL-Codebase

To run the local server:
```bash
node pokemon-showdown 7850 --no-security
```

Open in browser:
```
http://localhost:7850
```

---

## 📊 Features Used

- `my_hp`
- `opp_hp`
- `my_speed`
- `opp_speed`
- `faster`
- `max_my_damage`
- `max_opp_damage`

---

## 🎥 Demo

https://youtu.be/af5FeGHQ6FY

---

## 🙏 Acknowledgment

Base framework provided by Tryst IIT Delhi  
https://github.com/Aries-IITD/Tryst-RL-Codebase

---

## 👤 Author

Garv Chanana