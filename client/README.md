\# Auto-Generated TypeScript Client



> ⚠️ Do not edit these files manually. They are auto-generated from the OpenAPI spec.



\## Files

\- `types.gen.ts` — all request/response types

\- `sdk.gen.ts` — all API service methods

\- `client.gen.ts` — client configuration

\- `index.ts` — exports everything



\## Usage



```ts

import { ExplanationService } from './client';



const result = await ExplanationService.postExplanation({

&#x20; requestBody: { code: "print('hello')", language: "python" }

});



console.log(result.summary); // fully typed ✅

```



\## Regenerate Manually



```bash

\# Start the backend first

python -m uvicorn app.main:app --reload



\# Then run from project root:

openapi-ts

```

