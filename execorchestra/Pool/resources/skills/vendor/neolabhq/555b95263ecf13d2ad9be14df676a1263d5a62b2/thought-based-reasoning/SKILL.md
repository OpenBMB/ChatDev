---
name: thought-based-reasoning
description: Use when tackling complex reasoning tasks requiring step-by-step logic, multi-step arithmetic, commonsense reasoning, symbolic manipulation, or problems where simple prompting fails - provides comprehensive guide to Chain-of-Thought and related prompting techniques (Zero-shot CoT, Self-Consistency, Tree of Thoughts, Least-to-Most, ReAct, PAL, Reflexion) with templates, decision matrices, and research-backed patterns
---

# Thought-Based Reasoning Techniques for LLMs

## Overview

Chain-of-Thought (CoT) prompting and its variants encourage LLMs to generate intermediate reasoning steps before arriving at a final answer, significantly improving performance on complex reasoning tasks. These techniques transform how models approach problems by making implicit reasoning explicit.


## Quick Reference

| Technique | When to Use | Complexity | Accuracy Gain |
|-----------|-------------|------------|---------------|
| Zero-shot CoT | Quick reasoning, no examples available | Low | +20-60% |
| Few-shot CoT | Have good examples, consistent format needed | Medium | +30-70% |
| Self-Consistency | High-stakes decisions, need confidence | Medium | +10-20% over CoT |
| Tree of Thoughts | Complex problems requiring exploration | High | +50-70% on hard tasks |
| Least-to-Most | Multi-step problems with subproblems | Medium | +30-80% |
| ReAct | Tasks requiring external information | Medium | +15-35% |
| PAL | Mathematical/computational problems | Medium | +10-15% |
| Reflexion | Iterative improvement, learning from errors | High | +10-20% |

---

## Core Techniques

### 1. Chain-of-Thought (CoT) Prompting

**Paper**: "Chain of Thought Prompting Elicits Reasoning in Large Language Models" (Wei et al., 2022)
**Citations**: 14,255+

#### When to Use
- Multi-step arithmetic or math word problems
- Commonsense reasoning requiring logical deduction
- Symbolic reasoning tasks
- When you have good exemplars showing reasoning

#### How It Works
Provide few-shot examples that include intermediate reasoning steps, not just question-answer pairs. The model learns to generate similar step-by-step reasoning.

#### Prompt Template

```
Q: Roger has 5 tennis balls. He buys 2 more cans of tennis balls. Each can has 3 tennis balls. How many tennis balls does he have now?
A: Roger started with 5 balls. 2 cans of 3 tennis balls each is 6 tennis balls. 5 + 6 = 11. The answer is 11.

Q: The cafeteria had 23 apples. If they used 20 to make lunch and bought 6 more, how many apples do they have?
A: The cafeteria had 23 apples originally. They used 20 to make lunch. So they had 23 - 20 = 3. They bought 6 more apples, so they have 3 + 6 = 9. The answer is 9.

Q: [YOUR QUESTION HERE]
A:
```

#### Strengths
- Significant accuracy improvements on reasoning tasks
- Interpretable intermediate steps
- Works well with large models (>100B parameters)

#### Limitations
- Requires crafting good exemplars
- Less effective on smaller models
- Can still make calculation errors

---

### 2. Zero-shot Chain-of-Thought

**Paper**: "Large Language Models are Zero-Shot Reasoners" (Kojima et al., 2022)
**Citations**: 5,985+

#### When to Use
- No exemplars available
- Quick reasoning needed
- General-purpose reasoning across task types
- Prototyping before creating few-shot examples

#### How It Works
Simply append "Let's think step by step" (or similar phrase) to the prompt. This triggers the model to generate reasoning steps without any examples.

#### Prompt Template

```
Q: A juggler can juggle 16 balls. Half of the balls are golf balls, and half of the golf balls are blue. How many blue golf balls are there?

Let's think step by step.
```

**Alternative trigger phrases**:
- "Let's work this out step by step to be sure we have the right answer."
- "Let's break this down."
- "Let's approach this systematically."
- "First, let me understand the problem..."

#### Two-Stage Approach (More Robust)

**Stage 1 - Reasoning Extraction**:
```
Q: [QUESTION]
A: Let's think step by step.
```

**Stage 2 - Answer Extraction**:
```
[REASONING FROM STAGE 1]
Therefore, the answer is
```

