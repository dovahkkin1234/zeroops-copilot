"""Data pipeline utilities for batch processing."""
import pandas as pd


def merge_results(batch_df, results_df):
    """Merge two result DataFrames. Returns combined frame."""
    return batch_df.append(results_df, ignore_index=True)  # BUG: removed in pandas 2.0


def compute_stats(df):
    """Return summary statistics for a results frame."""
    return {
        "mean": df["value"].mean(),
        "count": len(df),
        "max": df["value"].max(),
    }
