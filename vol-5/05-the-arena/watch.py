"""Replay a saved Q-table in the same terminal view the human plays in.

    python watch.py --checkpoint output/ep-00000.json      # random flailing
    python watch.py --checkpoint output/ep-01000.json      # getting the idea
    python watch.py --checkpoint output/ep-20000.json      # does not die
    python watch.py --checkpoint sample-data/trained-ep-20000.json

    python watch.py --checkpoint output/ep-20000.json --episodes 5 --fast
        no frame delay, no rendering, just the scores. This is how you measure.

    python watch.py --compare output/ep-00000.json output/ep-20000.json
        both checkpoints over the same seeds, side by side numbers.

Nothing here trains. It loads a dict of state -> [q_nothing, q_jump] and takes
the higher one every tick. A state the table never saw is a coin flip, which is
why ep-00000.json plays randomly rather than standing still.
"""

from __future__ import annotations

import argparse
import json
import random
import time

from arena import Arena, draw
from train import greedy, load


def run_episode(table: dict, seed: int, rng: random.Random, delay: float,
                cap: int, render: bool, label: str = "") -> int:
    env = Arena(seed=seed)
    state = env.reset()
    header = f"{label}   seed {seed}" if label else f"seed {seed}"
    if render:
        draw(env, header=header, first=True)
    while not env.done and env.steps < cap:
        state, _, _ = env.step(greedy(table, state, rng))
        if render:
            draw(env, header=header)
            if delay:
                time.sleep(delay)
    return env.steps


def describe(path: str) -> str:
    with open(path) as f:
        payload = json.load(f)
    meta = payload.get("meta", {})
    return (f"{path}: episode {payload.get('episode')}, "
            f"{meta.get('states', len(payload['q']))} states, "
            f"training eval mean {meta.get('eval_mean', 'n/a')}")


def scores(table: dict, seeds, cap: int) -> list[int]:
    rng = random.Random(999)
    return [run_episode(table, s, rng, 0.0, cap, render=False) for s in seeds]


def main() -> None:
    ap = argparse.ArgumentParser(description="Watch a trained Arena agent play.")
    ap.add_argument("--checkpoint", help="path to a saved Q-table JSON")
    ap.add_argument("--compare", nargs=2, metavar=("EARLY", "LATE"),
                    help="score two checkpoints over the same seeds")
    ap.add_argument("--episodes", type=int, default=1)
    ap.add_argument("--seed", type=int, default=900_000,
                    help="first track to play, episodes run seed, seed+1, ...")
    ap.add_argument("--delay", type=float, default=0.06, help="seconds per frame")
    ap.add_argument("--fast", action="store_true",
                    help="no delay and no rendering, print scores only")
    ap.add_argument("--cap", type=int, default=2000,
                    help="stop a run at this score, it counts as survived")
    args = ap.parse_args()

    if args.compare:
        seeds = [args.seed + i for i in range(max(args.episodes, 10))]
        print(f"{len(seeds)} identical tracks, cap {args.cap}\n")
        for path in args.compare:
            got = scores(load(path), seeds, args.cap)
            survived = sum(1 for s in got if s >= args.cap)
            print(f"{path:<34} mean {sum(got) / len(got):>7.1f}  "
                  f"min {min(got):>5}  max {max(got):>5}  "
                  f"survived {survived}/{len(seeds)}")
        return

    if not args.checkpoint:
        ap.error("pass --checkpoint PATH or --compare EARLY LATE")

    print(describe(args.checkpoint))
    table = load(args.checkpoint)
    rng = random.Random(999)
    label = args.checkpoint
    got = []
    for i in range(args.episodes):
        score = run_episode(table, args.seed + i, rng,
                            0.0 if args.fast else args.delay,
                            args.cap, render=not args.fast, label=label)
        got.append(score)
        print(f"episode {i + 1}  seed {args.seed + i}  score {score}")
    print(f"mean score {sum(got) / len(got):.1f} over {len(got)} episodes")


if __name__ == "__main__":
    main()
