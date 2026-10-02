"""The Arena: a tiny jumping game that a human can play and a Q-table can learn.

    python arena.py --play              # you play it, space to jump, q to quit
    python arena.py --demo --fast       # watch the always-jump baseline bot
    python arena.py --selftest          # check the physics and the encoding

The game is also the environment. Everything an agent needs is in three methods:

    env = Arena(seed=7)
    state = env.reset()
    state, reward, done = env.step(action)   # action: 0 = nothing, 1 = jump

Deterministic given a seed, integer physics, no floats anywhere in the dynamics.
Pure standard library. No numpy, no torch, no network calls.
"""

from __future__ import annotations

import argparse
import random
import sys
import time

# ---------------------------------------------------------------------------
# Game constants. Integer physics so a seed replays exactly, forever.
# ---------------------------------------------------------------------------

JUMP_VELOCITY = 4        # upward velocity the instant you leave the ground
GRAVITY = 1              # subtracted from velocity every tick
MAX_HEIGHT = 10          # the apex a jump reaches, given the two numbers above
OBSTACLE_HEIGHTS = (2, 5, 8, 10)
OBSTACLE_WIDTHS = (1, 2)
GAP_MIN, GAP_MAX = 9, 20  # ticks between the END of one obstacle and the next
LANE_WIDTH = 46          # how many cells of track you can see
PLAYER_X = 6             # the player never moves horizontally, the world does
MAX_STEPS = 100_000      # a hard ceiling so a perfect agent cannot run forever

ACTIONS = (0, 1)         # 0 = do nothing, 1 = jump (ignored while airborne)

# A full jump arc. Tick 0 is the tick you press jump, you cannot steer mid-air:
#   y: 0  4  7  9  10  10  9  7  4  0     (airborne 8 ticks, apex 10)
# An obstacle of height h fills cells y = 0 .. h-1, so you clear it when y >= h.
# That turns height into a timing window, which is where the difficulty lives:
#   h=2   clear on arc ticks 1-8   (8 wide, forgiving)
#   h=5   clear on arc ticks 2-7    (6 wide)
#   h=8   clear on arc ticks 3-6    (4 wide)
#   h=10  clear on arc ticks 4-5    (2 wide)
# Jumping when the block is `d` ticks away puts you on arc tick `d` as it
# arrives, so the window above is literally the set of distances you may take
# off from. A width-2 block needs two consecutive clearing ticks, so a 10-high
# 2-wide block has exactly ONE correct takeoff distance: d = 4. Run
# `python arena.py --selftest` and it prints these windows from the real arc.
# GAP_MIN of 9 means the tightest spacing forces you to land and jump again on
# the very next tick, so single jumps are not enough, you have to chain them.


