# ZeroOps Benchmark Results

**Run:** 20261116T121648Z  
**Commit:** f2ec415  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** no_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 80% | 2 | 44.2s | 5 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ✅ | ✅ | 90% | 2 | 18.2s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ❌ | ✅ | 100% | 3 | 27.8s | 1 |
| bug4 | validate_token variant (L0 test, handl | ❌ | ✅ | ✅ | 90% | 2 | 28.7s | 2 |
| bug5 | stale import in test_auth.py | ✅ | ❌ | ❌ | 90% | 4 | 45.5s | 2 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ❌ | ✅ | 90% | 2 | 20.9s | 0 |
| bug7 | collections.Mapping removed in Python  | ✅ | ❌ | ❌ | 51% | 0 | 2.3s | 0 |

**Pattern accuracy:** 3/7  
**File identification:** 5/7  
**Average confidence:** 84%  
**Prevention tickets:** 10  
**Total duration:** 187.7s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.