import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
  // When the first translated locale is added, register the UI-string collection here:
  //   i18n: defineCollection({ loader: i18nLoader(), schema: i18nSchema() })
  // with files in src/content/i18n/<code>.json (see help/CONTRIBUTING.md). Declaring it
  // with no files only produces a build warning.
};
