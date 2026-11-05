# Third-party resources

Original upstream licenses and attribution are retained. Resource manifests record the pinned source revision and original source URLs.

| Resource source | Upstream repository | Revision |
| --- | --- | --- |
| anthropic | https://github.com/anthropics/skills.git | `b29e7cf65e5cb78a5ac33d582270551bc74a14eb` |
| superpowers | https://github.com/obra/superpowers.git | `44c9b2d6e889982ac18c27d05a19fefe335194e1` |
| claudekit | https://github.com/mrgoonie/claudekit-skills.git | `80113d86bc4407f105af40a2c4ea58194f7c370a` |
| neolabhq | https://github.com/NeoLabHQ/context-engineering-kit.git | `555b95263ecf13d2ad9be14df676a1263d5a62b2` |
| n8n | https://github.com/czlonkowski/n8n-skills.git | `408670d181587b5227bd98153bf56e5a0038d6d2` |
| trailofbits | https://github.com/trailofbits/skills.git | `09dfbd91537b888136c9203dca4ffdee5a595c69` |
| openai_plugins | https://github.com/openai/plugins.git | `11c74d6ba24d3a6d48f54a194cd00ef3beea18f9` |

License texts for Anthropic and ClaudeKit resources accompany the relevant packages. Repository-level notices for Superpowers, Context Engineering Kit, and Trail of Bits accompany their pinned vendor directories. Additional parent-plugin licenses for 56 OpenAI plugin skills are supplied under `third_party_licenses/openai_plugins/`, copied from the same pinned revision. Agent attribution is in `Pool/resources/agents/LICENSES/VoltAgent-MIT.txt`.

`sgar_mvp/vendor/external_python/network_clients.zip` includes HTTP client dependencies and their `.dist-info/licenses` notices.

Distribution modifications: internationalized string literals in HTTPX, IDNA,
and the Expo deployment example use equivalent Unicode escapes; the upstream
`ui-styling/scripts/.coverage` database is omitted. Checksums and package
fingerprints describe the distributed files.

The GAIA scoring compatibility implementation in `evaluation/gaia/scorer.py` retains its AOrchestra attribution. The corresponding Apache 2.0 license is provided in [third_party_licenses/AOrchestra-LICENSE](third_party_licenses/AOrchestra-LICENSE).

## Parent plugin license mapping

| Plugin | Notice |
| --- | --- |
| expo | [LICENSE](third_party_licenses/openai_plugins/plugins/expo/LICENSE) |
| mixpanel-headless | [LICENSE](third_party_licenses/openai_plugins/plugins/mixpanel-headless/LICENSE) |
| render | [LICENSE](third_party_licenses/openai_plugins/plugins/render/LICENSE) |
| shopify | [LICENSE](third_party_licenses/openai_plugins/plugins/shopify/LICENSE) |
| supabase | [LICENSE](third_party_licenses/openai_plugins/plugins/supabase/LICENSE) |
| superhuman | [LICENSE](third_party_licenses/openai_plugins/plugins/superhuman/LICENSE) |
| superpowers | [LICENSE](third_party_licenses/openai_plugins/plugins/superpowers/LICENSE) |
| temporal | [LICENSE](third_party_licenses/openai_plugins/plugins/temporal/LICENSE) |
| zoom | [LICENSE](third_party_licenses/openai_plugins/plugins/zoom/LICENSE) |
