"""The AI assistants the agent page offers (change agent-onboarding).

ONE registry: tiles, panels, the `?client=` parameter, event properties and the
help anchors all come from `CLIENTS`. A client is described here and nowhere
else -- a template that names one outside this module is a bug.

Every vendor fact carries the date it was read (`verified`). Vendors rename
their screens often (ChatGPT's "Developer mode" became "Plugins" in 2026), so
`AgentClientRegistryTest` fails once a date is older than `VERIFY_MAX_AGE_DAYS`
and the steps have to be read again.

Step strings mark the names of buttons and menus the reader looks for on the
vendor's screen as `[[Name]]`; `agent_marks` escapes the string and draws those
as keys. Every URL is built from the server address handed in -- in practice
`settings.MCP_RESOURCE_URL` -- never from a literal host, so a preview offers
its own server.
"""
import base64
import datetime
import json
from dataclasses import dataclass, field
from urllib.parse import quote

from django.utils.translation import gettext_lazy as _

VERIFY_MAX_AGE_DAYS = 120

GROUP_CHAT = 'chat'
GROUP_CODE = 'code'
GROUPS = (
    (GROUP_CHAT, _('Chat assistants')),
    (GROUP_CODE, _('Coding tools')),
)

# How the panel connects: one vendor button, one terminal command, a few
# numbered steps, or an honest "cannot yet".
METHOD_LINK = 'link'
METHOD_COMMAND = 'command'
METHOD_STEPS = 'steps'
METHOD_UNSUPPORTED = 'unsupported'

TAG_ONE_CLICK = 'one_click'
TAG_LIMITED = 'limited'
TAG_NOT_YET = 'not_yet'
TAG_LABELS = {
    TAG_ONE_CLICK: _('1 click'),
    TAG_LIMITED: _('limited'),
    TAG_NOT_YET: _('not yet'),
}

DEFAULT_CLIENT = 'claude'
# Which vendor's chat the prompt step opens first for a client. Everyone else
# gets both buttons with equal weight, and "Copy prompt".
PROMPT_TARGET = {'claude': 'claude', 'claude-code': 'claude', 'chatgpt': 'chatgpt', 'codex': 'chatgpt'}

READ_2026_10_24 = datetime.date(2026, 10, 24)


def claude_install_url(server_url):
    """claude.ai's documented add-connector link: the dialog opens filled in."""
    return ('https://claude.ai/customize/connectors?modal=add-custom-connector'
            '&connectorName=Mapsurvey&connectorUrl=' + quote(server_url, safe=''))


def cursor_install_url(server_url):
    """Cursor's install link: `config` is base64 of the mcp.json entry."""
    config = base64.b64encode(json.dumps({'url': server_url}).encode()).decode()
    return 'cursor://anysphere.cursor-deeplink/mcp/install?name=mapsurvey&config=' + quote(config, safe='')


def vscode_install_url(server_url):
    """VS Code's install link: the URL-encoded server definition."""
    definition = json.dumps({'name': 'mapsurvey', 'type': 'http', 'url': server_url})
    return 'vscode:mcp/install?' + quote(definition, safe='')


@dataclass(frozen=True)
class AgentClient:
    slug: str
    name: str
    group: str
    method: str
    verified: datetime.date
    subtitle: str = ''
    icon: str = ''            # Font Awesome 5 class; empty -> `letter`
    letter: str = ''
    color: str = '#6b7280'
    tag: str = ''
    help_anchor: str = ''     # heading id in how-to/use-the-mcp-server.md
    install: object = None    # server_url -> vendor link (METHOD_LINK)
    commands: tuple = ()      # format strings with {url} (METHOD_COMMAND)
    vendor_url: str = ''      # where the steps start (METHOD_STEPS)
    vendor_label: str = ''
    steps: tuple = ()         # lazy strings; {url} is replaced by a copy field
    config: str = ''          # a config snippet with {url}, shown once
    notes: tuple = field(default_factory=tuple)

    def panel(self, server_url):
        """What the template draws for this client, URLs resolved."""
        return {
            'install_url': self.install(server_url) if self.install else '',
            'commands': [c.format(url=server_url) for c in self.commands],
            'config': self.config.replace('{url}', server_url) if self.config else '',
        }


