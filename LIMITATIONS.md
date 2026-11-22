# Limitations

- **Not an appraisal.** A USPAP-compliant appraisal requires a licensed or certified appraiser who inspects the property, defines the market area, and signs the report. This tool does none of that.
- **Synthetic data.** The benchmark market is generated from a log-linear price model plus noise (4.5% per sale) and one hidden smooth location effect. The regression is close to the true form, so errors are lower than real data would give. Real sales carry unobserved features (view, layout, finish, seller motivation) and bad records.
- **Few paired sales.** Strict matching leaves 23 to 70 pairs per feature in a 3,000-sale market. Paired rates for bedrooms and condition are noisy. Location adjustments use the regression only.
- **Extrapolated index.** The valuation month has no sales, so its index value is a linear extension of the last 6 months. A turning market will be missed.
- **Linear features.** Age, bedrooms, condition and quality are linear in ln(price). Real markets can bend. The generator bends age slightly past 30 years, and the tool does not model it.
- **Distance is straight-line** on an x/y kilometer grid. No school districts, flood zones, roads or zoning.
- **Condition and quality are 1 to 5 scores** supplied with the data. In practice those are appraiser judgments.
- **Weights and flags are conventions**, not rules: the 15% net and 25% gross flags are common guidelines, and inverse-gross weighting is one simple choice.
- **Not for lending, tax or legal use.**
