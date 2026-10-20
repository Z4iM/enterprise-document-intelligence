# NEXUS EDI — Frontend (Drop-in Monorepo Edition)

This folder belongs directly inside `enterprise-document-intelligence/` next to its existing `app/` backend. The ZIP includes `frontend/` as its top-level folder. **It does not contain or modify backend files.**

## Installation (Windows PowerShell)

1. Stop the current Next.js dev server (Ctrl+C).
2. Back up or rename the existing `frontend/` folder before extracting this ZIP (for example, `frontend_old/`). Do not overwrite the current frontend in place if you have local edits.
3. Extract this ZIP into the **project root**. Verify `frontend/package.json`, `frontend/postcss.config.js`, `frontend/tailwind.config.ts`, `frontend/src/app/globals.css`, and `frontend/src/lib/api.ts` exist.
4. Open PowerShell in the root of the repository and run:

   ```powershell
   cd frontend
   npm install
   Copy-Item .env.example .env.local
   npm run dev
   ```

   If `.env.local` already exists in the new folder, keep its correct backend URL; do not put any LLM API keys here.

5. In a second terminal from the **project root**:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

6. Visit http://127.0.0.1:3000/documents. The uploaded FastAPI documents should appear **with the original Tailwind styling**.
7. Optionally run `npm run lint` and `npm run build` within `frontend/` to verify the production build.

## Included configuration and styling

- `frontend/postcss.config.js` — PostCSS Tailwind CSS / Autoprefixer plugin registration.
- `frontend/tailwind.config.ts` — content glob and product palette.
- `frontend/src/app/globals.css` — Tailwind directives and global CSS.
- `frontend/tsconfig.json` — `@/*` points to `./src/*`, using `baseUrl: "."`.
- `frontend/package.json` — includes `tailwindcss` 3.x, `postcss`, and `autoprefixer`.

The files are **not** generated at runtime: they are present in this ZIP. `node_modules/`, `.next/`, database files and API keys are intentionally omitted.

## Design and safety notes

- Next.js proxies API calls to FastAPI at `BACKEND_API_URL` from `.env.local` (`http://127.0.0.1:8000` by default).
- Policy rules and human review still require the existing backend. The user interface is an MVP, not a production-secure system.
- The project currently lacks enterprise authentication; don't expose either service publicly or upload confidential documents.
- The package was created without any edits, commits, branches, or pushes to your GitHub repository.

If styles do not appear, from within `frontend/` inspect `npm ls tailwindcss --depth=0` and verify the configuration files listed above exist. Stop/restart `npm run dev` after installing dependencies.
