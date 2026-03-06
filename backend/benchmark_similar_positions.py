"""Offline benchmark harness for similar-position generation.

Run from the workspace root:
    python -m backend.benchmark_similar_positions

Or from the backend folder:
    python benchmark_similar_positions.py
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import time
from typing import Any, Dict, List, Sequence, Tuple

try:
    from .position_generator import generate_similar_positions_mvp, find_stockfish
except ImportError:
    from position_generator import generate_similar_positions_mvp, find_stockfish


BenchmarkCase = Tuple[str, str, str, str]


BENCHMARK_CASES: List[BenchmarkCase] = [
    (
        "Scholar mate pressure",
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "d2d3",
        "h5f7",
    ),
    (
        "Back rank weakness",
        "6k1/5ppp/8/8/8/8/5PPP/1r2R1K1 w - - 0 1",
        "e1e2",
        "e1b1",
    ),
    (
        "Center tension",
        "r1bqkbnr/pppppppp/2n5/8/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 2 2",
        "d7d6",
        "d7d5",
    ),
    (
        "Discovered attack",
        "r2qk2r/ppp2ppp/2n1bn2/3pp3/2B1P1b1/2NP1N2/PPP2PPP/R1BQ1RK1 w kq - 0 7",
        "h2h3",
        "c4d5",
    ),
]


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _merge_counts(target: Dict[str, int], incoming: Dict[str, int]):
    for key, value in incoming.items():
        target[key] = target.get(key, 0) + value


def run_benchmark(count: int, difficulty: str | None, timeout_seconds: float, seed: int | None) -> Dict[str, Any]:
    stockfish_available = find_stockfish() is not None
    aggregate_rejections: Dict[str, int] = {}
    aggregate_methods: Dict[str, int] = {}
    latencies: List[float] = []
    accepted_counts: List[int] = []
    novelty_scores: List[float] = []
    motif_precision: List[float] = []
    partial_runs = 0
    total_generated = 0
    per_case: List[Dict[str, Any]] = []

    for index, (label, fen, played_uci, best_uci) in enumerate(BENCHMARK_CASES):
        started_at = time.perf_counter()
        result = generate_similar_positions_mvp(
            fen=fen,
            played_uci=played_uci,
            best_uci=best_uci,
            count=count,
            difficulty=difficulty,
            use_stockfish=stockfish_available,
            timeout_seconds=timeout_seconds,
            seed=seed if seed is None else seed + index,
        )
        elapsed = time.perf_counter() - started_at

        generated = result.get("generated", [])
        stats = result.get("stats", {})
        source_motifs = set(result.get("source", {}).get("motifs", []))

        total_generated += len(generated)
        latencies.append(elapsed)
        accepted_counts.append(len(generated))
        partial_runs += int(bool(result.get("partial")))
        novelty_scores.extend(item.get("novelty_score", 0.0) for item in generated)

        matched = 0
        for item in generated:
            generated_motifs = set(item.get("motifs", []))
            if not source_motifs or source_motifs & generated_motifs:
                matched += 1
        precision = (matched / len(generated)) if generated else 0.0
        motif_precision.append(precision)

        _merge_counts(aggregate_rejections, stats.get("rejection_reasons", {}))
        _merge_counts(aggregate_methods, stats.get("accepted_methods", {}))

        per_case.append({
            "label": label,
            "latency_seconds": round(elapsed, 3),
            "generated": len(generated),
            "partial": bool(result.get("partial")),
            "motif_precision": round(precision, 3),
            "avg_novelty": round(
                sum(item.get("novelty_score", 0.0) for item in generated) / len(generated),
                3,
            ) if generated else 0.0,
            "accepted_methods": stats.get("accepted_methods", {}),
            "rejection_reasons": stats.get("rejection_reasons", {}),
        })

    summary = {
        "cases": len(BENCHMARK_CASES),
        "stockfish_available": stockfish_available,
        "count_requested": count,
        "difficulty": difficulty,
        "timeout_seconds": timeout_seconds,
        "total_generated": total_generated,
        "avg_generated_per_case": round(statistics.mean(accepted_counts), 3) if accepted_counts else 0.0,
        "acceptance_rate": round(total_generated / (len(BENCHMARK_CASES) * count), 3) if count else 0.0,
        "avg_motif_precision": round(statistics.mean(motif_precision), 3) if motif_precision else 0.0,
        "avg_novelty_score": round(statistics.mean(novelty_scores), 3) if novelty_scores else 0.0,
        "latency_p50_seconds": round(_percentile(latencies, 0.5), 3),
        "latency_p95_seconds": round(_percentile(latencies, 0.95), 3),
        "partial_runs": partial_runs,
        "accepted_methods": aggregate_methods,
        "rejection_reasons": aggregate_rejections,
        "per_case": per_case,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark similar-position generation")
    parser.add_argument("--count", type=int, default=8, help="Target generated positions per case")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout per generation request")
    parser.add_argument("--seed", type=int, default=7, help="Base seed for reproducible runs")
    parser.add_argument("--json", action="store_true", help="Print full JSON summary")
    parser.add_argument("--verbose", action="store_true", help="Show generator logs during the benchmark run")
    args = parser.parse_args()

    logging.getLogger("backend.position_generator").setLevel(logging.INFO if args.verbose else logging.ERROR)
    logging.getLogger("position_generator").setLevel(logging.INFO if args.verbose else logging.ERROR)

    summary = run_benchmark(
        count=args.count,
        difficulty=args.difficulty,
        timeout_seconds=args.timeout,
        seed=args.seed,
    )

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    print("Similar Position Benchmark")
    print(f"Cases: {summary['cases']}")
    print(f"Stockfish available: {summary['stockfish_available']}")
    print(f"Requested count: {summary['count_requested']}")
    print(f"Average generated per case: {summary['avg_generated_per_case']}")
    print(f"Acceptance rate: {summary['acceptance_rate']}")
    print(f"Average motif precision: {summary['avg_motif_precision']}")
    print(f"Average novelty score: {summary['avg_novelty_score']}")
    print(f"Latency p50: {summary['latency_p50_seconds']}s")
    print(f"Latency p95: {summary['latency_p95_seconds']}s")
    print(f"Partial runs: {summary['partial_runs']}")
    print(f"Accepted methods: {summary['accepted_methods']}")
    print(f"Rejection reasons: {summary['rejection_reasons']}")


if __name__ == "__main__":
    main()