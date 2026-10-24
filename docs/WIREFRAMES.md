# Screen plan

These wireframes were made before the first interface implementation. The current local release uses one page so the same result view works for one image or a small batch.

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
Local privacy note

How to read a result / credited model
```

## Processing and result

```text
Choose images                    Review results
                                [Analyze images] [Export CSV]
                                [thumbnail] name   Processing…
                                [thumbnail] name   Experimental model suggests Real
                                                   AI score, complement, cutoff
                                                   model revision, time
```

## Batch and future history

The batch view is the same result list, capped at eight files for the local demonstration. Each row has its own result, error, and retry. Account history is intentionally absent until authentication, ownership checks, retention, and deletion are designed and tested. The UI must never imply that guest results persist after the browser session.

## Visual review checklist

- Phone, tablet, and desktop widths
- Keyboard access to file selection, analyze, retry, remove, and CSV export
- Ready, processing, error, and result states
- Incorrect predictions remain visible as predictions, never rewritten as known origin
