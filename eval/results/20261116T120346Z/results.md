# ZeroOps Benchmark Results

**Run:** 20261116T120346Z  
**Commit:** f2ec415  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** no_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 80% | 2 | 55.5s | 5 |
| bug2 | utils.normalize_string → normalize_tex | ❌ | ❌ | ❌ | 0% | 0 | 19.4s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 95% | 2 | 19.7s | 0 |
| bug4 | validate_token variant (L0 test, handl | ❌ | ✅ | ✅ | 90% | 2 | 22.4s | 2 |
| bug5 | stale import in test_auth.py | ✅ | ✅ | ❌ | 80% | 3 | 33.3s | 5 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ✅ | ✅ | 80% | 2 | 18.3s | 0 |
| bug7 | collections.Mapping removed in Python  | ✅ | ❌ | ❌ | 51% | 0 | 2.6s | 0 |

**Pattern accuracy:** 5/7  
**File identification:** 4/7  
**Average confidence:** 68%  
**Prevention tickets:** 12  
**Total duration:** 171.3s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.