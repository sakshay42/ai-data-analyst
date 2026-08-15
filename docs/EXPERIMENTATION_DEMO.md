# Experimentation Demo

This demo simulates a two-arm pricing/offer experiment with known treatment effects,
then estimates uncertainty, power, and interpretation risks.

## Design

- Control users: 2,500
- Treatment users: 2,500
- Metrics: conversion rate and revenue per user
- Methods: two-proportion z-test, Welch t-test, bootstrap CI, effect sizes, power/MDE diagnostics, Benjamini-Hochberg correction

## Results

### Conversion rate

| Quantity | Value |
|---|---:|
| Control estimate | 10.68% |
| Treatment estimate | 13.04% |
| Absolute effect | 2.36% |
| Relative effect | 22.10% |
| 95% CI | [0.57%, 4.15%] |
| p-value | 0.00986 |
| Effect size | 0.0731 |
| Approx. power | 76.08% |
| 80% power MDE | 2.48% |

Audit findings:

- WARNING: Estimated power is 76.1%, below the 80% target.


### Revenue per user

| Quantity | Value |
|---|---:|
| Control estimate | 3.266 |
| Treatment estimate | 4.488 |
| Absolute effect | 1.223 |
| Relative effect | 37.43% |
| 95% CI | [0.542, 1.903] |
| p-value | 0.000431 |
| Effect size | 0.0996 |
| Approx. power | 94.10% |
| 80% power MDE | 0.972 |

Audit findings:

- No audit warnings.


## Multiple Testing

| Metric | raw p-value | BH adjusted p-value | reject at 5% FDR |
|---|---:|---:|---:|
| Conversion rate | 0.00986 | 0.00986 | True |
| Revenue per user | 0.000431 | 0.000862 | True |

## Artifacts

- Simulated data: `output/experimentation_demo/simulated_experiment.csv`
- Effect chart: `output/experimentation_demo/experiment_effects.png`
