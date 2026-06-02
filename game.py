import random
import heapq
import math
from flask import Flask, jsonify, request, render_template

app = Flask(__name__)

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
GRID_SIZE = 20
WALL_DENSITY = 0.22        # ~22 % of cells are walls
CHASE_RADIUS = 7           # tiles; triggers Chase FSM state
NUM_ENEMIES = 3
WANDER_INTERVAL = 2        # enemy moves every N player moves while wandering

# Global mutable game state (single-session demo; extend with sessions for multi-user)
game_state = {}


# ═══════════════════════════════════════════════════════════════════════════════
#  A* PATHFINDING
#  ─────────────────────────────────────────────────────────────────────────────
#  A* is a best-first graph-search algorithm that finds the shortest path from a
#  start node to a goal node.  It extends Dijkstra's algorithm by adding a
#  heuristic h(n) that estimates the remaining cost to the goal, making it both
#  complete and optimal when the heuristic is *admissible* (never over-estimates).
#
#  Time  complexity : O(E log V) in the worst case, where V = number of open nodes
#                     and E = edges explored.  On a uniform grid with an admissible
#                     heuristic this is O(N²) in the worst case (N = grid side).
#
#  Space complexity : O(V) — we store every node ever added to the open/closed set.
#                     On a 20×20 grid the maximum footprint is 400 nodes.
#
#  Heuristic used   : Manhattan distance — the sum of the absolute differences in
#                     row and column coordinates:
#                         h(n) = |n.row − goal.row| + |n.col − goal.col|
#                     This is *admissible* on a 4-directional grid because every
#                     path must traverse at least that many steps; it never counts
#                     diagonal shortcuts that do not exist in our movement model.
#                     It is also *consistent* (monotone), so each node is processed
#                     at most once — the closed-set check is a minor optimisation
#                     that becomes correct under consistency.
# ═══════════════════════════════════════════════════════════════════════════════

