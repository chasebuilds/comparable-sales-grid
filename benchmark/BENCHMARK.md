# Benchmark

200 synthetic subjects scored against the known true value, market of 3000 synthetic sales. Subjects are not in the sales file.

| Method | Median abs % error | Mean abs % error | Within 5% | Within 10% | Bias | Truth inside range |
|---|---|---|---|---|---|---|
| regression | 2.05% | 2.26% | 93.0% | 100.0% | -0.49% | 91.0% |
| paired | 2.54% | 2.90% | 83.0% | 99.5% | -0.73% | 77.5% |
| blend | 2.09% | 2.43% | 90.5% | 100.0% | -0.60% | 82.5% |

Context rows (same subjects):

| Estimate | Median abs % error | Within 5% | Within 10% |
|---|---|---|---|
| Median of chosen comps, time-adjusted only (no line adjustments) | 4.76% | 50.5% | 80.0% |
| Direct regression prediction (no comps) | 1.48% | 98.0% | 100.0% |

Truth is the noise-free synthetic value at the valuation date. Real sales carry noise and unobserved features the generator does not have, so real-world errors will be larger.
