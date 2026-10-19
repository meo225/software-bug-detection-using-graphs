# Task 3.2 flat pilot delivery format

This is a delivery-only contract. It does not change Schema 3.1, frozen V2
extraction, graph representation, original sources, cohort labels or acceptance.
Implementation is authorized; a production export, Git staging/commits and
publication each still require separate approval. No delivery is created by
importing the exporter. Tests use synthetic fixtures only.

## Scope and sources of truth

The original ordered 30-entry `data/sample_manifests/diversevul_graph_sample.csv`
and zero-based dataset indices are mandatory. The terminal accounting is 25
SUCCESS, 3 FAILED, 0 NOT_RUN and 2 UNSUPPORTED. SUCCESS includes accepted
OVERSIZED_GRAPH records; it does not imply semantic completeness.

The exporter reconciles the preserved intermediate 7B.3 ledger with the 7B.8
row-1601 failure and 7B.9 final-two successes. It checks frozen fingerprints,
source SHA256 and exact metadata, final-two checksums and original/staging
identity. Prior accepted mappings come from the ledger. Latest failures are
row-832 (7B), row-6038 (7B.2) and row-1601 (7B.8). Summary attempts, including
row-1601's 7B.3 pre-Joern WinError 5 and retained-CPG repetition receipts, remain
separate references; intermediate NOT_RUN entries are not execution attempts.

Both historical and final reports are protected by their approved checksums.
The known absent 7B.2 final_integrity.json is never recreated. Later checksum
receipts and current replay establish current integrity, not every historical
intermediate state. Absolute receipt mappings currently require the original
repository location; relocation fails closed and needs separate design review.

## Flat JSON variants

For 25 accepted pairs and 3 latest failure pairs, retain **every original graph
field/value** and add exactly two root fields:

* `source_reference`: the validated original manifest string, exactly
  `dataset row sample_id=row-N`. No original filename is available or invented.
* `record_kind`: `extracted_graph` or `failure_record`.

Reject either delivery field already present in an input. Removing both added
fields must reproduce the complete original graph object, including JSON value
types, root-key order and node/edge array order. Original bytes and delivery
bytes have separate checksums. Serialization is UTF-8 without BOM, two-space
indentation, ensure_ascii=False, finite numbers only and one final LF.

Root-level nodes and edges stay arrays. Node fields remain id, node_type,
code_token, line_number, rel_line_number. Edge fields stay src, dst, type.
Relation IDs are 0 AST, 1 CFG, 2 DATA_DEP. Graph A remains AST-only; Graph B
preserves its selected-METHOD shared node domain and matching AST edges.
Oversized graphs retain all nodes/edges and their actual warning status.

Failed records keep their original AST_EXTRACTION_ERROR, error_message,
NOT_COMPUTED, empty arrays and zero counts. Relocated quarantine metrics retain
their original staging paths: the exporter verifies that relocation explicitly,
source bytes, identity, failure metrics and logged parse/selection evidence;
it does not rewrite metrics to force the successful-artifact gate to pass.

For row-8932 and row-16198 only, construct a flat delivery-only record containing:

* Original sample_id and cwe, graph_type graph_a/graph_b, both split fields null.
* status UNSUPPORTED_SOURCE_REPRESENTATION; record_kind unsupported_source_record.
* ddg_status NOT_COMPUTED; nodes/edges []; num_nodes/num_edges 0.
* Original validated source_reference and this exact error_message:

  `Original source is a switch fragment without a unique explicit function definition; extraction was not attempted under the exact-function contract.`

No graph wrapper, synthetic functions, parser outcomes, dummy nodes, new
dependencies or frozen status enums are introduced. Failure/unsupported zero
counts describe non-graph payloads, never successfully extracted empty graphs.

## CSV manifests

Each graph directory contains exactly 30 row-N.json files and manifest.csv;
the package contains exactly these two directories and 62 files in total.
CSV is UTF-8 without BOM, comma-delimited with standard quoting and LF records.
Rows preserve original order, independent of filesystem enumeration.

The exact column order is:

```text
manifest_order,sample_id,dataset_index,cwe,source_reference,source_sha256,project_wise_split,seen_project_split,record_kind,cohort_status,status,graph_type,num_nodes,num_edges,ddg_status,error_message,json_file,json_sha256,json_bytes,original_artifact_reference,original_artifact_sha256,attempt_references
```

manifest_order is 1-based display order; dataset_index is canonical 0-based.
Blank CWE is the original empty string, never missing/filled metadata. Multi-CWE
strings retain exact order/separators. Both pilot splits are null in JSON and
blank in CSV, not experimental split assignments. Unsupported original-artifact
fields are blank; no runtime artifact exists. Accepted error_message is blank
when absent. json_file is a basename. Checksums are lowercase SHA256 of file
bytes; json_bytes is the actual serialized file size. Provenance paths are
repository-relative; attempt_references is a compact JSON-array CSV string.

## Validation, staging and publication (V1-V8)

