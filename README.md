# E-commerce Conversion Diagnostics — Google Analytics 4 & BigQuery

An import-ready ecommerce analysis tool for marketing and product teams. It identifies where an ordered session funnel loses participants, compares device and first-user acquisition segments, and produces a diagnostic report. It does not claim causal lift, optimal budgets, recovered revenue, or current Google Merchandise Store performance.

## Included version

This repository contains the original source archive supplied for upload. The subsequently reported BigQuery results, snapshot, report, and code fixes were not present in that archive and are not included here. The included suite passes 10 Python tests and 11 frontend assertions.

## Implementation status

- Implemented: parameterized extraction SQL, Python BigQuery runner with dry-run and billing caps, aggregate validation, descriptive Wilson intervals, atomic per-file outputs, HTML reporting, local Streamlit app, browser-local import/filter/report tool, regression tests.
- Not executed here: BigQuery queries, real-data analysis, Streamlit runtime with dependencies, sustained cloud execution, scheduled refresh, alert delivery.
- Reason: BigQuery connector disabled by workspace administrator; no configured local Google Cloud credentials.
- The hosted site starts empty. Test fixtures are confined to tests and are never presented as business observations.

## Source

`bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`

Google documentation: https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset
Schema: https://support.google.com/analytics/answer/7029846
Coverage: November 1, 2020–January 31, 2021. This is an obfuscated historical sample with limited internal consistency and placeholder values; it differs from the GA demo account. Source SQL uses fields documented for this historical export, avoiding newer session-attribution fields. SQL is authored, not warehouse-validated yet.

## Run

Requires Python 3.10+, a Google Cloud project with BigQuery API enabled, permission to create query jobs, and access to the public sample. The project can be a BigQuery sandbox project. Review your query estimate and account limits before execution.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gcloud auth application-default login
python pipeline.py --project YOUR_PROJECT --dry-run
python pipeline.py --project YOUR_PROJECT
streamlit run streamlit_app.py
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1`.
The default window is 2020-11-01 through 2020-11-07. Both queries independently enforce a 2,000,000,000-byte billing cap. Adjust `--max-bytes` deliberately, after a dry-run. One funnel and one quality query are executed in US; job IDs, processed bytes, and SQL hashes are recorded in the snapshot. Authentication uses standard Google Application Default Credentials; no credential is written into this project.

Outputs: `output/snapshot.json` and `output/report.html`. Import the snapshot into the hosted tool or local Streamlit app. Reprocess an existing snapshot without cloud credentials:

```bash
python pipeline.py --input output/snapshot.json --output reviewed
```

To expand the extraction window, supply `--start YYYY-MM-DD --end YYYY-MM-DD` within sample coverage. Each run replaces its entire aggregate snapshot; it does not append duplicate daily aggregates. All validation and report generation complete before output replacement. Each individual output replacement is atomic. A filesystem failure between the two replacements can leave different versions: compare the generated timestamp, rerun, and do not publish mismatched outputs.

## Measurement contract

- Unit: `(user_pseudo_id, ga_session_id)` across the selected extraction window. No identity fields leave BigQuery. Null/empty user IDs or missing session IDs are excluded and reported at event grain.
- Session date/device/source: first observed event within that window. Sessions crossing extraction boundaries can be truncated; use the same boundaries for comparisons and disclose this limitation.
- Ordered funnel: first view_item, earliest add_to_cart strictly after it, earliest begin_checkout strictly after that, earliest purchase strictly after checkout. Sessions, not event counts. A repeated purchase cannot multiply a session's completion count.
- Timestamps tied at microsecond resolution do not establish sequence; they do not advance the ordered funnel. This conservatism may undercount true progress.
- `purchasing_sessions` counts valid-identity sessions with any purchase event, regardless of funnel completeness. `purchases` counts ordered funnel-completing sessions. These are not transactions or units sold.
- Completion: ordered purchasing sessions / product-view sessions. Stage loss: previous ordered stage minus next ordered stage. Loss can reflect missing tracking or alternate paths, not only abandonment.
- Source: `traffic_source.source` is first-user acquisition source, not current session source or campaign attribution. Unknown and obfuscated source values are retained.
- Intervals: 95% Wilson binomial intervals. Independence is a simplifying assumption because visitors can contribute multiple sessions. These are descriptive uncertainty indicators, not hypothesis tests or causal estimates. No multiple-comparison significance claims.
- Daily/device/source rates are recomputed from their summed numerators and denominators; subgroup rates are not averaged.
- Quality: all checks cover the whole extraction. Duplicate transaction events = excess purchase events for non-placeholder transaction IDs across the window. Missing transaction IDs, negative or missing USD purchase revenue, excluded identities, and missing observed dates are surfaced. Counts can overlap. Obfuscation can cause these flags; they are not automatically instrumentation defects.
- Revenue and ROAS are omitted deliberately. Negative/missing revenue is a quality diagnostic only. No spend or margin data exists in the tool.

## Architecture and operating notes

BigQuery event export → aggregate SQL → Python validation → snapshot + HTML brief → browser or Streamlit.
The browser performs no network upload of imports and stores no imported snapshot across reloads. Filters affect the funnel, comparison tables, and downloaded brief. Quality remains explicitly source-wide. Imports over 20 MB are rejected. Invalid imports preserve a previously valid view. Export HTML escapes imported dimension text.

The hosted browser app is a static import interface; it is not a hosted Python service. The Streamlit app is included for local use. Source is maintained in the Site's git repository. Downloadable `source.zip` omits hosting identity, credentials, generated results, and test caches.

For a future scheduled job, run the CLI under a service identity with scoped BigQuery job permissions and write artifacts to durable storage; configure monitoring and alert delivery in that hosting target. No schedule, email, cloud job, or alert subscriber is currently configured. Historical replay must be labeled as replay. Do not describe this build as sustained production monitoring.

## Troubleshooting

- Authentication error: configure Application Default Credentials in your own environment. Do not paste keys into chat or commit them.
- Query permission error: check project BigQuery job permissions and public dataset access.
- Billing-cap error: inspect a dry-run; shorten the window before considering a larger cap.
- Invalid counts: inspect source query and snapshot grain; do not relax validators to force publication.
- Missing stages: confirm tracking and strict ordering before attributing the gap to customer behavior.
- Empty result: verify the historical date window and source availability.

## Verification

```bash
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
node --check dist/app.js
```

Tests use hand-constructed fixtures for invalid inputs and known confidence-interval values. BigQuery execution is an outstanding integration check; local tests cannot establish warehouse SQL correctness or source findings.