#### Strengths
- No exemplar crafting required
- Generalizes across task types
- Simple to implement

#### Limitations
- Less effective than few-shot CoT
- Can produce verbose or irrelevant reasoning
- Sensitive to exact phrasing

---

### 3. Self-Consistency

**Paper**: "Self-Consistency Improves Chain of Thought Reasoning in Language Models" (Wang et al., 2022)
**Citations**: 5,379+

#### When to Use
- High-stakes decisions requiring confidence
- Problems with multiple valid reasoning paths
- When you need to reduce variance in outputs
- Verification of reasoning correctness

#### How It Works
Sample multiple diverse reasoning paths, then select the most consistent answer via majority voting. The intuition: correct answers can be reached through multiple reasoning paths.

#### Prompt Template

```
[Use any CoT prompt - zero-shot or few-shot]

[Generate N samples with temperature > 0]

[Extract final answers from each sample]

[Return the most frequent answer (majority vote)]
```

#### Implementation Example

```python
def self_consistency(prompt, n_samples=5, temperature=0.7):
    answers = []
    for _ in range(n_samples):
        response = llm.generate(prompt, temperature=temperature)
        answer = extract_answer(response)
        answers.append(answer)

    # Majority vote
    return Counter(answers).most_common(1)[0][0]
```

#### Strengths
- Significant accuracy boost over single-path CoT
- Provides confidence measure (agreement level)
- Task-agnostic improvement

#### Limitations
- Higher computational cost (N times more generations)
- Requires extractable discrete answers
- Diminishing returns beyond ~10-20 samples

---

### 4. Tree of Thoughts (ToT)

**Paper**: "Tree of Thoughts: Deliberate Problem Solving with Large Language Models" (Yao et al., 2023)
**Citations**: 3,026+

#### When to Use
- Complex problems requiring exploration/backtracking
- Tasks where initial decisions are pivotal
- Creative problem-solving (writing, puzzles)
- When CoT alone achieves <50% accuracy

#### How It Works
Generalize CoT to a tree structure where each node is a "thought" (coherent language unit). Uses search algorithms (BFS/DFS) with self-evaluation to explore and select promising reasoning paths.

#### Prompt Template

**Thought Generation**:
```
Given the current state:
[STATE]

Generate 3-5 possible next steps to solve this problem.
```

**State Evaluation**:
```
Evaluate if the following partial solution is:
- "sure" (definitely leads to solution)
- "maybe" (could potentially work)
- "impossible" (cannot lead to solution)

Partial solution:
[THOUGHTS SO FAR]
```

**BFS/DFS Search**:
```python
def tree_of_thoughts(problem, max_depth=3, beam_width=3):
    queue = [(problem, [])]  # (state, thought_path)

    while queue:
        state, path = queue.pop(0)

        if is_solved(state):
            return path

        # Generate candidate thoughts
        thoughts = generate_thoughts(state, k=5)

        # Evaluate and keep top-k
        evaluated = [(t, evaluate(state, t)) for t in thoughts]
        top_k = sorted(evaluated, key=lambda x: x[1])[:beam_width]

        for thought, score in top_k:
            if score != "impossible":
                new_state = apply_thought(state, thought)
                queue.append((new_state, path + [thought]))

    return None
```

#### Example: Game of 24

```
Problem: Use 4, 9, 10, 13 to get 24 (use +, -, *, / and each number once)

Thought 1: 13 - 9 = 4 (Now have: 4, 4, 10)
Evaluation: "maybe" - have two 4s and 10, could work

Thought 2: 10 - 4 = 6 (Now have: 4, 6, 13)
Evaluation: "maybe" - 4 * 6 = 24, need to use 13

Thought 3: 4 + 9 = 13 (Now have: 10, 13, 13)
Evaluation: "impossible" - no way to get 24 from these
```

#### Strengths
- Dramatically improves performance on hard tasks (4% → 74% on Game of 24)
- Enables backtracking and exploration
- Self-evaluation catches errors early

#### Limitations
- Significantly higher computational cost
- Requires task-specific thought decomposition
- Complex to implement

---

### 5. Least-to-Most Prompting

**Paper**: "Least-to-Most Prompting Enables Complex Reasoning in Large Language Models" (Zhou et al., 2022)
**Citations**: 1,466+

#### When to Use
- Problems harder than your exemplars
- Compositional generalization tasks
- Multi-step problems with clear subproblems
- Symbol manipulation and SCAN-like tasks

