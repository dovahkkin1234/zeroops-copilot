# ZeroOps Benchmark Results

**Run:** 20261112T234420Z  
**Commit:** 9c3c2c5  
**Provider:** google-gla  
**Model:** gemini-2.5-flash  
**Condition:** with_memory  

| Bug | Name | Triage | Pattern | File | Confidence | Tools | Duration | Tickets |
|-----|------|:------:|:-------:|:----:|-----------:|------:|---------:|--------:|
| bug1 | auth.validate_token → verify_token (mi | ❌ | ❌ | ❌ | 0% | 0 | 12.4s | 0 |
| bug2 | utils.normalize_string → normalize_tex | ❌ | ❌ | ❌ | 0% | 0 | 1.8s | 0 |
| bug3 | unchecked None from parse_date (app) | ❌ | ❌ | ❌ | 0% | 0 | 1.6s | 0 |
| bug4 | validate_token variant (L0 test, handl | ❌ | ❌ | ❌ | 0% | 0 | 1.5s | 0 |
| bug5 | stale import in test_auth.py | ❌ | ❌ | ❌ | 0% | 0 | 1.6s | 0 |

**Pattern accuracy:** 0/5  
**File identification:** 0/5  
**Average confidence:** 0%  
**Prevention tickets:** 0  
**Total duration:** 18.9s  

> Sample size: n=5 seeded bugs, synthetic, authored by the builder.
> Confidence values are model self-reported, not externally calibrated.