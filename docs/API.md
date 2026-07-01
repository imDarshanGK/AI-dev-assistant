### Idempotency Contract

For critical state-mutating requests (`POST /share/`), clients can safely retry failed operations using the `Idempotency-Key` header.

* **Header Name**: `Idempotency-Key`
* **Format**: Unique client-generated request identifier string (e.g., UUID or hash).
* **Behavior**: Duplicate requests sent with a matching payload bypass database duplicate write cycles and instantly return the identical cached entry response from `IDEMPOTENCY_CACHE` to prevent partial errors.