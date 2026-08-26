"""Conditional visibility engine (openspec: conditional-question-visibility).

One pure pass over the survey structure decides, for a given set of answers, which
questions and sections a respondent sees. Everything else — form building, the POST
discard contract, navigation, progress, the editor lint — derives from this map, so
the respondent runtime and the editor can never disagree about what a rule means.

A rule is ``{"question_code": <str>, "choice_codes": [<int>, ...]}`` stored on
``Question.visibility_rule`` / ``SurveySection.visibility_rule``; ``null`` = always
visible. Matching is any-of over the controller's ``selected_choices``. A question is
visible only if its section is visible AND its own rule holds; a rule whose controller
is itself hidden is not satisfied (cascade).

Broken rules fail OPEN (item visible) — silently hiding content is worse than showing
it — and the same brokenness verdict feeds the editor's warning badges, so runtime
leniency never becomes editor silence.
"""

from django.conf import settings

# The only input types that may control a rule. Range/rating/ranking store
# selected_choices too, but the editor deliberately offers plain choice types only.
CONTROLLER_TYPES = ("choice", "multichoice")


def _ordered_sections(survey):
	"""Sections along the linked list, head first.

	Falls back to insertion order for orphans (defensive: a corrupted list must
	not make sections vanish from visibility computation — fail open here too).
	"""
	sections = list(survey.surveysection_set.all())
	by_id = {s.id: s for s in sections}
	head = next((s for s in sections if s.is_head), None)
	if head is None:
		return sections
	chain, seen = [], set()
	current = head
	while current is not None and current.id not in seen:
		chain.append(current)
		seen.add(current.id)
		current = by_id.get(current.next_section_id)
	chain.extend(s for s in sections if s.id not in seen)
	return chain


def _iter_questions(section):
	"""Top-level questions of a section in order. Sub-questions inherit their
	parent's visibility and never carry rules of their own."""
	return section.questions()


class VisibilityMap:
	"""The verdict for one survey + one answer state."""

	def __init__(self):
		self.question_visible = {}   # question_id -> bool
		self.section_visible = {}    # section_id -> bool
		self.visible_sections = []   # [SurveySection] in chain order
		self.broken = {}             # ('question'|'section', id) -> reason str

	def is_question_visible(self, question_id):
		return self.question_visible.get(question_id, True)

	def is_section_visible(self, section_id):
		return self.section_visible.get(section_id, True)


def _rule_verdict(rule, host_kind, host_section_index, host_order, questions_index):
	"""Classify a rule against the structure (answers not involved).

	Returns (controller_entry|None, matchable_codes, broken_reason|None).
	``questions_index`` maps question code -> dict(question=, section_index=, order=).
	"""
	if not isinstance(rule, dict):
		return None, [], "malformed rule"
	code = rule.get("question_code")
	wanted = rule.get("choice_codes")
	entry = questions_index.get(code)
	if entry is None:
		return None, [], "controlling question not found"
	controller = entry["question"]
	if controller.input_type not in CONTROLLER_TYPES:
		return None, [], "controlling question is not a choice question"
	# Position: a section rule may only look at earlier sections; a question rule
	# at earlier sections or earlier order_number within its own section.
	if host_kind == "section":
		if entry["section_index"] >= host_section_index:
			return None, [], "controlling question is not in an earlier section"
	else:
		if entry["section_index"] > host_section_index or (
			entry["section_index"] == host_section_index and entry["order"] >= host_order
		):
			return None, [], "controlling question does not come before this question"
	if not isinstance(wanted, list) or not wanted:
		return None, [], "no option codes referenced"
	defined = {c.get("code") for c in (controller.choices or []) if isinstance(c, dict)}
	matchable = [c for c in wanted if c in defined]
	if not matchable:
		return None, [], "every referenced answer option is gone"
	return entry, matchable, None


def compute_visibility(survey, answers_by_code, enabled=None):
	"""Evaluate every rule of ``survey`` against ``answers_by_code``.

	``answers_by_code``: {question_code: [selected choice codes as ints]} — only
	choice-type answers matter; absent/empty means unanswered.
	``enabled``: override for tests; defaults to settings.CONDITIONAL_VISIBILITY.
	"""
	if enabled is None:
		enabled = getattr(settings, "CONDITIONAL_VISIBILITY", True)

	vmap = VisibilityMap()
	sections = _ordered_sections(survey)

	questions_index = {}
	for s_idx, section in enumerate(sections):
		for question in _iter_questions(section):
			questions_index[question.code] = {
				"question": question,
				"section_index": s_idx,
				"order": question.order_number,
			}

	def rule_satisfied(rule, host_kind, host_key, s_idx, order):
		"""True when the item should be shown because of this rule."""
		entry, matchable, broken = _rule_verdict(rule, host_kind, s_idx, order, questions_index)
		if broken:
			vmap.broken[(host_kind, host_key)] = broken
			return True  # fail open
		controller = entry["question"]
		# Cascade: a hidden controller can never satisfy anything. The walk is in
		# survey order and controllers are constrained to come earlier, so their
		# visibility is already decided when we get here.
		if not vmap.question_visible.get(controller.id, True):
			return False
		answered = answers_by_code.get(controller.code) or []
		return any(code in answered for code in matchable)

	for s_idx, section in enumerate(sections):
		if not enabled:
			section_shown = True
		elif section.visibility_rule is None:
			section_shown = True
		else:
			section_shown = rule_satisfied(section.visibility_rule, "section", section.id, s_idx, None)
		vmap.section_visible[section.id] = section_shown
		if section_shown:
			vmap.visible_sections.append(section)

		for question in _iter_questions(section):
			if not enabled or question.visibility_rule is None:
				own = True
			else:
				own = rule_satisfied(question.visibility_rule, "question", question.id, s_idx, question.order_number)
			vmap.question_visible[question.id] = section_shown and own

	return vmap


