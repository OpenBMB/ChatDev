---
name: analyse-problem
description: Comprehensive A3 one-page problem analysis with root cause and action plan
argument-hint: Optional problem description to document
---

# A3 Problem Analysis

Apply A3 problem-solving format for comprehensive, single-page problem documentation and resolution planning.

## Description
Structured one-page analysis format covering: Background, Current Condition, Goal, Root Cause Analysis, Countermeasures, Implementation Plan, and Follow-up. Named after A3 paper size; emphasizes concise, complete documentation.

## Usage
`/analyse-problem [problem_description]`

## Variables
- PROBLEM: Issue to analyze (default: prompt for input)
- OUTPUT_FORMAT: markdown or text (default: markdown)

## Steps
1. **Background**: Why this problem matters (context, business impact)
2. **Current Condition**: What's happening now (data, metrics, examples)
3. **Goal/Target**: What success looks like (specific, measurable)
4. **Root Cause Analysis**: Why problem exists (use 5 Whys or Fishbone)
5. **Countermeasures**: Proposed solutions addressing root causes
6. **Implementation Plan**: Who, what, when, how
7. **Follow-up**: How to verify success and prevent recurrence

## A3 Template

```
═══════════════════════════════════════════════════════════════
                    A3 PROBLEM ANALYSIS
═══════════════════════════════════════════════════════════════

TITLE: [Concise problem statement]
OWNER: [Person responsible]
DATE: [YYYY-MM-DD]

┌─────────────────────────────────────────────────────────────┐
│ 1. BACKGROUND (Why this matters)                            │
├─────────────────────────────────────────────────────────────┤
│ [Context, impact, urgency, who's affected]                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. CURRENT CONDITION (What's happening)                     │
├─────────────────────────────────────────────────────────────┤
│ [Facts, data, metrics, examples - no opinions]              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3. GOAL/TARGET (What success looks like)                    │
├─────────────────────────────────────────────────────────────┤
│ [Specific, measurable, time-bound targets]                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 4. ROOT CAUSE ANALYSIS (Why problem exists)                 │
├─────────────────────────────────────────────────────────────┤
│ [5 Whys, Fishbone, data analysis]                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 5. COUNTERMEASURES (Solutions addressing root causes)       │
├─────────────────────────────────────────────────────────────┤
│ [Specific actions, not vague intentions]                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 6. IMPLEMENTATION PLAN (Who, What, When)                    │
├─────────────────────────────────────────────────────────────┤
│ [Timeline, responsibilities, dependencies, milestones]      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 7. FOLLOW-UP (Verification & Prevention)                    │
├─────────────────────────────────────────────────────────────┤
│ [Success metrics, monitoring plan, review dates]            │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════
```

## Examples

### Example 1: Database Connection Pool Exhaustion

