# ZeroOps Benchmark Results

**Run:** 20261116T120726Z  
**Commit:** f2ec415  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** no_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 90% | 2 | 51.1s | 4 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ❌ | ✅ | 80% | 2 | 17.6s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 90% | 2 | 19.5s | 0 |
| bug4 | validate_token variant (L0 test, handl | ❌ | ✅ | ✅ | 80% | 2 | 22.1s | 2 |
| bug5 | stale import in test_auth.py | ✅ | ✅ | ✅ | 100% | 3 | 28.8s | 5 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ✅ | ✅ | 90% | 2 | 16.9s | 0 |
| bug7 | collections.Mapping removed in Python  | ✅ | ✅ | ✅ | 90% | 4 | 24.2s | 1 |

**Pattern accuracy:** 6/7  
**File identification:** 7/7  
**Average confidence:** 89%  
**Prevention tickets:** 12  
**Total duration:** 180.1s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.