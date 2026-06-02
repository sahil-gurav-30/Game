# 💀 Survival Chase — AI-Driven Maze Game

Survival Chase is an interactive, retro-futuristic arcade game built using a **Flask** backend paired with a vanilla **HTML5 Canvas** frontend. The game places a player in a randomly generated $20 \times 20$ grid filled with obstacle walls and patrolling enemies. The enemies use a Finite State Machine (FSM) combined with optimal $A^*$ pathfinding to track, corner, and eliminate the player.

---

## ✨ Features

* **Optimal $A^*$ Pathfinding:** When tracking the player, enemies calculate the shortest viable path over a 4-directional grid using an admissible Manhattan distance heuristic.
* **FSM Enemy Behavior:** Enemies seamlessly switch between states:
* `WANDER`: Player is out of range; the enemy takes casual random steps to patrol the maze.
* `CHASE`: Player enters a $7$-tile radius; the enemy actively pursues using $A^*$ paths.


* **Dynamic Map Generation:** Automatically maps a custom layout with a dense structural variance (~22% wall coverage) while keeping spawn points and corners accessible.
* **Retro CRT Aesthetic:** Implements a localized cyberpunk terminal feel using scanline filters, flickering overlays, font packages (*Orbitron* and *Share Tech Mono*), and responsive neon canvas glows.
* **Dual-Input Mechanics:** Fully responsive gameplay across devices via event listeners for desktop keyboards (`WASD`/Arrows) and mobile touch interaction via a virtual D-Pad.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.x, Flask
* **Frontend:** HTML5 (Canvas API), CSS3, JavaScript (ES6+ Vanilla)
* **Mathematical Operations:** Priority queue data optimization (`heapq`), Euclidean space tracking, and coordinate distance mappings.

---

## 📁 Project Structure

```text
survival-chase/
│
├── Maze.py                 # Flask app, random map generators, and A* / FSM logic
├── templates/
│   └── Maze.html           # Main markup layout with HUD structure & control overlays
└── static/
    ├── css/
    │   └── style2.css      # Terminal CRT styling formulas, glowing palettes, and D-Pad design
    └── js/
        └── maze.js         # Canvas rendering loops, responsive updates, and API move sync

```

---

## 🚀 Getting Started

Follow these steps to host and run the Survival Chase simulation locally.

### 1. Requirements

Make sure you have Python 3 installed on your workstation:

```bash
python --version

```

### 2. Dependencies

Install Flask if it's missing from your Python runtime environment:

```bash
pip install Flask

```

### 3. Execution

Initialize the main game server script from your terminal:

```bash
python Maze.py

```

### 4. Play the Game

Open your web browser and navigate to the local hosting endpoint:

```text
http://127.0.0.1:5000/

```

---

## 🧠 Algorithmic Properties

### $A^*$ Pathfinding Complexity

* **Time Complexity:** $\mathcal{O}(V \log V)$ worst-case on grid dimensions, simplifying to $\mathcal{O}(N^2 \log N)$ where $N$ is the side length of the grid. On this $20 \times 20$ board, it optimizes tracking rapidly.
* **Space Complexity:** $\mathcal{O}(V)$ where $V \le 400$ total grid cell references cached into mapping lists.

### Manhattan Distance Heuristic

To determine cell tracking costs without computing diagonal shortcuts (which are forbidden in this maze's movement rules), the system enforces:

$$h(n) = |n.\text{row} - \text{goal}.\text{row}| + |n.\text{col} - \text{goal}.\text{col}|$$
