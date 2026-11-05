# ASCII Sequence Diagram Reference

Rules for drawing ASCII sequence diagrams inline in responses.

## Column Layout

Lay out participants as column headers, each above a vertical `|` lifeline.
Space columns ~28–32 characters apart so labels fit without wrapping:

```
Initiator                 Responder
   |                         |
   |                         |
```

For three or more participants, extend the layout rightward:

```
Client          Server          CA
   |               |             |
   |               |             |
```

## Arrow Conventions

| Element | Syntax | Use for |
|---------|--------|---------|
| Request (→) | `+------>` | message send |
| Reply (←) | `<- - - -+` | response / reply |
| Lost / async | `+------x` | dropped message |

- Sending end: `+`
- Receiving end: `>` (rightward) or `<` (leftward)
- Solid lines `---` for sends; dashed `- - -` for responses/replies
- Label goes **on the arrow line**, positioned between the two lifelines

```
   |                         |
   +------------------------>|  epk_I
   |                         |
   |  epk_R, Enc(k, cert_R)  |
   |<- - - - - - - - - - - - +
   |                         |
```

## Self-Loops (Local Computation)

For operations that happen at a single party without sending a message:

```
   |                         |
   +--.                      |
   |  | Sign(sk, transcript) |
   |<-'                      |
   |                         |
```

## Phase Labels

Group related steps under a phase label:

```
   |   -- Key Exchange --    |
   |                         |
   +------------------------>|  epk_I
   |                         |
```

## Abort / Error Paths

Place abort paths after the main flow, separated by a blank line:

```
   |   [on auth failure]     |
   |  abort(AUTH_FAILED)     |
   |<- - - - - - - - - - - - +
```

## Width and Labels

- Keep lines under ~60 characters wide
- If a label is too long, abbreviate it (e.g. `Enc(k,id||σ)`) and add a
  legend below the diagram explaining the abbreviations

## Inline Output Format

```
Protocol: <Name>
Output:   <filename>

<Participant1>            <Participant2>
   |                         |
   ...

## Protocol Summary

- **Parties:** ...
- **Round complexity:** ...
- **Key primitives:** ...
- **Authentication:** ...
- **Forward secrecy:** ...
- **Notable:** none
```
