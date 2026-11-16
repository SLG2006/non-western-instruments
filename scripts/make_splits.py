#!/usr/bin/env python3
"""Stage 5: split usable clips into train/test by source group (uploader).

A source group goes entirely to one side, across all instruments, so no
uploader's recordings leak from train to test. Greedy and seeded: each group
goes to the side that leaves the instruments most balanced.
"""
import random, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
from validate import usable_clips


def main():
    pc = C.cfg("pipeline")
    clips = {r["clip_id"]: r for r in C.read_csv(C.p("clips"))}
    usable = {c: lab for c, lab in usable_clips().items() if c in clips}
    by_group = defaultdict(Counter)
    for c, lab in usable.items():
        by_group[clips[c]["source_group"]][lab] += 1
    rng = random.Random(pc["seed"])
    order = sorted(by_group)
    rng.shuffle(order)
    order.sort(key=lambda g: -sum(by_group[g].values()))
    count = {"train": Counter(), "test": Counter()}
    side_of = {}
    for g in order:
        def cost(side):
            other = "test" if side == "train" else "train"
            return sum(abs(count[side][i] + by_group[g][i] - count[other][i]) for i in by_group[g])
        ct, ce = cost("train"), cost("test")
        side = "train" if ct < ce else "test" if ce < ct else rng.choice(["train", "test"])
        side_of[g] = side
        count[side].update(by_group[g])
    rows = [{"clip_id": c, "instrument": usable[c], "source_group": clips[c]["source_group"],
             "split": side_of[clips[c]["source_group"]]} for c in sorted(usable)]
    C.write_csv(C.p("splits"), rows, C.schema("splits"))
    for i in sorted(set(usable.values())):
        print(f"{i:16s} train={count['train'][i]:3d} test={count['test'][i]:3d}")


if __name__ == "__main__":
    main()
