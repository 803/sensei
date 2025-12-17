# Sensei Business Strategy

## My Honest Assessment of AI Coding Weaknesses

Having introspected on what I struggle with:

### 1. Documentation Hallucination (The Core Problem)

I confidently state things that are wrong:

- API signatures that don't exist
- Deprecated patterns presented as current
- Made-up configuration options
- Wrong version compatibility

**The worst part**: I don't know what I don't know. I can't distinguish "definitely right" from "probably right" from "totally made up."

### 2. Training Data Staleness

My knowledge has a cutoff. Frameworks evolve constantly:

- FastAPI 0.115 has features I've never seen
- React Server Components patterns keep evolving
- New libraries I can't recommend

### 3. Version Blindness

My training data is a mess of versions blended together. When someone asks about Prisma, I'm drawing from v2, v3, v4, v5 all at once with no awareness of which is which.

---

## The User Segments and Their Pain

### Professional Developers (Claude Code, Cursor)

- **CAN** often recognize bad suggestions
- **Pain**: Time wasted debugging AI mistakes, then verifying against docs
- **Cost of hallucination**: Hours lost, frustration, trust erosion

### Non-Technical Builders (Replit, Lovable, Bolt)

- **CANNOT** recognize bad suggestions
- **Pain**: Get stuck, can't debug, don't know what's wrong
- **Cost of hallucination**: Complete abandonment

**This is a crucial insight**: For non-technical users, hallucination cost is 10x higher because they CAN'T recover. They're stuck. They abandon. Everyone loses.

---

## Where Value Gets Destroyed Today

### The "Try It and See" Loop

```
AI writes code → doesn't work → user debugs → finds doc issue → fixes → repeat
```

This loop eats HOURS per issue. It's the primary destroyer of productivity.

### The "Is This Even Possible?" Problem

User asks AI to do something. AI hallucinates a solution that fundamentally CAN'T work (the API doesn't exist, the library doesn't support it). User spends hours trying to make an impossible thing work.

### The "Which Version?" Problem

User has library v2.3, AI trained on v1.8. APIs changed. User follows AI's instructions perfectly and nothing works.

### The "Outdated Pattern" Problem

AI suggests deprecated/discouraged patterns. User builds on a bad foundation. Technical debt from day one.

---

## How to Make Sensei Incredibly Valuable

### Strategy 1: Be Proactive, Not Just Reactive

Current Sensei waits for queries. But the highest value is **preventing errors before they happen**.

**Idea: Inline Verification**

- When any AI is about to write code using a library, Sensei validates BEFORE output
- Every generated API call checked against real docs
- Wrong things never reach the user

This is a paradigm shift: from "answer questions" to "prevent mistakes."

### Strategy 2: Version-Aware Precision

**Know the user's exact versions** from:

- `package.json`
- `requirements.txt`
- `Cargo.toml`
- `go.mod`

Then **only return docs for THOSE versions**. No more version soup.

**Even better**: Warn about deprecated features in their specific version. "This API exists but is deprecated in v3.2. Use X instead."

### Strategy 3: Verified Working Examples Database

Not just docs, but **TESTED code that actually works**.

```
This exact code works with:
- FastAPI 0.109.0
- Python 3.11
- Pydantic 2.5
Tested: 2024-12-15
```

Confidence through verification, not guessing.

### Strategy 4: Error-to-Fix Pipeline

When library errors happen, Sensei can diagnose:

- Parse the error message
- Match against known patterns
- Look up the fix in docs
- Return specific solution for user's version

"This error means X. Looking at your version (FastAPI 0.104), you need to change Y to Z."

### Strategy 5: Guardrails for Non-Technical Users

For Replit/Lovable users specifically:

- **Pre-flight checks**: Before generating complex code, verify it's actually possible
- **Impossibility detection**: "This library doesn't support X. Here's an alternative approach that does."
- **Plain-language explanations**: When things fail, explain WHY in simple terms
- **Guided recovery**: Step-by-step help when stuck, not just "try this code"

---

## Business Model Opportunities

### B2B2C: Platform Integration (Highest Leverage)

**Target**: Replit, Lovable, Bolt, v0, and similar

**Value prop**: "Increase user completion rates and retention"

- Their success = user success
- Lower hallucination rate = higher completion rate = happier users = more retention
- Sensei becomes infrastructure they depend on

**Pricing**: Per-query API, revenue share, or per-seat licensing

**Why this is compelling**: These platforms have massive distribution. If Sensei makes their AI 20% more accurate, that's millions of users benefiting, and those platforms will pay handsomely for competitive advantage.

### B2B: Developer Tool Integration

**Target**: Cursor, Windsurf, Codeium, Sourcegraph Cody

**Value prop**: "Differentiate on accuracy"

Same logic as above but for developer-focused tools.

### B2C: Direct to Developers

**Current model**: Claude Code plugin

**Enhancement**: Premium tier with:

- Faster responses (priority queue)
- More sources searched
- Team knowledge sharing
- Custom documentation ingestion

### Enterprise: Accuracy + Compliance

**Value prop**: "AI coding you can trust, with audit trails"

- Every answer traced to sources
- Internal docs + external docs unified
- Stack-specific tuning for their versions
- Team knowledge capture and sharing

---

## The Infrastructure Play (Biggest Long-Term Opportunity)

**Vision**: Sensei becomes the "accuracy layer" for ALL AI coding tools.

Like how:

- Stripe handles payments for everyone
- Twilio handles SMS for everyone
- Auth0 handles auth for everyone

**Sensei handles documentation accuracy for everyone.**

Every AI coding tool would integrate Sensei's API to:

1. Verify generated code before outputting
2. Get version-specific information
3. Access cache of verified working examples
4. Provide error diagnosis

This creates:

- **Network effects**: More queries → better cache → better for everyone
- **Data moat**: Feedback loop improves quality continuously
- **Switching costs**: Integrations are sticky

---

## The Flywheel

```
More integrations → More queries → Better cache → Better answers → More integrations
                          ↓
                    More feedback
                          ↓
                   Higher quality
                          ↓
                    More trust
```

**The cache is incredibly valuable**. If Sensei answers 1M queries about React hooks, every subsequent React hooks query is instant and verified. This compounds.

---

## Concrete Recommendations

### Near-Term (Validate & Wedge)

1. **Quantify the problem**: How much time do developers lose to doc hallucinations? What's abandonment rate on Replit/Lovable due to AI errors?
2. **Pick one wedge**:
   - **Option A**: Double down on Claude Code plugin (prove value, get testimonials)
   - **Option B**: Pursue one Replit/Lovable partnership (prove B2B2C model)
3. **Build feedback loop**: Make it trivially easy to report when Sensei is wrong/right

### Medium-Term (Moat Building)

1. **Verified examples database**: Start collecting TESTED code snippets
2. **Version awareness**: Build version detection and version-specific responses
3. **Error pattern library**: Map common errors to fixes

### Long-Term (Platform Play)

1. **API-first architecture**: Build for other tools to integrate
2. **Partnerships**: Official relationships with framework maintainers
3. **Become infrastructure**: "Powered by Sensei" badge

---

## The Key Insight

**Users don't want "better documentation search." They want working code and faster outcomes.**

Sensei's value isn't answering documentation questions—it's **preventing wasted time and failed projects**.

- For professionals: Hours saved, frustration avoided, trust maintained.
- For non-technical builders: Projects completed instead of abandoned. Dreams shipped instead of stuck.

That's the value to maximize.
