# Session Lifecycle

Typical flow:

1. Initialize SDK on customer and agent pages.
2. Generate role-specific JWT tokens.
3. Customer starts a session and receives a PIN.
4. Agent joins using the PIN.
5. Session events track connected/disconnected/end states.

See:
- [Get Started](../get-started.md)
- [Features (official)](../references/features-official.md)
