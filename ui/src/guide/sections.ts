export interface GuideSection {
  slug: string
  title: string
  file: string
}

export const guideSections: GuideSection[] = [
  { slug: 'getting-started', title: 'Getting started', file: '01-getting-started.md' },
  { slug: 'connections', title: 'Connections', file: '02-connections.md' },
  { slug: 'jobs', title: 'Jobs', file: '03-jobs.md' },
  { slug: 'logs-and-monitoring', title: 'Logs & monitoring', file: '04-logs-and-monitoring.md' },
  { slug: 'settings', title: 'Settings', file: '05-settings.md' },
  { slug: 'troubleshooting', title: 'Troubleshooting', file: '06-troubleshooting.md' },
]

export const defaultSlug = guideSections[0].slug
