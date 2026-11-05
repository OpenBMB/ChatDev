---
name: create-ideas
description: Generate ideas in one shot using creative sampling
argument-hint: Topic or problem to generate ideas for. Optional amount of ideas to generate.
---

# Generate Ideas

You are a helpful assistant. For each query, please generate a set of 6 possible responses, each as separate list item. Responses should each include a text and a numeric probability.
Please sample responses at random from the [full distribution / tails of the distribution], in such way that:

- For first 3 responses aim for high probability, over 0.80
- For last 3 responses aim for diversity - explore different regions of the solution space, such that the probability of each response is less than 0.10

Important: Avoid overlapping responses - each response should be genuinely different from the others!
