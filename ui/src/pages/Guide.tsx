import { useEffect } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import clsx from 'clsx'
import { defaultSlug, guideSections } from '../guide/sections'
import { getSectionContent } from '../guide/loadContent'

export default function Guide() {
  const { slug } = useParams()
  const targetSlug = slug ?? defaultSlug
  const content = getSectionContent(targetSlug)

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [targetSlug])

  return (
    <div className="flex gap-8">
      <aside className="w-56 shrink-0">
        <nav className="sticky top-6 space-y-1">
          <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            User guide
          </p>
          {guideSections.map((section) => (
            <NavLink
              key={section.slug}
              to={`/guide/${section.slug}`}
              end
              className={({ isActive }) =>
                clsx(
                  'block rounded-lg px-3 py-2 text-sm transition-colors',
                  // Treat the bare /guide path as the default section so the link highlights correctly.
                  isActive || (!slug && section.slug === defaultSlug)
                    ? 'bg-blue-50 font-medium text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100',
                )
              }
            >
              {section.title}
            </NavLink>
          ))}
        </nav>
      </aside>
      <article className="prose prose-slate max-w-3xl flex-1">
        {content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        ) : (
          <>
            <h1>Section not found</h1>
            <p>
              The section <code>{targetSlug}</code> doesn't exist.{' '}
              <NavLink to="/guide" className="text-blue-600 hover:underline">
                Return to the guide overview
              </NavLink>
              .
            </p>
          </>
        )}
      </article>
    </div>
  )
}
