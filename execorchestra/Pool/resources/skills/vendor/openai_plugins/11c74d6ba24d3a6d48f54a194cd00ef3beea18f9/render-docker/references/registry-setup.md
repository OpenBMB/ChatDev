# Private registry setup for Render

Render pulls private images when you attach **Registry Credentials** from the Dashboard and reference them in Blueprint YAML via **`registryCredential.fromRegistryCreds`**.

## Dashboard: Registry Credentials

1. Open the Render Dashboard → **Registry Credentials** (or your team’s equivalent settings).
2. Create a credential with a **memorable name** (you will use this name in `render.yaml`).
3. Store **only** what the registry expects (username + token, or cloud keys as required).

Blueprint reference pattern:

```yaml
services:
  - type: web
    name: api
    runtime: image
    image:
      url: docker.io/myorg/api:v1.2.3
    registryCredential:
      fromRegistryCreds:
        name: my-dockerhub-cred
```

Use the same `registryCredential` block for **`runtime: docker`** when the **base image** in your Dockerfile is private.

---

## Docker Hub

- **Username:** Docker Hub user or org name.
- **Password / token:** a **personal access token** or account password (prefer tokens).
- **Image URL examples:** `docker.io/myuser/myrepo:1.0.0`, or `myuser/myrepo@sha256:...` for immutability.

---

## GitHub Container Registry (GHCR)

- **Username:** GitHub username (or `x-access-token` patterns if your registry documents them).
- **Password:** GitHub **personal access token** with at least **`read:packages`** (and repo access if the package is private to a repo).
- **Image URL:** `ghcr.io/OWNER/IMAGE:tag` or digest form.

---

## AWS Elastic Container Registry (ECR)

- **Registry URL is regional:** `ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/repository:tag`.
- **Authentication:** IAM user or role access keys with `ecr:GetAuthorizationToken` and pull permissions on the repository, **or** long-lived credentials your org approves. Render’s Dashboard form expects the values Render documents for ECR (access key id + secret; confirm field names when creating the credential).
- **Important:** each **region** has its own registry host — the image URL must match the region where the image lives.

---

## Google Artifact Registry

- **Host:** `REGION-docker.pkg.dev/PROJECT/REPOSITORY/IMAGE:tag`.
- **Credential:** typically a **service account JSON key** with **Artifact Registry Reader** on the target repo (exact Dashboard fields follow Render’s registry UI).
- Prefer **service accounts** over user passwords for CI-style pulls.

---

## Blueprint: `runtime: image`

- Set **`runtime: image`** and **`image.url`** to the full reference (tag or digest).
- Add **`registryCredential`** when the registry is private.

Immutable deploys:

```yaml
image:
  url: ghcr.io/myorg/api@sha256:abc123...
```

---

## Auto-deploy and prebuilt images

Services that **only pull** a prebuilt image (**`runtime: image`**) **do not** auto-deploy when a mutable tag like **`latest`** is updated upstream. After publishing a new image you must:

- Trigger a **manual redeploy** in the Dashboard, or
- Call a **deploy hook** / API flow your team uses for CD.

Combine **immutable tags or digests** with your release pipeline so each deploy points at an explicit artifact.
