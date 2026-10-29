"""Conditional visibility engine (openspec: conditional-question-visibility).

One pure pass over the survey structure decides, for a given set of answers, which
questions and sections a respondent sees. Everything else — form building, the POST
discard contract, navigation, progress, the editor lint — derives from this map, so
the respondent runtime and the editor can never disagree about what a rule means.

A rule is stored on ``Question.visibility_rule`` / ``SurveySection.visibility_rule``
in one of two shapes (``rule_mode``); ``null`` = always visible.

* ``{"question_code": <str>, "choice_codes": [<int>, ...]}`` — any-of over the
  controller's ``selected_choices``.
* ``{"question_code": <str>, "answered": true}`` (change visibility-answered-condition,
  #339) — the controller has at least one selected choice, whichever option; options
  added later count without touching the rule. ``_rule_verdict`` returns the
  ``ANY_ANSWER`` sentinel as the matchable set and ``rule_matches`` is the ONE place
  that knows what it means — nothing else may inspect ``choice_codes``/``answered``.

A question is visible only if its section is visible AND its own rule holds; a rule
whose controller is itself hidden is not satisfied (cascade).

Broken rules fail OPEN (item visible) — silently hiding content is worse than showing
it — and the same brokenness verdict feeds the editor's warning badges, so runtime
leniency never becomes editor silence.

Pop-up rules (change subquestion-visibility-rules, #338): a sub-question of a geo /
Objects-on-the-map question may carry the same rule, controlled by an EARLIER choice
sub-question of the SAME pop-up. Those rules never enter ``compute_visibility`` — a
pop-up is answered once per placed feature or object, so ``popup_visibility`` evaluates
them per feature against that feature's own sub-answers (the section POST calls it for
every feature and every object it stores).

Group rules (change question-groups, #340): a ``QuestionGroup`` carries the same rule
and is judged exactly like a question at its own ``order_number`` (groups share their
siblings' order sequence, so the controller must come before the group, hence before
every member). A member is visible only if its group is; a member's own rule applies on
top. Section groups go through ``compute_visibility``, pop-up groups through
``popup_visibility``.

Audience (change operator-entry, spec question-audience): sections, groups and
questions carry ``audience``. Both engines take a ``surface`` (``respondent`` — the
public link — or ``operator`` — the entry form) and treat an item whose audience
excludes it as hidden, as one more AND term beside the rule. Unlike rules, audience is
NOT switched off by ``CONDITIONAL_VISIBILITY``: it says what exists on a surface, not
what a respondent's answers reveal.
"""

from django.conf import settings

from .question_types import SURFACE_RESPONDENT, audience_allows

# The only input types that may control a rule. Range/rating/ranking store
# selected_choices too, but the editor deliberately offers plain choice types only.
CONTROLLER_TYPES = ("choice", "multichoice")

# ``matchable`` of an "answered" rule: not a code list, so ``rule_matches`` is the only
# consumer allowed to interpret it (a stray ``for code in matchable`` would TypeError).
ANY_ANSWER = object()


def rule_mode(rule):
	"""``'answered'`` or ``'any_of'`` for a rule dict. ``answered: true`` wins over a
	stray ``choice_codes`` (import normalises to one shape; the editor never writes both)."""
	if isinstance(rule, dict) and rule.get("answered") is True:
		return "answered"
	return "any_of"


def rule_matches(matchable, answered_codes):
	"""The ONE match test: does the controller's selection satisfy the verdict?"""
	if matchable is ANY_ANSWER:
		return bool(answered_codes)
	return any(code in answered_codes for code in matchable)


def client_rule(rule):
	"""The shape conditional_visibility.js reads, for either mode."""
	if rule_mode(rule) == "answered":
		return {"question_code": rule.get("question_code"), "answered": True}
	return {
		"question_code": rule.get("question_code"),
		"choice_codes": [c for c in (rule.get("choice_codes") or [])],
	}


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
	parent's visibility; their own rules are pop-up rules (``popup_visibility``)."""
	return section.questions()


