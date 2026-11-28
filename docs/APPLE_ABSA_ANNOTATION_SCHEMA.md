# Apple Review ABSA Annotation Schema

## Representation

Frozen identifier `apple-absa-annotation/v1` pairs with
`apple-absa-guidelines/v1`. It describes one private annotation record per sampled
review/version. The frozen sample holds the original fields. Annotation
records reference that sample and preserve zero or more aspect entries.
All identifiers below are new annotation-contract fields except the
inherited source, review, version and preparation language fields.

The JSON Schema uses Draft 2020-12. Configure format validation for
`date-time` explicitly. Semantic checks following the schema are mandatory.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "guideline_version", "dataset_id", "sample_id",
    "source", "source_application_id", "source_review_id", "review_id",
    "version_id", "version_number", "language_status", "language",
    "workflow_status", "annotation_status", "no_aspect_reason", "aspects",
    "reviewer_id", "annotated_at"],
  "properties": {
    "schema_version": {"const": "apple-absa-annotation/v1"},
    "guideline_version": {"const": "apple-absa-guidelines/v1"},
    "dataset_id": {"type": "string", "minLength": 1},
    "sample_id": {"type": "string", "minLength": 1},
    "source": {"const": "apple_app_store"},
    "source_application_id": {"type": "string", "minLength": 1},
    "source_review_id": {"type": "string", "minLength": 1},
    "review_id": {"type": "string", "pattern": "^[1-9][0-9]*$"},
    "version_id": {"type": "string", "pattern": "^[1-9][0-9]*$"},
    "version_number": {"type": "string", "pattern": "^[1-9][0-9]*$"},
    "language_status": {"const": "unknown"},
    "language": {"type": ["string", "null"], "minLength": 1},
    "workflow_status": {"enum": ["pending", "complete"]},
    "annotation_status": {"enum": [null, "annotated", "no_identifiable_aspect",
      "ambiguous", "insufficient_context", "language_out_of_scope"]},
    "no_aspect_reason": {"type": ["string", "null"], "minLength": 1},
    "aspects": {"type": "array", "items": {"$ref": "#/$defs/aspect"}},
    "reviewer_id": {"type": ["string", "null"], "minLength": 1},
    "annotated_at": {"type": ["string", "null"], "format": "date-time"}
  },
  "$defs": {
    "aspect": {
      "type": "object", "additionalProperties": false,
      "required": ["aspect", "target_domain", "target", "sentiment", "evidence", "reason"],
      "properties": {
        "aspect": {"enum": ["functionality", "usability", "reliability",
          "performance", "pricing", "customer_support", "quality", "fulfillment",
          "personnel_service", "privacy", "other", "unclear"]},
        "target_domain": {"enum": ["app", "learning", "product", "marketplace",
          "transport", "transaction", "unclear"]},
        "target": {"type": "string", "minLength": 1},
        "sentiment": {"enum": ["positive", "negative", "neutral", "mixed", "unclear"]},
        "evidence": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/span"}},
        "reason": {"type": "string", "minLength": 1}
      }
    },
    "span": {
      "type": "object", "additionalProperties": false,
      "required": ["field", "start", "end", "text"],
      "properties": {
        "field": {"enum": ["title", "body"]},
        "start": {"type": "integer", "minimum": 0},
        "end": {"type": "integer", "minimum": 1},
        "text": {"type": "string", "minLength": 1}
      }
    }
  }
}
```

## Required semantic validation

- Resolve dataset and sample identifiers to the private manifest and check
  every source/review/version field against that exact sample row.
- Preserve numeric-looking IDs as strings. The database context scopes
  internal IDs. Keep original collection provenance in the frozen sample.
- A pending record has null annotation status, language, reviewer and time,
  null reason and an empty aspect array. Pending is a workflow state.
- A complete record has a nonnull status, human-verified language, actual
  reviewer identity and actual UTC completion time. Language uses a
  documented BCP 47 tag. Mixed or unresolved language remains pending with
  null final language and status. Model-assisted language observations
  cannot complete this check.
- Initial formal aspect annotation requires human-confirmed English.
  A complete `language_out_of_scope` record requires a human-confirmed
  non-English language outside the assigned reviewer's competence and a
  reason stating that restriction. Other non-English records remain pending
  until multilingual scope is decided.
- Complete annotated records contain at least one aspect and a null
  no-aspect reason. Every other complete status has zero aspects and a
  nonempty reason.
- Check `0 <= start < end <= len(original_field)` in Unicode code points,
  and exact slice equality for every evidence span. A null title cannot
  supply evidence. Ensure rationales and mixed polarity have textual support.
- Reject duplicate parent records within one reviewer/guideline output.
  Within a review, merge repeated aspect-and-target entries or document
  distinct experiences. Preserve independent reviewers in separate outputs.
- Review-level unresolved statuses contain zero aspects. Aspect category
  `unclear` and sentiment `unclear` can occur in an annotated record
  when an identifiable target and supporting evidence are present.

These checks require the frozen sample and semantic review. JSON Schema
alone cannot establish evidence truth, language accuracy or annotator identity.
Actual sample annotation remains pending. The synthetic fixture below
exercises the representation and carries invented identity and time fields.

## Synthetic example

Synthetic original body is `Easy menus, costly plan.`; title is null.
Example identities, reviewer and time below are invented fixtures.

```json
{
  "schema_version": "apple-absa-annotation/v1",
  "guideline_version": "apple-absa-guidelines/v1",
  "dataset_id": "synthetic",
  "sample_id": "synthetic-01",
  "source": "apple_app_store",
  "source_application_id": "0001",
  "source_review_id": "0002",
  "review_id": "1",
  "version_id": "2",
  "version_number": "1",
  "language_status": "unknown",
  "language": "en",
  "workflow_status": "complete",
  "annotation_status": "annotated",
  "no_aspect_reason": null,
  "aspects": [
    {"aspect": "usability", "target_domain": "app", "target": "menus",
     "sentiment": "positive",
     "evidence": [{"field": "body", "start": 0, "end": 10, "text": "Easy menus"}],
     "reason": "The interface is explicitly easy."},
    {"aspect": "pricing", "target_domain": "transaction", "target": "plan price",
     "sentiment": "negative",
     "evidence": [{"field": "body", "start": 12, "end": 23, "text": "costly plan"}],
     "reason": "The plan price receives an unfavorable evaluation."}
  ],
  "reviewer_id": "synthetic-reviewer",
  "annotated_at": "2000-01-01T00:00:00Z"
}
```