CLIENTS = (
    # ── Chat assistants ───────────────────────────────────────────────────
    AgentClient(
        slug='claude', name='Claude', group=GROUP_CHAT, method=METHOD_LINK,
        subtitle=_('web, desktop, phone'), letter='✳', color='#d97757', tag=TAG_ONE_CLICK,
        help_anchor='claude', install=claude_install_url, verified=READ_2026_10_24,
        steps=(
            _('In Claude press [[Add]]. The name and address are already filled in.'),
            _('Press [[Connect]] next to Mapsurvey.'),
            _('Back on Mapsurvey, check what Claude may do and press [[Allow]].'),
        ),
        notes=(
            _('One connector works in Claude on the web, on the desktop and on your phone.'),
            _("Claude's free plan allows one custom connector. On a Team or Enterprise plan, your Claude admin adds it once for everyone."),
        ),
    ),
    AgentClient(
        slug='chatgpt', name='ChatGPT', group=GROUP_CHAT, method=METHOD_STEPS,
        subtitle=_('on a computer'), icon='fas fa-circle-notch', color='#0d0d0d',
        help_anchor='chatgpt', vendor_url='https://chatgpt.com/', vendor_label=_('Open ChatGPT'),
        verified=READ_2026_10_24,
        steps=(
            _('Open ChatGPT on a computer, go to [[Plugins]], press [[Add]] and choose [[Add custom MCP server]].'),
            _('Name it Mapsurvey, paste this address and choose [[OAuth]]: {url}'),
            _('ChatGPT warns about custom servers; that is expected. Press [[Create]], then [[Connect]].'),
            _('On the Mapsurvey page that opens, press [[Allow]].'),
        ),
        notes=(
            _("Adding your own server needs a paid ChatGPT plan, and some plans only allow it for workspace admins. If you don't see the option, your plan doesn't include it yet."),
        ),
    ),
    AgentClient(
        slug='gemini', name='Gemini', group=GROUP_CHAT, method=METHOD_STEPS,
        subtitle=_('US only for now'), letter='G', color='#1a73e8', tag=TAG_LIMITED,
        help_anchor='gemini', vendor_url='https://gemini.google.com/', vendor_label=_('Open Gemini'),
        verified=READ_2026_10_24,
        steps=(
            _('On gemini.google.com open [[Settings]] → [[Connected apps]] → [[Add a custom app]].'),
            _('Paste this address and press [[Next]]: {url}'),
            _('On the Mapsurvey page that opens, press [[Allow]].'),
        ),
        notes=(
            _('Gemini connects to outside tools only in the US, with a personal Google account, in English, and inside Spark tasks. Elsewhere, use the Survey wizard or another assistant.'),
        ),
    ),
    AgentClient(
        slug='le-chat', name='Le Chat', group=GROUP_CHAT, method=METHOD_STEPS,
        subtitle=_('Mistral'), letter='M', color='#fa520f',
        help_anchor='le-chat', vendor_url='https://chat.mistral.ai/', vendor_label=_('Open Le Chat'),
        verified=READ_2026_10_24,
        steps=(
            _('In Le Chat open [[Connectors]] → [[+ Add Connector]] → [[Custom MCP Connector]].'),
            _('Name it Mapsurvey and paste this address: {url}'),
            _('Press [[Connect]], then [[Allow]] on the Mapsurvey page.'),
        ),
    ),
    AgentClient(
        slug='perplexity', name='Perplexity', group=GROUP_CHAT, method=METHOD_STEPS,
        subtitle=_('Pro and up'), letter='P', color='#20808d',
        help_anchor='perplexity', vendor_url='https://www.perplexity.ai/', vendor_label=_('Open Perplexity'),
        verified=READ_2026_10_24,
        steps=(
            _('In Perplexity open [[Customize]] → [[Connectors]] → [[+ Custom connector]] → [[Remote]].'),
            _('Name it Mapsurvey, paste this address, choose [[Streamable HTTP]] and [[OAuth]]: {url}'),
            _('On the Mapsurvey page that opens, press [[Allow]].'),
        ),
        notes=(_('Custom connectors need a Perplexity Pro, Max or Enterprise plan.'),),
    ),
    AgentClient(
        slug='copilot-studio', name='Microsoft Copilot', group=GROUP_CHAT, method=METHOD_STEPS,
        subtitle=_('Copilot Studio'), icon='fab fa-microsoft', color='#0078d4',
        help_anchor='copilot-studio', vendor_url='https://copilotstudio.microsoft.com/',
        vendor_label=_('Open Copilot Studio'), verified=READ_2026_10_24,
        steps=(
            _('In your agent open [[Tools]] → [[Add a tool]] → [[New tool]] → [[Model Context Protocol]].'),
            _('Name it Mapsurvey and paste this address: {url}'),
            _('Choose [[OAuth 2.0]] → [[Dynamic discovery]], create the connection and press [[Allow]] on the Mapsurvey page.'),
        ),
        notes=(_('This is for agents built in Copilot Studio. The Copilot app itself cannot add outside tools yet.'),),
    ),
    AgentClient(
        slug='other-chat', name=_('DeepSeek, Grok…'), group=GROUP_CHAT, method=METHOD_UNSUPPORTED,
        subtitle=_('no connectors yet'), letter='?', color='#4d6bfe', tag=TAG_NOT_YET,
        verified=READ_2026_10_24,
    ),
    AgentClient(
        slug='something-else', name=_('Something else'), group=GROUP_CHAT, method=METHOD_STEPS,
        subtitle=_('any MCP client'), icon='fas fa-ellipsis-h', color='#9ca3af',
        help_anchor='something-else', verified=READ_2026_10_24,
        steps=(
            _('Add a remote MCP server with this address: {url}'),
            _('Choose [[Streamable HTTP]] as the transport if asked.'),
            _('Sign in with [[OAuth]]; the client opens the Mapsurvey Allow page. If it only takes a header, create a personal token under API & connections and send it as Authorization: Bearer <token>.'),
        ),
    ),
    # ── Coding tools ──────────────────────────────────────────────────────
    AgentClient(
        slug='cursor', name='Cursor', group=GROUP_CODE, method=METHOD_LINK,
        letter='▲', color='#0d0d0d', tag=TAG_ONE_CLICK, help_anchor='cursor',
        install=cursor_install_url, verified=READ_2026_10_24,
        steps=(
            _('Cursor opens with Mapsurvey filled in. Press [[Install]].'),
            _('When Cursor asks you to sign in, your browser opens the Mapsurvey page: press [[Allow]].'),
        ),
    ),
    AgentClient(
        slug='vscode', name='VS Code', group=GROUP_CODE, method=METHOD_LINK,
        subtitle=_('Copilot'), icon='fas fa-code', color='#0065a9', tag=TAG_ONE_CLICK,
        help_anchor='vs-code', install=vscode_install_url, verified=READ_2026_10_24,
        steps=(
            _('VS Code opens with Mapsurvey filled in. Press [[Install]].'),
            _('When VS Code asks you to sign in, your browser opens the Mapsurvey page: press [[Allow]].'),
        ),
    ),
    AgentClient(
        slug='claude-code', name='Claude Code', group=GROUP_CODE, method=METHOD_COMMAND,
        icon='fas fa-terminal', color='#d97757', help_anchor='claude-code', verified=READ_2026_10_24,
        commands=('claude mcp add --transport http mapsurvey {url}',),
        notes=(_('The first time Claude uses Mapsurvey, your browser opens the Allow page. Connectors you added on claude.ai also appear here.'),),
    ),
    AgentClient(
        slug='codex', name='Codex', group=GROUP_CODE, method=METHOD_COMMAND,
        icon='fas fa-terminal', color='#0d0d0d', help_anchor='codex', verified=READ_2026_10_24,
        commands=('codex mcp add mapsurvey --url {url}', 'codex mcp login mapsurvey'),
        notes=(_('The second command opens the Mapsurvey Allow page in your browser.'),),
    ),
    AgentClient(
        slug='windsurf', name='Windsurf', group=GROUP_CODE, method=METHOD_STEPS,
        letter='W', color='#09b6a2', help_anchor='windsurf', verified=READ_2026_10_24,
        steps=(
            _('In the Cascade panel open [[⋯]] → [[Open MCP config]].'),
            _('Add Mapsurvey under mcpServers, save, and sign in when Windsurf asks.'),
        ),
        config='"mapsurvey": { "serverUrl": "{url}" }',
    ),
    AgentClient(
        slug='gemini-cli', name='Gemini CLI', group=GROUP_CODE, method=METHOD_COMMAND,
        subtitle=_('or Antigravity'), icon='fas fa-terminal', color='#1a73e8',
        help_anchor='gemini-cli', verified=READ_2026_10_24,
        commands=('gemini mcp add --transport http mapsurvey {url}',),
        notes=(_('Then run /mcp auth mapsurvey inside Gemini CLI. Antigravity CLI reads the same address from "serverUrl" in mcp_config.json.'),),
    ),
)

BY_SLUG = {c.slug: c for c in CLIENTS}


def get(slug):
    return BY_SLUG.get(slug)


def grouped():
    """[(group key, label, [clients])] in display order: chat first."""
    return [(key, label, [c for c in CLIENTS if c.group == key]) for key, label in GROUPS]