class VisibilityMap:
	"""The verdict for one survey + one answer state."""

	def __init__(self):
		self.question_visible = {}   # question_id -> bool
		self.section_visible = {}    # section_id -> bool
		self.visible_sections = []   # [SurveySection] in chain order
		self.broken = {}             # ('question'|'section'|'group', id) -> reason str
		self.group_visible = {}      # group_id -> bool
		# question_id -> bool: section AND own rule, the group left out — lets the
		# respondent page keep a member whose only hiding cause is a group rule the
		# client toggles live.
		self.question_own = {}
		# ('question'|'group'|'section', id) hidden by audience on this surface —
		# never rendered, not even for a client-side rule to toggle.
		self.audience_hidden = set()
		self.surface = SURFACE_RESPONDENT

	def is_question_visible(self, question_id):
		return self.question_visible.get(question_id, True)

	def is_group_visible(self, group_id):
		return self.group_visible.get(group_id, True)

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
	if rule_mode(rule) == "answered":
		# No option codes to go stale: such a rule breaks only through its controller.
		return entry, ANY_ANSWER, None
	if not isinstance(wanted, list) or not wanted:
		return None, [], "no option codes referenced"
	defined = {c.get("code") for c in (controller.choices or []) if isinstance(c, dict)}
	matchable = [c for c in wanted if c in defined]
	if not matchable:
		return None, [], "every referenced answer option is gone"
	return entry, matchable, None


def compute_visibility(survey, answers_by_code, enabled=None, surface=SURFACE_RESPONDENT):
	"""Evaluate every rule of ``survey`` against ``answers_by_code``.

	``answers_by_code``: {question_code: [selected choice codes as ints]} — only
	choice-type answers matter; absent/empty means unanswered.
	``enabled``: override for tests; defaults to settings.CONDITIONAL_VISIBILITY.
	``surface``: whose page is being judged — audience applies whatever ``enabled`` is.
	"""
	if enabled is None:
		enabled = getattr(settings, "CONDITIONAL_VISIBILITY", True)

	vmap = VisibilityMap()
	vmap.surface = surface
	sections = _ordered_sections(survey)
	groups_by_section = _section_groups(survey)

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
		return rule_matches(matchable, answered)

	for s_idx, section in enumerate(sections):
		if not enabled:
			section_shown = True
		elif section.visibility_rule is None:
			section_shown = True
		else:
			section_shown = rule_satisfied(section.visibility_rule, "section", section.id, s_idx, None)
		if not audience_allows(section.audience, surface):
			section_shown = False
			vmap.audience_hidden.add(("section", section.id))
		vmap.section_visible[section.id] = section_shown
		if section_shown:
			vmap.visible_sections.append(section)

		for kind, item in walk(_iter_questions(section), groups_by_section.get(section.id, [])):
			if not enabled or item.visibility_rule is None:
				own = True
			else:
				own = rule_satisfied(item.visibility_rule, kind, item.id, s_idx, item.order_number)
			if not audience_allows(item.audience, surface):
				own = False
				vmap.audience_hidden.add((kind, item.id))
			if kind == "group":
				vmap.group_visible[item.id] = section_shown and own
				continue
			group_shown = vmap.group_visible.get(item.group_id, True) if item.group_id else True
			if item.group_id and ("group", item.group_id) in vmap.audience_hidden:
				vmap.audience_hidden.add(("question", item.id))
			vmap.question_own[item.id] = section_shown and own
			vmap.question_visible[item.id] = section_shown and group_shown and own

	return vmap


def _section_groups(survey):
	"""Top-level groups of every section of ``survey``: {section_id: [group]} (one query)."""
	from .models import QuestionGroup
	result = {}
	for group in QuestionGroup.objects.filter(
		survey_section__survey_header=survey, parent_question__isnull=True,
	).order_by("order_number", "id"):
		result.setdefault(group.survey_section_id, []).append(group)
	return result


def walk(questions, groups):
	"""Questions and groups of one bucket in order, a group before a member of the
	same number — so a group's verdict exists when its members are judged."""
	items = [(g.order_number, 0, g.id, "group", g) for g in groups]
	items += [(q.order_number, 1, q.id, "question", q) for q in questions]
	items.sort(key=lambda t: t[:3])
	return [(kind, obj) for *_k, kind, obj in items]


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