def heuristic(a, b):
    """
    Manhattan distance between two grid cells.

    Parameters
    ----------
    a : (int, int)  — (row, col) of the current node
    b : (int, int)  — (row, col) of the goal node

    Returns
    -------
    int  — admissible heuristic cost estimate (never over-estimates on a
           4-directional grid because diagonal moves are forbidden).
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(grid, start, goal):
    """
    Find the shortest passable path from *start* to *goal* on a 2-D grid.

    Algorithm outline
    -----------------
    1. Maintain an *open set* (min-heap) of (f, g, node) tuples.
       f = g + h  where:
         g = exact cost from start to this node (= steps taken so far)
         h = heuristic estimate from this node to the goal (Manhattan distance)
    2. Pop the node with the lowest f each iteration — this is the "most
       promising" unexplored node.
    3. If it is the goal, reconstruct and return the path.
    4. Otherwise, expand its four neighbours (up/down/left/right).  Skip walls
       and already-closed nodes.  If we find a shorter g for an already-open
       node, push a new entry (lazy deletion — stale entries are discarded when
       popped).
    5. Return an empty list if the goal is unreachable.

    Parameters
    ----------
    grid  : list[list[int]]  — 2-D grid; 1 = wall, 0 = passable
    start : (int, int)       — (row, col) start position
    goal  : (int, int)       — (row, col) goal position

    Returns
    -------
    list[(int, int)]  — ordered path from start (exclusive) to goal (inclusive),
                        or [] if no path exists.

    Complexity (summary)
    --------------------
    Time  : O(N² log N²) worst case on an N×N grid  ≡  O(N² log N)
    Space : O(N²)
    """

    # ── Edge case: start == goal ──────────────────────────────────────────────
    if start == goal:
        return []

    rows, cols = len(grid), len(grid[0])

    # ── Open set: min-heap of (f_score, g_score, (row, col)) ─────────────────
    # Python's heapq is a min-heap, so the node with the lowest f is always
    # popped first — exactly the node we want to expand next.
    open_heap = []
    heapq.heappush(open_heap, (0 + heuristic(start, goal), 0, start))

    # ── Tracking structures ───────────────────────────────────────────────────
    came_from = {}                     # node → predecessor (for path reconstruction)
    g_score   = {start: 0}            # best known cost from start to each node
    closed    = set()                  # nodes already fully expanded

    # Four cardinal directions: (Δrow, Δcol)
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    while open_heap:
        # ── Pop the most promising node (lowest f) ────────────────────────────
        f, g, current = heapq.heappop(open_heap)

        # Skip stale heap entries (lazy deletion)
        if current in closed:
            continue
        closed.add(current)

        # ── Goal reached → reconstruct path ──────────────────────────────────
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            return path          # path[0] is the first step after `start`

        # ── Expand neighbours ─────────────────────────────────────────────────
        for dr, dc in directions:
            neighbour = (current[0] + dr, current[1] + dc)
            nr, nc = neighbour

            # Bounds check
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            # Wall check
            if grid[nr][nc] == 1:
                continue
            # Already expanded (closed)
            if neighbour in closed:
                continue

            # g+1: every step costs exactly 1 (uniform-cost grid)
            tentative_g = g + 1

            # Only consider this path if it is strictly better than what we know
            if tentative_g < g_score.get(neighbour, float('inf')):
                g_score[neighbour] = tentative_g
                came_from[neighbour] = current
                f_new = tentative_g + heuristic(neighbour, goal)
                heapq.heappush(open_heap, (f_new, tentative_g, neighbour))

    # Goal unreachable
    return []


# ─────────────────────────────────────────────
#  MAP GENERATION
# ─────────────────────────────────────────────

def generate_grid():
    """Return a GRID_SIZE×GRID_SIZE grid with random walls.
    Guarantees the four corners are always free (spawn-safe zones).
    """
    grid = []
    for r in range(GRID_SIZE):
        row = []
        for c in range(GRID_SIZE):
            # Keep corners passable so spawn points are never walled in
            corner = (r in (0, 1) and c in (0, 1)) or \
                     (r in (0, 1) and c in (GRID_SIZE - 2, GRID_SIZE - 1)) or \
                     (r in (GRID_SIZE - 2, GRID_SIZE - 1) and c in (0, 1)) or \
                     (r in (GRID_SIZE - 2, GRID_SIZE - 1) and c in (GRID_SIZE - 2, GRID_SIZE - 1))
            if corner:
                row.append(0)
            else:
                row.append(1 if random.random() < WALL_DENSITY else 0)
        grid.append(row)
    return grid


def random_free_cell(grid, excluded=None):
    """Pick a random passable cell not already in *excluded*."""
    excluded = excluded or []
    attempts = 0
    while attempts < 10000:
        r = random.randint(0, GRID_SIZE - 1)
        c = random.randint(0, GRID_SIZE - 1)
        if grid[r][c] == 0 and (r, c) not in excluded:
            return (r, c)
        attempts += 1
    # Fallback: scan sequentially
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] == 0 and (r, c) not in excluded:
                return (r, c)
    return (0, 0)


# ─────────────────────────────────────────────
#  FINITE STATE MACHINE (FSM) HELPERS
# ─────────────────────────────────────────────

def euclidean_dist(a, b):
    return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)


def enemy_wander(enemy, grid):
    """Return a random valid neighbour for the wandering enemy."""
    r, c = enemy['pos']
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    random.shuffle(directions)
    for dr, dc in directions:
        nr, nc = r + dr, c + dc
        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE and grid[nr][nc] == 0:
            return (nr, nc)
    return (r, c)   # stuck — stay put


def fsm_update_enemy(enemy, player_pos, grid):
    """
    FSM with two states:
      WANDER  – player is outside CHASE_RADIUS; enemy moves randomly.
      CHASE   – player is within CHASE_RADIUS; enemy uses A* to close in.

    Transitions:
      WANDER → CHASE : dist(enemy, player) ≤ CHASE_RADIUS
      CHASE  → WANDER: dist(enemy, player) > CHASE_RADIUS
    """
    dist = euclidean_dist(tuple(enemy['pos']), tuple(player_pos))

    if dist <= CHASE_RADIUS:
        enemy['state'] = 'CHASE'
        path = astar(grid, tuple(enemy['pos']), tuple(player_pos))
        if path:
            enemy['pos'] = list(path[0])
        # If A* finds no path (fully enclosed), fall back to wander
        else:
            enemy['pos'] = list(enemy_wander(enemy, grid))
    else:
        enemy['state'] = 'WANDER'
        # Rate-limit wander moves so wandering enemies feel slower
        enemy['wander_tick'] = enemy.get('wander_tick', 0) + 1
        if enemy['wander_tick'] >= WANDER_INTERVAL:
            enemy['wander_tick'] = 0
            enemy['pos'] = list(enemy_wander(enemy, grid))

    return enemy


# ─────────────────────────────────────────────
#  FLASK ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('Maze.html')


@app.route('/api/new_game', methods=['POST'])
def new_game():
    """Initialise (or re-initialise) the game state."""
    grid = generate_grid()
    occupied = []

    player_pos = random_free_cell(grid, occupied)
    occupied.append(player_pos)

    enemies = []
    for _ in range(NUM_ENEMIES):
        # Ensure enemies spawn at least 6 tiles away from the player
        for _ in range(200):
            pos = random_free_cell(grid, occupied)
            if euclidean_dist(pos, player_pos) >= 6:
                break
        occupied.append(pos)
        enemies.append({'pos': list(pos), 'state': 'WANDER', 'wander_tick': 0})

    # Place an exit tile far from the player
    exit_pos = random_free_cell(grid, occupied)
    for _ in range(200):
        candidate = random_free_cell(grid, occupied)
        if euclidean_dist(candidate, player_pos) > euclidean_dist(exit_pos, player_pos):
            exit_pos = candidate

    game_state.clear()
    game_state.update({
        'grid': grid,
        'player': list(player_pos),
        'enemies': enemies,
        'exit': list(exit_pos),
        'status': 'playing',   # 'playing' | 'dead' | 'escaped'
        'moves': 0,
    })

    return jsonify(sanitise_state())


@app.route('/api/move', methods=['POST'])
def move():
    """Process a player move then advance all enemies."""
    if game_state.get('status') != 'playing':
        return jsonify(sanitise_state())

    data      = request.get_json(force=True)
    direction = data.get('direction', '')   # 'up' | 'down' | 'left' | 'right'

    grid = game_state['grid']
    pr, pc = game_state['player']

    delta = {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}
    if direction in delta:
        dr, dc = delta[direction]
        nr, nc = pr + dr, pc + dc
        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE and grid[nr][nc] == 0:
            game_state['player'] = [nr, nc]
            game_state['moves'] += 1

    # ── Advance every enemy via FSM ───────────────────────────────────────────
    player_pos = game_state['player']
    for i, enemy in enumerate(game_state['enemies']):
        game_state['enemies'][i] = fsm_update_enemy(enemy, player_pos, grid)

    # ── Collision detection ───────────────────────────────────────────────────
    for enemy in game_state['enemies']:
        if enemy['pos'] == game_state['player']:
            game_state['status'] = 'dead'
            break

    # ── Win condition ─────────────────────────────────────────────────────────
    if game_state['status'] == 'playing' and game_state['player'] == game_state['exit']:
        game_state['status'] = 'escaped'

    return jsonify(sanitise_state())


def sanitise_state():
    """Return a JSON-safe snapshot (lists only, no internal tick counters)."""
    enemies_out = [
        {'pos': e['pos'], 'state': e['state']}
        for e in game_state.get('enemies', [])
    ]
    return {
        'grid':   game_state.get('grid', []),
        'player': game_state.get('player', [0, 0]),
        'enemies': enemies_out,
        'exit':   game_state.get('exit', [0, 0]),
        'status': game_state.get('status', 'playing'),
        'moves':  game_state.get('moves', 0),
    }


if __name__ == '__main__':
    app.run(debug=True)
