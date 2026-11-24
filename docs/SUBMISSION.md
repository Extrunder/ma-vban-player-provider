# Publication and catalog admission

Repository: https://github.com/Extrunder/ma-vban-player-provider

This provider is not admitted to the catalog yet. Local checks and a GitHub release alone
do not make it available in the Marketplace. Music Assistant 2.10.13 has no community installer.

1. Choose a **public** GitHub repository and its maintainer. The repository must recognise
   the included Apache-2.0 licence.
2. Configure the actual repository and GitHub handle, from the project root:

   ```sh
   python scripts/configure_repository.py Extrunder/ma-vban-player-provider --maintainer Extrunder
   ```

3. Push this project to that repository. Keep `vban/` at its root. No custom MA image
   is needed to use this as a community provider.
4. Wait for all CI jobs: lint/unit tests, real community loading/FFmpeg, and the official
   reusable catalog check. The last job checks the current `nightly` catalog channel.
5. For a preview on HA OS, use **Music Assistant DEV SERVER**, with its own data,
   and set **Provider repository** to `Extrunder/ma-vban-player-provider@main`. It uses the same ports as
   normal MA, so stop the normal App before starting the test App. No production MA
   upgrade or data migration is performed by this project.
6. Run the **Publish release** GitHub Actions workflow with version `0.2.1`.
   It reruns CI, validates real repository metadata, and publishes `v0.2.1` as a normal
   GitHub release, not a draft or prerelease. The catalog downloads the tagged source,
   not a manually uploaded Python package.
7. Open [Submit a provider](https://github.com/music-assistant/community-catalog/issues/new?template=submit-provider.yml)
   from the account that owns the repository or is listed in `codeowners`. Supply:

   - Repository: `Extrunder/ma-vban-player-provider`.
   - Folder: `vban`.
   - Tag prefix: empty.
   - Moving from the server: no (this domain is not a built-in MA provider).

8. Catalog maintainers decide admission. Once admitted and passing on a server channel,
   administrators of that channel can enable the community catalog in the Marketplace
   and install **VBAN Player**.

Updates use new normal GitHub releases. Existing installs are handled by the catalog's
compatibility checks. Restoring a server's data/backup retains its provider state; a clean
MA reinstall without data still requires installing/configuring the provider again.
There is no guarantee of compatibility with all future server releases.

Rules and templates:

- [Building a provider](https://developers.music-assistant.io/building-a-provider/)
- [Community catalog](https://github.com/music-assistant/community-catalog)
- [Exact requirements](https://github.com/music-assistant/community-catalog/blob/main/MAINTAINING.md#what-a-provider-needs)

