# CHANGELOG


## v0.4.2 (2026-07-03)

### Bug Fixes

- Update scraper for new site layout and handle field renames
  ([`a5d3948`](https://github.com/JakeLunn/one-pace-assistant/commit/a5d394830d7836f4ff853a65ebb21c480313eba8))


## v0.4.1 (2026-04-14)

### Bug Fixes

- Fixed auto versioning again
  ([`e7a1cc2`](https://github.com/JakeLunn/one-pace-assistant/commit/e7a1cc2ebe823edbfe81f980b371d75240cd1453))


## v0.4.0 (2026-04-14)

### Documentation

- Added conventional commits to readme
  ([`8902da7`](https://github.com/JakeLunn/one-pace-assistant/commit/8902da7d015d8f6151d0a9d07d94a389ddcbcec5))

### Features

- Rsync command
  ([`7357e57`](https://github.com/JakeLunn/one-pace-assistant/commit/7357e572d678ed359c469fb03050e995b792030f))

`onepace rsync` to sync files to a target server over rsync ssh. Note: This requires rsync to be
  installed on both machines. This is meant to be a simple helper for quickly moving your media
  files to the target server, should you be downloading and serving the media on separate machines.


## v0.3.2 (2026-04-13)

### Bug Fixes

- Version number derive from metadata
  ([`2f70e85`](https://github.com/JakeLunn/one-pace-assistant/commit/2f70e853b1e6bf7e5bebf6a7a03280e50ef23a62))

version number (seen with --version arg) now is derived from the semantic versioning metadata
  instead of a hard-coded value.


## v0.3.1 (2026-04-13)

### Bug Fixes

- Seasons are now properly generated for nfos
  ([`f59418f`](https://github.com/JakeLunn/one-pace-assistant/commit/f59418f46f9ea2b00bcf1a14ddad4a81dea19aee))

NOTE: This was fixed in pr 5, using semantic commit message to trigger release update.


## v0.3.0 (2026-04-13)

### Features

- Pixel drain API key support
  ([`798fce9`](https://github.com/JakeLunn/one-pace-assistant/commit/798fce96df72dfbe5d594fd5f713c67fc93995d6))

NOTE: using semantic commit message to trigger release.


## v0.2.0 (2026-01-23)

### Documentation

- Added --variant example to readme
  ([`5e8a8c3`](https://github.com/JakeLunn/one-pace-assistant/commit/5e8a8c37fe3d45e57805a8e1ac53e84d4b851896))

### Features

- Added "--variant" option to download command
  ([`362c8e7`](https://github.com/JakeLunn/one-pace-assistant/commit/362c8e7115225e872e14e0ce9b6088ed215a15a4))

`--variant extended` can now be passed optionally to download extended variants of arcs like wano.


## v0.1.0 (2026-01-22)

### Chores

- Added ruff_cache folder to gitignore
  ([`711e5ba`](https://github.com/JakeLunn/one-pace-assistant/commit/711e5ba5b2d691d35b496ac3587d50d7c2373bab))

### Documentation

- Added license, disclaimer to readme
  ([`5597049`](https://github.com/JakeLunn/one-pace-assistant/commit/5597049b266a01403c1ac29d818e95a706a6930d))

- Updated installation instructions in readme
  ([`1a3e2c4`](https://github.com/JakeLunn/one-pace-assistant/commit/1a3e2c4e224baf49e9f69c396817ae27d1f53f3e))

- Updated Readme
  ([`ef15333`](https://github.com/JakeLunn/one-pace-assistant/commit/ef1533327efc37b127276d955085e58e0aa56b91))

### Features

- Added generate-nfo, add-posters commands
  ([`670371a`](https://github.com/JakeLunn/one-pace-assistant/commit/670371a182a9677b253b15597035ddb804b8a428))

added optional --posters-dir arg to download command.

- Added hint, made individual downloads default
  ([`2b9ebc5`](https://github.com/JakeLunn/one-pace-assistant/commit/2b9ebc509a04f3ee072c174326f15885aa6af1b7))

- Added zip downloading
  ([`7afd616`](https://github.com/JakeLunn/one-pace-assistant/commit/7afd616b2a259525691b3ff18f3ae1bc8ba46acb))

- Initial release with automated builds
  ([`f938769`](https://github.com/JakeLunn/one-pace-assistant/commit/f938769635bd2ef4473ccce69a124da2c4378aeb))
