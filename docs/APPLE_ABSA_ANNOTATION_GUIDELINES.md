# Apple Review ABSA Annotation Guidelines

## Review status

Framework identifier `apple-absa-guidelines/v1` is frozen after the focused
framework review. Its paired schema is `apple-absa-annotation/v1`.
Future changes to label meanings or validation rules require a new version
and an explicit migration decision. Inspect the exact stored title and
body of the frozen review/version. Hide star ratings and previous usefulness
labels. Preserve the original text and preparation language status.

## Taxonomy

Each aspect has a target domain and a free-text target description.
Domains are `app`, `learning`, `product`, `marketplace`,
`transport`, `transaction` and `unclear`.
The table defines the aspect identifiers used by the
[annotation schema](APPLE_ABSA_ANNOTATION_SCHEMA.md).

| Identifier | Definition and inclusion | Boundary and exclusion | Synthetic example |
| --- | --- | --- | --- |
| functionality | Available or missing capabilities, integrations and workflows | Ease belongs to usability; malfunction to reliability | "Please add shared tags." |
| usability | Navigation, layout, interaction effort and accessibility | Response delay belongs to performance | "The buttons are easy to find." |
| reliability | Crashes, failed operations, incorrect state, compatibility failures | Slow but functioning behavior belongs to performance | "The saved list disappears." |
| performance | Latency, loading and responsiveness of software | Delivery or driver delays belong to fulfillment | "Typing takes several seconds." |
| pricing | Prices, subscriptions, fees and perceived monetary value | Refund execution belongs to fulfillment; contact handling to support | "The monthly plan costs too much." |
| customer_support | Assistance, responsiveness and problem resolution | Driver or seller conduct outside support belongs to personnel_service | "Support answered promptly." |
| quality | Learning material, learning effectiveness, product quality or authenticity | Software operation belongs to functionality or reliability | "The exercises explain fractions clearly." |
| fulfillment | Delivery, booking execution, availability, cancellations, payment and refund execution | Interface steps belong to usability; perceived price to pricing | "Half the parcel was missing." |
| personnel_service | Driver or seller conduct, professionalism, communication and service environment | Support contacts belong to customer_support | "The driver was polite." |
| privacy | Collection, exposure, retention or control of personal data | Dislike of a feature without a data concern stays functionality | "My search history cannot be erased." |
| other | A clearly described aspect outside the defined set | Record a specific target and reason; generic praise stays unassigned | "This service harms local communities." |
| unclear | An identifiable target whose aspect category cannot be resolved | Missing context for any stable target uses a review-level status | "The reward allocation feels unfair." |

Use the narrowest justified aspect. Preserve uncertainty about cause.
For example, a delivery failure does not establish a software defect.
Where two dimensions are independently evaluated, create separate entries.
Avoid duplicating the same complaint under several near-synonymous labels.
Record disputed boundaries for adjudication before expanding the taxonomy.

### Boundary examples

All examples are synthetic. Interpret each sentence using its stated target.

| Text | Aspect | Domain | Sentiment | Decision |
| --- | --- | --- | --- | --- |
| "The exercises explain concepts poorly." | quality | learning | negative | Evaluates teaching material |
| "The app lacks practice exercises." | functionality | app | negative | Identifies a missing capability |
| "The refund has not arrived." | fulfillment | transaction | negative | Evaluates execution of a refund |
| "Support ignored my refund question." | customer_support | transaction | negative | Evaluates response to a support contact |
| "The driver was courteous." | personnel_service | transport | positive | Evaluates routine service conduct |
| "The support agent was courteous." | customer_support | transport | positive | Evaluates conduct during assistance |

A seller discussing an ordinary purchase belongs to personnel_service.
The same seller handling a complaint belongs to customer_support.
When a review independently evaluates the missing refund and unanswered
support contacts, retain both aspects with their own evidence.

## Sentiment

| Label | Rule |
| --- | --- |
| positive | An explicit favorable evaluation or beneficial outcome for the target |
| negative | An explicit unfavorable evaluation or adverse outcome |
| neutral | A factual mention or request with no evaluative direction |
| mixed | Both positive and negative evaluations of the same aspect and target |
| unclear | Evidence identifies a target but leaves polarity unresolved |

"Please add a calendar" may be neutral. "The missing calendar makes planning
impossible" supports negative functionality. A request alone does not prove
dissatisfaction. Sarcasm requires enough textual context; otherwise use unclear.
Do not use rating, presumed developer intent or world knowledge as evidence.

