"""Allow running benchmark as: python -m eval.benchmark"""
from eval.benchmark import run_benchmark
import asyncio

asyncio.run(run_benchmark())
