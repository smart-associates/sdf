import { guideSections } from './sections'

const rawModules = import.meta.glob('./content/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const contentBySlug: Record<string, string> = {}
for (const section of guideSections) {
  const key = `./content/${section.file}`
  contentBySlug[section.slug] = rawModules[key] ?? `# ${section.title}\n\n_Section content not found._`
}

export function getSectionContent(slug: string): string | null {
  return contentBySlug[slug] ?? null
}
