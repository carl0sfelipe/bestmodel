# bestmodel.run v2

Next.js App Router port of the bestmodel.run prototype. It uses the derived JSON snapshots in `public/data/derived/` and keeps the original capture console in `public/console/`.

## Run

```bash
npm install
npm run dev
```

Build the production app with `npm run build`, then serve it with `npm run start`.

## Routes

- `/` home narrative
- `/hardware` reference rigs ordered by run count
- `/wall` filterable measured/reported pool cells
- `/m/[slug]` statically generated model pages
- `/track-record` contributor trust ladder
- `/mural` SAMPLE-only social preview
- `/console` entry point to the copied static console
- `/llms.txt` agent surface

The UI is mobile-first and keeps wide data tables inside horizontal overflow containers. No Tailwind, icon package, or UI kit is used.
