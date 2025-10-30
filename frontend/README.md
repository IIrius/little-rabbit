# Frontend application

Modern React application scaffolded with Vite, TypeScript, ESLint, Prettier, React Router, and Redux Toolkit Query.

## Requirements

- Node.js 20+
- npm 10+

## Getting started

1. Install dependencies:

   ```bash
   npm install
   ```

2. Copy the example environment file and adjust values to match your API:

   ```bash
   cp .env.example .env
   ```

3. Run the development server:

   ```bash
   npm run dev
   ```

   The app will be available at [http://localhost:5173](http://localhost:5173).

## Available scripts

| Command              | Description                                          |
|----------------------|------------------------------------------------------|
| `npm run dev`        | Start the Vite development server with HMR.          |
| `npm run build`      | Type-check and build the production bundle.          |
| `npm run preview`    | Preview the production build locally.                |
| `npm run lint`       | Run ESLint with type-aware rules.                    |
| `npm run format`     | Format the codebase with Prettier.                   |
| `npm run format:check` | Check formatting without applying changes.        |
| `npm run test`       | Execute the Vitest test suite once.                  |
| `npm run test:watch` | Run tests in watch mode.                             |

## Architecture overview

- **Routing:** Managed by [React Router](https://reactrouter.com/) with a shared layout component and support for nested routes.
- **State management:** [Redux Toolkit](https://redux-toolkit.js.org/) powers the global store and [RTK Query](https://redux-toolkit.js.org/rtk-query/overview) for data fetching and caching.
- **API client:** Centralised RTK Query service (`src/services/api.ts`) attaches bearer tokens from local storage (configured via `VITE_STORAGE_TOKEN_KEY`) and handles authentication failures.
- **Styling:** Global utility styles defined in `src/index.css` with semantic class names for layout components.
- **Testing:** [Vitest](https://vitest.dev/) with [Testing Library](https://testing-library.com/docs/react-testing-library/intro/) for component tests (`src/pages/dashboard/DashboardPage.test.tsx`).

## Environment variables

| Key                      | Description                                       |
|--------------------------|---------------------------------------------------|
| `VITE_APP_NAME`          | Display name rendered in the shell header.        |
| `VITE_API_BASE_URL`      | Base URL for API requests (e.g. `http://localhost:8000/api`). |
| `VITE_STORAGE_TOKEN_KEY` | Local storage key used to persist auth tokens.    |

## Next steps

- Connect the dashboard queries to real backend endpoints.
- Add authentication flows and protected routes.
- Extend the design system and component library as new features are added.
