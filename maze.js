/* ═══════════════════════════════════════════════════
   SURVIVAL CHASE  ·  game.js
   Responsibilities:
     1. Bootstrap / new-game fetch
     2. Canvas rendering (CSS Grid-style cells on Canvas)
     3. Keyboard + D-Pad input capture
     4. Asynchronous move loop (fetch → render)
     5. Overlay management (game-over / win screens)
   ═══════════════════════════════════════════════════ */

'use strict';

// ── DOM references ─────────────────────────────────────────────────────────
const canvas       = document.getElementById('gameCanvas');
const ctx          = canvas.getContext('2d');
const overlay      = document.getElementById('overlay');
const overlayIcon  = document.getElementById('overlay-icon');
const overlayTitle = document.getElementById('overlay-title');
const overlaySub   = document.getElementById('overlay-sub');
const btnRestart   = document.getElementById('btn-restart');
const moveCount    = document.getElementById('move-count');
const gameStatus   = document.getElementById('game-status');

// ── Canvas / cell size ─────────────────────────────────────────────────────
const GRID  = 20;     // must match Python GRID_SIZE
let   CELL  = 20;     // px per cell — recalculated on resize

/**
 * Recompute CELL so the canvas fills ~90 vw on mobile or up to 440 px on desktop,
 * while always using an integer number of pixels per cell (crisp rendering).
 */
function computeCell() {
  const maxPx = Math.min(
    window.innerWidth  * 0.92,
    window.innerHeight * 0.52,
    440
  );
  CELL = Math.floor(maxPx / GRID);
  canvas.width  = CELL * GRID;
  canvas.height = CELL * GRID;
}

// ── Colour palette (mirrors CSS variables but defined here for Canvas use) ──
const C = {
  bg:           '#050a0f',
  wall:         '#0a1825',
  wallEdge:     '#0d2035',
  free:         '#060d14',
  grid:         '#0a1520',
  player:       '#00ff9d',
  playerGlow:   '#00ff9d',
  enemyChase:   '#ff3c5a',
  enemyWander:  '#ff8c00',
  exit:         '#b060ff',
  exitGlow:     '#b060ff',
  overlayText:  '#c8e8ff',
};

// ── Game state cache (populated by API) ────────────────────────────────────
let state      = null;   // { grid, player, enemies, exit, status, moves }
let busy       = false;  // prevent concurrent fetch calls
let animFrame  = null;

// ═══════════════════════════════════════════════════════════════════════════
//  RENDERING
// ═══════════════════════════════════════════════════════════════════════════

/** Draw everything to the canvas from the current `state`. */
function render() {
  if (!state) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  drawGrid();
  drawExit();
  drawEnemies();
  drawPlayer();
}

/** Draw all 20×20 cells. */
function drawGrid() {
  const { grid } = state;
  for (let r = 0; r < GRID; r++) {
    for (let c = 0; c < GRID; c++) {
      const x = c * CELL;
      const y = r * CELL;
      if (grid[r][c] === 1) {
        // Wall – layered fill + subtle highlight on top edge
        ctx.fillStyle = C.wall;
        ctx.fillRect(x, y, CELL, CELL);
        ctx.fillStyle = C.wallEdge;
        ctx.fillRect(x, y, CELL, 1);
        ctx.fillRect(x, y, 1, CELL);
      } else {
        // Passable floor
        ctx.fillStyle = C.free;
        ctx.fillRect(x, y, CELL, CELL);
        // Faint grid lines
        ctx.strokeStyle = C.grid;
        ctx.lineWidth = 0.5;
        ctx.strokeRect(x + .5, y + .5, CELL - 1, CELL - 1);
      }
    }
  }
}

/** Draw the exit portal with a pulsing glow. */
function drawExit() {
  const [er, ec] = state.exit;
  const x = ec * CELL;
  const y = er * CELL;

  // Pulsing outer glow using time
  const pulse = 0.55 + 0.45 * Math.sin(Date.now() / 400);

  // Radial gradient fills the cell
  const grd = ctx.createRadialGradient(
    x + CELL / 2, y + CELL / 2, 0,
    x + CELL / 2, y + CELL / 2, CELL * 0.75
  );
  grd.addColorStop(0,   `rgba(176,96,255,${0.7 * pulse})`);
  grd.addColorStop(0.5, `rgba(176,96,255,${0.25 * pulse})`);
  grd.addColorStop(1,   'rgba(176,96,255,0)');

  ctx.save();
  ctx.fillStyle = grd;
  ctx.fillRect(x, y, CELL, CELL);

  // Centre diamond
  const cx = x + CELL / 2;
  const cy = y + CELL / 2;
  const r  = CELL * 0.28;
  ctx.beginPath();
  ctx.moveTo(cx,     cy - r);
  ctx.lineTo(cx + r, cy    );
  ctx.lineTo(cx,     cy + r);
  ctx.lineTo(cx - r, cy    );
  ctx.closePath();
  ctx.fillStyle = C.exit;
  ctx.shadowColor = C.exitGlow;
  ctx.shadowBlur  = 10 * pulse;
  ctx.fill();
  ctx.restore();
}

/** Draw all enemies with state-dependent colours and glow. */
function drawEnemies() {
  for (const enemy of state.enemies) {
    const [er, ec] = enemy.pos;
    const isChasing = enemy.state === 'CHASE';
    const colour    = isChasing ? C.enemyChase : C.enemyWander;

    drawCircle(ec, er, 0.36, colour, 8);

    // Chase enemies get an outer ring pulse
    if (isChasing) {
      const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 180);
      drawCircleOutline(ec, er, 0.46, colour, 1.5 * pulse);
    }
  }
}

