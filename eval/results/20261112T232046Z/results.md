# ZeroOps Benchmark Results

**Run:** 20261112T232046Z  
**Commit:** 9c3c2c5  
**Provider:** google-gla  
**Model:** gemini-4-hydrogen  
**Condition:** with_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ❌ | ❌ | ❌ | 0% | 0 | 81.7s | 0 |
| bug2 | utils.normalize_string → normalize_tex | ✅ | ✅ | ❌ | 95% | 1 | 199.6s | 0 |
| bug3 | unchecked None from parse_date (app) | ✅ | ✅ | ✅ | 95% | 1 | 52.5s | 0 |
| bug4 | validate_token variant (L0 test, handl | ❌ | ❌ | ❌ | 0% | 0 | 71.5s | 0 |
| bug5 | stale import in test_auth.py | ❌ | ❌ | ❌ | 0% | 0 | 103.7s | 0 |

**Pattern accuracy:** 2/5  
**File identification:** 1/5  
**Average confidence:** 38%  
**Prevention tickets:** 0  
**Total duration:** 509.1s  

> Sample size: n=5 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.