#### How It Works
Two-stage process:
1. **Decomposition**: Break complex problem into simpler subproblems
2. **Sequential Solving**: Solve subproblems in order, using previous answers

#### Prompt Template

**Stage 1: Decomposition**
```
Q: Four years ago, Kody was only half as old as Mohamed. If Mohamed is currently twice as old as 30 years old, how old is Kody?

To solve "Four years ago, Kody was only half as old as Mohamed. If Mohamed is currently twice as old as 30 years old, how old is Kody?", we need to first solve:
- "If Mohamed is currently twice as old as 30 years old, how old is Mohamed?"
Then we need to solve:
- "Four years ago, Kody was only half as old as Mohamed. How old is Kody?"
```

**Stage 2: Sequential Solving**
```
Q: If Mohamed is currently twice as old as 30 years old, how old is Mohamed?
A: Mohamed is twice as old as 30, so Mohamed is 30 * 2 = 60 years old.

Q: Four years ago, Kody was only half as old as Mohamed. Mohamed is 60 years old. How old is Kody?
A: Four years ago, Mohamed was 60 - 4 = 56 years old. Kody was half as old, so Kody was 56 / 2 = 28 years old four years ago. Therefore, Kody is currently 28 + 4 = 32 years old.

The answer is 32.
```

#### Strengths
- Excellent at generalizing to harder problems
- Works well on compositional tasks
- Explicit problem decomposition aids interpretability

#### Limitations
- Requires two-stage prompting
- Decomposition step can fail on novel structures
- More complex setup than single-stage CoT

---

### 6. ReAct (Reasoning + Acting)

**Paper**: "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022)
**Citations**: 5,012+

#### When to Use
- Tasks requiring external information (search, APIs)
- Interactive decision-making environments
- Multi-hop question answering
- When pure reasoning leads to hallucination

#### How It Works
Interleave reasoning traces ("Thought") with actions ("Action") and observations ("Observation"). Reasoning helps plan actions; actions provide new information for reasoning.

#### Prompt Template

```
Question: What is the elevation range for the area that the eastern sector of the Colorado orogeny extends into?

Thought 1: I need to search Colorado orogeny, find the area that the eastern sector extends into, then find the elevation range of that area.
Action 1: Search[Colorado orogeny]
Observation 1: The Colorado orogeny was an episode of mountain building (an orogeny) in Colorado and surrounding areas.

Thought 2: It does not mention the eastern sector. So I need to look up eastern sector.
Action 2: Lookup[eastern sector]
Observation 2: The eastern sector extends into the High Plains.

Thought 3: The eastern sector extends into the High Plains. I need to search High Plains and find its elevation range.
Action 3: Search[High Plains]
Observation 3: High Plains refers to one of two distinct land regions: High Plains (United States)...

Thought 4: I need to search High Plains (United States).
Action 4: Search[High Plains (United States)]
Observation 4: The High Plains are a subregion of the Great Plains... elevation of around 1,800 to 7,000 ft (550 to 2,130 m).

Thought 5: The elevation range is 1,800 to 7,000 ft.
Action 5: Finish[1,800 to 7,000 ft]
```

#### Action Types
- `Search[query]` - Search for information
- `Lookup[keyword]` - Look up keyword in current context
- `Finish[answer]` - Return final answer

#### Strengths
- Reduces hallucination by grounding in external knowledge
- Interpretable action traces
- Handles exceptions through adaptive reasoning

#### Limitations
- Requires integration with external tools
- More complex orchestration
- Action space must be defined

---

### 7. PAL (Program-Aided Language Models)

**Paper**: "PAL: Program-aided Language Models" (Gao et al., 2022)
**Citations**: 608+

#### When to Use
- Mathematical/arithmetic reasoning
- Problems requiring precise computation
- Symbolic manipulation
- When CoT makes calculation errors

#### How It Works
Generate code (typically Python) instead of natural language reasoning. Execute the code to get the answer. The LLM handles decomposition; the interpreter handles computation.

#### Prompt Template

