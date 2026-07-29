"""Cohort vocabulary, email-domain classification and assignment helpers.

Cohorts are analytical labels only -- they grant no access and carry no billing
meaning. See openspec/changes/user-cohorts/design.md.

Two kinds of classification rule, split by a rule this repository has to honour
because it is **public**: anything here must name no customer.

- Generic rules live in this file: freemail providers, student-subdomain markers,
  TLD suffixes. `.gov.uk -> municipality` identifies nobody.
- Rules that map one organisation's domain to a segment live in the database
  (`DomainSegmentRule`), loaded from a gitignored file. Committed here, they
  would publish our customer roster -- see
  openspec/changes/domain-rules-to-db/design.md (D1).
"""

from .funnel import FREEMAIL_DOMAINS, _domain
from .models import Cohort, CohortDimension, DomainSegmentRule, UserCohort

# Dimension slugs seeded by migration.
DIM_PLAN = 'plan'
DIM_SEGMENT = 'segment'

# Segment cohort slugs seeded by migration.
SEG_UNIVERSITY = 'university'
SEG_STUDENT_COHORT = 'student-cohort'
SEG_MUNICIPALITY = 'municipality'
SEG_CONSULTANCY = 'consultancy'
SEG_NGO = 'ngo'
SEG_BUSINESS = 'business'
SEG_INDIVIDUAL = 'individual'

# Domain fragments that mark a student rather than faculty. Checked before the
# generic academic rules: `student.<university>` is a student, the bare domain is
# staff. Naming conventions, not institutions.
STUDENT_MARKERS = ('student.', 'students.', 'stud.', 'alumnos.', 'alumni.')

# Ordered suffix rules, first match wins. Each entry is (suffixes, cohort slug).
SEGMENT_SUFFIX_RULES = (
    (('.gov', '.gov.uk', '.gov.au', '.go.jp', '.gc.ca', '.gouv.fr', '.gov.pl'),
     SEG_MUNICIPALITY),
    (('.edu', '.edu.eg', '.edu.au', '.edu.pl', '.edu.co', '.ac.uk', '.ac.jp',
      '.ac.id', '.ac.nz', '.ac.il', '.ac.th'),
     SEG_UNIVERSITY),
    (('.org', '.org.uk', '.ngo'), SEG_NGO),
)

# Academic naming conventions in country TLDs that carry no .edu/.ac marker.
# Patterns, not named institutions.
ACADEMIC_DOMAIN_PREFIXES = ('uni-', 'tu-', 'uni.', 'univ-', 'hs-', 'fh-')
ACADEMIC_DOMAIN_KEYWORDS = ('universit', 'hochschule', 'polytech')


def load_domain_map():
    """`{domain: cohort_slug}` from the database rules -- one query.

    Pass the result to `classify_segment` when classifying many users, so a bulk
    run does not query per address (design D3).
    """
    return dict(
        DomainSegmentRule.objects
        .filter(cohort__dimension__slug=DIM_SEGMENT)
        .values_list('domain', 'cohort__slug')
    )


def classify_segment(email, domain_map=None):
    """Propose a segment cohort slug for an email address, or None.

    Order: database domain rule, student marker, suffix rule, academic naming
    convention. Freemail and unparseable addresses yield None on purpose -- an
    absent signal is not evidence of a segment, and leaving the user unassigned
    keeps the dashboard's "unclassified" figure honest.

    `domain_map` short-circuits the database lookup; see `load_domain_map`.
    """
    domain = _domain(email)
    if not domain or domain in FREEMAIL_DOMAINS:
        return None

    if domain_map is None:
        rule = (DomainSegmentRule.objects
                .filter(domain=domain, cohort__dimension__slug=DIM_SEGMENT)
                .values_list('cohort__slug', flat=True)
                .first())
        if rule:
            return rule
    elif domain in domain_map:
        return domain_map[domain]

    if any(marker in domain for marker in STUDENT_MARKERS):
        return SEG_STUDENT_COHORT

    for suffixes, slug in SEGMENT_SUFFIX_RULES:
        if any(domain == s.lstrip('.') or domain.endswith(s) for s in suffixes):
            return slug

    if domain.startswith(ACADEMIC_DOMAIN_PREFIXES):
        return SEG_UNIVERSITY
    if any(kw in domain for kw in ACADEMIC_DOMAIN_KEYWORDS):
        return SEG_UNIVERSITY

    return None


def get_cohort(dimension_slug, cohort_slug):
    """Look up a cohort by (dimension slug, cohort slug), or None if absent."""
    return Cohort.objects.filter(
        dimension__slug=dimension_slug, slug=cohort_slug,
    ).select_related('dimension').first()


def assign_cohort(user, cohort, source='manual', note=''):
    """Give `user` `cohort`, replacing any assignment in the same dimension.

    Returns the `UserCohort` row, or None when an automatic rule declined to
    touch a manual assignment. Automatic classification must never overwrite a
    human decision (user-cohorts design, D2).
    """
    existing = UserCohort.objects.filter(
        user=user, dimension=cohort.dimension,
    ).select_related('cohort').first()

    if existing is not None:
        if source == 'auto' and existing.source == 'manual':
            return None
        if existing.cohort_id == cohort.id and existing.source == source:
            return existing
        existing.cohort = cohort
        existing.source = source
        if note:
            existing.note = note
        existing.save()
        return existing

    return UserCohort.objects.create(
        user=user, dimension=cohort.dimension, cohort=cohort,
        source=source, note=note,
    )


def user_cohort_map(dimension_slug=None):
    """`{user_id: {dimension_slug: cohort_slug}}` for every assignment.

    One query; consumed by the funnel dashboard breakdown.
    """
    qs = UserCohort.objects.select_related('cohort', 'dimension')
    if dimension_slug:
        qs = qs.filter(dimension__slug=dimension_slug)
    out = {}
    for uid, dim, coh in qs.values_list('user_id', 'dimension__slug', 'cohort__slug'):
        out.setdefault(uid, {})[dim] = coh
    return out


def dimensions_with_cohorts():
    """All dimensions, each with its cohorts prefetched, in display order."""
    return list(
        CohortDimension.objects.prefetch_related('cohorts').order_by('order', 'name')
    )