```
═══════════════════════════════════════════════════════════════
                    A3 PROBLEM ANALYSIS
═══════════════════════════════════════════════════════════════

TITLE: API Downtime Due to Connection Pool Exhaustion
OWNER: Backend Team Lead
DATE: 2024-11-14

┌─────────────────────────────────────────────────────────────┐
│ 1. BACKGROUND                                                │
├─────────────────────────────────────────────────────────────┤
│ • API goes down 2-3x per week during peak hours             │
│ • Affects 10,000+ users, average 15min downtime             │
│ • Revenue impact: ~$5K per incident                         │
│ • Customer satisfaction score dropped from 4.5 to 3.8       │
│ • Started 3 weeks ago after traffic increased 40%           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. CURRENT CONDITION                                         │
├─────────────────────────────────────────────────────────────┤
│ Observations:                                                │
│ • Connection pool size: 10 (unchanged since launch)         │
│ • Peak concurrent users: 500 (was 300 three weeks ago)      │
│ • Average request time: 200ms (was 150ms)                   │
│ • Connections leaked: ~2 per hour (never released)          │
│ • Error: "Connection pool exhausted" in logs                │
│                                                              │
│ Pattern:                                                     │
│ • Occurs at 2pm-4pm daily (peak traffic)                    │
│ • Gradual degradation over 30 minutes                       │
│ • Recovery requires app restart                             │
│ • Long-running queries block pool (some 30+ seconds)        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3. GOAL/TARGET                                               │
├─────────────────────────────────────────────────────────────┤
│ • Zero downtime due to connection exhaustion                │
│ • Support 1000 concurrent users (2x current peak)           │
│ • All connections released within 5 seconds                 │
│ • Achieve within 1 week                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 4. ROOT CAUSE ANALYSIS                                       │
├─────────────────────────────────────────────────────────────┤
│ 5 Whys:                                                      │
│ Problem: Connection pool exhausted                          │
│ Why 1: All 10 connections in use, none available            │
│ Why 2: Connections not released after requests              │
│ Why 3: Error handling doesn't close connections             │
│ Why 4: Try-catch blocks missing .finally()                  │
│ Why 5: No code review checklist for resource cleanup        │
│                                                              │
│ Contributing factors:                                        │
│ • Pool size too small for current load                      │
│ • No connection timeout configured (hangs forever)          │
│ • Slow queries hold connections longer                      │
│ • No monitoring/alerting on pool metrics                    │
│                                                              │
│ ROOT CAUSE: Systematic issue with resource cleanup +        │
│             insufficient pool sizing                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 5. COUNTERMEASURES                                           │
├─────────────────────────────────────────────────────────────┤
│ Immediate (This Week):                                       │
│ 1. Audit all DB code, add .finally() for connection release │
│ 2. Increase pool size: 10 → 30                              │
│ 3. Add connection timeout: 10 seconds                       │
│ 4. Add pool monitoring & alerts (>80% used)                 │
│                                                              │
│ Short-term (2 Weeks):                                        │
│ 5. Optimize slow queries (add indexes)                      │
│ 6. Implement connection pooling best practices doc          │
│ 7. Add automated test for connection leaks                  │
│                                                              │
│ Long-term (1 Month):                                         │
│ 8. Migrate to connection pool library with auto-release     │
│ 9. Add linter rule detecting missing .finally()             │
│ 10. Create PR checklist for resource management             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 6. IMPLEMENTATION PLAN                                       │
├─────────────────────────────────────────────────────────────┤
│ Week 1 (Nov 14-18):                                          │
│ • Day 1-2: Audit & fix connection leaks [Dev Team]          │
│ • Day 2: Increase pool size, add timeout [DevOps]           │
│ • Day 3: Set up monitoring [SRE]                            │
│ • Day 4: Test under load [QA]                               │
│ • Day 5: Deploy to production [DevOps]                      │
│                                                              │
│ Week 2 (Nov 21-25):                                          │
│ • Optimize identified slow queries [DB Team]                │
│ • Write best practices doc [Tech Writer + Dev Lead]         │
│ • Create connection leak test [QA Team]                     │
│                                                              │
│ Week 3-4 (Nov 28 - Dec 9):                                   │
│ • Evaluate connection pool libraries [Dev Team]             │
│ • Add linter rules [Dev Lead]                               │
│ • Update PR template [Dev Lead]                             │
│                                                              │
│ Dependencies: None blocking Week 1 fixes                     │
│ Resources: 2 developers, 1 DevOps, 1 SRE                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 7. FOLLOW-UP                                                 │
├─────────────────────────────────────────────────────────────┤
│ Success Metrics:                                             │
│ • Zero downtime incidents (monitor 4 weeks)                 │
│ • Pool usage stays <80% during peak                         │
│ • No connection leaks detected                              │
│ • Response time <200ms p95                                  │
│                                                              │
│ Monitoring:                                                  │
│ • Daily: Check pool usage dashboard                         │
│ • Weekly: Review connection leak alerts                     │
│ • Bi-weekly: Team retrospective on progress                 │
│                                                              │
│ Review Dates:                                                │
│ • Week 1 (Nov 18): Verify immediate fixes effective         │
│ • Week 2 (Nov 25): Assess optimization impact               │
│ • Week 4 (Dec 9): Final review, close A3                    │
│                                                              │
│ Prevention:                                                  │
│ • Add connection handling to onboarding                     │
│ • Monthly audit of resource management code                 │
│ • Include pool metrics in SRE runbook                       │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════
```

### Example 2: Security Vulnerability in Production