```
Q: Roger has 5 tennis balls. He buys 2 more cans of tennis balls. Each can has 3 tennis balls. How many tennis balls does he have now?

# solution in Python:
def solution():
    """Roger has 5 tennis balls. He buys 2 more cans of tennis balls. Each can has 3 tennis balls. How many tennis balls does he have now?"""
    tennis_balls_initial = 5
    bought_cans = 2
    tennis_balls_per_can = 3
    tennis_balls_bought = bought_cans * tennis_balls_per_can
    tennis_balls_total = tennis_balls_initial + tennis_balls_bought
    return tennis_balls_total

Q: The bakers at the Beverly Hills Bakery baked 200 loaves of bread on Monday morning. They sold 93 loaves in the morning and 39 loaves in the afternoon. A grocery store returned 6 unsold loaves. How many loaves of bread did they have left?

# solution in Python:
def solution():
    """The bakers baked 200 loaves. They sold 93 in morning, 39 in afternoon. A store returned 6. How many left?"""
    loaves_baked = 200
    loaves_sold_morning = 93
    loaves_sold_afternoon = 39
    loaves_returned = 6
    loaves_left = loaves_baked - loaves_sold_morning - loaves_sold_afternoon + loaves_returned
    return loaves_left
```

#### Strengths
- Eliminates arithmetic errors
- Clear variable naming aids interpretability
- Leverages code execution for verification

#### Limitations
- Requires code interpreter
- Not suitable for non-computational reasoning
- Model must generate syntactically correct code

---

### 8. Auto-CoT

**Paper**: "Automatic Chain of Thought Prompting in Large Language Models" (Zhang et al., 2022)
**Citations**: 838+

#### When to Use
- No manually crafted exemplars available
- Want to automate few-shot CoT setup
- Scaling CoT to many tasks
- When zero-shot CoT isn't sufficient

#### How It Works
1. Cluster questions by diversity
2. Use Zero-shot CoT to generate reasoning chains for representative questions
3. Use these auto-generated chains as few-shot exemplars

#### Prompt Template

**Step 1: Generate diverse demonstrations**
```python
# Cluster questions
clusters = cluster_questions(all_questions, k=8)

# For each cluster, pick representative and generate CoT
demonstrations = []
for cluster in clusters:
    question = select_representative(cluster)
    reasoning = zero_shot_cot(question)  # "Let's think step by step"
    demonstrations.append((question, reasoning))
```

**Step 2: Use as few-shot exemplars**
```
Q: [Demo question 1]
A: Let's think step by step. [Generated reasoning 1]

Q: [Demo question 2]
A: Let's think step by step. [Generated reasoning 2]

...

Q: [New question]
A: Let's think step by step.
```

#### Strengths
- No manual exemplar creation
- Diversity sampling improves robustness
- Matches manual CoT performance

#### Limitations
- Quality depends on zero-shot CoT quality
- Clustering requires similarity metric
- Some generated chains contain errors

---

### 9. Reflexion

**Paper**: "Reflexion: Language Agents with Verbal Reinforcement Learning" (Shinn et al., 2023)
**Citations**: 2,179+

#### When to Use
- Iterative improvement over multiple attempts
- Learning from errors without fine-tuning
- Complex coding or decision-making tasks
- When single-pass reasoning is insufficient

#### How It Works
After task failure, the agent generates a verbal "reflection" analyzing what went wrong. This reflection is stored in memory and used in subsequent attempts to avoid repeating mistakes.

#### Prompt Template

**Initial Attempt**:
```
Task: [TASK DESCRIPTION]

Thought: [REASONING]
Action: [ACTION]
...
Result: [FAILURE/PARTIAL SUCCESS]
```

**Reflection**:
```
The previous attempt failed because:
1. [SPECIFIC ERROR ANALYSIS]
2. [WHAT SHOULD HAVE BEEN DONE]
3. [KEY INSIGHT FOR NEXT ATTEMPT]

Reflection: In the next attempt, I should...
```

**Subsequent Attempt (with memory)**:
```
Task: [TASK DESCRIPTION]

Previous reflections:
- [REFLECTION 1]
- [REFLECTION 2]

Using these insights, I will now attempt the task again.

Thought: [IMPROVED REASONING]
Action: [BETTER ACTION]
```

#### Example: Code Generation

```
Task: Write a function to find the longest palindromic substring.

Attempt 1: [CODE WITH BUG]
Test Result: Failed on "babad" - expected "bab" or "aba", got "b"

Reflection: My solution only checked single characters. I need to:
1. Consider substrings of all lengths
2. Use expand-around-center technique for efficiency
3. Track both start position and maximum length

Attempt 2: [IMPROVED CODE USING REFLECTION]
Test Result: Passed all tests
```

