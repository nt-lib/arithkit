# The Zen of arithkit

    Correct is better than maintainable.
    Maintainable is better than fast.
    Fast is still better than slow.

    Write it twice: once to understand, once to run.
    The toy is the oracle; the oracle is never clever.
    If toy and native disagree, there is a bug, even if no one can say where yet.
    The interface is written down before it is implemented.

    The mathematics comes first, with proofs, before the code.
    Every arbitrary choice is fixed, written down and given a name.
    Canonical is better than deterministic.
    Deterministic is better than characterised.
    Characterised is better than random.
    Even random needs a seed.

    Equality only within a parent.
    Coercion is a guess; conversion is a decision.
    An element does not shout its parent's name.
    Immutable values cannot surprise you.

    Same input, same output, same exception.
    A panic is always a bug.
    No tricks that trade correctness for speed.
    Prefer pruning that you can prove.
    Bulk work belongs in Rust; Python is for asking.

    Data is never edited, only superseded.
    A shard may be retracted, but it is never forgotten.
    Every number knows where it came from, and how to compute it again.
    One recipe is a claim; two independent recipes are evidence.
    A commit you cannot check out again is not a version.

    Before the first release, nothing is sacred except correctness.
    Tests that only one implementation passes are not tests.
    Every pull request is reviewed by a human before it reaches main.

The detailed rules behind these lines are in [CLAUDE.md](CLAUDE.md).
