# ZeroOps Benchmark Results

**Run:** 20261118T071135Z  
**Commit:** 607c4e0  
**Provider:** ollama  
**Model:** qwen2.5:7b  
**Condition:** with_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ❌ | ❌ | 0% | 0 | 35.5s | 0 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ❌ | ❌ | 0% | 0 | 2.1s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 90% | 2 | 17.9s | 0 |
| bug4 | validate_token variant (L0 test, handl | ✅ | ✅ | ❌ | 80% | 0 | 2.7s | 0 |
| bug5 | stale import in test_auth.py | ✅ | ❌ | ❌ | 90% | 4 | 30.0s | 2 |
| bug6 | pandas DataFrame.append() removed in 2 | ✅ | ✅ | ✅ | 80% | 2 | 22.0s | 0 |
| bug7 | collections.Mapping removed in Python  | ✅ | ✅ | ✅ | 80% | 2 | 16.5s | 0 |

**Pattern accuracy:** 4/7  
**File identification:** 3/7  
**Average confidence:** 60%  
**Prevention tickets:** 2  
**Total duration:** 126.6s  

> Sample size: n=7 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.