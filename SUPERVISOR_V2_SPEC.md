# Supervisor v2 — Architecture Specification

**Status:** Planned for v2 (after first paying dealer onboarded)
**Estimated build time:** 1.5–2 days of focused work
**Trigger to start:** When you have 50+ real conversations from a live dealer
**Author:** Aman Dominator, with Claude

---

## Why v2 exists

The v1 bot is a **state machine + bolt-on patches** architecture:

User msg → state dispatcher → handler → response
↑
+ _detect_correction (patch)
+ _handle_intent_correction (patch)
+ _handle_intent_restart (patch)
+ memory_feature welcome-back (patch)



Each patch solves one class of edge case. But humans speak in ways that don't fit boxes. Every new edge case = new patch = more places for bugs to hide.

The Supervisor architecture **inverts** this:



User msg → SUPERVISOR (decides what should happen) → executor (does it)



Single brain. Single decision-maker. Predictable, debuggable, scalable.

---

## When to build it

**Build trigger:** First paying dealer accumulates 50+ real conversations. Reasons:

1. **Speculation kills good architecture.** v1's 8 event types are my guesses. Real users' actual edge cases will be different. Wait until you have real data.
2. **Patches buy time.** v1 is good enough to demo and onboard.
3. **You'll build it 10x better with data.** "Users frequently say X in state Y" beats "I imagine users might say X."

