# ZeroOps Benchmark Results

**Run:** 20261116T173835Z  
**Commit:** 3a4af96  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** with_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 80% | 2 | 653.2s | 4 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ✅ | ✅ | 95% | 2 | 16.8s | 1 |
| bug3 | unchecked None from parse_date (app) | ✅ | ❌ | ✅ | 85% | 2 | 17.3s | 0 |
| bug4 | validate_token variant (L0 test, handl | ✅ | ❌ | ❌ | 72% | 0 | 2.8s | 0 |
| bug5 | stale import in test_auth.py | ✅ | ✅ | ❌ | 80% | 3 | 30.1s | 6 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ❌ | ✅ | 80% | 2 | 23.7s | 1 |
| bug7 | collections.Mapping removed in Python  | ✅ | ✅ | ✅ | 80% | 2 | 25.0s | 7 |

**Pattern accuracy:** 4/7  
**File identification:** 5/7  
**Average confidence:** 82%  
**Prevention tickets:** 19  
**Total duration:** 768.9s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.