```
═══════════════════════════════════════════════════════════════
                    A3 PROBLEM ANALYSIS
═══════════════════════════════════════════════════════════════

TITLE: Critical SQL Injection Vulnerability
OWNER: Security Team Lead
DATE: 2024-11-14

┌─────────────────────────────────────────────────────────────┐
│ 1. BACKGROUND                                                │
├─────────────────────────────────────────────────────────────┤
│ • Critical security vulnerability reported by researcher    │
│ • SQL injection in user search endpoint                     │
│ • Potential data breach affecting 100K+ user records        │
│ • CVSS score: 9.8 (Critical)                                │
│ • Vulnerability exists in production for 6 months           │
│ • Similar issue found in 2 other endpoints (scanning)       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. CURRENT CONDITION                                         │
├─────────────────────────────────────────────────────────────┤
│ Vulnerable Code:                                             │
│ • /api/users/search endpoint uses string concatenation      │
│ • Input: search query (user-provided, not sanitized)        │
│ • Pattern: `SELECT * FROM users WHERE name = '${input}'`    │
│                                                              │
│ Scope:                                                       │
│ • 3 endpoints vulnerable (search, filter, export)           │
│ • All use same unsafe pattern                               │
│ • No parameterized queries                                  │
│ • No input validation layer                                 │
│                                                              │
│ Risk Assessment:                                             │
│ • Exploitable from public internet                          │
│ • No evidence of exploitation (logs checked)                │
│ • Similar code in admin panel (higher privilege)            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3. GOAL/TARGET                                               │
├─────────────────────────────────────────────────────────────┤
│ • Patch all SQL injection vulnerabilities within 24 hours   │
│ • Zero SQL injection vulnerabilities in codebase            │
│ • Prevent similar issues in future code                     │
│ • Verify no unauthorized access occurred                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 4. ROOT CAUSE ANALYSIS                                       │
├─────────────────────────────────────────────────────────────┤
│ 5 Whys:                                                      │
│ Problem: SQL injection vulnerability in production          │
│ Why 1: User input concatenated directly into SQL            │
│ Why 2: Developer wasn't aware of SQL injection risks        │
│ Why 3: No security training for new developers              │
│ Why 4: Security not part of onboarding checklist            │
│ Why 5: Security team not involved in development process    │
│                                                              │
│ Contributing Factors (Fishbone):                             │
│ • Process: No security code review                          │
│ • Technology: ORM not used consistently                     │
│ • People: Knowledge gap in secure coding                    │
│ • Methods: No SAST tools in CI/CD                           │
│                                                              │
│ ROOT CAUSE: Security not integrated into development        │
│             process, training gap                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 5. COUNTERMEASURES                                           │
├─────────────────────────────────────────────────────────────┤
│ Immediate (24 Hours):                                        │
│ 1. Patch all 3 vulnerable endpoints                         │
│ 2. Deploy hotfix to production                              │
│ 3. Scan codebase for similar patterns                       │
│ 4. Review access logs for exploitation attempts             │
│                                                              │
│ Short-term (1 Week):                                         │
│ 5. Replace all raw SQL with parameterized queries           │
│ 6. Add input validation middleware                          │
│ 7. Set up SAST tool in CI (Snyk/SonarQube)                  │
│ 8. Security team review of all data access code             │
│                                                              │
│ Long-term (1 Month):                                         │
│ 9. Mandatory security training for all developers           │
│ 10. Add security review to PR process                       │
│ 11. Migrate to ORM for all database access                  │
│ 12. Implement security champion program                     │
│ 13. Quarterly security audits                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 6. IMPLEMENTATION PLAN                                       │
├─────────────────────────────────────────────────────────────┤
│ Hour 0-4 (Emergency Response):                               │
│ • Write & test patches [Security + Senior Dev]              │
│ • Emergency PR review [CTO + Tech Lead]                     │
│ • Deploy to staging [DevOps]                                │
│                                                              │
│ Hour 4-24 (Production Deploy):                               │
│ • Deploy hotfix [DevOps + On-call]                          │
│ • Monitor for issues [SRE Team]                             │
│ • Scan logs for exploitation [Security Team]                │
│ • Notify stakeholders [Security Lead + CEO]                 │
│                                                              │
│ Day 2-7:                                                     │
│ • Full codebase remediation [Dev Team]                      │
│ • SAST tool setup [DevOps + Security]                       │
│ • Security review [External Auditor]                        │
│                                                              │
│ Week 2-4:                                                    │
│ • Security training program [Security + HR]                 │
│ • Process improvements [Engineering Leadership]             │
│                                                              │
│ Dependencies: External auditor availability (Week 2)         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 7. FOLLOW-UP                                                 │
├─────────────────────────────────────────────────────────────┤
│ Success Metrics:                                             │
│ • Zero SQL injection vulnerabilities (verified by scan)     │
│ • 100% of PRs pass SAST checks                              │
│ • 100% developer security training completion               │
│ • No unauthorized access detected in log analysis           │
│                                                              │
│ Verification:                                                │
│ • Day 1: Verify patch deployed, vulnerability closed        │
│ • Week 1: External security audit confirms fixes            │
│ • Week 2: SAST tool catching similar issues                 │
│ • Month 1: Training completion, process adoption            │
│                                                              │
│ Prevention:                                                  │
│ • SAST tools block vulnerable code in CI                    │
│ • Security review required for data access code             │
│ • Quarterly penetration testing                             │
│ • Annual security training refresh                          │
│                                                              │
│ Incident Report:                                             │
│ • Post-mortem meeting: Nov 16                               │
│ • Document lessons learned                                  │
│ • Share with engineering org                                │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════
```

## Notes
- A3 forces concise, complete thinking (fits on one page)
- Use data and facts, not opinions or blame
- Root cause analysis is critical—use `/why` or `/cause-and-effect`
- Countermeasures must address root causes, not symptoms
- Implementation plan needs clear ownership and timelines
- Follow-up ensures sustainable improvement
- A3 becomes historical record for organizational learning
- Update A3 as situation evolves (living document until closed)
- Consider A3 for: incidents, recurring issues, major improvements
- Overkill for: small bugs, one-line fixes, trivial issues

