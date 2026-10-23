"""/me: who the token is, where it reaches, on which plan. Any valid token
with audience `api`, no scope, any plan -- the call that explains
`pro_required` before it happens."""
from ninja import Router

from ..views import me_payload
from .auth import Bearer
from .docs import errors
from .schemas import MeOut

router = Router(tags=['Account'])


@router.get('/me', response=MeOut, auth=Bearer(), url_name='me', openapi_extra=errors())
def me(request):
    """The token's user, its workspaces with their plan and whether the API is
    included, and the token's kind, scopes, audiences, binding and expiry."""
    return me_payload(request.principal)
