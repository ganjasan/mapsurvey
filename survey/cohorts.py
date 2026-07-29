"""Cohort vocabulary, email-domain classification and assignment helpers.

Cohorts are analytical labels only -- they grant no access and carry no billing
meaning. See openspec/changes/user-cohorts/design.md.

The split of responsibility is deliberate: cohort *vocabulary* lives in the
database (staff-editable, no migration), while classification *rules* live here
(logic, reviewed in PRs). The curated domain map below is the seam between them.
"""

from .funnel import FREEMAIL_DOMAINS, _domain
from .models import Cohort, CohortDimension, UserCohort

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

# Exact domains we have actually investigated (dossiers under
# docs/marketing/user-outreach/). Checked before the suffix rules, so a
# consultancy on an .edu-looking domain still lands correctly.
CURATED_DOMAIN_SEGMENTS = {
    # planning / mobility / engineering consultancies
    'decisio.nl': SEG_CONSULTANCY,
    'migcom.com': SEG_CONSULTANCY,
    'mbakerintl.com': SEG_CONSULTANCY,
    'stantec.com': SEG_CONSULTANCY,
    'agnewbeck.com': SEG_CONSULTANCY,
    'giffelswebster.com': SEG_CONSULTANCY,
    'futuriaconsulting.fi': SEG_CONSULTANCY,
    'think-jena.de': SEG_CONSULTANCY,
    'statwerk.de': SEG_CONSULTANCY,
    'mapsstudio.pl': SEG_CONSULTANCY,
    'carpe.studio': SEG_CONSULTANCY,
    'arkilab.dk': SEG_CONSULTANCY,
    'rpi-h.co.jp': SEG_CONSULTANCY,
    'towardlabs.com': SEG_CONSULTANCY,
    'line-grade.com': SEG_CONSULTANCY,
    # public sector that no suffix rule would catch
    'senmvku.berlin.de': SEG_MUNICIPALITY,
    'sodankyla.fi': SEG_MUNICIPALITY,
    'rivco.org': SEG_MUNICIPALITY,
    # non-consultancy commercial
    'lichtblick.de': SEG_BUSINESS,
    'spen.com.pl': SEG_BUSINESS,
    'agriprotech.fr': SEG_BUSINESS,
    'flagship-housing.co.uk': SEG_BUSINESS,
    'ellbit.com': SEG_BUSINESS,
    'bitoini.com': SEG_BUSINESS,
    # NGO / civic
    'awana.digital': SEG_NGO,
    'trco.or.tz': SEG_NGO,
    # research institutes (public research, not a teaching university)
    'cnr.it': SEG_UNIVERSITY,
}

# Domain fragments that mark a student rather than faculty. Checked before the
# generic academic rules: `student.polsl.pl` is a student, `polsl.pl` is staff.
STUDENT_MARKERS = ('student.', 'students.', 'stud.', 'alumnos.', 'alumni.', 'mail.uc.edu')

# Ordered suffix rules, first match wins. Each entry is (suffixes, cohort slug).
SEGMENT_SUFFIX_RULES = (
    (('.gov', '.gov.uk', '.gov.au', '.go.jp', '.gc.ca', '.gouv.fr', '.gov.pl'),
     SEG_MUNICIPALITY),
    (('.edu', '.edu.eg', '.edu.au', '.edu.pl', '.edu.co', '.ac.uk', '.ac.jp',
      '.ac.id', '.ac.nz', '.ac.il', '.ac.th', '.uni-potsdam.de', '.uc.edu'),
     SEG_UNIVERSITY),
    (('.org', '.org.uk', '.ngo'), SEG_NGO),
)

# Whole domains (not suffixes) that are academic but end in a country TLD with no
# academic marker -- the long tail of European universities.
ACADEMIC_DOMAIN_PREFIXES = ('uni-', 'tu-', 'uni.', 'univ-', 'hs-', 'fh-')
ACADEMIC_DOMAIN_KEYWORDS = ('universit', 'hochschule', 'polytech')

# Country-coded academic domains that carry no .edu/.ac marker at all. Kept as an
# explicit set so a random .ee or .it domain is not silently called a university.
ACADEMIC_EXACT_DOMAINS = frozenset({
    'tlu.ee', 'ufu.br', 'unimi.it', 'ulaval.ca', 'uekat.pl', 'tuc.gr',
    'hesge.ch', 'hr.nl', 'uni-weimar.de', 'uni-potsdam.de', 'tu-dortmund.de',
    'feps.edu.eg', 'plymouth.ac.uk', 'cardiff.ac.uk', 'york.ac.uk',
})


def classify_segment(email):
    """Propose a segment cohort slug for an email address, or None.

    Freemail and unparseable addresses yield None on purpose: an absent signal is
    not evidence of a segment, and leaving the user unassigned keeps the
    dashboard's "unclassified" figure honest (design D3).
    """
    domain = _domain(email)
    if not domain or domain in FREEMAIL_DOMAINS:
        return None

    if domain in CURATED_DOMAIN_SEGMENTS:
        return CURATED_DOMAIN_SEGMENTS[domain]

    if any(marker in domain for marker in STUDENT_MARKERS):
        return SEG_STUDENT_COHORT

    for suffixes, slug in SEGMENT_SUFFIX_RULES:
        if any(domain == s.lstrip('.') or domain.endswith(s) for s in suffixes):
            return slug

    if domain in ACADEMIC_EXACT_DOMAINS:
        return SEG_UNIVERSITY
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
    human decision (design D2).
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
