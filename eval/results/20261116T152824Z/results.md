# ZeroOps Benchmark Results

**Run:** 20261116T152824Z  
**Commit:** 714e939  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** with_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 95% | 2 | 64.9s | 4 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ❌ | ✅ | 80% | 2 | 25.2s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 80% | 2 | 22.7s | 0 |
| bug4 | validate_token variant (L0 test, handl | ✅ | ❌ | ❌ | 95% | 0 | 3.3s | 0 |
| bug5 | stale import in test_auth.py | ✅ | ❌ | ❌ | 90% | 7 | 45.4s | 5 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ✅ | ✅ | 90% | 2 | 23.9s | 0 |
| bug7 | collections.Mapping removed in Python  | ✅ | ❌ | ❌ | 51% | 0 | 2.8s | 0 |

**Pattern accuracy:** 3/7  
**File identification:** 4/7  
**Average confidence:** 83%  
**Prevention tickets:** 9  
**Total duration:** 188.2s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.