1. V1: require absent destination, permitted existing parents, frozen input and
   report fingerprints; take a protected project-file baseline. Git/venv
   internals are excluded; project files, datasets and ignored evidence are not.
   A missing inventory root, os.walk enumeration error, inaccessible subtree,
   missing protected file or checksum read failure aborts the check. Enumeration
   errors are explicitly raised through onerror; a partial scan is never PASS.
2. V2: require exactly the original ordered IDs, 25/3/0/2, source hashes,
   project/commit/label/CWE metadata, canonical references and null pilot splits.
3. V3: replay the unchanged accepted-artifact gate and verify publication versus
   staging and receipt hashes; independently verify preserved failure evidence.
4. V4: build flat records with exactly the approved additions and typed original
   projection equality; separately construct the two approved unsupported IDs.
5. V5: preserve counts, relation types, shared nodes/AST and warning semantics.
6. V6: verify 60 JSONs/two manifests, original order, every metadata field,
   manifest checksum/byte count, original checksum and provenance reference.
7. V7: retain UUID evidence outside the package and stage a complete package on
   the destination filesystem; atomically rename with **no replacement**.
8. V8: replay package/checksum checks, rehash protected files and run the fixed
   read-only git diff --check command. Only then finalize completion evidence as
   described below. No further mandatory package/Git checks follow finalization.

Windows os.rename refuses existing targets. Linux uses renameat2 with
RENAME_NOREPLACE; other platforms fail closed. Atomic namespace publication is
not a guarantee of power-loss durability. Concurrent changes abort verification;
run in a quiescent checkout. Failure handling never deletes existing evidence,
staging or the published directory. No retries or overwrite/cleanup are automatic.

### Completion and failure evidence

Completion is first written to a unique `.final_integrity-<UUID>.pending` file.
The complete bytes must be flushed and fsynced successfully, then read back and
compared before an atomic no-replace rename to `final_integrity.json`. A partial,
unsynchronized or merely pending file is never completion evidence. A receipt
collision aborts without replacing the existing file. Pending files remain for
diagnosis on failure; they are not automatically removed or retried.

Accept an export only when **all** these conditions hold:

* The invocation completed successfully (exit 0), not interrupted or unknown.
* A valid finalized final_integrity.json matches the verified package hashes,
  protected-file checks and configuration/validation receipts.
* No failure.json exists: **failure receipt presence overrides a finalized PASS**.
* Independent package/count/checksum verification passes. check_completion()
  checks receipt state; it cannot prove process exit status or current file bytes.

Any exception after directory publication propagates as a failed/incomplete run;
the package remains in place and must not be accepted merely because it exists.
The exception handler attempts to persist failure.json, preserving the original
exception. An error immediately after receipt rename can leave both receipts;
failure takes precedence and no automatic rollback occurs.
Failure receipts are written only inside an evidence directory successfully
created by this invocation. A UUID collision never appends a failure to a prior
run's evidence directory.

Preflight can fail before any staging/evidence exists. Evidence-directory setup
is inside the failure handler, but setup/storage failures may make even a failure
receipt impossible to write. This limitation and the original error are reported
to stderr when possible; neither a receipt nor its timestamp is fabricated.
If both storage and stderr fail, only the propagated original error/unsuccessful
invocation may be available. Unknown exit status is not acceptance. A complete
receipt alone cannot certify that the process returned successfully.

The pending file is fsynced before rename. This protocol does not claim durable
directory entries after power loss, survival of filesystem/controller failures,
or protection from a concurrent external writer after the checks. No directory
fsync portability guarantee is made. Missing/conflicting receipts or an
interrupted invocation require a separate read-only audit, never an automatic
rerun, deletion or repair of the existing package.

The destination is reports/graph/3_2_pilot. UUID evidence is local-only under
data/graphs/pilot_delivery_export_evidence/. The CLI has --check-only (no writes)
and --export (requires separate approval), plus --root for the repository root.
Use Windows Python with bytecode writing disabled (`python -B`). No Joern, WSL,
source parser subprocess or full-extraction entry point is called. The existing
static textual function resolver and read-only gate are used. The only external
command is fixed git diff --check; the exporter never stages or commits.

## Publication and remaining limits

Implementation does not authorize a production export or public distribution.
Dataset-derived tokens, third-party redistribution/attribution and original
failure messages containing local paths require review. Never silently redact
original failure information. The current three latest failure messages contain
original machine-specific staging paths;
the manifests preserve those messages too. Earlier WinError evidence may contain
Windows usernames/home-directory paths and remains separately referenced local
history. A local export is not GitHub privacy or licensing clearance. Raw sources,
runtime installations, CPGs, full
logs/quarantines and bulk data/graphs are not GitHub deliverables.

The official historical report remains unchanged. An index to the authoritative
final V2 report still needs deliverable-owner acceptance. Publication paths are
delivery exceptions, not replacements for operational graph paths in configs.
Single-METHOD projection, omitted nested lexical/lambda structure, DDG semantic
uncertainty and unmeasured peak RAM remain. Structural acceptance authorizes no
training, evaluation, source repair, retry or 9,077-record scaling.