/** Draw the player. */
function drawPlayer() {
  const [pr, pc] = state.player;
  drawCircle(pc, pr, 0.38, C.player, 12);
}

/**
 * Helper — filled circle centred on a grid cell.
 * @param {number} col       - grid column
 * @param {number} row       - grid row
 * @param {number} fraction  - radius as fraction of CELL
 * @param {string} colour    - fill colour
 * @param {number} blur      - shadow blur (glow)
 */
function drawCircle(col, row, fraction, colour, blur) {
  const cx = col * CELL + CELL / 2;
  const cy = row * CELL + CELL / 2;
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, CELL * fraction, 0, Math.PI * 2);
  ctx.fillStyle   = colour;
  ctx.shadowColor = colour;
  ctx.shadowBlur  = blur;
  ctx.fill();
  ctx.restore();
}

/** Helper — outlined ring on a grid cell. */
function drawCircleOutline(col, row, fraction, colour, lineW) {
  const cx = col * CELL + CELL / 2;
  const cy = row * CELL + CELL / 2;
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, CELL * fraction, 0, Math.PI * 2);
  ctx.strokeStyle = colour;
  ctx.lineWidth   = lineW;
  ctx.globalAlpha = 0.6;
  ctx.stroke();
  ctx.restore();
}

/** Continuously re-render so the pulsing animations stay alive. */
function animLoop() {
  render();
  animFrame = requestAnimationFrame(animLoop);
}

// ═══════════════════════════════════════════════════════════════════════════
//  HUD UPDATE
// ═══════════════════════════════════════════════════════════════════════════

function updateHUD() {
  if (!state) return;
  moveCount.textContent = state.moves;
  const labels = { playing: 'ALIVE', dead: 'DEAD', escaped: 'ESCAPED' };
  const colours = { playing: '#00ff9d', dead: '#ff3c5a', escaped: '#b060ff' };
  gameStatus.textContent = labels[state.status] || state.status.toUpperCase();
  gameStatus.style.color = colours[state.status] || '#c8e8ff';
}

// ═══════════════════════════════════════════════════════════════════════════
//  OVERLAY MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

function showOverlay(status) {
  if (status === 'dead') {
    overlayIcon.textContent  = '💀';
    overlayTitle.textContent = 'ELIMINATED';
    overlayTitle.classList.remove('win');
    overlaySub.textContent   = 'The enemies caught you.';
  } else if (status === 'escaped') {
    overlayIcon.textContent  = '🚀';
    overlayTitle.textContent = 'ESCAPED';
    overlayTitle.classList.add('win');
    overlaySub.textContent   = `You reached the exit in ${state.moves} moves!`;
  }
  overlay.hidden = false;
}

function hideOverlay() {
  overlay.hidden = true;
  overlayTitle.classList.remove('win');
}

// ═══════════════════════════════════════════════════════════════════════════
//  API CALLS
// ═══════════════════════════════════════════════════════════════════════════

/** POST /api/new_game — reset everything. */
async function newGame() {
  if (busy) return;
  busy = true;
  hideOverlay();
  try {
    const res  = await fetch('/api/new_game', { method: 'POST' });
    state      = await res.json();
    updateHUD();
  } catch (e) {
    console.error('newGame error:', e);
  } finally {
    busy = false;
  }
}

/**
 * POST /api/move with a direction string.
 * Awaits the response before allowing another move (serialises inputs).
 *
 * @param {string} direction — 'up' | 'down' | 'left' | 'right'
 */
async function sendMove(direction) {
  if (busy || !state || state.status !== 'playing') return;
  busy = true;
  try {
    const res = await fetch('/api/move', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ direction }),
    });
    state = await res.json();
    updateHUD();
    if (state.status !== 'playing') {
      showOverlay(state.status);
    }
  } catch (e) {
    console.error('sendMove error:', e);
  } finally {
    busy = false;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
//  INPUT HANDLING
// ═══════════════════════════════════════════════════════════════════════════

/** Map keyboard codes to direction strings. */
const KEY_MAP = {
  ArrowUp:    'up',   KeyW: 'up',
  ArrowDown:  'down', KeyS: 'down',
  ArrowLeft:  'left', KeyA: 'left',
  ArrowRight: 'right',KeyD: 'right',
};

document.addEventListener('keydown', e => {
  const dir = KEY_MAP[e.code];
  if (!dir) return;
  e.preventDefault();   // stop page scroll
  sendMove(dir);
});

// ── D-Pad buttons ──────────────────────────────────────────────────────────
document.querySelectorAll('.dpad-btn').forEach(btn => {
  const dir = btn.dataset.dir;

  // Pointer events (covers mouse + touch uniformly)
  btn.addEventListener('pointerdown', e => {
    e.preventDefault();
    btn.classList.add('pressed');
    sendMove(dir);
  });
  btn.addEventListener('pointerup',   () => btn.classList.remove('pressed'));
  btn.addEventListener('pointerleave',() => btn.classList.remove('pressed'));
});

// ── Restart button ─────────────────────────────────────────────────────────
btnRestart.addEventListener('click', () => newGame());

// ═══════════════════════════════════════════════════════════════════════════
//  RESPONSIVE RESIZE
// ═══════════════════════════════════════════════════════════════════════════

function onResize() {
  computeCell();
  render();
}

window.addEventListener('resize', onResize);

// ═══════════════════════════════════════════════════════════════════════════
//  BOOTSTRAP
// ═══════════════════════════════════════════════════════════════════════════

(async function init() {
  computeCell();
  animLoop();         // start render loop (will draw nothing until state loads)
  await newGame();    // fetch first game state from server
})();
