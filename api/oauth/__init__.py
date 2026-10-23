"""The authorization server (change oauth-server, #313; epic #378 item 2).

django-oauth-toolkit does the protocol work -- metadata, codes, PKCE, refresh
rotation, DCR, CIMD, resource indicators. This package holds what the
toolkit has no opinion on:

- `redirects`  the loopback exception and exact matching, used on every path
- `audiences`  RFC 8707 `resource` -> `TokenProfile.audiences`
- `tokens`     the `msa_` / `msr_` generators
- `validator`  the one `OAuth2Validator` subclass: redirects, the profile
               beside every token, double-redemption revocation, audiences
- `forms`      the consent form (dangerous scopes as switches)
- `views`      consent page with its memory; DCR behind a limiter
- `dcr`        the limiter and the metadata normalisation DCR and CIMD share
- `cimd`       the fetcher subclass that applies that normalisation
- `grants`     connected apps on the connections page, disconnect
"""