#### Strengths
- Learns from errors without weight updates
- Achieves 91% on HumanEval (surpassing GPT-4's 80%)
- Builds episodic memory of insights

#### Limitations
- Requires multiple attempts
- Memory management for long sessions
- Quality of reflection affects improvement

---

## Decision Matrix: Which Technique to Use

```
                           Need Examples?
                          /              \
                        No                Yes
                        |                  |
                Zero-shot CoT          Few-shot CoT
                        |                  |
                Need higher accuracy?  Need computation?
                /                \           |
              Yes               No          PAL
               |                |
    Self-Consistency    Done with CoT
               |
        Still not enough?
        /              \
      Yes              No
       |                |
  Problem decomposable?  Done
  /                    \
Yes                    No
 |                      |
Least-to-Most     Need exploration?
                  /              \
                Yes              No
                 |                |
          Tree of Thoughts   Need external info?
                             /              \
                           Yes              No
                            |                |
                          ReAct         Need iteration?
                                        /           \
                                      Yes           No
                                       |             |
                                   Reflexion      Use CoT
```

---

## Best Practices

### 1. Start Simple
Begin with Zero-shot CoT ("Let's think step by step"), then progress to more complex techniques if needed.

### 2. Match Technique to Task
- **Math/Logic**: CoT, PAL, Self-Consistency
- **Multi-hop QA**: ReAct, Least-to-Most
- **Creative/Puzzles**: Tree of Thoughts
- **Iterative Tasks**: Reflexion

### 3. Combine Techniques
Techniques are often complementary:
- ReAct + Self-Consistency for robust factual answers
- ToT + PAL for complex computational exploration
- Least-to-Most + Reflexion for hard multi-step problems

### 4. Prompt Engineering Tips
- Use clear step markers ("Step 1:", "First,", etc.)
- Include diverse exemplars covering edge cases
- Format consistently across examples
- Add verification steps ("Let me verify...")

---

## Common Mistakes

| Mistake | Why It's Wrong | Fix |
|---------|---------------|-----|
| Using CoT for simple lookups | Adds unnecessary tokens and latency | Reserve for multi-step reasoning |
| Too few samples in Self-Consistency | Majority voting needs adequate samples | Use 5-10 samples minimum |
| Generic "think step by step" without checking output | Model may produce irrelevant reasoning | Validate reasoning quality, not just presence |
| Mixing techniques without understanding trade-offs | Computational cost without benefit | Understand when each technique adds value |
| Using PAL without code interpreter | Code generation is useless without execution | Ensure execution environment available |
| Not testing exemplar quality in few-shot CoT | Poor exemplars lead to poor reasoning | Validate exemplars solve problems correctly |
| Applying Tree of Thoughts to linear problems | Massive overhead for no benefit | Use ToT only when exploration needed |


---

## References

1. Wei, J. et al. (2022). "Chain of Thought Prompting Elicits Reasoning in Large Language Models." [arXiv:2201.11903](https://arxiv.org/abs/2201.11903)

2. Kojima, T. et al. (2022). "Large Language Models are Zero-Shot Reasoners." [arXiv:2205.11916](https://arxiv.org/abs/2205.11916)

3. Wang, X. et al. (2022). "Self-Consistency Improves Chain of Thought Reasoning in Language Models." [arXiv:2203.11171](https://arxiv.org/abs/2203.11171)

4. Yao, S. et al. (2023). "Tree of Thoughts: Deliberate Problem Solving with Large Language Models." [arXiv:2305.10601](https://arxiv.org/abs/2305.10601)

5. Zhou, D. et al. (2022). "Least-to-Most Prompting Enables Complex Reasoning in Large Language Models." [arXiv:2205.10625](https://arxiv.org/abs/2205.10625)

6. Yao, S. et al. (2022). "ReAct: Synergizing Reasoning and Acting in Language Models." [arXiv:2210.03629](https://arxiv.org/abs/2210.03629)

7. Gao, L. et al. (2022). "PAL: Program-aided Language Models." [arXiv:2211.10435](https://arxiv.org/abs/2211.10435)

8. Zhang, Z. et al. (2022). "Automatic Chain of Thought Prompting in Large Language Models." [arXiv:2210.03493](https://arxiv.org/abs/2210.03493)

9. Shinn, N. et al. (2023). "Reflexion: Language Agents with Verbal Reinforcement Learning." [arXiv:2303.11366](https://arxiv.org/abs/2303.11366)