def _sibling_index(parent):
	"""``questions_index`` over one pop-up: every sub-question of ``parent`` at
	section index 0, ordered by ``order_number`` — so ``_rule_verdict``'s
	"earlier question in the section" test reads as "earlier sibling"."""
	return {
		sub.code: {"question": sub, "section_index": 0, "order": sub.order_number}
		for sub in parent.subQuestions()
	}


class PopupVisibility:
	"""The verdict for one pop-up + one feature's answers."""

	def __init__(self):
		self.question_visible = {}   # sub-question id -> bool
		self.group_visible = {}      # pop-up group id -> bool
		self.broken = {}             # ('subquestion'|'group', id) -> reason str

	def is_question_visible(self, question_id):
		return self.question_visible.get(question_id, True)

	def is_group_visible(self, group_id):
		return self.group_visible.get(group_id, True)


def popup_visibility(parent, answers_by_code, enabled=None, surface=SURFACE_RESPONDENT):
	"""Evaluate the pop-up rules of ``parent``'s sub-questions for ONE feature.

	``answers_by_code``: {sub-question code: [selected choice codes as ints]} of
	that feature (or layer object) — the choice-type properties of a posted geo
	feature, the ``obj__<key>__<code>`` fields of one object. Same any-of match,
	same cascade (a hidden controller satisfies nothing), same fail-open as the
	section engine; a controller outside the pop-up is "not found" and so broken.
	"""
	if enabled is None:
		enabled = getattr(settings, "CONDITIONAL_VISIBILITY", True)
	verdict = PopupVisibility()
	index = _sibling_index(parent)
	subs = [entry["question"] for entry in index.values()]
	for kind, item in walk(subs, _popup_groups(parent)):
		if not enabled or item.visibility_rule is None:
			own = True
		else:
			controller_entry, matchable, broken = _rule_verdict(
				item.visibility_rule, "question", 0, item.order_number, index)
			if broken:
				verdict.broken[("subquestion" if kind == "question" else "group", item.id)] = broken
				own = True
			else:
				controller = controller_entry["question"]
				if not verdict.question_visible.get(controller.id, True):
					own = False
				else:
					own = rule_matches(matchable, answers_by_code.get(controller.code) or [])
		# The parent's own audience is judged by compute_visibility (a hidden
		# parent posts no features); here only the pop-up's items.
		own = own and audience_allows(item.audience, surface)
		if kind == "group":
			verdict.group_visible[item.id] = own
		else:
			group_shown = verdict.group_visible.get(item.group_id, True) if item.group_id else True
			verdict.question_visible[item.id] = group_shown and own
	return verdict


def _popup_groups(parent):
	"""Groups of one pop-up. An unsaved parent (the editor's live preview) has none."""
	if parent.pk is None:
		return []
	return list(parent.sub_question_groups.order_by("order_number", "id"))


def popup_rules_for_client(parent, enabled=None):
	"""Valid pop-up rules of ``parent`` keyed by sub-question code — what the
	respondent page and the editor preview hand to conditional_visibility.js.
	Broken rules are left out: the client would otherwise hide what the server
	shows."""
	if enabled is None:
		enabled = getattr(settings, "CONDITIONAL_VISIBILITY", True)
	if not enabled:
		return {}
	verdict = popup_visibility(parent, {}, enabled=True)
	rules = {}
	# In pop-up order, a group before its members: the client applies them so.
	for kind, item in walk(list(parent.subQuestions()), _popup_groups(parent)):
		rule = item.visibility_rule
		broken_key = ("subquestion" if kind == "question" else "group", item.id)
		if not isinstance(rule, dict) or broken_key in verdict.broken:
			continue
		rules[item.code if kind == "question" else group_rule_key(item)] = client_rule(rule)
	return rules


