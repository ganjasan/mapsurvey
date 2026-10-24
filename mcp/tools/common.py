"""What every handler needs: the actor, the survey at a role, nested ids
through it -- all `api.v1.deps`, except the actor's surface."""
from survey.abuse import client_ip
from survey.services.context import SURFACE_MCP, Actor

from api.v1 import deps


def actor(request):
    return Actor(user=request.principal.user, ip=client_ip(request) or None, surface=SURFACE_MCP)


survey = deps.survey
section = deps.section
question = deps.question
top_questions = deps.top_questions
