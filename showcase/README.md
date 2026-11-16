# Static showcase

This dependency-free static case study is separate from the FastAPI application.
It makes no AWS API calls and contains no live metrics. Evidence is dated and the
ECS stack is described as on demand. OIDC publishing and live rollback remain
unverified or deferred.

With a supported Node installation:

```text
npm install
npm run lint
npm run build
npm run test:browser
```

Browser tests use the installed Google Chrome by default; set `SHOWCASE_BROWSER`
to another local Chromium-based executable when needed. Playwright and axe-core
are development dependencies; no browser download is required. Screenshots and
the sanitized test summary are written under ignored `.tools/task36e/`, never to
the static site output. Automated accessibility checks do not prove complete
WCAG compliance.

The build copies only `index.html`, `style.css`, `app.js` and the public CI screenshot into `dist/`.
Paths are relative and work under a GitHub Pages project subpath. `dist/` and
`node_modules/` are ignored. The Pages workflow builds and uploads only those
four files. It runs only when manually dispatched for `main`; merging the
workflow does not activate Pages or publish the site.

The live project URL is `https://priyanka13-gb.github.io/RDP-Aws/`. After an
approved change is merged, an authorized operator can manually run **Publish
showcase to GitHub Pages** from `main` and verify the deployment URL. Repository
Pages availability and environment protection may require administrator action.
