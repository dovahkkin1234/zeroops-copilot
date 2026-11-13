# ZeroOps Benchmark Results

**Run:** 20261113T113725Z  
**Commit:** fb1904c  
**Provider:** google-gla  
**Model:** gemini-3.5-flash  
**Condition:** with_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ✅ | ✅ | ✅ | 30% | 1 | 192.6s | 2 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ✅ | ❌ | 100% | 1 | 117.8s | 1 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 100% | 1 | 122.5s | 1 |
| bug4 | validate_token variant (L0 test, handl | ❌ | ✅ | ❌ | 100% | 1 | 47.4s | 0 |
| bug5 | stale import in test_auth.py | ✅ | ❌ | ❌ | 100% | 1 | 163.1s | 1 |

**Pattern accuracy:** 4/5  
**File identification:** 2/5  
**Average confidence:** 86%  
**Prevention tickets:** 5  
**Total duration:** 643.5s  

> Sample size: n=5 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.