def section_rules_for_client(section, enabled=None):
	"""Same-section rules of a section's questions and groups, group keys before
	their members' — the editor preview's copy of what the respondent page ships
	(it has no session, so nothing is resolved server-side there)."""
	if enabled is None:
		enabled = getattr(settings, "CONDITIONAL_VISIBILITY", True)
	if not enabled:
		return {}
	from .groups import groups_for
	questions = list(section.questions())
	codes = {q.code for q in questions}
	rules = {}
	for kind, item in walk(questions, groups_for(section)):
		rule = item.visibility_rule
		if isinstance(rule, dict) and rule.get("question_code") in codes:
			rules[item.code if kind == "question" else group_rule_key(item)] = client_rule(rule)
	return rules


def group_rule_key(group):
	"""Key of a group's rule in the client rule maps: ``group:<code>`` — question codes
	never contain a colon, so the two kinds cannot collide."""
	return f"group:{group.code}"


def popup_controller_options(parent, host=None):
	"""Siblings eligible to control a rule on a sub-question of ``parent``:
	choice-type sub-questions with a smaller ``order_number`` (all of them for
	a sub-question not yet created — it always lands last)."""
	return [
		sub for sub in parent.subQuestions()
		if sub.input_type in CONTROLLER_TYPES
		and (host is None or sub.order_number < host.order_number)
	]


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
	broken = dict(vmap.broken)
	for section in sections:
		for question in _iter_questions(section):
			questions_by_code[question.code] = question
			# Pop-up rules are judged per parent; only their brokenness is lint.
			broken.update(popup_visibility(question, {}, enabled=True).broken)

	dependents = {}
	section_codes_covered = {}  # controller_id -> set of covered choice codes
	groups_by_section = _section_groups(survey)
	for section in sections:
		hosts = [("section", section, section.visibility_rule)]
		hosts += [("question", q, q.visibility_rule) for q in _iter_questions(section)]
		hosts += [("group", g, g.visibility_rule) for g in groups_by_section.get(section.id, [])]
		for kind, host, rule in hosts:
			if not isinstance(rule, dict):
				continue
			controller = questions_by_code.get(rule.get("question_code"))
			if controller is None:
				continue
			dependents[controller.id] = dependents.get(controller.id, 0) + 1
			if kind == "section":
				covered = section_codes_covered.setdefault(controller.id, set())
				if rule_mode(rule) == "answered":
					# Shown for whichever option: every option leads somewhere.
					covered.update(
						c.get("code") for c in (controller.choices or []) if isinstance(c, dict))
				else:
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

	return {"broken": broken, "dependents": dependents, "uncovered": uncovered}


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
			if host_kind in ('question', 'group'):
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
	{'label': 'if <controller> = <options>' | 'if <controller> answered',
	 'broken': bool, 'reason': str|None, 'controller': Question|None}.
	"""
	rule = host.visibility_rule
	if not isinstance(rule, dict):
		return None
	host_order = getattr(host, 'order_number', None)
	if host_kind == 'subquestion':
		# Judged inside its pop-up: the siblings are the whole world.
		entry, matchable, broken = _rule_verdict(
			rule, 'question', 0, host_order, _sibling_index(host.parent_question_id))
		return _with_audience_warning(_describe_verdict(entry, matchable, broken), host_kind, host)
	if host_kind == 'group' and host.parent_question_id is not None:
		entry, matchable, broken = _rule_verdict(
			rule, 'question', 0, host_order, _sibling_index(host.parent_question))
		return _with_audience_warning(_describe_verdict(entry, matchable, broken), host_kind, host)
	sections = _ordered_sections(survey)
	questions_index = {}
	host_section_index = None
	for s_idx, section in enumerate(sections):
		if host_kind == 'section' and section.id == host.id:
			host_section_index = s_idx
		if host_kind == 'group' and section.id == host.survey_section_id:
			host_section_index = s_idx
		for question in _iter_questions(section):
			if host_kind == 'question' and question.id == host.id:
				host_section_index = s_idx
			questions_index[question.code] = {
				'question': question, 'section_index': s_idx, 'order': question.order_number,
			}
	if host_section_index is None:
		host_section_index = len(sections)

	verdict_kind = 'question' if host_kind == 'group' else host_kind
	entry, matchable, broken = _rule_verdict(rule, verdict_kind, host_section_index, host_order, questions_index)
	return _with_audience_warning(_describe_verdict(entry, matchable, broken), host_kind, host)


def _host_shown_to_respondents(host_kind, host):
	if host_kind == 'section':
		return audience_allows(host.audience, SURFACE_RESPONDENT)
	if host_kind == 'group':
		owner = host.parent_question if host.parent_question_id else None
		if owner is not None and not shown_on(owner, SURFACE_RESPONDENT):
			return False
		return (audience_allows(host.audience, SURFACE_RESPONDENT)
		        and audience_allows(host.survey_section.audience, SURFACE_RESPONDENT))
	return shown_on(host, SURFACE_RESPONDENT)


def _with_audience_warning(info, host_kind, host):
	"""Lint (spec question-audience): a rule whose controller only operators see
	can never show the host to a respondent — say so on the badge."""
	if info and not info['broken'] and info['controller'] is not None:
		if operator_only(info['controller']) and _host_shown_to_respondents(host_kind, host):
			info['warning'] = 'controller is shown to operators only, so respondents never see this'
	return info


def _describe_verdict(entry, matchable, broken):
	if broken:
		return {'label': None, 'broken': True, 'reason': broken, 'controller': None}
	controller = entry['question']
	title = controller.name or controller.code
	if matchable is ANY_ANSWER:
		label = f'if {title} answered'
	else:
		names = ', '.join(controller.get_choice_name(c) for c in matchable)
		label = f'if {title} = {names}'
	return {'label': label, 'broken': False, 'reason': None, 'controller': controller}


def validate_rule(rule, host_kind, *, survey=None, section=None, order=None, parent=None):
	"""Strict write-time check of a rule (change rest-api-v1). Returns the reason
	it is refused, or None.

	The runtime and the editor fail OPEN on a broken rule and badge it, so a
	creator never loses an in-progress rule; a programmatic client instead gets
	the reason at once and learns the contract from it. Same verdict as
	``_rule_verdict`` -- controller exists, is a choice type, comes earlier (an
	earlier sibling of the same pop-up for ``host_kind='subquestion'``) -- plus
	one thing the runtime tolerates: every referenced option code must exist.

	``order`` is the host's ``order_number``; None for an item not created yet,
	which always lands last.
	"""
	if rule is None:
		return None
	if not isinstance(rule, dict) or not isinstance(rule.get("question_code"), str):
		return "malformed rule"
	if host_kind == "subquestion":
		index = _sibling_index(parent)
		s_idx, kind = 0, "question"
	else:
		sections = _ordered_sections(survey)
		index = {}
		for i, s in enumerate(sections):
			for question in _iter_questions(s):
				index[question.code] = {"question": question, "section_index": i, "order": question.order_number}
		s_idx = next((i for i, s in enumerate(sections) if s.id == section.id), len(sections))
		kind = "section" if host_kind == "section" else "question"
	host_order = order if order is not None else float("inf")
	entry, _matchable, broken = _rule_verdict(rule, kind, s_idx, host_order, index)
	if broken:
		return broken
	if rule_mode(rule) == "answered":
		return None
	defined = {c.get("code") for c in (entry["question"].choices or []) if isinstance(c, dict)}
	unknown = [c for c in rule.get("choice_codes") if c not in defined]
	if unknown:
		return "unknown option code(s): " + ", ".join(str(c) for c in unknown)
	return None


def _chain_audiences(question):
	"""Audiences that narrow ``question``: its own, its group's, its section's,
	and for a sub-question the same chain of its parent."""
	out = [question.audience]
	if question.group_id:
		out.append(question.group.audience)
	if question.parent_question_id_id:
		out.extend(_chain_audiences(question.parent_question_id))
	elif question.survey_section_id:
		out.append(question.survey_section.audience)
	return out


def shown_on(question, surface):
	"""True when every audience along ``question``'s containment admits ``surface``."""
	return all(audience_allows(a, surface) for a in _chain_audiences(question))


def operator_only(question):
	"""The question exists only on the operator form — its `required` is the
	operator's own; everything respondents also see is soft there (spec operator-entry)."""
	return not shown_on(question, SURFACE_RESPONDENT)