**Do NOT build it because:**
- The bot has a few rough edges (patch them)
- You feel like refactoring (don't refactor without a goal)
- Someone said you should use LLMs more (you already do)

---

## Architecture

### Four files

#### `supervisor.py` (NEW — the brain)

Single entry point for every user message. Decides what happens.

```python
class Supervisor:
    def decide(self, message, session, inventory) -> SupervisorDecision:
        """
        Hybrid rule + LLM. Returns one of 8 events with payload.
        """
        # 1. Cheap rule-based fast path (no LLM call needed for obvious cases)
        if self._is_obvious_yes_no(message): ...
        if self._is_obvious_email(message): ...
        if self._is_obvious_phone(message): ...
        
        # 2. Otherwise: call Gemini once with full context
        decision = self._llm_classify(message, session, inventory)
        
        # 3. Apply confidence threshold (don't act on low-confidence decisions)
        if decision.confidence < 0.75:
            return SupervisorDecision(event=Event.CONTINUE, ...)
        
        return decision
```

**Cost optimization:** Rule-based fast path handles ~50% of messages (yes/no/email/phone/single-word answers) with zero LLM calls. Only ambiguous messages go to Gemini.

#### `intent_classifier.py` (KEEP — already built)

The current `intent_classifier.py` from v1 becomes the LLM backend for the Supervisor. Same function signature, same prompts. The Supervisor wraps it with rule-based pre-filtering.

#### `conversation_flow.py` (SIMPLIFY — reduce 50%)

Strip out all patches:
- ❌ Delete `_detect_correction`
- ❌ Delete `_handle_intent_correction`
- ❌ Delete `_handle_intent_restart`
- ❌ Delete `_handle_returning_user_confirm`

Keep only:
- ✅ `handle_message` (now just a thin dispatcher)
- ✅ Per-state handlers (`_handle_city`, `_handle_budget`, etc.) — each one stays focused on a single thing: capturing one field
- ✅ 6 core states only: GREETING, AWAITING_INFO, SHOWING_PROPERTY, AWAITING_FEEDBACK, SCHEDULING, DONE

Each handler asks: "Given the supervisor's decision, what do I do?" — never tries to second-guess the user.

#### `session_memory.py` (NEW — proper context store)

Replaces the scattered `conversation_state.update()` calls. Single object per user:

```python
class Session:
    fields: Dict[str, Any]              # city, prop_type, budget, email, etc.
    history: List[Message]              # last 20 messages with timestamps
    state: FlowState                    # current state
    signals: Dict[str, int]             # hesitation_count, correction_count, etc.
    last_seen: datetime
    tier: MemoryTier                    # silent/friendly/confirm
    fingerprint: str
```

Persistence: in-memory + JSON file snapshot every 30s. Redis-ready for scaling later.

---

## The 8 Supervisor Events

These are v1 guesses. **Adjust based on real conversation data from your first dealer.**

| Event | Trigger | Action |
|---|---|---|
| `CONTINUE` | User answered the asked question normally | Pass through to current state's handler |
| `CORRECT_FIELD` | User changed one previously-given value | Update field, stay in current state |
| `RESTART_SEARCH` | User wants fresh search with new criteria | Reset session except identity, jump to first missing field |
| `INTERRUPT_QUESTION` | User asked the bot a question mid-flow | Answer the question, then re-prompt original state |
| `EXPRESS_FRUSTRATION` | User shows annoyance/anger ("this is taking forever") | Apologize + escalate to human consultant |
| `OFF_TOPIC` | User said something unrelated to property | Gentle redirect: "Happy to chat, but back to your search..." |
| `READY_TO_BUY` | User shows high purchase intent ("send me details NOW", "I'm ready") | Skip remaining qualification, fast-track to scheduling |
| `DROPOFF_RISK` | User seems unsure, long pauses, vague answers | Send reassurance + simplified options, lower friction |

---

## Implementation milestones

**Milestone 1 — Build the Supervisor skeleton** (3 hours)
- Create `supervisor.py` with `Supervisor.decide()` returning v1 intent_classifier output
- Wire into `handle_message` as a single call before state dispatch
- All existing tests pass

**Milestone 2 — Migrate event handling** (4 hours)
- Add handlers for CORRECT_FIELD, RESTART_SEARCH, INTERRUPT_QUESTION
- Each event has ONE clean handler in the Supervisor, not scattered across flow handlers
- Delete v1 patches: `_detect_correction`, `_handle_intent_correction`, `_handle_intent_restart`

**Milestone 3 — Build session_memory** (3 hours)
- Create `Session` dataclass + `SessionStore`
- Migrate from scattered `conversation_state` calls to centralized session API
- Add JSON-snapshot persistence

**Milestone 4 — Add the 4 new events** (4 hours)
- EXPRESS_FRUSTRATION → handover trigger
- OFF_TOPIC → soft redirect
- READY_TO_BUY → fast-track
- DROPOFF_RISK → reassurance flow

**Milestone 5 — Test against real conversations** (4 hours)
- Take 50 real dealer conversations from v1
- Replay each through v2
- Verify Supervisor decisions match what good UX would do
- Tune confidence thresholds

**Total: ~18 focused hours, spread over 2 days.**

---

## What to learn from your first dealer before building

Track these during your first 30 days of paid operation:

1. **Top 5 user message types the bot mishandles.** Real edge cases, not theoretical.
2. **Conversion drop-off step.** Where do leads stop responding?
3. **Dealer's complaint themes.** "Bot doesn't sound like my brand" / "Misses obvious questions" / etc.
4. **Conversation length distribution.** How many turns to qualify a hot lead?
5. **Correction frequency.** How often do users change their answer mid-flow?

This data IS your v2 spec. The 8 events above are placeholders; your real data will refine them.

---

## Cost analysis

v1 cost per conversation: ~1 Gemini call per user message = $X
v2 cost per conversation: 
- Rule-based fast path: 0 Gemini calls
- LLM path: 1 Gemini call
- Expected mix: 50% rules, 50% LLM = ~0.5 Gemini calls per message = $X/2

**v2 should cost half as much to run, with better accuracy.**

---

## Migration safety

Keep v1 running in parallel while building v2:
- New env var: `USE_SUPERVISOR=false` (default)
- Set to `true` for one dealer at a time
- Monitor logs for divergence
- Roll back instantly if anything goes wrong

---

## Definition of done for v2

- [ ] Single entry point: every message goes through `Supervisor.decide()` first
- [ ] Zero `_detect_*` or `_handle_intent_*` methods in `conversation_flow.py`
- [ ] `conversation_flow.py` under 600 lines (currently ~1500)
- [ ] All 8 events have one clean handler each
- [ ] Cost per conversation cut by 40%+
- [ ] At least 50 real conversations replayed cleanly through v2
- [ ] Kill switch tested (`USE_SUPERVISOR=false` instantly reverts to v1)
- [ ] One paying dealer migrated and approves the v2 experience