One review may contain several aspect entries. Group repeated mentions of
the same aspect and target, retaining all necessary evidence spans.
"The interface is clear but the subscription is expensive" produces two
entries with different sentiments. For genuinely mixed polarity, include
both positive and negative spans. Distinct experiences can stay separate
using different target descriptions.

For the synthetic text "The interface is clear, but the plan is costly.",
record usability positive and pricing negative as separate entries.
For "Support solved my first issue but ignored my second.", one
customer_support entry can be mixed when its target is the same support
service across both contacts. Retain both evidence spans. If the text
evaluates distinct support providers, keep their targets separate.

## Review-level handling

| Status | Rule |
| --- | --- |
| annotated | At least one supported aspect entry |
| no_identifiable_aspect | Generic evaluation or text with no assessable aspect |
| ambiguous | Incompatible readings prevent a reliable review-level decision |
| insufficient_context | References lack the context needed to identify a target |
| language_out_of_scope | The review cannot be annotated within the approved language scope |

Uncompleted records use a separate `workflow_status=pending` with
`annotation_status=null`. Completed records use `workflow_status=complete`.
For a completed zero-aspect record, give a nonempty `no_aspect_reason`.
For annotated records this field is null. Shortness alone never excludes a
review. Third-party product and service experiences remain in scope using
their target domains. Multiple unrelated experiences require independent
targets. Retain out-of-scope and uncompleted records in the sample.

"The driver was courteous." is short and supports a specific aspect and
positive sentiment. "Great!" has no identifiable aspect. Length supplies
neither decision on its own.

Review-level `ambiguous` and `insufficient_context` describe a review
that cannot support an aspect entry. Aspect identifier `unclear` means
the target is identifiable but its category is unresolved. Sentiment
`unclear` means the target is identifiable but polarity is unresolved.
Those aspect-level cases use review status `annotated` when the evidence
supports an entry. Keep the three decisions separate.

## Human language verification

English-first remains the proposed initial scope. The exploratory
77 English / 2 Russian / 1 Spanish counts are model-assisted observations
awaiting human verification. Preserve inherited `language_status=unknown`.

Before completing any annotation, a competent human must read the original
title and body and verify language. Only human-confirmed English reviews
enter the initial formal ABSA annotation. Record the confirmed language in
`language` with a BCP 47 tag and the actual reviewer and completion time.

Use `language_out_of_scope` only after human verification establishes a
non-English language outside the assigned reviewer's competence. Keep its
aspect array empty and explain the scope and competence restriction.
A reviewer competent in that language retains the record pending an
explicit multilingual-scope decision. Mixed-language or unidentified text
also remains pending with null final language and annotation status.
Record language questions in private review notes keyed to the sample row.
The schema's pending record remains empty of final labels. Preserve all
eighty rows throughout this process.

## Evidence

Locate spans in the original stored `title` or `body`, using zero-based
Unicode code point offsets and an exclusive end. Each span stores its field,
start, end and exact text. Use the original text without NFC, trimming or
newline conversion. Normalized analysis-text offsets cannot be substituted.
Include negation, qualifications and enough target context. Discontinuous
evidence uses several spans; overlapping spans across different aspects are
allowed when each is justified.

Validate `original[field][start:end] == text`. Offsets refer to the exact
frozen version, including emoji and combining characters. JavaScript tools
must convert UTF-16 offsets to Unicode code points.

## Procedure and quality control

1. Assign a real human reviewer identity and verify language competence.
   Record actual completion time in UTC. Keep pending identity and time null.
2. Re-read the twenty initial records with the frozen v1 boundaries and
   verify language. Record boundary questions for adjudication. Codex
   exploration remains a separate research aid.
3. Use the frozen v1 rules to annotate the remaining sixty, then revisit
   the first twenty with those same rules. If review requires a semantic
   rule change, resolve versioning before continuing.
4. Validate parent dataset, sample, source, review and version references,
   required fields, taxonomy enums, status consistency and exact evidence.
5. Check every mixed entry for both polarity directions and every zero-aspect
   record for a reason. Review requests, generic opinions and service targets.
6. If a second reviewer participates, annotate a declared overlapping subset
   independently before adjudication. Report sample size and disagreements
   separately for aspect identification and polarity. With one reviewer,
   report single-reviewer limitations and omit agreement claims.

Freeze guideline and schema versions before training/evaluation splitting.
Group splits by stable source review identity across versions and avoid
learning from an evaluation set used to revise the taxonomy.
