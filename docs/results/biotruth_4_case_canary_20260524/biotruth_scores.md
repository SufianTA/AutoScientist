# BioTruth Correctness Scores

Mode: `judge`
Packets: `16`
Scored: `16`

## Overall

- Count: `16`
- Mean weighted score: `71.88`
- Median weighted score: `73.0`
- Pass rate: `0.4375`
- Critical failure rate: `0.0`
- Evidence certainty: `{'high': 9, 'low': 4, 'moderate': 3}`

## By Ablation

### full
- Count: `4`
- Mean weighted score: `79.5`
- Median weighted score: `82.0`
- Pass rate: `0.75`
- Critical failure rate: `0.0`
- Evidence certainty: `{'high': 4}`

### no_memory
- Count: `4`
- Mean weighted score: `74.5`
- Median weighted score: `74.5`
- Pass rate: `0.5`
- Critical failure rate: `0.0`
- Evidence certainty: `{'high': 3, 'moderate': 1}`

### no_public_tools
- Count: `4`
- Mean weighted score: `56.75`
- Median weighted score: `58.0`
- Pass rate: `0.0`
- Critical failure rate: `0.0`
- Evidence certainty: `{'low': 4}`

### no_sciflow
- Count: `4`
- Mean weighted score: `76.75`
- Median weighted score: `77.5`
- Pass rate: `0.5`
- Critical failure rate: `0.0`
- Evidence certainty: `{'high': 2, 'moderate': 2}`

## By Domain

### autoimmune_inflammation
- Count: `8`
- Mean weighted score: `69.0`
- Median weighted score: `71.0`
- Pass rate: `0.125`
- Critical failure rate: `0.0`
- Evidence certainty: `{'high': 3, 'low': 2, 'moderate': 3}`

### oncology
- Count: `8`
- Mean weighted score: `74.75`
- Median weighted score: `79.5`
- Pass rate: `0.75`
- Critical failure rate: `0.0`
- Evidence certainty: `{'high': 6, 'low': 2}`

## Limitations

- Heuristic mode is a prefilter and does not establish biological correctness.
- Judge mode depends on the chosen model and should be audited with expert spot checks.
- A credible claim requires full versus ablation comparison on the same BioTruth tasks.