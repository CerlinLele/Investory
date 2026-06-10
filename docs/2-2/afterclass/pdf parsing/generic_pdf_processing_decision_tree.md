# Generic PDF Processing Decision Tree

## Goal

This note describes how I would handle a PDF in Codex when there is no project-specific `.venv` requirement and no preselected PDF toolchain.

The aim is not to force one stack everywhere. The aim is to choose the smallest workable path based on:

- what kind of PDF it is
- what tools already exist in the environment
- what the user actually needs from the PDF

## First Questions

Before touching dependencies, I would answer these four questions:

1. Is the PDF text-based, scanned, or mixed?
2. Do we need plain text, page metadata, tables, layout, or OCR?
3. Does the current repo already have Python, Node, Docker, or system PDF tools?
4. Is this a one-off extraction, a repeatable workflow, or part of product code?

These answers drive the tool choice much more than personal preference.

## High-Level Decision Tree

```text
Start
  -> Confirm file exists, file size, and page count
  -> Try lightweight text extraction
       -> Good text quality?
            -> Yes: continue with extracted text
            -> No:
                 -> Is the PDF scanned or image-heavy?
                      -> Yes: use OCR path
                      -> No: try a different parser or add cleanup
  -> Validate extraction quality on a few pages
  -> If needed, chunk / index / analyze
  -> Save the process, findings, and caveats
```

## Step 1: Inspect the Environment

I would first inspect what is already available instead of installing immediately.

Typical checks:

- Python available?
- Node available?
- Existing dependency manager already in use?
- System tools such as `pdftotext`, `tesseract`, or `mutool` available?
- Docker already part of the repo workflow?

Preference order:

1. Reuse the repo's existing runtime if one clearly exists.
2. Reuse already-installed PDF libraries if they are sufficient.
3. Create an isolated local environment if new dependencies are needed.
4. Use a container if the environment should stay clean or reproducible.

## Step 2: Classify the PDF

I would loosely classify the PDF into one of three buckets:

### 1. Text PDF

Examples:

- reports
- fact sheets
- whitepapers
- prospectuses

Characteristics:

- selectable text in a PDF viewer
- parsers usually return meaningful text

Preferred path:

- `pdfplumber`
- `pypdf`
- `PyMuPDF`
- `pdftotext`

### 2. Scanned PDF

Examples:

- scanned contracts
- photo-based handouts
- old printed material

Characteristics:

- text selection fails or is sparse
- extracted text is empty or nonsense

Preferred path:

- OCR using `tesseract`
- or OCR-capable pipelines built on rendered page images

### 3. Mixed PDF

Examples:

- text plus embedded scanned pages
- reports with image-based appendices

Preferred path:

- extract native text first
- identify weak pages
- run OCR only on weak pages

This mixed strategy is often the best tradeoff.

## Step 3: Choose the Smallest Useful Tool

I usually pick tools by need:

### When plain text is enough

Use:

- `pypdf` for minimal dependency extraction
- `pdfplumber` for better page-oriented text extraction

Why:

- simple setup
- fast to test
- enough for chunking, RAG, summarization, and review flows

### When layout or tables matter

Use:

- `pdfplumber`
- `PyMuPDF`

Why:

- better page granularity
- easier debugging page by page
- more control around tables and coordinates

### When scanned content is the main problem

Use:

- `tesseract`
- a PDF-to-image step plus OCR

Why:

- text extractors alone will fail
- OCR gives a usable fallback, even if noisier

## Step 4: Validate Early

I never trust the first successful extraction blindly. I validate on a few pages before building anything on top.

What I check:

- page count
- empty pages
- extracted character count per page
- whether headings and paragraphs survive
- whether tables collapse into junk
- whether there is severe word-joining or broken spacing
- whether page headers or footers dominate the text

This early check is usually enough to decide whether the current parser is good enough.

## Step 5: Decide Whether Cleanup Is Needed

If raw extraction is usable but messy, I would usually add lightweight cleanup instead of changing the entire parser.

Common cleanup steps:

- trim leading/trailing whitespace
- collapse excessive blank lines
- remove repeated headers and footers
- normalize broken spacing where safe
- preserve page boundaries in metadata

If the text is fundamentally bad, cleanup is not enough. Then I would switch parser or move to OCR.

## Step 6: Choose the Runtime Strategy

Without a project-specific `.venv`, I would choose one of these runtime strategies.

### Option A: Reuse existing local environment

Use when:

- the repo already has a Python environment
- the needed library is already installed

Best for:

- fast local analysis
- low setup friction

### Option B: Create a temporary virtual environment

Use when:

- Python exists but the repo has no PDF setup
- I want to avoid polluting the global environment

Best for:

- one-off experiments
- local repeatable scripts

### Option C: Use Docker

Use when:

- dependencies are heavier
- OCR or system packages are involved
- reproducibility matters

Best for:

- team workflows
- CI-compatible processing

### Option D: Use system tools directly

Use when:

- tools like `pdftotext` or `tesseract` are already installed
- the task is operational and simple

Best for:

- fast experiments
- shell-oriented pipelines

## Step 7: Match the Extraction to the User Goal

The extraction path should fit the end goal.

### Goal: quick summary

Need:

- plain text
- basic quality check

Usually enough:

- `pypdf` or `pdfplumber`

### Goal: chunking or RAG

Need:

- consistent text
- stable page ordering
- enough cleanup to avoid noisy chunks

Usually enough:

- `pdfplumber`
- page metadata
- deterministic chunking

### Goal: structured review or audit

Need:

- page traceability
- headers, sections, tables if possible
- explicit confidence about extraction limits

Usually better:

- `pdfplumber` or `PyMuPDF`
- possible per-page metadata
- extraction notes saved to Markdown

### Goal: scanned document processing

Need:

- OCR
- often page images
- probably heavier post-cleaning

Usually required:

- OCR workflow, not plain PDF parsing

## Step 8: Save the Process

If the PDF processing matters to the project, I save the process as a Markdown note.

I usually include:

- input file path
- tool used
- why that tool was chosen
- page count
- extracted text size
- quality observations
- chunking implications
- known limitations

This turns a one-off experiment into reusable project knowledge.

## Practical Default Recommendation

If I had no repo constraints and just needed a practical default, I would usually start here:

1. Try `pdfplumber`.
2. Check page count, empty pages, and a few page samples.
3. If text quality is acceptable, continue.
4. If text is empty or obviously image-based, switch to OCR.
5. If layout matters a lot, compare with `PyMuPDF`.

This is a strong default because it balances quality, speed, and debugging ease.

## What I Would Avoid

I would avoid these habits unless there is a clear reason:

- installing random global packages into the user's machine
- assuming every PDF is text-based
- building chunking or RAG on top of unvalidated extraction
- overengineering a full parser pipeline before checking 3 sample pages
- hiding extraction quality problems behind downstream prompts

## A Simple Working Heuristic

If I need a fast decision in Codex, I use this heuristic:

```text
If text extraction works and looks readable on sample pages:
    keep the current parser
Else if the PDF looks scanned:
    use OCR
Else:
    try one better parser, then reassess
```

That rule is simple, but in practice it catches most cases well.

## Bottom Line

Without a project-specific `.venv`, I would still handle PDF work the same way in spirit:

- inspect the environment first
- choose the smallest workable tool
- validate extraction quality early
- adapt to text PDF vs scanned PDF
- document the process when it matters

The exact library can change. The decision pattern usually should not.
