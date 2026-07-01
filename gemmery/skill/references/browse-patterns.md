# Browse patterns (spec §6)

Retrieval is **not** `get_relevant(query) → top_k` injected once. It is a bounded
loop you drive. This is the whole bet: GitOfThoughts held the agent fixed and
found memory inert; an agent that *browses* converts an impossible recall problem
into a tractable recognition problem.

## The loop

```
budget = N model-calls          # a hard ceiling; honesty depends on it
cues = initial_query
while budget and not satisfied:
    queries  = reformulate(cues)       # 2-4 surface forms, not one cosine
    hits     = hybrid_retrieve(queries)# pre-filter columnar, THEN semantic
    partials = read(hits)              # their content becomes the next cues
    cues, satisfied = assess(partials) # recognition: "is the fragment here?"
return recognized_marks
```

## Reformulation — issue several surface forms

Generate both **problem-side** and **solution-side** framings. The method you
want often lives at *low problem-similarity, high solution-similarity* — a
differently-worded problem solved the same way. Examples for one need:

- problem-side: "checkout fails intermittently on payment timeout"
- solution-side: "operator that retries an idempotent op with backoff"
- precondition-side: "precondition: transient error AND idempotent"

## Pre-filter on handles, then read (the hybrid contract)

Never semantic-search the whole store cold. Narrow with columnar handles first:

| you want | filter |
|---|---|
| a specific method | `action_type` |
| same solution shape | `precondition_shape` tokens (`pre_any` / `pre_all`) |
| things that worked | `outcome="ok"` or `min_credit > 0` |
| a domain | `domain` |
| recent only | `since_ts` |

…then run semantic search **over the survivors**. The columnar layer is a
pre-filter, the embeddings are a re-rank.

## Recognition over recall (the load-bearing bet)

You don't need to retrieve the right gem by similarity. You need to *recognize*
it as applicable when you read it across a few queries. If you can't tell a
relevant abandoned fragment from a superficially similar irrelevant one,
browsing won't save you — it will give fixation more surface area. Read the
`reasoning` field; that's where applicability is decided.

## Walk the topology (why git, not a flat vector store)

Mid-loop, you can walk the graph — a flat store can't offer this:

```bash
gemmery browse "<goal>"                  # the loop
gemmery one-shot "<goal>"                # the baseline modality (for contrast)
git -C "$GEMMERY_STORE" log -G 'backoff' # pickaxe across diffs (content/effect)
git -C "$GEMMERY_STORE" tag -l 'ok/*'    # outcome filter
git -C "$GEMMERY_STORE" log main..frontier/<task>/0   # what a branch tried
```

## Membrane permeability (default sealed)

Cross-branch synthesis is powerful but biases exploration: open the membrane and
branches cross-read into one basin and converge early (fixation).

- **Divergent exploration → keep sealed** (`--permeability sealed`, the default):
  retrieval stays within `main` + your own branch.
- **Synthesis → open** (`--permeability open`): pull fragments from abandoned
  sibling frontiers.

Use `open` deliberately, when you *want* to recombine, not by habit.
