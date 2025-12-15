import { createRootRoute, Outlet } from '@tanstack/react-router'
import { Layout } from '~/components/layout'
import { QueryProvider } from '~/lib/query-client'
import '../app.css'

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  return (
    <QueryProvider>
      <Layout>
        <Outlet />
      </Layout>
    </QueryProvider>
  )
}