class Arena:
    """The game. Scrolling lane, one player, blocks of 4 heights and 2 widths.

    State encoding, which is what the Q-table actually keys on, is a 5-tuple:

      dist      0..13   ticks until the next block's leading edge reaches the
                        player. 0..12 exactly, then 13 for "further than 12",
                        because nothing you do more than 12 ticks out matters.
      height    2,5,8,10
      width     1 or 2
      y_bucket  0..4    0 = on the ground, 1 = y 1-4, 2 = 5-7, 3 = 8-9, 4 = 10
      vy_bucket 0..2    0 = rising, 1 = at the apex (vy == 0), 2 = falling

    Ceiling is 14 * 4 * 2 * 5 * 3 = 1,680 keys, of which about 700 are actually
    reachable. Small enough that tabular Q-learning visits every one of them
    hundreds of times in a minute, which is the only reason this works with a
    plain dict and no neural network anywhere.

    Deliberately NOT in the state: the obstacle after the next one. The agent is
    blind to it, so when two blocks are spaced 9 apart it has to commit to a
    takeoff before it can see what it is committing to. That one omission is
    most of the remaining error at convergence, and it is a choice you can undo.
    """

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed
        self.reset()

    # -- the three-method API ------------------------------------------------

    def reset(self) -> tuple:
        self.rng = random.Random(self.seed)
        self.y = 0
        self.vy = 0
        self.steps = 0
        self.jumps = 0
        self.done = False
        # Each obstacle is [x, height, width], filling cells x .. x+width-1.
        self.obstacles: list[list[int]] = []
        self.next_spawn = 24          # a calm runway before the first one
        return self.state()

    def step(self, action: int) -> tuple[tuple, float, bool]:
        """Advance one tick. Returns (state, reward, done)."""
        if self.done:
            raise RuntimeError("step() after done, call reset() first")

        if action == 1 and self.y == 0:
            self.vy = JUMP_VELOCITY
            self.jumps += 1

        # Move the player vertically.
        self.y += self.vy
        self.vy -= GRAVITY
        if self.y <= 0:
            self.y = 0
            self.vy = 0

        # Move the world left, spawn, retire anything behind the player.
        for ob in self.obstacles:
            ob[0] -= 1
        self.obstacles = [ob for ob in self.obstacles if ob[0] + ob[2] > PLAYER_X - 1]
        self.next_spawn -= 1
        if self.next_spawn <= 0:
            height = self.rng.choice(OBSTACLE_HEIGHTS)
            width = self.rng.choice(OBSTACLE_WIDTHS)
            self.obstacles.append([LANE_WIDTH + 2, height, width])
            self.next_spawn = width + self.rng.randint(GAP_MIN, GAP_MAX)

        self.steps += 1

        crashed = any(ob[0] <= PLAYER_X < ob[0] + ob[2] and self.y < ob[1]
                      for ob in self.obstacles)
        if crashed:
            self.done = True
            return self.state(), -50.0, True

        if self.steps >= MAX_STEPS:
            self.done = True
            return self.state(), 1.0, True

        return self.state(), 1.0, False

    # -- state encoding ------------------------------------------------------

    def next_obstacle(self) -> tuple[int, int, int]:
        """(ticks until its leading edge arrives, height, width).

        An obstacle the player is currently inside counts as distance 0, so the
        agent is never told "nothing ahead" while it is still over a block.
        """
        ahead = [ob for ob in self.obstacles if ob[0] + ob[2] > PLAYER_X]
        if not ahead:
            return 13, OBSTACLE_HEIGHTS[0], OBSTACLE_WIDTHS[0]
        ob = min(ahead, key=lambda o: o[0])
        return max(0, ob[0] - PLAYER_X), ob[1], ob[2]

    def state(self) -> tuple:
        dist, height, width = self.next_obstacle()
        dist_bucket = dist if dist <= 12 else 13
        if self.y == 0:
            y_bucket = 0
        elif self.y <= 4:
            y_bucket = 1
        elif self.y <= 7:
            y_bucket = 2
        elif self.y <= 9:
            y_bucket = 3
        else:
            y_bucket = 4
        vy_bucket = 0 if self.vy > 0 else (1 if self.vy == 0 else 2)
        return (dist_bucket, height, width, y_bucket, vy_bucket)

    # -- rendering -----------------------------------------------------------

    def render(self) -> str:
        """The exact same view the human plays in and watch.py replays."""
        rows = []
        for row_y in range(MAX_HEIGHT, -1, -1):
            cells = [" "] * LANE_WIDTH
            for ob in self.obstacles:
                if row_y >= ob[1]:
                    continue
                for x in range(ob[0], ob[0] + ob[2]):
                    if 0 <= x < LANE_WIDTH:
                        cells[x] = "#"
            if row_y == self.y:
                cells[PLAYER_X] = "@"
            rows.append("|" + "".join(cells) + "|")
        rows.append("+" + "=" * LANE_WIDTH + "+")
        rows.append(f" score {self.steps:>5}   jumps {self.jumps:>4}   "
                    f"y {self.y}  vy {self.vy:>2}   state {self.state()}")
        return "\n".join(rows)


# ---------------------------------------------------------------------------
# Terminal plumbing shared by --play, --demo and watch.py
# ---------------------------------------------------------------------------

FRAME_HEIGHT = MAX_HEIGHT + 3   # lane rows + floor + status line


def draw(env: Arena, header: str = "", first: bool = False) -> None:
    """Repaint the frame in place, so the lane looks like it is scrolling."""
    if not first:
        sys.stdout.write(f"\033[{FRAME_HEIGHT + (1 if header else 0)}A")
    if header:
        sys.stdout.write("\033[2K" + header + "\n")
    for line in env.render().split("\n"):
        sys.stdout.write("\033[2K" + line + "\n")
    sys.stdout.flush()


