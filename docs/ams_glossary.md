# AMS / ZeroOps Glossary

**Application Management Services (AMS):** The practice of maintaining and operating enterprise application landscapes. The single largest line item in most IT services contracts.

**Ticket Tiers:**
- **L0** — Self-service (knowledge base, bot). No human touch.
- **L1** — First-line human: basic troubleshooting, scripted fixes.
- **L2** — Deeper technical: functional and configuration analysis.
- **L3** — Developer-level: code changes, deep debugging.
- **L4** — Vendor escalation.

Each tier escalation roughly doubles cost. The economic game is **shift-left**.

**ZeroOps:** The target end-state where intelligent automation has pushed enough tickets leftward that developers spend ~zero time on infrastructure/ops. Unlike NoOps (fully human-free, still aspirational), ZeroOps keeps humans in the loop for novel cases and uses automation for everything repeatable.

**ITIL Ticket Types:**
- **Incident** — Something broke, restore service.
- **Service Request** — User wants access/password/report.
- **Problem** — The underlying cause of recurring incidents.
- **Change Request** — Planned modification.

**Key Insight:** Incidents flow from Problems. Resolving a Problem eliminates a whole class of future Incidents.

---

*Source: Conversation with a senior engineering manager at Cognizant, framing the AMS shift-left and ZeroOps direction, April 2026.*
