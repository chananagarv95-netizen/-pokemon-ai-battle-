# Pokémon Battle AI (ML Project)

## 📌 Overview
This project builds an AI system that predicts optimal moves in Pokémon battles using Machine Learning.

The base battle simulation framework was provided by the Tryst IIT Delhi competition. This project extends that framework by implementing custom AI strategies and integrating a machine learning model for intelligent decision-making.

---

## 🎥 Demo Video
https://youtu.be/af5FeGHQ6FY

---

## 🔗 GitHub Repository
https://github.com/chananagarv95-netizen/-pokemon-ai-battle-

---

## ⚙️ My Contributions
- Implemented multiple AI strategies (AI1, AI2, AI3…)
- Built a rule-based AI (AI1) using damage + speed logic
- Created a dataset from simulated battles
- Developed a machine learning pipeline
- Trained a Random Forest model to predict optimal moves
- Evaluated model performance (training/testing accuracy)

---

## 🧠 How It Works

### 1. Rule-Based AI (AI1)
- Calculates damage
- Compares speed
- Predicts KO
- Chooses best move

### 2. Machine Learning Model (AI5)
- Learns from battle data
- Uses Random Forest
- Predicts best move based on state

---

## 📊 Dataset
Generated using battle simulations.

Features used:
- my_hp  
- opp_hp  
- my_speed  
- opp_speed  
- faster  
- max_my_damage  
- max_opp_damage  

---

## 🚀 Running the Project

This project includes all dependencies (node_modules) so the server can run directly.

---

## 🖥️ Start Pokémon Showdown Server

### Linux / Mac
./pokemon-showdown 7850 --no-security

### Windows
node pokemon-showdown 7850 --no-security

---

## 🌐 Open UI
http://localhost:7850

---

## ⚠️ Requirements
- Node.js (v21.1.0 recommended)
- Python 3

---

## 🤖 Run AI Client

Navigate to client folder:
cd client pip install -r requirements.txt

Run help:
python3 driver.py -h

---

## ⚔️ Run Battle

Example:
python3 driver.py battle ai1 ai2 --n 10

---

## 🧪 Challenge Bots

Example:
python3 driver.py challenge ai1 5ccf9bAIPly11 --replay

Bot IDs:
- 5ccf9bAIPly11  
- 2d8493AIPly11  
- b815fcAIPly11  
- e75c45AIPly11  

---

## ⚙️ Configuration

Edit:
client/env.txt

- Set server port  
- Set connection settings  

---

## 🔧 Custom AI

Modify:
client/ai.py

Add your own strategies (ai2, ai3, etc.)

---

## 📁 Notes

- Full server + dependencies are included for direct execution  
- If any module error occurs:
pip install poke_env

---

## 🙏 Acknowledgment
Base framework provided by:
https://github.com/Aries-IITD/Tryst-RL-Codebase  

Poke-Env:
https://github.com/hsahovic/poke-env  

---

## 👤 Author
Garv 