class KeyReader:
    """Non-blocking single-key reads on a POSIX terminal. Restores the tty."""

    def __enter__(self):
        import termios
        import tty
        self.fd = sys.stdin.fileno()
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def pressed(self) -> str | None:
        import select
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None
        return sys.stdin.read(1)

    def __exit__(self, *exc) -> None:
        import termios
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)


def play(seed: int, delay: float) -> None:
    env = Arena(seed=seed)
    env.reset()
    print("Space or j to jump, q to quit. Clear the # blocks.\n")
    draw(env, first=True)
    try:
        with KeyReader() as keys:
            while not env.done:
                action = 0
                key = keys.pressed()
                while key is not None:          # drain, so held keys do not queue
                    if key in ("q", "\x03"):
                        return
                    if key in (" ", "j", "\n", "\r"):
                        action = 1
                    key = keys.pressed()
                env.step(action)
                draw(env)
                time.sleep(delay)
    except Exception:
        pass
    print(f"\nCrashed at score {env.steps}. Run it again, the seed is the same.")


def demo(seed: int, delay: float) -> None:
    """The always-jump baseline. Watch it die on a landing tick."""
    env = Arena(seed=seed)
    env.reset()
    draw(env, header="baseline: jump on every tick it can", first=True)
    while not env.done:
        env.step(1)
        draw(env, header="baseline: jump on every tick it can")
        if delay:
            time.sleep(delay)
    print(f"\nAlways-jump baseline scored {env.steps}.")


# ---------------------------------------------------------------------------

def selftest() -> None:
    """Checks the claims in the comments above, so the README cannot drift."""
    env = Arena(seed=1)
    env.reset()
    arc = [env.y]
    env.step(1)
    arc.append(env.y)
    while env.y > 0:
        env.step(0)
        arc.append(env.y)
    assert arc == [0, 4, 7, 9, 10, 10, 9, 7, 4, 0], arc
    airborne = sum(1 for y in arc if y > 0)
    print(f"jump arc      {arc}  apex {max(arc)}  airborne {airborne} ticks")
    for height in OBSTACLE_HEIGHTS:
        window = [i for i, y in enumerate(arc) if y >= height]
        print(f"  height {height:>2}    clearable on ticks {window}")

    a, b = Arena(seed=4), Arena(seed=4)
    a.reset(), b.reset()
    for _ in range(300):
        if a.done or b.done:
            break
        sa, ra, da = a.step(1)
        sb, rb, db = b.step(1)
        assert (sa, ra, da) == (sb, rb, db)
    print(f"determinism   two seed-4 runs matched for {a.steps} ticks")

    seen = set()
    for seed in range(60):
        env = Arena(seed=seed)
        s = env.reset()
        seen.add(s)
        for _ in range(2000):
            s, _, done = env.step(random.choice(ACTIONS))
            seen.add(s)
            if done:
                break
    print(f"state space   {len(seen)} distinct states reachable (ceiling 1680)")

    scores = []
    for seed in range(20):
        env = Arena(seed=seed)
        env.reset()
        while not env.done and env.steps < 2000:
            env.step(1)
        scores.append(env.steps)
    print(f"always-jump   mean score {sum(scores) / len(scores):.1f} over 20 seeds")
    print("selftest ok")


def main() -> None:
    ap = argparse.ArgumentParser(description="The Arena: play it, or test it.")
    ap.add_argument("--play", action="store_true", help="play it yourself")
    ap.add_argument("--demo", action="store_true", help="watch the always-jump bot")
    ap.add_argument("--selftest", action="store_true", help="verify physics + encoding")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--delay", type=float, default=0.07, help="seconds per frame")
    ap.add_argument("--fast", action="store_true", help="no frame delay")
    args = ap.parse_args()

    delay = 0.0 if args.fast else args.delay
    if args.selftest:
        selftest()
    elif args.demo:
        demo(args.seed, delay)
    elif args.play:
        play(args.seed, delay)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
