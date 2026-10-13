// Mapsurvey help centre — help.mapsurvey.org (openspec: help-site, issue #298).
//
// Static Starlight site built from this folder by the `mapsurvey-help` Render service
// (render.yaml). Everything is decided at build time: PostHog is injected only when
// PUBLIC_POSTHOG_KEY is set, and a preview build (Render sets IS_PULL_REQUEST=true)
// marks every page noindex so a half-written guide never lands in search results.
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLinksValidator from 'starlight-links-validator';

const SITE = 'https://help.mapsurvey.org';
const MAIN_SITE = 'https://mapsurvey.org';
const REPO = 'https://github.com/ganjasan/mapsurvey';

const isPreview = process.env.IS_PULL_REQUEST === 'true';
const posthogKey = process.env.PUBLIC_POSTHOG_KEY || '';
const posthogHost = process.env.PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com';

const head = [
  { tag: 'meta', attrs: { name: 'theme-color', content: '#0FA58E' } },
  { tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.googleapis.com' } },
  { tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: true } },
  {
    tag: 'link',
    attrs: {
      rel: 'stylesheet',
      href: 'https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap',
    },
  },
];

if (isPreview) {
  head.push({ tag: 'meta', attrs: { name: 'robots', content: 'noindex' } });
}

if (posthogKey) {
  // The official array stub; `site: 'help'` is registered as a super property so the
  // events can be told apart from the product's in the shared PostHog project.
  head.push({
    tag: 'script',
    content: `!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
posthog.init(${JSON.stringify(posthogKey)},{api_host:${JSON.stringify(posthogHost)},person_profiles:'identified_only',capture_pageview:true,capture_pageleave:true,disable_session_recording:true});
posthog.register({site:'help'});`,
  });
}

export default defineConfig({
  site: SITE,
  trailingSlash: 'always',
  // Renamed or moved pages keep their old URL: add `'/old/path/': '/new/path/'` here
  // (slugs are identifiers — the product links to them, see survey/help_links.py).
  redirects: {},
  integrations: [
    starlight({
      title: 'Mapsurvey Help',
      description: 'How to build, run and read participatory mapping surveys with Mapsurvey — and how to do citizen engagement well.',
      logo: { src: './src/assets/mapsurvey-icon.png', alt: 'Mapsurvey' },
      favicon: '/favicon-32x32.png',
      defaultLocale: 'root',
      locales: {
        root: { label: 'English', lang: 'en' },
      },
      head,
      customCss: ['./src/styles/custom.css'],
      components: {
        SocialIcons: './src/components/OpenMapsurvey.astro',
        Footer: './src/components/Footer.astro',
      },
      lastUpdated: true,
      editLink: { baseUrl: `${REPO}/edit/master/help/` },
      // Sidebar groups are the Diátaxis sections; each is a directory, so a new page
      // shows up without touching this file.
      sidebar: [
        { label: 'Start here', items: [{ autogenerate: { directory: 'start-here' } }] },
        { label: 'How-to guides', items: [{ autogenerate: { directory: 'how-to' } }] },
        { label: 'Reference', items: [{ autogenerate: { directory: 'reference' } }] },
        { label: 'Troubleshooting', items: [{ autogenerate: { directory: 'troubleshooting' } }] },
        { label: 'Learn', items: [{ autogenerate: { directory: 'learn' } }] },
        { label: 'Use cases', items: [{ autogenerate: { directory: 'use-cases' } }] },
        { label: 'FAQ', link: '/faq/' },
      ],
      plugins: [
        starlightLinksValidator({
          // External links are not checked (no network at build time).
          errorOnRelativeLinks: true,
        }),
      ],
    }),
  ],
  vite: {
    define: {
      __MAIN_SITE__: JSON.stringify(MAIN_SITE),
    },
  },
});
