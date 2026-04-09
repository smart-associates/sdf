import { http, HttpResponse } from 'msw'
import { DatabaseConnection } from '../../api/connections'

export const mockConnections: DatabaseConnection[] = [
  {
    id: 1,
    name: 'Production PG',
    db_type: 'postgresql',
    host: 'db.example.com',
    port: 5432,
    database: 'myapp',
    username: 'admin',
    last_test_status: 'success',
  },
  {
    id: 2,
    name: 'Staging MySQL',
    db_type: 'mysql',
    host: 'staging.example.com',
    port: 3306,
    database: 'staging',
    username: 'reader',
    last_test_status: 'failed',
    last_test_error: 'Connection refused',
  },
]

export const handlers = [
  http.get('*/api/connections', () => {
    return HttpResponse.json(mockConnections)
  }),
]