def answers_by_code_for_session(survey_session):
	"""Choice answers of a session keyed by question code — the engine's input.

	Non-choice answers can't control rules, so only selected_choices are read.
	"""
	from .models import Answer
	result = {}
	rows = (
		Answer.objects.filter(survey_session=survey_session, parent_answer_id__isnull=True)
		.select_related("question")
	)
	for answer in rows:
		if answer.question.input_type in CONTROLLER_TYPES and answer.selected_choices:
			result[answer.question.code] = [int(c) for c in answer.selected_choices]
	return result


def lint_rules(survey):
	"""Editor-side diagnostics; same brokenness verdicts the runtime fails open on.

	Returns {
	  'broken': {('question'|'section', id): reason},
	  'dependents': {controller_question_id: count},
	  'uncovered': {controller_question_id: [choice codes no section rule shows]},
	}
	"""
	vmap = compute_visibility(survey, {}, enabled=True)
	sections = _ordered_sections(survey)
	questions_by_code = {}
	for section in sections:
		for question in _iter_questions(section):
			questions_by_code[question.code] = question

	dependents = {}
	section_codes_covered = {}  # controller_id -> set of covered choice codes
	for section in sections:
		hosts = [("section", section, section.visibility_rule)]
		hosts += [("question", q, q.visibility_rule) for q in _iter_questions(section)]
		for kind, host, rule in hosts:
			if not isinstance(rule, dict):
				continue
			controller = questions_by_code.get(rule.get("question_code"))
			if controller is None:
				continue
			dependents[controller.id] = dependents.get(controller.id, 0) + 1
			if kind == "section":
				covered = section_codes_covered.setdefault(controller.id, set())
				covered.update(c for c in (rule.get("choice_codes") or []))

	# Uncovered options only matter for controllers that fan out into sections:
	# a controller with no section rules gets no lint (question-level rules are
	# not expected to cover the option space).
	uncovered = {}
	for controller_id, covered in section_codes_covered.items():
		controller = next(
			(q for q in questions_by_code.values() if q.id == controller_id), None
		)
		if controller is None:
			continue
		defined = [c.get("code") for c in (controller.choices or []) if isinstance(c, dict)]
		missing = [c for c in defined if c not in covered]
		if missing:
			uncovered[controller_id] = missing

	return {"broken": vmap.broken, "dependents": dependents, "uncovered": uncovered}


def controller_options(survey, host_section, host_kind, host_question=None):
	"""Questions eligible to control a rule on the given host, grouped by section.

	Returns [(section, [Question, ...]), ...] in survey order.
	``host_kind='section'``: strictly earlier sections only.
	``host_kind='question'``: earlier sections plus same-section questions with a
	smaller order_number (all of the section's choice questions when the host is
	not yet created — a new question always lands last).
	"""
	groups = []
	for section in _ordered_sections(survey):
		if section.id == host_section.id:
			if host_kind == 'question':
				if host_question is None:
					eligible = [q for q in _iter_questions(section) if q.input_type in CONTROLLER_TYPES]
				else:
					eligible = [
						q for q in _iter_questions(section)
						if q.input_type in CONTROLLER_TYPES and q.order_number < host_question.order_number
					]
				if eligible:
					groups.append((section, eligible))
			break
		eligible = [q for q in _iter_questions(section) if q.input_type in CONTROLLER_TYPES]
		if eligible:
			groups.append((section, eligible))
	return groups


def describe_rule(host_kind, host, survey):
	"""Badge info for a conditioned editor item.

	Returns None for rule-less hosts, else
	{'label': 'if <controller> = <options>', 'broken': bool, 'reason': str|None,
	 'controller': Question|None}.
	"""
	rule = host.visibility_rule
	if not isinstance(rule, dict):
		return None
	sections = _ordered_sections(survey)
	questions_index = {}
	host_section_index = None
	host_order = getattr(host, 'order_number', None)
	for s_idx, section in enumerate(sections):
		if host_kind == 'section' and section.id == host.id:
			host_section_index = s_idx
		for question in _iter_questions(section):
			if host_kind == 'question' and question.id == host.id:
				host_section_index = s_idx
			questions_index[question.code] = {
				'question': question, 'section_index': s_idx, 'order': question.order_number,
			}
	if host_section_index is None:
		host_section_index = len(sections)

	entry, matchable, broken = _rule_verdict(rule, host_kind, host_section_index, host_order, questions_index)
	if broken:
		return {'label': None, 'broken': True, 'reason': broken, 'controller': None}
	controller = entry['question']
	names = ', '.join(controller.get_choice_name(c) for c in matchable)
	return {
		'label': f'if {controller.name or controller.code} = {names}',
		'broken': False, 'reason': None, 'controller': controller,
	}
