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
```

The build copies only `index.html`, `style.css` and `app.js` into `dist/`.
Paths are relative and work under a GitHub Pages project subpath. `dist/` and
`node_modules/` are ignored. No Pages deployment workflow, repository setting,
or hosting service is enabled by this directory. Publish only after privacy,
accessibility, visual and branch-protection review. The build output contains no
private preparation documents.
