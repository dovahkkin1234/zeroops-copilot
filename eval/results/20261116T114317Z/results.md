# ZeroOps Benchmark Results

**Run:** 20261116T114317Z  
**Commit:** f2ec415  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** with_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 80% | 2 | 37.1s | 4 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ✅ | ✅ | 90% | 2 | 23.4s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 95% | 2 | 22.7s | 0 |
| bug4 | validate_token variant (L0 test, handl | ✅ | ❌ | ❌ | 72% | 0 | 2.8s | 0 |
| bug5 | stale import in test_auth.py | ✅ | ❌ | ❌ | 90% | 12 | 50.7s | 1 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ✅ | ✅ | 90% | 2 | 16.3s | 0 |
| bug7 | collections.Mapping removed in Python  | ✅ | ❌ | ❌ | 51% | 0 | 2.3s | 0 |

**Pattern accuracy:** 4/7  
**File identification:** 4/7  
**Average confidence:** 81%  
**Prevention tickets:** 5  
**Total duration:** 155.3s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.