# Deviations and clarifications

Changes to, or implementation choices within, `PREREGISTRATION.md` after it was committed. Each entry records the date, what was decided, why, and whether any variant results had been seen.

## 2026-11-05: Event population fixed from the unfiltered analysis (clarification)

- Pre-registration text: events with an incomplete path are excluded, and counts are reported for every variant.
- Clarification: membership of the isolated, overlapping, and incomplete groups is determined once, from variant 1 (unfiltered, 15-minute bins), and held fixed for every variant.
- Reason: the YAMNet filter and 5-minute bins can remove whole bins, which would drop events from the path-completeness rule for reasons unrelated to the research question.
- Per-variant usable events, recorders, and clips are still reported.
- Variant results seen when written: none (only the reference estimate, reproduced in Week 1).

## 2026-11-05: Definition of the detection exclusion tail (clarification)

- Pre-registration text: clips with `Human Activity != "no"`, together with clips recorded during the following five minutes.
- Clarification: a clip is excluded if it is YAMNet-positive, or if its timestamp is within 300 seconds after a YAMNet-positive clip from the same recorder.
- The rule is applied to every clip in the dataset (events, baseline, and placebo candidates alike).
- Variant results seen when written: none.

## 2026-11-05: Two exploratory analyses added after variant results were seen

- What: (1) a complete-window analysis, using only events whose pre and post windows have a usable baseline in every bin; (2) a raw pre/post contrast with no baseline adjustment (the design document's comparison of mean activity with the preceding 60 minutes), using all observed bins.
- Why: a coverage diagnostic showed that for Audio_Moth_5 and Audio_Moth_6, post-onset bins often have no usable baseline, because an event occurs around the same time of day on every recorded day. The baseline-adjusted contrast for those events rests on 0 to 2 bins.
- Status: post hoc and exploratory. Not part of the decision rules. Reported next to all other results, labeled by the `method` column.
- Caution: the raw contrast is confounded by the normal rise and fall of activity around dawn and dusk, when most events were staged.
- Variant results seen when written: yes, all six primary variants (all non-significant, two-sided p from 0.48 to 0.69). The motivation was data coverage, not the size or direction of any estimate.
