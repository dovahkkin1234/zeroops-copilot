# ZeroOps Benchmark Results

**Run:** 20261116T121355Z  
**Commit:** f2ec415  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** no_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 90% | 2 | 39.3s | 3 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ✅ | ✅ | 80% | 2 | 24.1s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 80% | 2 | 15.8s | 0 |
| bug4 | validate_token variant (L0 test, handl | ❌ | ❌ | ✅ | 90% | 2 | 18.7s | 1 |
| bug5 | stale import in test_auth.py | ✅ | ✅ | ❌ | 100% | 3 | 29.6s | 4 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ✅ | ✅ | 80% | 2 | 19.6s | 0 |
| bug7 | collections.Mapping removed in Python  | ✅ | ❌ | ❌ | 100% | 0 | 2.4s | 0 |

**Pattern accuracy:** 5/7  
**File identification:** 5/7  
**Average confidence:** 89%  
**Prevention tickets:** 8  
**Total duration:** 149.6s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.