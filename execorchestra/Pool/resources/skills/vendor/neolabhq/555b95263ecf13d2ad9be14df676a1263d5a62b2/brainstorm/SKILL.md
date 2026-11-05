---
name: brainstorm
description: Use when creating or developing, before writing code or implementation plans - refines rough ideas into fully-formed designs through collaborative questioning, alternative exploration, and incremental validation. Don't use during clear 'mechanical' processes
argument-hint: Optional initial feature concept, topic to brainstorm or draft specification file
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design in small sections (200-300 words), checking after each section whether it looks right so far.

## The Process

**Understanding the idea:**

- Check out the current project state first (files, docs, recent commits)
- Ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**

- Generate 6 possible approaches with trade-offs. Approaches should each include a text and a numeric probability. Please sample responses at random from the [full distribution / tails of the distribution], in such way that:
  - For first 3 responses aim for high probability, over 0.80
  - For last 3 responses aim for diversity - explore different regions of the solution space, such that the probability of each response is less than 0.10
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**

- Once you believe you understand what you're building, present the design
- Break it into sections of 200-300 words
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

## After the Design

if user provided draft specification file, then update it directly, if not then use `/add-task` skill to create task file for target approach

Important: In specification file, write target approach in sections, in `## Initial User Prompt -> ### Requirements` section, before `## Description` section. Description will be filled in future stage.

After filling task file, suggest use to run `/clear` and then `/plan-task <task-file-path>` to refine the task file.

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design in sections, validate each
- **Be flexible** - Go back and clarify when something doesn't make sense
