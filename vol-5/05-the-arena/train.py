"""Tabular Q-learning for The Arena. One dict, no frameworks, no numpy.

    python train.py                       # 20,000 episodes, ~1 minute
    python train.py --episodes 50000      # longer, if you want it flawless
    python train.py --no-crash-penalty    # see the degenerate agent (README)

Writes JSON checkpoints to output/ at several training stages so watch.py can
replay the same agent at random, mediocre and unbeatable:

    output/ep-00000.json   untouched table, every action is a coin flip
    output/ep-00100.json
    output/ep-01000.json
    output/ep-05000.json
    output/ep-20000.json

The algorithm, in one line, is the only line that matters:

    Q[s][a]  <-  Q[s][a] + alpha * (reward + gamma * max(Q[s2]) - Q[s][a])

Q[s][a] is the agent's current guess at "total future score if I take action a
in state s and keep playing like this". The update nudges that guess toward what
it just actually observed. Repeat a few million times. That is the whole method.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time

from arena import ACTIONS, Arena

OUTPUT_DIR = "output"
CHECKPOINTS = (0, 100, 1000, 5000, 20000)

# Seeds held back from training, so the reported score is on unseen tracks.
EVAL_SEEDS = tuple(range(900_000, 900_030))


def q_get(table: dict, state: tuple) -> list[float]:
    row = table.get(state)
    if row is None:
        row = [0.0] * len(ACTIONS)
        table[state] = row
    return row


def greedy(table: dict, state: tuple, rng: random.Random) -> int:
    """Best known action. A state never visited, or a tie, is a coin flip, so an
    untrained table plays genuinely randomly instead of standing still."""
    row = table.get(state)
    if row is None or row[0] == row[1]:
        return rng.choice(ACTIONS)
    return 0 if row[0] > row[1] else 1


def evaluate(table: dict, seeds=EVAL_SEEDS, cap: int = 2000) -> tuple[float, int]:
    """Greedy play on held-out seeds. Returns (mean score, best score)."""
    rng = random.Random(999)
    scores = []
    for seed in seeds:
        env = Arena(seed=seed)
        state = env.reset()
        while not env.done and env.steps < cap:
            state, _, _ = env.step(greedy(table, state, rng))
        scores.append(env.steps)
    return sum(scores) / len(scores), max(scores)


def save(table: dict, episode: int, meta: dict, out_dir: str = OUTPUT_DIR) -> str:
    """JSON cannot key on a tuple, so states are stored as 'd,h,w,y,v' strings."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"ep-{episode:05d}.json")
    payload = {
        "episode": episode,
        "meta": meta,
        "q": {",".join(str(n) for n in s): row for s, row in sorted(table.items())},
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=1, sort_keys=True)
    return path


def load(path: str) -> dict:
    with open(path) as f:
        payload = json.load(f)
    return {tuple(int(n) for n in key.split(",")): row
            for key, row in payload["q"].items()}


def train(episodes: int, alpha: float, gamma: float, eps_start: float,
          eps_end: float, train_cap: int, crash_penalty: bool,
          jump_cost: float, seed_offset: int,
          out_dir: str = OUTPUT_DIR) -> dict:
    table: dict[tuple, list[float]] = {}
    rng = random.Random(12345)
    history: list[tuple[int, float, int]] = []
    started = time.time()

    print(f"episodes {episodes}  alpha {alpha}  gamma {gamma}  "
          f"epsilon {eps_start} -> {eps_end}  crash penalty {crash_penalty}  "
          f"jump cost {jump_cost}")
    print(f"{'episode':>8} {'epsilon':>8} {'states':>7} {'mean':>8} {'best':>6}  "
          f"{'elapsed':>8}")

    for episode in range(episodes + 1):
        if episode in CHECKPOINTS or episode == episodes:
            mean, best = evaluate(table)
            history.append((episode, mean, best))
            print(f"{episode:>8} {epsilon(episode, episodes, eps_start, eps_end):>8.3f} "
                  f"{len(table):>7} {mean:>8.1f} {best:>6} "
                  f"{time.time() - started:>7.1f}s")
            if episode in CHECKPOINTS:
                save(table, episode, {
                    "alpha": alpha, "gamma": gamma,
                    "eps_start": eps_start, "eps_end": eps_end,
                    "crash_penalty": crash_penalty,
                    "eval_mean": mean, "eval_best": best,
                    "states": len(table),
                }, out_dir)
        if episode == episodes:
            break

        eps = epsilon(episode, episodes, eps_start, eps_end)
        env = Arena(seed=seed_offset + episode)
        state = env.reset()
        for _ in range(train_cap):
            if rng.random() < eps:
                action = rng.choice(ACTIONS)
            else:
                action = greedy(table, state, rng)
            nxt, reward, done = env.step(action)
            if not crash_penalty and reward < 0:
                reward = 0.0        # the ablation that produces the broken agent
            if jump_cost and action == 1 and state[3] == 0:
                reward -= jump_cost  # makes pointless mid-field jumps cost score
            row = q_get(table, state)
            target = reward if done else reward + gamma * max(q_get(table, nxt))
            row[action] += alpha * (target - row[action])
            state = nxt
            if done:
                break

    return table


def epsilon(episode: int, episodes: int, start: float, end: float) -> float:
    """Linear decay over the first 60% of training, then flat at `end`."""
    ramp = max(1, int(episodes * 0.6))
    if episode >= ramp:
        return end
    return start + (end - start) * (episode / ramp)


def main() -> None:
    ap = argparse.ArgumentParser(description="Train a Q-table to play The Arena.")
    ap.add_argument("--episodes", type=int, default=20000)
    ap.add_argument("--alpha", type=float, default=0.2, help="learning rate")
    ap.add_argument("--gamma", type=float, default=0.99, help="discount factor")
    ap.add_argument("--eps-start", type=float, default=1.0)
    ap.add_argument("--eps-end", type=float, default=0.02)
    ap.add_argument("--train-cap", type=int, default=400,
                    help="max ticks per training episode, keeps runtime sane")
    ap.add_argument("--no-crash-penalty", action="store_true",
                    help="reward distance only, no -50 for crashing")
    ap.add_argument("--jump-cost", type=float, default=0.0,
                    help="subtract this from the reward on every takeoff")
    ap.add_argument("--out-dir", default=OUTPUT_DIR,
                    help="where checkpoints go, use another dir for ablations")
    ap.add_argument("--seed-offset", type=int, default=0,
                    help="training tracks are seeds offset..offset+episodes")
    args = ap.parse_args()

    table = train(args.episodes, args.alpha, args.gamma, args.eps_start,
                  args.eps_end, args.train_cap, not args.no_crash_penalty,
                  args.jump_cost, args.seed_offset, args.out_dir)

    mean, best = evaluate(table)
    print(f"\nfinal: {len(table)} states learned, mean score {mean:.1f}, best {best}")
    print(f"checkpoints in {args.out_dir}/  ->  python watch.py --checkpoint "
          f"{args.out_dir}/ep-{min(args.episodes, CHECKPOINTS[-1]):05d}.json")


if __name__ == "__main__":
    main()
