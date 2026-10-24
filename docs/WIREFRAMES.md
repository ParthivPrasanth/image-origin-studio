# Screen plan

These wireframes began before the first interface implementation. The local app keeps one page for one image or a small batch. The dual-model update adds a choice of V3 E2, Community Forensics, or both before analysis.

## Upload and empty result

```text
Header: Image Origin Studio                         Research model demo

Explore what the model sees.
Plain-language limitation statement

01 Choose images                  02 Review results
┌─────────────────────┐           ┌──────────────────────────────┐
│ Drop or choose files│           │ Empty-state explanation      │
│ File types and limit│           │                              │
└─────────────────────┘           └──────────────────────────────┘
Choose models: [V3 E2] [Community Forensics] (both selected by default)
Local privacy note

How to read a result / credited model
```

## Processing and result

```text
Choose images                    Review results
                                [Analyze images] [Export CSV]
                                [thumbnail] name   Processing…
                                [thumbnail] name   V3 E2 suggestion and score
                                                   Community Forensics suggestion and score
                                                   Disagreement note if labels differ
                                                   Each model's cutoff, version, and time
```

## Batch and future history

The batch view is the same result list, capped at eight files for the local demonstration. Each row has its own result, error, and retry. Account history is intentionally absent until authentication, ownership checks, retention, and deletion are designed and tested. The UI must never imply that guest results persist after the browser session.

## Visual review checklist

- Phone, tablet, and desktop widths
- Keyboard access to file selection, analyze, retry, remove, and CSV export
- Ready, processing, per-model error, partial success, and result states
- One-model and both-model layouts; changing the selector does not relabel existing results
- Disagreement remains visible; a failed model can be retried without discarding the other result
- Incorrect predictions remain visible as predictions, never rewritten as known origin
